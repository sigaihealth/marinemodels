# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26,<3", "numcodecs>=0.12,<0.18"]
# ///
"""Regenerate the archived forecast excerpt for the SIG.AI Ocean explorer.

    uv run extract_glonet_subset.py --output site/assets/glonet-midatlantic-2024.json
    uv run extract_glonet_subset.py --output forecast.json --audit-manifest audit.json

Source: https://oceanbench.edito.eu/challengers/
Reader definitions: https://github.com/mercator-ocean/oceanbench/blob/main/oceanbench/core/challenger_datasets.py

The two source grids share these coordinates and nominal depths. Only the needed
compressed Zarr chunks are downloaded. A typical run transfers about 47 MB.
"""

import argparse
import hashlib
import json
import math
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from uuid import uuid4
from urllib.request import Request, urlopen

import numpy as np
from numcodecs import get_codec


ROOT = "https://s3.waw3-1.cloudferro.com/oceanbench-bucket/public"
STORES = {"forecast": "ml-forecast-outputs/glonet", "persistence": "baseline-forecasts/persistence"}
REFERENCE_DATES = (date(2024, 1, 2), date(2024, 7, 2))
SITES = [
    {"id": "west", "latitude": 36.0, "longitude": -74.75},
    {"id": "central", "latitude": 36.0, "longitude": -74.25},
    {"id": "east", "latitude": 36.0, "longitude": -73.50},
]
DEPTHS = [0.494025, 47.373692, 92.326073]
VARIABLES = {
    "thetao": {"name": "Potential temperature", "units": "°C", "archiveUnits": "degrees_C"},
    "so": {"name": "Practical salinity", "units": "dimensionless", "archiveUnits": "1e-3"},
}
LEADS = 10
MAX_DOWNLOAD_BYTES = 5_000_000


def download(url, audit):
    request = Request(url, headers={"User-Agent": "marinemodels OceanBench subset extractor"})
    with urlopen(request, timeout=40) as response:
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"Unexpectedly large object from {url}")
    audit[url] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return data


def read_chunk(store, metadata, variable, key, audit):
    spec = metadata[f"{variable}/.zarray"]
    if (spec["zarr_format"] != 2 or spec["order"] != "C" or spec["filters"]
            or spec.get("dimension_separator", ".") != "." or spec["compressor"]["id"] != "blosc"):
        raise ValueError(f"Unsupported chunk encoding for {variable} in {store}")
    url = f"{store}/{variable}/" + ".".join(map(str, key))
    data = get_codec(spec["compressor"]).decode(download(url, audit))
    return np.frombuffer(data, dtype=spec["dtype"]).reshape(spec["chunks"])


def match_coordinate(axis, target):
    indices = np.flatnonzero(np.isclose(axis, target, rtol=0, atol=0.0001))
    if len(indices) != 1:
        raise ValueError(f"Expected exactly one grid coordinate matching {target}")
    return int(indices[0])


def check_dates(metadata, time, reference, first_day, kind):
    attrs = metadata[".zattrs"]
    units = metadata["time/.zattrs"]["units"]
    if units != f"days since {first_day} 00:00:00" or not np.array_equal(time, np.arange(LEADS)):
        raise ValueError(f"Unexpected lead dates for {kind} on {first_day}")
    if kind == "forecast":
        if attrs.get("forecast_reference_time") != reference.isoformat():
            raise ValueError(f"GLONET reference date differs from {reference}")
    else:
        # Each appended GLO12 daily analysis names the date interval in its filename.
        stamp = reference.strftime("%Y%m%d")
        if f"_{stamp}-{stamp}_" not in attrs.get("history", ""):
            raise ValueError(f"Cannot verify the {reference} persistence analysis date")


