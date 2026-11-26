"""Refresh Pioneer storm inputs through an observed UTC cutoff, without refitting a model."""

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import os
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote
from urllib.request import Request, urlopen
from xml.etree import ElementTree

UTC = timezone.utc
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
WAVE_START = datetime(2026, 10, 15, tzinfo=UTC)
STUDY_START = datetime(2026, 11, 1, tzinfo=UTC)
SENSOR_START = STUDY_START - DAY
SEED_ONSET = datetime(2026, 11, 24, 15, tzinfo=UTC)
DEPLOYMENTS = "https://raw.githubusercontent.com/oceanobservatories/asset-management/master/deployment/CP10CNSM_Deploy.csv"
CDIP = "https://thredds.cdip.ucsd.edu/thredds"
CATALOG = CDIP + "/catalog/cdip/archive/192p1/catalog.xml"
PREPROCESSING = {
    "pioneer-6h/sources/fetch_ctd.py": "eee9f4afc341358cb17662139d1e78ac8f7fed115ac9d2ea2b3d11398367095f",
    "pioneer-6h-tide-current/sources/fetch_currents.py": "fd4a2a4797fd2bebb248de6f491a117279b09f9e6dcf68bc545b5cbfe013e33b",
    "pioneer-6h-tide-current/sources/fetch_tides.py": "7c9358f5571cbf173cc205d7a5b2342f0103e99603b8da9f51c1e73450f67703",
    "pioneer-6h/sources/build_weather.py": "814fec8b9dfa2ec6d82bfadceff3802c1e3272269fc2dab747d96b9e13ddcb43",
    "pioneer-6h-tide-current/sources/extend_holdout.py": "c5133f464054701782afd6c817c413ded43d439c9f2545b02ede47012612177a",
}
EVENT_FIELDS = (
    "event_key",
    "storm_id",
    "window_start",
    "window_end",
    "onset",
    "end",
    "peak_time",
    "peak_wave_m",
    "qualifying_runs",
    "status",
    "observed_through",
    "wave_window_closed",
    "sequence_certain",
    "blocking_wave_gap_hours",
)


def parse(s):
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("Supply a UTC offset or Z")
    return t.astimezone(UTC)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get(url, empty_ok=False):
    for attempt in range(4):
        try:
            req = Request(
                url, headers={"User-Agent": "SIGAI-Pioneer-research/1.0", "Accept-Encoding": "gzip"}
            )
            with urlopen(req, timeout=75) as response:
                data = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
                return data
        except HTTPError as e:
            if e.code == 404 and empty_ok and b"no matching results" in e.read().lower():
                return b""
            if (e.code < 500 and e.code != 429) or attempt == 3:
                raise
        except OSError:
            if attempt == 3:
                raise
        time.sleep(2**attempt)


class RawCache:
    """Only cache sealed OOI ranges and CDIP archive reads, and revisit them weekly."""

    def __init__(self, directory):
        self.path = directory
        directory.mkdir(parents=True, exist_ok=True)

    def read(self, url, sealed=False, empty_ok=False, identity=""):
        if not sealed:
            return get(url, empty_ok)
        path = self.path / (sha((url + identity).encode()) + ".gz")
        if path.is_file() and time.time() - path.stat().st_mtime < 7 * 86400:
            return gzip.decompress(path.read_bytes())
        data = get(url, empty_ok)
        if data:
            with tempfile.NamedTemporaryFile(dir=self.path, delete=False) as temp:
                temp.write(gzip.compress(data, mtime=0))
            os.replace(temp.name, path)
        return data

    def ooi(self, url, empty_ok):
        upper = re.search(r"&time<([^&]+)", unquote(url))
        sealed = upper and parse(upper.group(1)) < datetime.now(UTC) - 21 * DAY
        return self.read(url, sealed, empty_ok)


