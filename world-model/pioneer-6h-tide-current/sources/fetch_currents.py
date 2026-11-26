"""Build forecast-time upper-water current vectors from OOI's Pioneer Central mooring."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from time import sleep


ORIGIN = "https://erddap.dataexplorer.oceanobservatories.org/erddap"
STREAM = "ooi-cp10cnsm-rid26-04-velpta000"
STATION = "CP10CNSM-RID26-04-VELPTA000"
ASSET = ("https://raw.githubusercontent.com/oceanobservatories/asset-management/"
         "4466ceaa325eb23e125eff7c9850dd000fc79aef/deployment/CP10CNSM_Deploy.csv")
U, V = "eastward_sea_water_velocity", "northward_sea_water_velocity"
VARS = ("time", U, V, U + "_qc_agg", V + "_qc_agg", "depth_reading")
HOUR = timedelta(hours=1)
GUARD = timedelta(minutes=15)
UTC = timezone.utc
START = datetime(2024, 4, 1, tzinfo=UTC)
STOP = datetime(2026, 11, 26, 2, tzinfo=UTC)
MAX_AGE = timedelta(minutes=30)
FIELDS = ["time", "u_ms", "v_ms", "source_time", "first_source_time", "sample_count", "deployment"]


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=UTC)


def load(url, cache):
    if cache.exists():
        return gzip.decompress(cache.read_bytes())
    for attempt in range(4):
        try:
            req = Request(url, headers={"User-Agent": "SIGAI-Pioneer-research/1.0"})
            with urlopen(req, timeout=90) as resp:
                buf = resp.read()
            break
        except HTTPError as err:
            if err.code == 404 and b"no matching results" in err.read().lower():
                buf = b""
                break
            if err.code < 500 or attempt == 3:
                raise
        except OSError:
            if attempt == 3:
                raise
        sleep(2 ** attempt)
    tmp = cache.with_suffix(".partial")
    tmp.write_bytes(gzip.compress(buf, mtime=0))
    tmp.replace(cache)
    return buf


def fetch_chunk(job):
    start, end, cache = job
    q = ",".join(VARS) + f"&time>={iso(start)}&time<{iso(end)}"
    url = f"{ORIGIN}/tabledap/{STREAM}.csv?" + quote(q, safe="=,:&")
    raw = load(url, cache / (start.strftime("%Y%m%dT%H%M") + "_" + end.strftime("%Y%m%dT%H%M") + ".csv.gz"))
    return raw, {"url": url, "raw_sha256": hashlib.sha256(raw).hexdigest()}


def deployment_windows(buf):
    ds = []
    for row in csv.DictReader(io.StringIO(buf.decode())):
        if row["Reference Designator"] != STATION:
            continue
        ds.append(dict(number=int(row["deploymentNumber"]), start=row["startDateTime"],
                       stop=row["stopDateTime"] or None, sensor=row["sensor.uid"],
                       lat=float(row["lat"]), lon=float(row["lon"]), nominal_depth_m=float(row["deployment_depth"])))
    if not ds or any(d["nominal_depth_m"] != 7 for d in ds):
        raise ValueError("Unexpected deployment inventory/geometry")
    return ds


def main(out, start, stop):
    out.mkdir(exist_ok=True, parents=True)
    cache = out / "raw"
    cache.mkdir(exist_ok=True)
    asset = load(ASSET, cache / "deployments.csv.gz")
    deps = deployment_windows(asset)
    windows = [(d["number"], parse(d["start"]), parse(d["stop"]) if d["stop"] else stop + HOUR) for d in deps]
    # The latest possible issue uses currents ending 15 minutes before stop.
    begin = start - HOUR - GUARD
    finish = stop + timedelta(seconds=1)
    jobs = []
    while begin < finish:
        next_month = (begin.replace(day=1, hour=0, minute=0, second=0) + timedelta(days=32)).replace(day=1)
        end = min(next_month, finish)
        jobs.append((begin, end, cache))
        begin = end
    buckets = defaultdict(dict)
    chunks = []
    counts = Counter()
    source_times = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        for buf, meta in pool.map(fetch_chunk, jobs):
            chunks.append(meta)
            if not buf:
                continue
            rows = csv.DictReader(io.StringIO(buf.decode()))
            next(rows)  # units row
            for row in rows:
                t = parse(row["time"])
                source_times.append(t)
                counts["native_rows"] += 1
                u, v = float(row[U]), float(row[V])
                if not (math.isfinite(u) and math.isfinite(v) and row[U+"_qc_agg"] == row[V+"_qc_agg"] == "1"):
                    counts["excluded_quality_or_missing"] += 1
                    continue
                dep = [n for n, lo, hi in windows if lo <= t < hi]
                if len(dep) != 1:
                    counts["excluded_deployment_boundary"] += 1
                    continue
                depth = float(row["depth_reading"])
                if math.isfinite(depth) and not 3.0 <= depth <= 12.0:
                    counts["excluded_measured_depth"] += 1
                    continue
                if not math.isfinite(depth):
                    counts["accepted_with_nominal_depth_only"] += 1
                # Left-open, right-closed sampling interval (issue-75m, issue-15m].
                guarded = t + GUARD
                issue = guarded.replace(minute=0, second=0, microsecond=0)
                if issue < guarded:
                    issue += HOUR
                b = buckets[issue]
                if t in b and b[t] != (u, v, dep[0]):
                    raise ValueError(f"Conflicting velocity at {iso(t)}")
                b[t] = (u, v, dep[0])

    hourly = []
    issue = start
    while issue <= stop:
        b = buckets.get(issue, {})
        ds = {c[2] for c in b.values()}
        if len(b) >= 2 and len(ds) == 1 and issue - max(b) <= MAX_AGE:
            assert all(issue - HOUR - GUARD < t <= issue - GUARD for t in b)
            # Never cross an overlap or recovery at issue time.
            if [n for n, lo, hi in windows if lo <= issue < hi] == list(ds):
                hourly.append(dict(time=iso(issue), u_ms=math.fsum(c[0] for c in b.values()) / len(b),
                                   v_ms=math.fsum(c[1] for c in b.values()) / len(b), source_time=iso(max(b)),
                                   first_source_time=iso(min(b)), sample_count=len(b), deployment=ds.pop()))
        issue += HOUR
    if not hourly:
        raise ValueError("No eligible hourly vectors")
    path = out / "currents.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(hourly)
    source_times.sort()
    intervals = Counter(int((b-a).total_seconds()) for a,b in zip(source_times,source_times[1:]))
    info = dict(station=STATION, dataset=f"{ORIGIN}/tabledap/{STREAM}.html", asset_url=ASSET,
                asset_sha256=hashlib.sha256(asset).hexdigest(), deployments=deps,
                native_first=iso(min(source_times)), native_last=iso(max(source_times)),
                most_common_native_intervals_s=intervals.most_common(6), counts=dict(counts),
                requested_start=iso(start), requested_last_issue=iso(stop), issue_count=len(hourly),
                first_issue=hourly[0]["time"], last_issue=hourly[-1]["time"], units="m/s, eastward and northward",
                rule="Paired finite east and north QARTOD aggregate 1. Unique deployment; measured depth 3–12 m if available; otherwise nominal 7 m. Mean of at least two distinct vectors in (t−75 min,t−15 min]; latest source age <=30 min. No interpolation. Historical source receipt time is unknown.",
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), sources=chunks)
    (out/"current_provenance.json").write_text(json.dumps(info,indent=2)+"\n")
    print(json.dumps({key:info[key] for key in ["native_first","native_last","issue_count","first_issue","last_issue","counts","most_common_native_intervals_s","sha256"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--start", type=parse, default=START)
    parser.add_argument("--last-issue", type=parse, default=STOP)
    opt = parser.parse_args()
    main(opt.output, opt.start, opt.last_issue)
