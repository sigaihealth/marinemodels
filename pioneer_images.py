"""Download a small, reproducible set of OOI IFCB images from Winter Storm Gianna."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from urllib.request import urlopen


BASE = "https://ifcb-data.oceanobservatories.org"
DATASET = "PioneerMABMoored"
PLATFORM = "CP10CNSM"
DAY = "2026-02-01"
BIN_IDS = ("D20260201T002546_IFCB200", "D20260201T152545_IFCB200")
EXPORT_URL = f"{BASE}/api/export_metadata/{DATASET}?start_date={DAY}&end_date={DAY}"
EVENT_SOURCE = (
    "https://oceanobservatories.org/2026/09/"
    "ooi-plankton-imagery-and-co-located-environmental-data-now-ready-for-analysis/"
)
IMAGES_PER_BIN = 12


def fetch_bytes(url):
    with urlopen(url, timeout=20) as response:
        limit = 2 * 1024 * 1024
        payload = response.read(limit + 1)
        if len(payload) > limit:
            raise ValueError(f"Response exceeded the sample download limit: {url}")
        return payload


def draw_contact_sheet(output, bins):
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    columns = 6
    tile_width, tile_height = 161, 126
    group_height = 43 + 2 * tile_height
    margin = 20
    width = 2 * margin + columns * tile_width
    sheet = Image.new("RGB", (width, 103 + len(bins) * group_height), "#f2f6f6")
    draw = ImageDraw.Draw(sheet)
    try:
        heading = ImageFont.load_default(size=24)
        body = ImageFont.load_default(size=14)
    except TypeError:
        # Use the built-in bitmap font on Pillow versions before scalable defaults.
        heading = body = ImageFont.load_default()

    draw.text((margin, 14), "Winter Storm Gianna | Pioneer MAB plankton imagery", fill="#12343b", font=heading)
    draw.text((margin, 46), "NSF Ocean Observatories Initiative | CP10CNSM, 7 m | 2026-02-01 UTC", fill="#214852", font=body)
    draw.text(
        (margin, 66),
        "Unclassified image regions may contain plankton or other particles. Crops are resized independently.",
        fill="#214852", font=body,
    )

    for group, sample in enumerate(bins):
        y = 101 + group * group_height
        timestamp = sample["time_utc"][11:19]
        title = (
            f"{timestamp} UTC | {sample['id']} | {sample['image_count']:,} regions"
            f" in {sample['volume_analyzed_ml']:.2f} mL"
        )
        draw.text((margin, y), title, fill="#12343b", font=body)
        for index, image in enumerate(sample["images"]):
            row, column = divmod(index, columns)
            left = margin + column * tile_width
            top = y + 22 + row * tile_height
            draw.rectangle((left, top, left + tile_width - 8, top + 102), fill="#fff", outline="#c8d7d9")
            with Image.open(output / image["filename"]) as original:
                thumb = ImageOps.contain(original.convert("RGB"), (tile_width - 22, 91))
                sheet.paste(thumb, (left + (tile_width - 8 - thumb.width) // 2, top + (102 - thumb.height) // 2))
            draw.text((left + 4, top + 105), f"ROI {image['target_number']:05d}", fill="#12343b")
    sheet.save(output / "pioneer-ifcb-contact-sheet.png")


def download(output):
    from PIL import Image

    output.joinpath("roi").mkdir()
    metadata = fetch_bytes(EXPORT_URL).decode("utf-8-sig")
    rows = {row["pid"]: row for row in csv.DictReader(StringIO(metadata))}
    bins = []
    for bin_id in BIN_IDS:
        row = rows.get(bin_id)
        if row is None or row["dataset"] != DATASET or row["sample_type"] != "moored":
            raise ValueError(f"Moored image sample is missing: {bin_id}")
        list_url = f"{BASE}/api/list_images/{bin_id}"
        targets = sorted(json.loads(fetch_bytes(list_url))["images"])
        image_count = int(row["n_images"])
        if len(targets) != image_count or image_count < IMAGES_PER_BIN:
            raise ValueError(f"Unexpected number of image regions for {bin_id}")
        timestamp = datetime.fromisoformat(row["sample_time"]).astimezone(timezone.utc)
        sample = {
            "id": bin_id,
            "time_utc": timestamp.isoformat().replace("+00:00", "Z"),
            "source_url": f"{BASE}/bin?dataset={DATASET}&bin={bin_id}",
            "metadata_url": f"{BASE}/api/metadata/{bin_id}",
            "image_list_url": list_url,
            "image_count": image_count,
            "volume_analyzed_ml": float(row["ml_analyzed"]),
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "depth_m": float(row["depth"]),
            "images": [],
        }

        # Sample the middle of each equal-sized segment of the sorted target list.
        for index in range(IMAGES_PER_BIN):
            target = targets[(2 * index + 1) * image_count // (2 * IMAGES_PER_BIN)]
            filename = f"{bin_id}_{target:05d}.png"
            url = f"{BASE}/data/{filename}"
            payload = fetch_bytes(url)
            with Image.open(BytesIO(payload)) as image:
                if image.format != "PNG":
                    raise ValueError(f"Expected PNG for {url}")
                width, height = image.size
                image.verify()
            relative_path = f"roi/{filename}"
            output.joinpath(relative_path).write_bytes(payload)
            sample["images"].append({
                "filename": relative_path,
                "target_number": target,
                "source_url": url,
                "width_px": width,
                "height_px": height,
                "sha256": hashlib.sha256(payload).hexdigest(),
            })
        bins.append(sample)

    draw_contact_sheet(output, bins)
    manifest = {
        "dataset": DATASET,
        "platform": PLATFORM,
        "instrument_reference": "CP10CNSM-RID27-07-PLIMSA000",
        "platform_doi": "https://doi.org/10.58046/OOI-CP10CNSM",
        "data_provider": "NSF Ocean Observatories Initiative IFCB Dashboard",
        "event_source": EVENT_SOURCE,
        "metadata_export_url": EXPORT_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "selection": "Middle target from each of 12 equal segments of each bin's sorted image target list.",
        "classification": "Unclassified image regions may contain plankton or other particles.",
        "contact_sheet": "pioneer-ifcb-contact-sheet.png",
        "bins": bins,
    }
    output.joinpath("pioneer-ifcb-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="new directory for the image set")
    args = parser.parse_args()
    output = args.output_dir
    if output.exists() or output.is_symlink():
        parser.error(f"output directory already exists: {output}")

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".pioneer-images-", dir=output.parent) as staging:
            completed = Path(staging) / "completed"
            completed.mkdir()
            download(completed)
            if output.exists() or output.is_symlink():
                raise FileExistsError(f"output directory already exists: {output}")
            completed.rename(output)
    except ImportError:
        parser.error("Pillow is required. Install it with python -m pip install Pillow")
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        print(f"OOI image download failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote 24 original image crops, a contact sheet, and a provenance manifest to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