def write_csv(path, rows, names):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_waves(cutoff, cache, helper):
    # UCSD's archive rolls over by physical deployment. Never assume rt.nc remains d09.
    catalog = get(CATALOG)
    root = ElementTree.fromstring(catalog)
    archives = []
    for node in root.iter():
        name = node.attrib.get("urlPath", "")
        m = re.fullmatch(r"cdip/archive/192p1/192p1_d(\d+)\.nc", name)
        if m and int(m[1]) >= 9:  # d09 was active when this prospective study began.
            archives.append(f"{CDIP}/dodsC/{name}")
    realtime = CDIP + "/dodsC/cdip/realtime/192p1_rt.nc"
    records = [*sorted(set(archives)), realtime]
    native = {}
    sources = []
    for url in records:
        archive = url != realtime
        try:
            meta = cache.read(url + ".das", sealed=archive)
        except HTTPError as e:
            if e.code == 404 and not archive and native:
                sources.append({"url": url, "http_status": 404})
                continue
            raise
        s = meta.decode()
        wmo = re.search(r'String wmo_platform_code "(\d+)"', s)
        dep = re.search(r'String cdip_deployment_id "(192p1_d\d+)"', s)
        if not dep or not wmo or wmo[1] != "44095":
            raise ValueError(f"Unexpected CDIP station/deployment metadata at {url}")
        bounds = [
            re.search(r"String time_coverage_" + edge + r' "([^"]+)"', s) for edge in ("start", "end")
        ]
        if None in bounds:
            raise ValueError("CDIP archive lacks time coverage")
        if parse(bounds[1][1]) < WAVE_START - HOUR or parse(bounds[0][1]) > cutoff:
            continue
        axis = cache.read(url + ".ascii?waveTime", sealed=archive)
        seconds = [int(x) for x in helper.vector(axis.decode(), "waveTime")]
        # For open files, a delayed/missing delivery may end before cutoff.
        if not seconds or any(a >= b for a, b in zip(seconds, seconds[1:])):
            raise ValueError(f"Missing or nonmonotone time axis in {url}")
        first = helper.bisect_left(seconds, (WAVE_START - HOUR).timestamp())
        final = helper.bisect_right(seconds, cutoff.timestamp()) - 1
        chunk_hashes = []
        for start in range(first, final + 1, 2048):
            sel = f"[{start}:1:{min(start + 2047, final)}]"
            fields = ("waveTime", "waveHs", "waveFlagPrimary")
            query = (
                url
                + ".ascii?"
                + ",".join(x + sel for x in fields)
                + ",waveTimeBounds"
                + sel
                + "[0:1:1]"
            )
            segment = seconds[start : min(start + 2048, final + 1)]
            # Index positions in rt.nc can change on a deployment rollover or backfill.
            # Reuse a sealed segment only if its deployment and complete native time axis match.
            signature = dep[1] + sha(",".join(map(str, segment)).encode())
            sealed = archive or datetime.fromtimestamp(segment[-1], UTC) < datetime.now(UTC) - 21 * DAY
            raw = cache.read(query, sealed=sealed, identity=signature)
            text = raw.decode()
            spans = re.findall(r"^\[\d+\], (\d+), (\d+)$", text, re.MULTILINE)
            arrays = [helper.vector(text, k) for k in fields]
            if not spans or any(len(a) != len(spans) for a in arrays):
                raise ValueError(f"Unaligned CDIP inputs: {query}")
            for ts, hs, qc, (lo, hi) in zip(*arrays, spans):
                start_obs, end_obs = int(lo), int(hi)
                if int(ts) != start_obs or not 0 < end_obs - start_obs <= 3600:
                    raise ValueError("Unexpected CDIP measurement averaging bounds")
                end_t = datetime.fromtimestamp(end_obs, UTC)
                if WAVE_START - HOUR < end_t <= cutoff:
                    row = (float(hs), int(qc), dep[1])
                    # Prefer archival revisions over concurrent RT duplicates.
                    # A different deployment with conflicting reports is ambiguous.
                    prior = native.get(end_t)
                    if prior and prior[2] != dep[1] and prior[:2] != row[:2]:
                        native[end_t] = (float("nan"), 9, "ambiguous_overlap")
                    elif prior is None or archive:
                        native[end_t] = row
            chunk_hashes.append({"url": query, "sha256": sha(raw)})
        sources.append(
            {
                "url": url,
                "deployment": dep[1],
                "metadata_sha256": sha(meta),
                "time_axis_sha256": sha(axis),
                "chunks": chunk_hashes,
            }
        )
    if not native:
        raise ValueError("No wave observations in prospective monitoring interval")
    valid = [(t, h, None) for t, (h, q, _) in native.items() if q == 1 and 0 <= h < 99]
    if not valid:
        raise ValueError("No passing significant wave heights in the monitoring interval")
    return (
        valid,
        max(native),
        {
            "catalog": CATALOG,
            "catalog_sha256": sha(catalog),
            "sources": sources,
            "last_actual_native_time": iso(max(native)),
            "last_qc_pass_native_time": iso(max(t for t, h, _ in valid)),
        },
    )


