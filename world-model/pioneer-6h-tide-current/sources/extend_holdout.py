"""Extend the frozen Pioneer target/44095 event definition using same-station archives."""
import argparse
from bisect import bisect_left, bisect_right
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen

UTC = timezone.utc
HOUR = timedelta(hours=1)
START = datetime(2026, 10, 15, tzinfo=UTC)
FIRST_NEW = datetime(2026, 11, 1, tzinfo=UTC)
LAST = datetime(2026, 11, 26, 2, tzinfo=UTC)  # inclusive hour
CDIP = "https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip"
RECORDS = (f"{CDIP}/realtime/192p1_rt.nc", f"{CDIP}/archive/192p1/192p1_d09.nc")


def stamp(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def utc(t):
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "SIGAI Ocean data research"}), timeout=40) as response:
        return response.read()


def vector(ascii_text, name):
    match = re.search(r"^" + name + r"\[\d+\]\n([^\n]+)", ascii_text, re.MULTILINE)
    if match is None:
        raise ValueError(f"Missing vector {name}")
    return match[1].split(", ")


def read_cdip():
    for record in RECORDS:
        try:
            meta = fetch(record + ".das")
        except HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        if b'wmo_platform_code "44095"' not in meta or b'cdip_deployment_id "192p1_d09"' not in meta:
            continue
        axis = fetch(record + ".ascii?waveTime")
        secs = list(map(int, vector(axis.decode(), "waveTime")))
        if secs[0] > (START-HOUR).timestamp() or secs[-1] < (LAST-HOUR).timestamp():
            continue
        a = bisect_left(secs, int((START-HOUR).timestamp()))
        b = bisect_right(secs, int(LAST.timestamp())) - 1
        sel = f"[{a}:1:{b}]"
        fields = ("waveTime", "waveHs", "waveFlagPrimary")
        url = record + ".ascii?" + ",".join(k+sel for k in fields) + ",waveTimeBounds"+sel+"[0:1:1]"
        raw = fetch(url)
        text = raw.decode()
        bounds = re.findall(r"^\[(\d+)\], (\d+), (\d+)$", text, re.MULTILINE)
        arrays = [vector(text, f) for f in fields]
        if not all(len(v) == len(bounds) for v in arrays):
            raise ValueError("CDIP fields and time bounds differ in length")
        rows = []
        for ts, hs, flag, (i, start, stop) in zip(*arrays, bounds):
            if ts != start:
                raise ValueError("Unexpected CDIP observation start time")
            start = datetime.fromtimestamp(int(start), UTC)
            stop = datetime.fromtimestamp(int(stop), UTC)
            if START-HOUR < stop <= LAST:
                rows.append(dict(start=stamp(start),end=stamp(stop),wave_height_m=float(hs),primary_qc=int(flag)))
        return rows, dict(collection=record, data_query=url, metadata_sha256=sha(meta), axis_sha256=sha(axis),
                          subset_sha256=sha(raw), wmo="44095", deployment="192p1_d09")
    raise ValueError("CDIP release or deployment alternative could not serve the study interval")


def read_ndbc():
    sources = ["https://www.ndbc.noaa.gov/data/stdmet/Nov/44095b2026.txt.gz",
               "https://www.ndbc.noaa.gov/data/stdmet/Nov/44095.txt",
               "https://www.ndbc.noaa.gov/data/historical/stdmet/44095h2026.txt.gz",
               "https://www.ndbc.noaa.gov/data/realtime2/44095.txt"]
    attempts = []
    for url in sources:
        try:
            raw = fetch(url)
        except HTTPError as exc:
            if exc.code != 404:
                raise
            attempts.append({"url":url, "status":404})
            continue
        content = gzip.decompress(raw) if raw.startswith(b"\x1f\x8b") else raw
        lines = content.decode().splitlines()
        index = lines[0].split().index("WVHT")
        rows = []
        for line in lines[2:]:
            x = line.split()
            if len(x) <= index or x[index] == "MM":
                continue
            ts = datetime(*map(int,x[:5]),tzinfo=UTC)
            val = float(x[index])
            if FIRST_NEW-HOUR < ts <= LAST and 0<=val<99:
                rows.append((ts,val,None))
        attempts.append({"url":url,"status":200,"sha256":sha(raw),"accepted":len(rows)})
        # Require full date range. Otherwise the current-day rolling feed may have expired.
        if rows and min(r[0] for r in rows) <= FIRST_NEW and max(r[0] for r in rows) >= LAST-HOUR:
            return rows, attempts
    raise ValueError("No NDBC source covering the full fresh wave interval")


