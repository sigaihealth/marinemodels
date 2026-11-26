"""Produce a timestamp-only exclusion ledger from the frozen first Pioneer hindcast."""
import argparse
import csv
import importlib.util
from pathlib import Path


def reconstruct(previous, output):
    spec = importlib.util.spec_from_file_location("first_study", previous / "run_hindcast.py")
    first = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(first)
    data = previous / "data"
    ctd = first.read_csv(data / "ctd_hourly.csv")
    station = first.keyed(ctd, first.TARGETS)
    dep = {first.date(row["time"]): row["deployment"] for row in ctd}
    weather = first.keyed(first.read_csv(data / "weather.csv"), ("wind_u_ms", "wind_v_ms", "wave_height_m"))
    maps = first.available_maps(first.read_csv(data / "sst_daily.csv"))
    storms = first.read_csv(data / "storms.csv")
    train_end = first.SPLIT - 72 * first.HOUR
    for row in storms:
        a, b = first.date(row["window_start"]), first.date(row["window_end"])
        if a < first.SPLIT <= b:
            train_end = min(train_end, a)
    fit = set()
    for t, x in station.items():
        valid = t + 6 * first.HOUR
        if valid >= train_end or x is None or station.get(valid) is None or dep[t] != dep[valid]:
            continue
        _, stage = first.features(t, x, station, weather, maps, dep)
        if stage == "eligible":
            fit.add(t)
    test = {first.date(r["issue"]) for r in first.read_csv(previous / "results/predictions.csv")}
    assert len(fit) == 7556 and len(test) == 926
    consumed = {t+h*first.HOUR for t in fit | test for h in (-12,-6,-3,0,6)}
    rows = []
    for s in storms:
        start, end = first.date(s["window_start"]), first.date(s["window_end"])
        overlap = sum(start <= t <= end+6*first.HOUR for t in consumed)
        rows.append(dict(storm_id=s['storm_id'],window_start=s['window_start'],window_end=s['window_end'],
                         peak_time=s['peak_time'],peak_wave_m=s['peak_wave_m'],prior_ctd_timestamps=overlap))
    with output.open("w", newline="") as f:
        w=csv.DictWriter(f, fieldnames=rows[0], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args=parser.parse_args()
    reconstruct(args.previous,args.output)