def potential_wave_gaps(rows):
    """A weakly sampled bin between two fully sampled calm bins cannot form a two-hour run."""

    def certain(row):
        return row["wave_height_m"] != "" and int(row["wave_native_count"]) >= 2

    def calm(row):
        return certain(row) and row["wave_height_m"] < 3

    return [
        parse(row["time"])
        for i, row in enumerate(rows)
        if not certain(row) and not (0 < i < len(rows) - 1 and calm(rows[i - 1]) and calm(rows[i + 1]))
    ]


def inventory(weather, valid, last_native, as_of):
    # Ceil to publication bin as in original study; never include bins after the query cutoff.
    last_bin = last_native.replace(minute=0, second=0, microsecond=0)
    if last_native != last_bin:
        last_bin += HOUR
    until = min(last_bin, as_of)
    weather.START, weather.STOP = WAVE_START, until + HOUR
    wave = weather.weather_hours({}, weather.observation_hours(valid))
    gaps = potential_wave_gaps(wave)
    result = []
    for storm in weather.storm_events(wave):
        onset = parse(storm["onset"])
        if onset < STUDY_START:
            continue
        start, end = parse(storm["window_start"]), parse(storm["end"])
        guard_end = end + 72 * HOUR
        window_closed = until >= guard_end and until >= parse(storm["window_end"]) + 6 * HOUR
        critical = [g for g in gaps if start - 72 * HOUR <= g <= guard_end]
        # The first November storm is already known. Earlier gaps before its guard window
        # cannot hide an intervening *subsequent* event. Later gaps affect cohort ordering.
        prior = [g for g in gaps if SEED_ONSET - 84 * HOUR <= g < onset]
        row = dict(
            storm,
            event_key="ORE-ONSET-" + onset.strftime("%Y%m%dT%HZ"),
            status="complete" if window_closed and not critical else "provisional",
            observed_through=iso(until),
            wave_window_closed=int(window_closed and not critical),
            sequence_certain=int(not prior),
            blocking_wave_gap_hours=len(set(critical + prior)),
        )
        result.append(row)
    return wave, result, gaps


