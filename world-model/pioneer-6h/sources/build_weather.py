"""Produce causal hourly wind/wave inputs and outcome-independent storm windows from NOAA NDBC."""
import argparse
import calendar
import csv
import gzip
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "https://www.ndbc.noaa.gov/data"
START = datetime(2024, 4, 1, tzinfo=timezone.utc)
STOP = datetime(2026, 11, 1, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
WIND = "41083"
WAVE = "44095"


def stamp(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, cache):
    # Keep individual year/month paths distinct when a monthly file is named just STATION.txt.
    path = cache / url.removeprefix(BASE + "/")
    if path.exists():
        return path.read_bytes()
    try:
        with urlopen(Request(url, headers={"User-Agent": "SIG.AI Ocean research"}), timeout=50) as response:
            raw = response.read()
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def read_source(spec, cache):
    station, year, month = spec
    annual = f"{BASE}/historical/stdmet/{station}h{year}.txt.gz"
    if month is None:
        options = [annual]
    else:
        folder = f"{BASE}/stdmet/{calendar.month_abbr[month]}"
        archive_code = "123456789abc"[month - 1]
        options = [f"{folder}/{station}{archive_code}{year}.txt.gz", f"{folder}/{station}.txt", annual]
    for url in options:
        raw = fetch(url, cache)
        if raw is None:
            continue
        data = gzip.decompress(raw) if raw.startswith(b"\x1f\x8b") else raw
        lines = data.decode("ascii").splitlines()
        if not lines or not lines[0].startswith("#YY"):
            raise ValueError(f"Unexpected stdmet response from {url}")
        idx = {field: i for i, field in enumerate(lines[0].split())}
        rows = []
        for line in lines[1:]:
            if not line or line[0] == "#":
                continue
            cols = line.split()
            t = datetime(*map(int, cols[:5]), tzinfo=timezone.utc)
            if t.year != year or (month and t.month != month) or not START - HOUR <= t < STOP:
                continue
            if station == WIND:
                speed, direction = (float(cols[idx[k]]) for k in ("WSPD", "WDIR"))
                if not (0 <= speed < 99 and (speed == 0 or 0 <= direction <= 360)):
                    continue
                angle = math.radians(direction)
                rows.append((t, -speed * math.sin(angle), -speed * math.cos(angle)))
            else:
                height, period = (float(cols[idx[k]]) for k in ("WVHT", "DPD"))
                if 0 <= height < 99:
                    rows.append((t, height, period if 0 < period < 99 else None))
        if rows:
            return rows, {"station": station, "year": year, "month": month, "url": url,
                          "sha256": hashlib.sha256(raw).hexdigest(), "valid_native_records": len(rows)}
        if url.endswith(f"/{station}.txt"):
            continue
        return [], {"station": station, "year": year, "month": month, "url": url,
                    "sha256": hashlib.sha256(raw).hexdigest(), "valid_native_records": 0}
    return [], {"station": station, "year": year, "month": month, "url": None, "valid_native_records": 0}


def observation_hours(native):
    # Each t bins into (issue - 1h, issue], ensuring a record later than issue never enters a feature.
    buckets = {}
    unique = {}
    for t, first, second in native:
        if t in unique and unique[t] != (first, second):
            raise ValueError(f"Conflicting duplicate native value at {t}")
        unique[t] = (first, second)
    for t, values in sorted(unique.items()):
        boundary = t.replace(minute=0, second=0)
        if t != boundary:
            boundary += HOUR
        buckets.setdefault(boundary, []).append((t, *values))
    return buckets


def formatted(value):
    return "" if value is None else round(value, 5)


def weather_hours(wind, wave):
    result = []
    at = START
    while at < STOP:
        wi, wa = wind.get(at, []), wave.get(at, [])
        wtime, h, period = wa[-1] if wa else (None, None, None)
        row = {"time": stamp(at), "wave_height_m": formatted(h), "wave_period_s": formatted(period),
               "wind_u_ms": formatted(sum(r[1] for r in wi) / len(wi) if wi else None),
               "wind_v_ms": formatted(sum(r[2] for r in wi) / len(wi) if wi else None),
               "wave_source_time": stamp(wtime) if wtime else "", "wind_last_source_time": stamp(wi[-1][0]) if wi else "",
               "wind_native_count": len(wi), "wave_native_count": len(wa)}
        result.append(row)
        at += HOUR
    return result


def storm_events(weather):
    # Identify qualifying contiguous runs before declustering. All times are UTC hourly bins.
    waves = [r["wave_height_m"] for r in weather]
    episodes = []
    start = None
    for i, value in enumerate([*waves, ""]):
        if value != "" and value >= 3:
            if start is None:
                start = i
        elif start is not None:
            if i - start >= 2:
                peak = max(range(start, i), key=lambda j: waves[j])
                episodes.append((start, i - 1, peak))
            start = None
    clusters = []
    for start, end, peak in episodes:
        if clusters:
            previous = clusters[-1]
            # Collapse nearby episode peaks, then collapse overlapping expanded windows.
            if peak - previous["last_peak"] < 72 or start - 12 <= previous["end"] + 24:
                previous["end"] = end
                previous["last_peak"] = peak
                previous["episodes"] += 1
                if waves[peak] > waves[previous["peak"]]:
                    previous["peak"] = peak
                continue
        clusters.append({"start": start, "end": end, "peak": peak, "last_peak": peak, "episodes": 1})

    result = []
    for c in clusters:
        start, end, peak = c["start"], c["end"], c["peak"]
        times = lambda i: weather[i]["time"]
        result.append({"storm_id": "ORE-" + (START + HOUR * peak).strftime("%Y%m%dT%HZ"),
                       "window_start": times(max(start - 12, 0)),
                       "window_end": times(min(end + 24, len(weather)-1)),
                       "onset": times(start), "end": times(end), "peak_time": times(peak),
                       "peak_wave_m": waves[peak], "qualifying_runs": c["episodes"]})
    for prior, current in zip(result, result[1:]):
        if current["window_start"] <= prior["window_end"]:
            raise AssertionError("Overlapping windows")
        if datetime.fromisoformat(current["peak_time"]) - datetime.fromisoformat(prior["peak_time"]) < 72*HOUR:
            raise AssertionError("Non-independent peaks")
    return result


def write_csv(path, rows):
    with path.open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    cache = args.cache or out / "raw"
    specs = [(s, y, m) for s in (WIND, WAVE) for y in (2024, 2025, 2026)
             for m in (range(1,11) if y == 2026 else [None])]
    records = {WIND: [], WAVE: []}
    sources = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows, metadata in pool.map(lambda spec: read_source(spec, cache), specs):
            records[metadata["station"]].extend(rows)
            sources.append(metadata)
    hourly = weather_hours(observation_hours(records[WIND]), observation_hours(records[WAVE]))
    storms = storm_events(hourly)
    write_csv(out / "weather.csv", hourly)
    write_csv(out / "storms.csv", storms)
    summary = {"start": stamp(START), "stop_exclusive": stamp(STOP), "hours": len(hourly),
               "wind_station": WIND, "wave_station": WAVE,
               "wind_hours": sum(bool(r["wind_native_count"]) for r in hourly),
               "wave_hours": sum(bool(r["wave_native_count"]) for r in hourly),
               "wind_and_wave_hours": sum(bool(r["wind_native_count"] and r["wave_native_count"]) for r in hourly),
               "storms": len(storms),
               "source_records": sources}
    (out / "weather_provenance.json").write_text(json.dumps(summary, indent=2) + "\n")
    print({k:v for k,v in summary.items() if k != "source_records"})


if __name__ == "__main__":
    main()
