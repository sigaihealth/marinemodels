"""Build a paired, past-only hourly OOI Pioneer near-surface CTD series using the Python standard library."""
import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


STATION = "CP10CNSM-RID27-03-CTDBPC000"
STREAM = "ooi-cp10cnsm-rid27-03-ctdbpc000"
ERDDAP = "https://erddap.dataexplorer.oceanobservatories.org/erddap"
TABLE = f"{ERDDAP}/tabledap/{STREAM}.csv"
ASSET_COMMIT = "4466ceaa325eb23e125eff7c9850dd000fc79aef"
DEPLOYMENTS = f"https://raw.githubusercontent.com/oceanobservatories/asset-management/{ASSET_COMMIT}/deployment/CP10CNSM_Deploy.csv"
TEMP = "sea_water_temperature"
SALT = "sea_water_practical_salinity"
VARS = ("time", TEMP, SALT, TEMP + "_qc_agg", SALT + "_qc_agg", "depth_reading")
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MINUTE = dt.timedelta(minutes=1)
HOUR = dt.timedelta(hours=1)


def fetch(url, allow_empty=False):
    for attempt in range(4):
        try:
            req = Request(url, headers={"User-Agent": "SIGAI-Pioneer-research/1.0", "Accept-Encoding": "gzip"})
            with urlopen(req, timeout=75) as response:
                data = response.read()
                return gzip.decompress(data) if response.headers.get("Content-Encoding") == "gzip" else data
        except HTTPError as exc:
            if allow_empty and exc.code == 404 and b"no matching results" in exc.read().lower():
                return b""
            if exc.code < 500 or attempt == 3:
                raise
        except (URLError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)


