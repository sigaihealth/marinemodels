"""Reproduce the fixed six-hour Pioneer storm comparison from hourly input CSVs."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import gzip
import io
import json
from pathlib import Path
import platform
import sys

import numpy as np


HOUR = timedelta(hours=1)
START = datetime(2024, 4, 1, tzinfo=timezone.utc)
SPLIT = datetime(2025, 11, 1, tzinfo=timezone.utc)
STOP = datetime(2026, 11, 1, tzinfo=timezone.utc)
TARGETS = ("temperature_c", "salinity")
MODELS = ("persistence", "history", "weather", "weather_sst")


def date(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def data_bytes(path):
    if path.is_file():
        return path.read_bytes()
    return gzip.decompress(path.with_suffix(path.suffix + ".gz").read_bytes())


def read_csv(path):
    with io.StringIO(data_bytes(path).decode("utf-8"), newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def values(row, fields):
    if row is None:
        return None
    try:
        a = np.array([float(row[k]) for k in fields])
    except (ValueError, TypeError):
        return None
    return a if np.all(np.isfinite(a)) else None


def keyed(rows, fields):
    result = {}
    for row in rows:
        t = date(row["time"])
        if t in result:
            raise ValueError(f"Duplicate hour {t}")
        result[t] = values(row, fields)
    return result


def features(t, x, ocean, weather, maps, deployment):
    lag_times = [t - h * HOUR for h in (3, 6, 12)]
    past = [ocean.get(time) for time in lag_times]
    if any(v is None for v in past) or any(deployment.get(time) != deployment[t] for time in lag_times):
        return None, "history"
    phase = 2 * np.pi * (t - datetime(t.year, 1, 1, tzinfo=timezone.utc)).total_seconds() / (365.2425 * 86400)
    history = np.r_[x, x-past[0], x-past[1], x-past[2], np.sin(phase), np.cos(phase)]
    w, lagged = weather.get(t), weather.get(t - 6 * HOUR)
    if w is None or lagged is None:
        return None, "weather"
    u, v, height = w
    speed = np.hypot(u, v)
    windwave = np.r_[history, w, u * speed, v * speed, height**2, w-lagged]
    if t not in maps:
        return None, "sst"
    time_map, avail, sst = maps[t]
    age = (t-time_map).total_seconds()/86400
    center, mean, spread, east_west, north_south = sst
    combined = np.r_[windwave, center-x[0], mean-x[0], spread, east_west, north_south, age]
    return (history, windwave, combined, age, time_map, avail), "eligible"


def available_maps(rows):
    records = []
    for row in rows:
        fields = ("sst_center", "sst_mean", "sst_spread", "sst_east_minus_west", "sst_north_minus_south")
        sst = values(row, fields)
        if sst is None or not row["available_time"]:
            continue
        t, avail = date(row["map_time"]), date(row["available_time"])
        if avail < t:
            raise ValueError(f"Invalid map release date {avail} for {t}")
        records.append((avail, t, sst))
    records.sort(key=lambda a: (a[0], a[1]))
    result = {}
    newest = None
    idx = 0
    t = START
    while t < STOP:
        while idx < len(records) and records[idx][0] <= t:
            avail, tm, sst = records[idx]
            if newest is None or tm >= newest[0]:
                newest = (tm, avail, sst)
            idx += 1
        if newest and t - newest[0] <= 30 * 24 * HOUR:
            result[t] = newest
        t += HOUR
    return result


def ridge(train_x, delta, test_x):
    means = train_x.mean(axis=0)
    stdev = train_x.std(axis=0)
    stdev[stdev < 1e-10] = 1.0
    z = (train_x - means) / stdev
    intercept = delta.mean(axis=0)
    gram = z.T @ z
    gram += (0.01 * len(z)) * np.eye(z.shape[1])
    weights = np.linalg.solve(gram, z.T @ (delta - intercept))
    return ((test_x - means) / stdev) @ weights + intercept


def main(data, output):
    output.mkdir(parents=True, exist_ok=True)
    files = ("ctd_hourly.csv", "weather.csv", "sst_daily.csv", "storms.csv")
    ctd, wind, sst, storms = [read_csv(data / name) for name in files]
    ocean = keyed(ctd, TARGETS)
    deployment = {date(row['time']): row['deployment'] for row in ctd}
    weather = keyed(wind, ("wind_u_ms", "wind_v_ms", "wave_height_m"))
    maps = available_maps(sst)
    train_bound = SPLIT - 72 * HOUR
    storm_for = {}
    held = {}
    for row in storms:
        start, end = date(row["window_start"]), date(row["window_end"])
        if start < SPLIT <= end:
            train_bound = min(train_bound, start)
        if not (SPLIT <= start <= end < STOP):
            continue
        name = row["storm_id"]
        held[name] = dict(row)
        for k in ("origins", "no_ctd_pair", "no_history", "no_weather", "no_sst", "eligible"):
            held[name][k] = 0
        t = start
        while t <= end:
            if t in storm_for:
                raise ValueError(f"Overlapping test storms at {t}")
            storm_for[t] = name
            t += HOUR

    train_x, test_x = [[], [], []], [[], [], []]
    train_delta, train_hours, test_current, test_y, info = [], [], [], [], []
    t = START
    while t + 6 * HOUR < STOP:
        verify = t + 6 * HOUR
        training = verify < train_bound
        event = storm_for.get(t)
        if not training and not event:
            t += HOUR
            continue
        if event:
            held[event]["origins"] += 1
        x, y = ocean.get(t), ocean.get(verify)
        if x is None or y is None or deployment[t] != deployment[verify]:
            if event:
                held[event]["no_ctd_pair"] += 1
            t += HOUR
            continue
        feat, stage = features(t, x, ocean, weather, maps, deployment)
        if feat is None:
            if event:
                held[event]["no_" + stage] += 1
            t += HOUR
            continue
        dst = train_x if training else test_x
        for col, arr in zip(dst, feat[:3]):
            col.append(arr)
        if training:
            train_delta.append(y - x)
            train_hours.append(t)
        else:
            held[event]["eligible"] += 1
            info.append((event, t, verify, *feat[3:]))
            test_current.append(x)
            test_y.append(y)
        t += HOUR
    write_csv(output / "storm_coverage.csv", list(held.values()))
    if len(train_delta) < 50 or len(info) < 1:
        raise ValueError(f"Insufficient paired cases: train={len(train_delta)}, test={len(info)}")
    current, observed = np.array(test_current), np.array(test_y)
    corrections = [ridge(np.array(tx), np.array(train_delta), np.array(vx)) for tx, vx in zip(train_x, test_x)]
    preds = np.stack([current, *[current + fitted for fitted in corrections]], axis=1)
    error = preds - observed[:, None, :]
    abs_error = np.abs(error)
    event_ids = np.array([i[0] for i in info])
    tested = list(dict.fromkeys(event_ids.tolist()))
    event_mae = np.stack([abs_error[event_ids == e].mean(axis=0) for e in tested])
    ids = np.random.default_rng(6306).integers(0, len(tested), size=(5000, len(tested)))
    metrics = []
    comparisons = []
    by_event = []
    for k, target in enumerate(TARGETS):
        for m, model in enumerate(MODELS):
            e = error[:, m, k]
            metrics.append(dict(target=target, model=model, storm_mae=float(event_mae[:, m, k].mean()),
                                pooled_mae=float(np.abs(e).mean()), pooled_rmse=float(np.sqrt(np.mean(e**2))),
                                pooled_bias=float(e.mean())))
            for j, event in enumerate(tested):
                by_event.append(dict(storm_id=event, target=target, model=model, n=int(held[event]["eligible"]),
                                     mae=float(event_mae[j,m,k])))
            references = sorted({0, m-1}) if m else []
            for previous in references:
                diff = event_mae[:, previous, k] - event_mae[:, m, k]
                bounds = np.quantile(diff[ids].mean(axis=1), [.025, .975])
                comparisons.append(dict(target=target, model=model, reference=MODELS[previous],
                                        mae_reduction=float(diff.mean()), ci_low=float(bounds[0]),
                                        ci_high=float(bounds[1]), storms_improved=int((diff>0).sum()),
                                        storms_scored=len(tested)))
    pred_rows = []
    for i,(event,t,valid,age,tm,avail) in enumerate(info):
        row = dict(storm_id=event, issue=iso(t), valid=iso(valid), sst_map_time=iso(tm), sst_available=iso(avail))
        for k,target in enumerate(TARGETS):
            row[target] = observed[i,k]
            for m,model in enumerate(MODELS):
                row[f"{model}_{target}"] = preds[i,m,k]
        pred_rows.append(row)
    write_csv(output / "predictions.csv", pred_rows)
    write_csv(output / "metrics.csv", metrics)
    write_csv(output / "comparisons.csv", comparisons)
    write_csv(output / "per_storm.csv", by_event)
    ages = [i[3] for i in info]
    summary = dict(train_hours=len(train_hours), train_first=iso(train_hours[0]),train_last=iso(train_hours[-1]),
                   test_hours=len(info), test_first=iso(info[0][1]), test_last=iso(info[-1][1]),
                   held_events=len(held), scored_events=len(tested), test_map_age_days_min_median_max=np.quantile(ages,[0,.5,1]).tolist(),
                   input_sha256={n:hashlib.sha256(data_bytes(data/n)).hexdigest() for n in files},
                   numpy=np.__version__, python=sys.version.split()[0], platform=platform.system())
    (output / "summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary, indent=2))
    for row in metrics:
        print(row['target'], row['model'], round(row['storm_mae'],6))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    opts = parser.parse_args()
    main(opts.data, opts.out)