def write_table(path, rows, fields=None):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f,fieldnames=fields or list(rows[0]),lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", required=True, type=Path, help="Directory of the frozen world-model/pioneer-6h study")
    p.add_argument("--output", type=Path, default=Path("."))
    args=p.parse_args()
    out=args.output;out.mkdir(exist_ok=True,parents=True)
    weather=load(args.baseline/"sources/build_weather.py")
    ctd=load(args.baseline/"sources/fetch_ctd.py")
    ctd.build(out/"ctd",datetime(2026,10,31), (LAST+HOUR).replace(tzinfo=None))
    wave, info = read_cdip()
    write_table(out/"cdip_native.csv",wave)
    native = [(utc(r['end']), r['wave_height_m'], None) for r in wave if r["primary_qc"] == 1 and 0<=r["wave_height_m"]<99]
    weather.START, weather.STOP = START, LAST+HOUR
    cdip = weather.weather_hours({},weather.observation_hours(native))
    cluster = weather.storm_events(cdip)
    archived_waves = {}
    with gzip.open(args.baseline/"data/weather.csv.gz","rt") as fp:
        for r in csv.DictReader(fp):
            if r["wave_height_m"]:
                archived_waves[r["time"]]=float(r["wave_height_m"])
    common = [r for r in cdip if r["time"] in archived_waves and r["wave_height_m"] != ""]
    matching = sum(abs(archived_waves[r["time"]]-r["wave_height_m"])<0.006 for r in common)
    old_events = list(csv.DictReader((args.baseline/"data/storms.csv").open()))
    replay_events = [e for e in cluster if utc(e["window_end"]) < FIRST_NEW and utc(e["window_start"]) > START]
    for e in replay_events:
        original = next(r for r in old_events if r["storm_id"] == e["storm_id"])
        if not all(str(e[k])==str(original[k]) for k in e):
            raise ValueError("CDIP precision overlap disagrees with previous event definition")
    ndbc, ndbc_meta = read_ndbc()
    nd_live = weather.weather_hours({},weather.observation_hours(ndbc))
    nd_storms = [e for e in weather.storm_events(nd_live) if utc(e["onset"])>=FIRST_NEW]
    rows = [{"time":r["time"],"wave_height_m":r["wave_height_m"],"native":r["wave_native_count"],
             "ndbc_wave_height_m":nr["wave_height_m"]} for r,nr in zip(cdip,nd_live) if utc(r["time"])>=FIRST_NEW]
    write_table(out/"fresh_wave_hourly.csv",rows)
    new_events = [e for e in cluster if utc(e["window_start"]) >= FIRST_NEW]
    fields = list(old_events[0]) + ["status", "observed_through"]
    for e in new_events:
        # At least 72h after last high-wave hour is sufficient to close the peak/overlap merge horizon.
        closed = utc(e["end"])+72*HOUR <= LAST and utc(e["window_end"])+6*HOUR <= LAST
        # Ensure there are no gaps in the required wave history, including 72h of subsequent evidence.
        lo = utc(e["window_start"])-72*HOUR
        hi = min(utc(e["end"])+72*HOUR,LAST)
        continuous = all(r["wave_height_m"] != "" for r in cdip if lo<=utc(r["time"])<=hi)
        e["status"] = "complete" if closed and continuous else "provisional"
        e["observed_through"] = stamp(LAST)
    write_table(out/"fresh_storms.csv",new_events,fields)
    summary={"cutoff_inclusive":stamp(LAST),"new_start":stamp(FIRST_NEW),"first_new_storm_window_after":old_events[-1]["window_end"],
             "method":"Unchanged previous storm_events and hourly aggregation, using last primary-QC=1 sample ending within each trailing hour. Native heights in metres have 0.01 m precision.",
             "source":info,"ndbc_sources":ndbc_meta,"ndbc_check_events":nd_storms,
             "raw_hourly_overlap_before_new_interval":len(common),"overlap_within_0.006_m":matching,
             "closed_overlap_events_reproduced":replay_events,"new_hours":len(rows),
             "fresh_wave_hours":sum(r["wave_height_m"]!="" for r in rows),"fresh_storms":new_events,
             "latest_ctd_hour":json.loads((out/"ctd/ctd_provenance.json").read_text())["last_hour"],
             "ctd_url":ctd.TABLE,"ctd_source_sha256":sha((args.baseline/"sources/fetch_ctd.py").read_bytes()),
             "wave_code_sha256":sha((args.baseline/"sources/build_weather.py").read_bytes())}
    products = ("fresh_storms.csv", "fresh_wave_hourly.csv", "cdip_native.csv", "ctd/ctd_hourly.csv")
    summary["files_sha256"] = {name: sha((out/name).read_bytes()) for name in products}
    (out/"fresh_provenance.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:summary[k] for k in ('new_hours','fresh_wave_hours','fresh_storms','latest_ctd_hour')},indent=2))


if __name__ == "__main__":
    main()