def each_month(start, stop):
    cursor = start
    while cursor < stop:
        following = (cursor.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        end = min(following, stop)
        yield cursor, end
        cursor = end


def utc(value):
    return value.strftime(DATE_FORMAT)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def cached_csv(path, url, allow_empty=False):
    if not path.is_file():
        data = fetch(url, allow_empty)
        tmp = path.with_suffix(".partial")
        tmp.write_bytes(gzip.compress(data, mtime=0))
        tmp.replace(path)
    return gzip.decompress(path.read_bytes())


def get_chunk(interval, cache):
    start, stop = interval
    query = ",".join(VARS) + f"&time>={utc(start)}&time<{utc(stop)}"
    url = TABLE + "?" + quote(query, safe=",:=&")
    filename = f"ctd-{start.date().isoformat()}--{stop.date().isoformat()}.csv.gz"
    data = cached_csv(cache / filename, url, allow_empty=True)
    return data, {"file": filename, "url": url, "sha256_csv": digest(data)}


def asset_intervals(raw):
    records = []
    for row in csv.DictReader(io.StringIO(raw.decode())):
        if row["Reference Designator"] != STATION:
            continue
        records.append({"number": int(row["deploymentNumber"]), "sensor_uid": row["sensor.uid"],
                        "start": row["startDateTime"], "stop": row["stopDateTime"] or None,
                        "depth_m": float(row["deployment_depth"]), "lat": float(row["lat"]),
                        "lon": float(row["lon"])})
    if not records or any(r["depth_m"] != 7 for r in records):
        raise ValueError("Expected near-surface deployments at nominal 7 m.")
    return sorted(records, key=lambda r: r["number"])


def build(out, start, stop):
    out.mkdir(exist_ok=True, parents=True)
    cache = out / "cache"
    cache.mkdir(exist_ok=True)
    raw_assets = cached_csv(cache / f"deployment-{ASSET_COMMIT}.csv.gz", DEPLOYMENTS)
    deployments = asset_intervals(raw_assets)
    periods = [(r, dt.datetime.fromisoformat(r["start"]), dt.datetime.fromisoformat(r["stop"])
                if r["stop"] else dt.datetime.max) for r in deployments]
    latest = {}
    duplicates = set()
    counts = collections.Counter()
    qall = collections.Counter()
    manifest = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for data, info in pool.map(lambda pair: get_chunk(pair, cache), each_month(start, stop)):
            manifest.append(info)
            if not data:
                continue
            reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
            if tuple(reader.fieldnames) != VARS:
                raise ValueError(f"Unexpected ERDDAP variables: {reader.fieldnames}")
            next(reader)  # ERDDAP's units line
            for r in reader:
                counts["raw_rows"] += 1
                tq, sq = r[TEMP + "_qc_agg"], r[SALT + "_qc_agg"]
                qall[(tq, sq)] += 1
                if (tq, sq) != ("1", "1"):
                    continue
                if not all(math.isfinite(float(r[k])) for k in (TEMP, SALT)):
                    continue
                counts["pass_pair_rows"] += 1
                t = dt.datetime.fromisoformat(r["time"].removesuffix("Z"))
                hour = t.replace(minute=0, second=0, microsecond=0)
                if t != hour:
                    hour += HOUR
                if hour >= stop or hour - t > 15 * MINUTE:
                    continue
                active = [d for d, opened, closed in periods if opened <= t < closed]
                at_hour = [d for d, opened, closed in periods if opened <= hour < closed]
                if len(active) != 1 or active != at_hour:
                    counts["unassigned_or_overlapping_rows"] += 1
                    continue
                val = (r["time"], r[TEMP], r[SALT], r["depth_reading"], active[0]["number"])
                current = latest.get(hour)
                if current is None or val[0] > current[0]:
                    latest[hour] = val
                    duplicates.discard(hour)
                elif val[0] == current[0] and val != current:
                    duplicates.add(hour)
    for key in duplicates:
        latest.pop(key)
    if not latest:
        raise ValueError("No usable CTD data.")
    path = out / "ctd_hourly.csv"
    with path.open("w", newline="") as dest:
        writer = csv.writer(dest, lineterminator="\n")
        writer.writerow(["time", "temperature_c", "salinity", "source_time", "deployment", "measured_depth_m"])
        for hour, (timestamp, temp, salinity, depth, dep) in sorted(latest.items()):
            writer.writerow([utc(hour), temp, salinity, timestamp, dep, depth])
    report = {"reference_designator": STATION, "instrument_page": "https://oceanobservatories.org/site/cp10cnsm/",
              "source_metadata": f"{ERDDAP}/info/{STREAM}/index.html",
              "asset_url": DEPLOYMENTS, "asset_csv_sha256": digest(raw_assets), "deployments": deployments,
              "start_utc": utc(start), "exclusive_end_utc": utc(stop), "counts": dict(counts),
              "pair_qc_frequencies_temp_salinity": {f"{a},{b}": n for (a,b),n in sorted(qall.items())},
              "hours": len(latest), "hours_with_conflicting_best_rows_excluded": len(duplicates),
              "exactly_on_the_hour": sum(utc(t) == v[0] for t, v in latest.items()),
              "hours_per_deployment": dict(sorted(collections.Counter(v[4] for v in latest.values()).items())),
              "first_hour": utc(min(latest)), "last_hour": utc(max(latest)), "hourly_csv_sha256": digest(path.read_bytes()),
              "rule": "Latest paired finite temperature and practical salinity at or before each whole UTC hour, both aggregate QC=1 (PASS), maximum age 15 minutes. Both record and hour belong to exactly one identical asset deployment; ambiguous overlaps excluded. Reported timestamps are used; original data receipt times are unavailable. No interpolation. Do not cross deployment boundaries in forecast pairs.",
              "chunks": manifest}
    (out / "ctd_provenance.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"{report['hours']} hourly states, {report['first_hour']} through {report['last_hour']}.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("."))
    parser.add_argument("--start", type=dt.datetime.fromisoformat, default=dt.datetime(2024, 4, 3))
    parser.add_argument("--end", type=dt.datetime.fromisoformat, default=dt.datetime(2026, 11, 25),
                        help="exclusive UTC date at midnight")
    opts = parser.parse_args()
    if opts.start >= opts.end or any(x.time() != dt.time() or x.tzinfo for x in (opts.start, opts.end)):
        parser.error("Supply increasing UTC calendar dates")
    build(opts.output, opts.start, opts.end)
