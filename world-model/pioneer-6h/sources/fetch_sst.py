"""Build daily Pioneer shelf SST maps and features using NOAA ERDDAP and NASA CMR."""
import argparse
import calendar
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import re
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ERDDAP = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.csv"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
COLLECTION = "C1996881146-POCLOUD"
LATS = (35.65, 35.80, 35.95, 36.10, 36.25)
LONS = (-75.42, -75.27, -75.12, -74.97, -74.82)
CELL_FIELDS = ("map_time", "lat", "lon", "sst_degC")
FEATURES = ("sst_center", "sst_mean", "sst_spread", "sst_east_minus_west", "sst_north_minus_south")
DAY = dt.timedelta(days=1)


def download(url, filename):
    if filename.exists():
        return filename.read_bytes()
    for attempt in range(4):
        try:
            req = Request(url, headers={"User-Agent": "SIG.AI-Ocean-Pioneer-SST/1.0"})
            with urlopen(req, timeout=180) as response:
                data = response.read()
            tmp = filename.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(filename)
            return data
        except (HTTPError, URLError, TimeoutError) as error:
            if attempt == 3 or isinstance(error, HTTPError) and error.code not in (408, 429, 500, 502, 503, 504):
                raise
            time.sleep(2 ** attempt)


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def utc(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def shelf_subset(start, end, cache):
    name = f"{start}_{end}"
    bounds = f"[({start}T09:00:00Z):1:({end}T09:00:00Z)][(35.65):15:(36.25)][(-75.42):15:(-74.82)]"
    url = f"{ERDDAP}?" + quote("analysed_sst" + bounds, safe="")
    body = download(url, cache / (name + ".csv"))
    reader = csv.reader(io.StringIO(body.decode()))
    if next(reader) != ["time", "latitude", "longitude", "analysed_sst"] or next(reader)[-1] != "degree_C":
        raise ValueError(f"Unexpected SST variables or units at {url}")
    maps = {}
    for stamp, lat, lon, value in reader:
        grid = maps.setdefault(stamp, {})
        cell = (float(lat), float(lon))
        if cell in grid or cell[0] not in LATS or cell[1] not in LONS:
            raise ValueError(f"Unexpected/duplicate cell {cell} at {stamp}")
        grid[cell] = float(value)
    return maps, {"url": url, "sha256": hashlib.sha256(body).hexdigest()}


def metadata(start, end, cache):
    # Nominal MUR time is 09Z. Each granule's coverage spans the evening before
    # through the evening of that nominal day, so these bounds select this month.
    params = {"collection_concept_id": COLLECTION, "page_size": 100,
              "temporal": f"{start}T09:00:00Z,{end}T09:00:01Z"}
    url = CMR + "?" + urlencode(params)
    data = download(url, cache / f"{start}_{end}.json")
    payload = json.loads(data)
    if payload["hits"] != len(payload["items"]):
        raise ValueError("NASA CMR response was paginated unexpectedly")
    records = {}
    for item in payload["items"]:
        umm, meta = item["umm"], item["meta"]
        granule_id = umm["GranuleUR"]
        m = re.match(r"^(\d{8})090000-JPL-L4_GHRSST-SSTfnd-MUR-GLOB-v02\.0-fv04\.1(?:\.nc)?$", granule_id)
        if not m:
            raise ValueError(f"Unexpected NASA product: {granule_id}")
        nominal = dt.datetime.strptime(m.group(1), "%Y%m%d").replace(hour=9, tzinfo=dt.timezone.utc)
        if not start <= nominal.date() <= end:
            continue
        time_range = umm["TemporalExtent"]["RangeDateTime"]
        coverage_end = timestamp(time_range["EndingDateTime"])
        production = timestamp(umm["DataGranule"]["ProductionDateTime"])
        provider = max(timestamp(d["Date"]) for d in umm["ProviderDates"] if d["Type"] in ("Insert", "Update"))
        revision = timestamp(meta["revision-date"])
        available = max(coverage_end, production, provider, revision)
        archive = umm["DataGranule"]["ArchiveAndDistributionInformation"]
        source_file = next(a for a in archive if a["Name"].endswith(".nc"))
        checksum = source_file["Checksum"]
        if checksum["Algorithm"].upper() != "MD5":
            raise ValueError("Unexpected NASA archive checksum algorithm")
        key = nominal.strftime("%Y-%m-%dT%H:%M:%SZ")
        if key in records:
            raise ValueError(f"Duplicate granule at {key}")
        records[key] = {"available_time": utc(available), "coverage_end": utc(coverage_end),
                        "produced_time": utc(production), "provider_time": utc(provider),
                        "catalog_time": utc(revision), "concept_id": meta["concept-id"],
                        "cmr_revision": meta["revision-id"], "source_file_md5": checksum["Value"]}
    return records, {"url": url, "sha256": hashlib.sha256(data).hexdigest()}


def fetch_month(task):
    start, end, cache = task
    maps, source = shelf_subset(start, end, cache)
    records, cmr = metadata(start, end, cache)
    dates = {(start + dt.timedelta(days=i)).isoformat() + "T09:00:00Z" for i in range((end-start).days+1)}
    if set(maps) != dates or set(records) != dates:
        raise ValueError(f"Missing daily granules or maps {start}–{end}, map gaps {sorted(dates-set(maps))}, CMR gaps {sorted(dates-set(records))}")
    for stamp, grid in maps.items():
        if len(grid) != len(LATS)*len(LONS):
            raise ValueError(f"Incomplete grid for {stamp}")
    return maps, records, {"start": str(start), "end": str(end), "sst": source, "cmr": cmr}


def gradient(a, b):
    return statistics.fmean(a) - statistics.fmean(b) if len(a) >= 3 and len(b) >= 3 else math.nan


def summarize(grid):
    valid = {k: v for k, v in grid.items() if math.isfinite(v)}
    if len(valid) < 20:
        return [math.nan]*len(FEATURES)
    west, east = ([v for (_, x), v in valid.items() if x == e] for e in (LONS[0], LONS[-1]))
    south, north = ([v for (y, _), v in valid.items() if y == e] for e in (LATS[0], LATS[-1]))
    return [valid.get((LATS[2], LONS[2]), math.nan), statistics.fmean(valid.values()),
            statistics.pstdev(valid.values()), gradient(east, west), gradient(north, south)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2024, 3, 1))
    parser.add_argument("--end", type=dt.date.fromisoformat, default=dt.date(2026, 10, 31))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("start exceeds end")
    output = args.output
    cache = output / "sst-cache"
    cache.mkdir(parents=True, exist_ok=True)
    chunks = []
    current = args.start
    while current <= args.end:
        last = min(current.replace(day=calendar.monthrange(current.year, current.month)[1]), args.end)
        chunks.append((current, last, cache))
        current = last + DAY
    sources, maps, records = [], {}, {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for part, recs, provenance in pool.map(fetch_month, chunks):
            maps.update(part)
            records.update(recs)
            sources.append(provenance)
    fieldnames = ["map_time", "available_time", *FEATURES, "valid_cells", "coverage_end", "produced_time",
                  "provider_time", "catalog_time", "concept_id", "cmr_revision", "source_file_md5"]
    lags = []
    coverage = Counter()
    with (output / "sst_daily.csv").open("w", newline="") as ts, gzip.GzipFile(
            filename=str(output / "sst_map_cells.csv.gz"), mode="wb", mtime=0) as comp:
        cells = io.TextIOWrapper(comp, encoding="utf-8", newline="")
        grids = csv.writer(cells, lineterminator="\n")
        grids.writerow(CELL_FIELDS)
        writer = csv.DictWriter(ts, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for stamp, grid in sorted(maps.items()):
            for (y, x), v in sorted(grid.items()):
                grids.writerow([stamp, f"{y:.2f}", f"{x:.2f}", f"{v:.3f}" if math.isfinite(v) else ""])
            n = sum(math.isfinite(v) for v in grid.values())
            coverage[str(n)] += 1
            features = {k: f"{v:.6f}" if math.isfinite(v) else "" for k, v in zip(FEATURES, summarize(grid))}
            writer.writerow({"map_time": stamp, "valid_cells": n, **features, **records[stamp]})
            lags.append((timestamp(records[stamp]["available_time"]) - timestamp(stamp)).total_seconds()/86400)
        cells.flush()
        cells.detach()
    digest = lambda f: hashlib.sha256((output / f).read_bytes()).hexdigest()
    summary = {"product": "NASA JPL MUR v4.1 daily foundation SST, satellite and in-situ blended analysis",
               "sampled_lats": LATS, "sampled_lons": LONS, "unit": "degC", "series": len(maps),
               "cell_count_distribution": dict(coverage),
               "available_lag_days_min_median_max": [min(lags), statistics.median(lags), max(lags)],
               "available_rule": "maximum of source time coverage end, NASA production, provider insert/update, and recorded CMR revision timestamps",
               "historical_subset_version": "contiguous current NOAA ERDDAP subset, paired by product and nominal day with current NASA CMR records",
               "sst_daily_sha256": digest("sst_daily.csv"), "sst_map_cells_gz_sha256": digest("sst_map_cells.csv.gz"),
               "sources": sources}
    (output / "sst_provenance.json").write_text(json.dumps(summary, indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k not in ("sources",)}, indent=2))


if __name__ == "__main__":
    main()
