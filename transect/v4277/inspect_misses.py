"""Inspect box geometry and potential overlap for tracks neither model uniquely matched."""
import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


def overlap(a, b):
    width = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    shared = width * height
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - shared
    return shared / union if shared else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "tracks", "ecotype", "megalodon", "out"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args()
    with args.tracks.open() as src:
        missed = {int(row["track"]): [] for row in csv.DictReader(src) if row["track_group"] == "neither"}
    predictions = {m: defaultdict(list) for m in ("ecotype", "megalodon")}
    for method, per_frame in predictions.items():
        for row in json.loads(getattr(args, method).read_text())["sightings"]:
            per_frame[row["frame_id"]].append(row["bbox_xyxy"])
    for frame in json.loads(args.reference.read_text())["frames"]:
        for obj in frame["annotations"]:
            if obj["track_id"] not in missed:
                continue
            bbox = obj["bbox"]
            row = dict(t=frame["timestamp_s"], width=bbox[2]-bbox[0], height=bbox[3]-bbox[1],
                       border=min(bbox[0], bbox[1], frame["width"]-bbox[2], frame["height"]-bbox[3]) <= 2)
            for method, per_frame in predictions.items():
                row[method] = max((overlap(bbox, b) for b in per_frame[frame["frame_id"]]), default=0.)
            missed[obj["track_id"]].append(row)
    details = []
    for track, rows in missed.items():
        details.append(dict(track=track, appearances=len(rows), first_s=rows[0]["t"], last_s=rows[-1]["t"],
                            median_box_width_px=round(statistics.median(r["width"] for r in rows), 2),
                            median_box_height_px=round(statistics.median(r["height"] for r in rows), 2),
                            box_within_2px_of_image_edge=sum(r["border"] for r in rows),
                            frames_with_any_box_at_iou_050={m: sum(r[m] >= .5 for r in rows) for m in predictions},
                            max_raw_iou={m: round(max(r[m] for r in rows), 4) for m in predictions}))
    args.out.write_text(json.dumps(details, indent=2) + "\n")


if __name__ == "__main__":
    main()