def sample_variable(store, metadata, variable, positions, profiles, kind, audit):
    attrs = metadata[f"{variable}/.zattrs"]
    spec = metadata[f"{variable}/.zarray"]
    if (attrs["_ARRAY_DIMENSIONS"] != ["time", "depth", "latitude", "longitude"]
            or attrs["units"] != VARIABLES[variable]["archiveUnits"]
            or "scale_factor" in attrs or "add_offset" in attrs):
        raise ValueError(f"Unexpected dimensions, units or packing for {store}/{variable}")

    # This local cache is released between variables. Multiple stations and leads
    # often occur within a single compressed chunk.
    @lru_cache(maxsize=24)
    def load(key):
        return read_chunk(store, metadata, variable, key, audit)

    leads = range(LEADS) if kind == "forecast" else (0, LEADS - 1)
    for site_id, depth, spatial_indices in positions:
        series = []
        for lead in leads:
            indices = (lead, *spatial_indices)
            offsets = [divmod(index, size) for index, size in zip(indices, spec["chunks"], strict=True)]
            key, local = zip(*offsets)
            value = float(load(key)[local])
            if not math.isfinite(value) or value == spec["fill_value"]:
                series.append(None)
            elif attrs["valid_min"] <= value <= attrs["valid_max"]:
                series.append(value)
            else:
                raise ValueError(f"Invalid unmasked {variable} at {indices} in {store}")
        if kind == "persistence" and series[0] != series[-1]:
            raise ValueError(f"Persistence changed across leads for {site_id}, {depth}, {variable}")
        rounded = [round(value, 5) if value is not None else None for value in series]
        profiles[site_id][str(depth)][variable][kind] = rounded if kind == "forecast" else rounded[0]
    load.cache_clear()


def extract_run(reference, audit):
    dates = [reference + timedelta(days=lead) for lead in range(1, LEADS + 1)]
    profiles = {
        site["id"]: {str(depth): {name: {} for name in VARIABLES} for depth in DEPTHS}
        for site in SITES
    }
    sources = {}
    for kind, prefix in STORES.items():
        store = f"{ROOT}/{prefix}/{dates[0]:%Y%m%d}.zarr"
        sources[kind] = f"{store}/.zmetadata"
        metadata = json.loads(download(sources[kind], audit))["metadata"]
        coordinates = {}
        for name in ("latitude", "longitude", "time", "depth"):
            spec = metadata[f"{name}/.zarray"]
            if spec["chunks"] != spec["shape"] or metadata[f"{name}/.zattrs"]["_ARRAY_DIMENSIONS"] != [name]:
                raise ValueError(f"Unexpected coordinate layout for {store}/{name}")
            coordinates[name] = read_chunk(store, metadata, name, (0,), audit)
        check_dates(metadata, coordinates["time"], reference, dates[0], kind)
        positions = []
        for site in SITES:
            lat = match_coordinate(coordinates["latitude"], site["latitude"])
            lon = match_coordinate(coordinates["longitude"], site["longitude"])
            for depth in DEPTHS:
                z = match_coordinate(coordinates["depth"], depth)
                positions.append((site["id"], depth, (z, lat, lon)))
        for variable in VARIABLES:
            sample_variable(store, metadata, variable, positions, profiles, kind, audit)
    return {"referenceDate": str(reference), "dates": list(map(str, dates)), "sources": sources, "profiles": profiles}


def write_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temp_path.open("xb") as stream:
            stream.write(data)
        if path.is_file():
            temp_path.chmod(path.stat().st_mode & 0o777)
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True, type=Path, help="Destination for the forecast JSON.")
    parser.add_argument("--audit-manifest", type=Path, help="Optional JSON with source object URLs, sizes and SHA-256 digests.")
    args = parser.parse_args()
    if args.audit_manifest and args.output.resolve() == args.audit_manifest.resolve():
        parser.error("Output and audit manifest need distinct paths.")
    audit = {}
    data = {
        "title": "GLONET archived Mid-Atlantic forecast output",
        "provider": "Mercator Ocean International / OceanBench. Persistence contains E.U. Copernicus Marine Service Information.",
        "grid": "GLONET 1/4°, GLO12 persistence 1/12°, sampled on shared exact latitudes, longitudes and depths.",
        "time": "Daily means, UTC valid date; lead 1 is the day after the Zarr forecast_reference_time.",
        "baseline": "Official GLO12 persistence holds the previous day’s GLO12 analysis fixed; source lead 1 and lead 10 agree at each extracted location.",
        "precision": "Source values rounded to 5 decimal places; null is masked/unavailable.",
        "variables": VARIABLES,
        "sites": SITES,
        "depths": DEPTHS,
        "forecasts": [extract_run(reference, audit) for reference in REFERENCE_DATES],
    }
    payload = (json.dumps(data, allow_nan=False, separators=(",", ":")) + "\n").encode()
    write_file(args.output, payload)
    if args.audit_manifest:
        manifest = {"output_sha256": hashlib.sha256(payload).hexdigest(), "objects": audit}
        write_file(args.audit_manifest, (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode())
    print(f"Wrote {args.output} ({len(payload):,} bytes) from {len(audit)} source objects.")


if __name__ == "__main__":
    main()
