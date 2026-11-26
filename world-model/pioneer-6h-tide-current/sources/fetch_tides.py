"""Fetch hourly astronomical tide heights at Duck from the NOAA CO-OPS Data API."""

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


STATION = "8651370"
API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
META = f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{STATION}"
UTC = dt.timezone.utc
HOUR = dt.timedelta(hours=1)
DAY = dt.timedelta(days=1)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fetch(url):
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "SIGAI-Pioneer-research/1.0"})
            with urlopen(request, timeout=45) as response:
                return response.read()
        except HTTPError as error:
            if error.code != 429 and error.code < 500 or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        sleep(2**attempt)


def fetch_year(pair):
    start, end = pair
    query = {"product": "predictions", "application": "sigai_pioneer_research",
             "begin_date": start.strftime("%Y%m%d"), "end_date": end.strftime("%Y%m%d"),
             "datum": "MLLW", "station": STATION, "time_zone": "gmt", "units": "metric",
             "interval": "h", "format": "json"}
    url = API + "?" + urlencode(query)
    raw = fetch(url)
    records = json.loads(raw)["predictions"]
    expected = dt.datetime.combine(start, dt.time(), tzinfo=UTC)
    rows = []
    for record in records:
        instant = dt.datetime.strptime(record["t"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
        if instant != expected or not math.isfinite(float(record["v"])):
            raise ValueError(f"Invalid hourly prediction at {expected}: {record}")
        rows.append((instant.strftime("%Y-%m-%dT%H:00:00Z"), record["v"]))
        expected += HOUR
    if expected != dt.datetime.combine(end + DAY, dt.time(), tzinfo=UTC):
        raise ValueError(f"Incomplete response for {start} through {end}")
    return rows, {"url": url, "raw_sha256": sha(raw), "n_hours": len(rows)}


def build(start, end, dest):
    if start > end:
        raise ValueError("start must be on or before end")
    chunks = []
    day = start
    while day <= end:
        last = min(end, dt.date(day.year, 12, 31), day + 364 * DAY)
        chunks.append((day, last))
        day = last + DAY
    with ThreadPoolExecutor(max_workers=3) as pool:
        downloads = list(pool.map(fetch_year, chunks))
    all_rows = [row for chunk, _ in downloads for row in chunk]
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["time", "tide_m"])
    writer.writerows(all_rows)
    series = out.getvalue().encode()

    station_url = META + ".json?units=metric"
    datum_url = META + "/datums.json?units=metric"
    harmonic_url = META + "/harcon.json?units=metric"
    source_metadata = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for url, raw in zip((station_url, datum_url, harmonic_url), pool.map(fetch, (station_url, datum_url, harmonic_url))):
            source_metadata[url] = (json.loads(raw), sha(raw))
    station = source_metadata[station_url][0]["stations"][0]
    datum = source_metadata[datum_url][0]
    count = len(source_metadata[harmonic_url][0]["HarmonicConstituents"])
    evidence = {
        "station": {"id": station["id"], "name": station["name"], "state": station["state"],
                    "latitude": station["lat"], "longitude": station["lng"]},
        "datum": "Mean Lower Low Water (MLLW)", "datum_epoch": datum["epoch"],
        "datum_acceptance": datum["accepted"], "n_published_constituents": count,
        "product": "hourly astronomical tide predictions (metres, UTC)",
        "validation": "Exactly one finite model prediction per hour; no gaps or observation fills.",
        "first": all_rows[0][0], "last": all_rows[-1][0], "n_hours": len(all_rows),
        "minimum_m": min(float(x[1]) for x in all_rows), "maximum_m": max(float(x[1]) for x in all_rows),
        "sources": [entry for _, entry in downloads],
        "metadata_sha256_by_url": {url: pair[1] for url, pair in source_metadata.items()},
        "tides_csv_sha256": sha(series),
    }
    dest.mkdir(exist_ok=True, parents=True)
    (dest/"tides.csv").write_bytes(series)
    (dest/"tide_provenance.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"{len(all_rows):,} hourly predictions, {all_rows[0][0]} through {all_rows[-1][0]}, sha256 {sha(series)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2024, 3, 31))
    parser.add_argument("--end", type=dt.date.fromisoformat, default=dt.date(2026, 11, 26))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    build(args.start, args.end, args.output)
