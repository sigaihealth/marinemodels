"""Download four OOI sensor streams and replay the Gianna storm by UTC hour."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta, timezone
from io import TextIOWrapper
import json
import math
from pathlib import Path
from statistics import median
import sys
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen


ERDDAP = "https://erddap.dataexplorer.oceanobservatories.org/erddap/tabledap"
EVENT = (
    "https://oceanobservatories.org/2026/09/"
    "ooi-plankton-imagery-and-co-located-environmental-data-now-ready-for-analysis/"
)
DATASETS = {
    "plims": ("ooi-cp10cnsm-rid27-07-plimsa000", ("roipml", "volana")),
    "fluorometer": (
        "ooi-cp10cnsm-rid27-02-flortd000",
        ("mass_concentration_of_chlorophyll_a_in_sea_water",),
    ),
    "ctd": ("ooi-cp10cnsm-rid27-03-ctdbpc000", ("sea_water_practical_salinity",)),
    "meteorology": ("ooi-cp10cnsm-sbd11-06-metbka000", ("air_pressure",)),
}
QC_USED = {"1", "2"}


def iso_utc(timestamp):
    return timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")


def fetch(dataset, variables, start, end):
    fields = ["time", "latitude", "longitude"]
    for variable in variables:
        fields.extend((variable, f"{variable}_qc_agg"))
    query = ",".join(fields) + f"&time>={iso_utc(start)}&time<{iso_utc(end)}"
    url = f"{ERDDAP}/{dataset}.csv?{quote(query, safe=',&=:')}"

    try:
        with urlopen(url, timeout=30) as response:
            records = csv.DictReader(TextIOWrapper(response, encoding="iso-8859-1"))
            units = next(records, None)
            if records.fieldnames != fields or units is None or units["time"] != "UTC":
                raise ValueError(f"Unexpected ERDDAP CSV schema for {dataset}")
            rows = list(records)
    except HTTPError as exc:
        with exc:
            message = exc.read(1024).decode("utf-8", errors="replace")
        if exc.code != 404 or "Your query produced no matching results" not in message:
            raise RuntimeError(f"ERDDAP returned HTTP {exc.code} for {dataset}") from exc
        rows, units = [], {}

    return fields, units, rows, url


def observations_to_csv(path, fields, rows, dataset):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*fields, "dataset_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "dataset_id": dataset})


def replay(start, end, output):
    bins = defaultdict(list)
    variables = []
    summary = {
        "platform": "CP10CNSM",
        "platform_doi": "https://doi.org/10.58046/OOI-CP10CNSM",
        "event_source": EVENT,
        "data_provider": "NSF Ocean Observatories Initiative Data Explorer ERDDAP",
        "acknowledgement_guidance": "https://oceanobservatories.org/how-to-use-acknowledge-and-cite-data/",
        "retrieved_utc": iso_utc(datetime.now(timezone.utc)),
        "start_inclusive_utc": iso_utc(start),
        "end_exclusive_utc": iso_utc(end),
        "alignment": "Hourly UTC medians over finite observations. No interpolation.",
        "qc_policy": "Include 1 (pass) and 2 (not evaluated). Keep all upstream flags in observation CSVs.",
        "sources": {},
    }

    for name, (dataset, products) in DATASETS.items():
        fields, units, rows, url = fetch(dataset, products, start, end)
        observations_to_csv(output / f"{name}.csv", fields, rows, dataset)
        source = {
            "dataset_id": dataset,
            "source_url": url,
            "observation_csv": f"{name}.csv",
            "observation_rows": len(rows),
            "variables": {},
        }
        summary["sources"][name] = source

        for product in products:
            variables.append(product)
            qc_field = f"{product}_qc_agg"
            flags = Counter()
            occupied_hours = set()
            for row in rows:
                flag = row[qc_field]
                flags[flag] += 1
                if flag not in QC_USED or not row[product]:
                    continue
                value = float(row[product])
                if not math.isfinite(value):
                    continue
                timestamp = datetime.fromisoformat(row["time"].replace("Z", "+00:00"))
                hour = timestamp.replace(minute=0, second=0, microsecond=0)
                bins[hour, product].append((value, flag))
                occupied_hours.add(hour)

            source["variables"][product] = {
                "unit": units.get(product),
                "qc_flag_counts": dict(sorted(flags.items())),
                "hours_with_data": len(occupied_hours),
            }

    if not bins:
        raise ValueError("No finite observations with QC flag 1 or 2 in the requested window")

    with (output / "replay.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        headers = ["hour_utc"]
        for variable in variables:
            headers.extend((f"{variable}_median", f"{variable}_n", f"{variable}_qc2_n"))
        writer.writerow(headers)

        hour = start
        while hour < end:
            row = [iso_utc(hour)]
            for variable in variables:
                samples = bins.get((hour, variable), [])
                center = median(value for value, flag in samples) if samples else ""
                row.extend((center, len(samples), sum(flag == "2" for _, flag in samples)))
            writer.writerow(row)
            hour += timedelta(hours=1)

    with (output / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default="2026-01-29", help="inclusive UTC date (YYYY-MM-DD)")
    parser.add_argument("--end", type=date.fromisoformat, default="2026-02-04", help="exclusive UTC date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", type=Path, default=Path("data/gianna"), help="new directory for replay files")
    args = parser.parse_args()
    if not 1 <= (args.end - args.start).days <= 31:
        parser.error("use a window of 1 to 31 days")
    start = datetime.combine(args.start, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(args.end, datetime.min.time(), tzinfo=timezone.utc)
    output = args.output_dir
    if output.exists() or output.is_symlink():
        parser.error(f"output directory already exists: {output}")

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".ooi-replay-", dir=output.parent) as staging:
            completed = Path(staging) / "completed"
            completed.mkdir()
            replay(start, end, completed)
            completed.rename(output)
    except (OSError, ValueError, RuntimeError, csv.Error) as exc:
        print(f"OOI replay failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote observation CSVs, replay.csv and summary.json to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
