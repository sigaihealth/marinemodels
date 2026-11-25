"""Build an offline HTML timeline from an OOI replay and its recovered images."""

import argparse
import base64
import csv
import json
from pathlib import Path


SERIES = [
    ("roipml", "Image regions", "ROIs/mL", "#146648"),
    ("air_pressure", "Air pressure", "mbar", "#364f83"),
    ("sea_water_practical_salinity", "Practical salinity", "", "#176c79"),
    ("mass_concentration_of_chlorophyll_a_in_sea_water", "Chlorophyll-a", "µg/L", "#935522"),
]


def build(directory):
    with (directory / "replay.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("The replay contains no hourly rows.")

    hours = [row["hour_utc"] for row in rows]
    series = []
    for key, label, unit, color in SERIES:
        values = [float(row[f"{key}_median"]) if row[f"{key}_median"] else None for row in rows]
        counts = [int(row[f"{key}_qc2_n"]) for row in rows]
        series.append(dict(label=label, unit=unit, color=color, values=values, qc2=counts))

    pictures = []
    image_dir = directory / "ifcb"
    manifest = image_dir / "pioneer-ifcb-manifest.json"
    if manifest.exists():
        for sample in json.loads(manifest.read_text())["bins"]:
            hour = sample["time_utc"][:13] + ":00:00Z"
            if hour not in hours:
                continue
            crops = []
            for image in sample["images"]:
                encoded = base64.b64encode((image_dir / image["filename"]).read_bytes()).decode("ascii")
                crops.append(dict(target=image["target_number"], png="data:image/png;base64," + encoded))
            pictures.append(dict(index=hours.index(hour), time=sample["time_utc"], count=sample["image_count"],
                                 volume=sample["volume_analyzed_ml"], url=sample["source_url"], crops=crops))

    data = json.dumps(dict(hours=hours, series=series, pictures=pictures), allow_nan=False)
    template = Path(__file__).with_name("pioneer_playback.html.in").read_text(encoding="utf-8")
    result = directory / "pioneer_playback.html"
    result.write_text(template.replace("__REPLAY_JSON__", data.replace("<", r"\u003c")), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay_dir", type=Path, help="directory containing replay.csv and optional ifcb/")
    print(build(parser.parse_args().replay_dir))