def refresh(out, cache_dir, world_model, cutoff):
    modules = []
    for relative, expected in PREPROCESSING.items():
        source = world_model / relative
        if sha(source.read_bytes()) != expected:
            raise ValueError(f"Registered preprocessing source changed: {relative}")
        modules.append(load_module(source))
    ctd, flow, tide, weather, cdip = modules
    out.mkdir(parents=True, exist_ok=True)
    cache = RawCache(cache_dir)
    # Reuse the original QC selector and vector binning against an up-to-date asset inventory.
    assets = get(DEPLOYMENTS)
    ctd.DEPLOYMENTS = flow.ASSET = DEPLOYMENTS
    ctd.cached_csv = lambda path, url, allow_empty=False: (
        assets if url == DEPLOYMENTS else cache.ooi(url, allow_empty)
    )
    flow.load = lambda url, path: assets if url == DEPLOYMENTS else cache.ooi(url, True)
    with tempfile.TemporaryDirectory(dir=out, prefix=".refresh-") as tmp:
        stage = Path(tmp)
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = [
                pool.submit(
                    ctd.build,
                    stage / "ctd",
                    SENSOR_START.replace(tzinfo=None),
                    (cutoff + HOUR).replace(tzinfo=None),
                ),
                pool.submit(flow.main, stage / "flow", SENSOR_START, cutoff),
                pool.submit(
                    tide.build, SENSOR_START.date(), (cutoff + 6 * HOUR).date(), stage / "tide"
                ),
            ]
            wave_job = pool.submit(read_waves, cutoff, cache, cdip)
            for job in jobs:
                job.result()
            valid, last_native, wave_info = wave_job.result()
        hourly, events, gaps = inventory(weather, valid, last_native, cutoff)
        wave_rows = [
            {k: r[k] for k in ("time", "wave_height_m", "wave_source_time", "wave_native_count")}
            for r in hourly
        ]
        write_csv(stage / "wave_hourly.csv", wave_rows, list(wave_rows[0]))
        write_csv(stage / "events.csv", events, EVENT_FIELDS)
        for d, name in (("ctd", "ctd_hourly"), ("flow", "currents"), ("tide", "tides")):
            (stage / d / (name + ".csv")).replace(stage / (name + ".csv"))
        metas = {
            k: json.loads((stage / d / n).read_text())
            for k, d, n in [
                ("ctd", "ctd", "ctd_provenance.json"),
                ("currents", "flow", "current_provenance.json"),
                ("tides", "tide", "tide_provenance.json"),
            ]
        }
        # Receipt timing for station observations is not historically recoverable. Publish
        # their real valid data horizons explicitly rather than substituting wall-clock time.
        info = {
            "as_of": iso(cutoff),
            "retrieved_at": iso(datetime.now(UTC)),
            "ctd_through": metas["ctd"]["last_hour"],
            "currents_through": metas["currents"]["last_issue"],
            "tides_through": metas["tides"]["last"],
            "waves_through": hourly[-1]["time"],
            "wave_bounds_source": wave_info,
            "critical_missing_wave_hours": [iso(t) for t in gaps],
            "pending_single_high_hour": (
                hourly[-1]["time"]
                if len(hourly) >= 2
                and hourly[-1]["wave_height_m"] != ""
                and hourly[-1]["wave_height_m"] >= 3
                and (hourly[-2]["wave_height_m"] == "" or hourly[-2]["wave_height_m"] < 3)
                else None
            ),
            "sources": metas,
            "deployment_asset_url": DEPLOYMENTS,
            "deployment_asset_sha256": sha(assets),
            "data_sha256": {p.name: sha(p.read_bytes()) for p in sorted(stage.glob("*.csv"))},
        }
        (stage / "refresh_provenance.json").write_text(json.dumps(info, indent=2) + "\n")
        for name in [*info["data_sha256"], "refresh_provenance.json"]:
            (stage / name).replace(out / name)
    print(
        f"Published {len(events)} identified storms through {info['waves_through']}; "
        f"QC CTD through {info['ctd_through']}, current through {info['currents_through']}."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--world-model", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument(
        "--as-of", type=parse, help="Last permissible UTC hour; defaults to current completed hour"
    )
    args = parser.parse_args()
    clock = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    cutoff = (args.as_of or clock).replace(minute=0, second=0, microsecond=0)
    if cutoff > clock or cutoff < STUDY_START:
        parser.error("Cutoff lies outside the monitored past")
    refresh(args.out, args.cache or args.out / ".cache", args.world_model, cutoff)
