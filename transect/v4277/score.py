"""Evaluate blind detector records on MBARI Ventana V4277 and generate its frame reviewer."""
import argparse
import base64
import csv
import gzip
import hashlib
import io
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import scipy
from PIL import Image
from scipy.optimize import linear_sum_assignment

METHODS = ("ecotype", "megalodon")
GROUPS = ("neither", "ecotype_only", "megalodon_only", "both")
SOURCE = "https://huggingface.co/datasets/MBARI-org/DeepSea-MOT"
MIN_IOU = 0.50


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_text())


def check(ok, why):
    if not ok:
        raise ValueError(why)


def valid_box(box):
    return (len(box) == 4 and all(isinstance(n, (int, float)) and math.isfinite(n) for n in box)
            and box[0] < box[2] and box[1] < box[3])


def match(truth, predicted):
    if not truth or not predicted:
        return {}
    a = np.asarray([r["bbox"] for r in truth], dtype=float)[:, None, :]
    b = np.asarray([r["bbox_xyxy"] for r in predicted], dtype=float)[None, :, :]
    overlap = np.maximum(np.minimum(a[..., 2:], b[..., 2:]) - np.maximum(a[..., :2], b[..., :2]), 0).prod(axis=-1)
    area_a = (a[..., 2:] - a[..., :2]).prod(axis=-1)
    area_b = (b[..., 2:] - b[..., :2]).prod(axis=-1)
    ious = overlap / (area_a + area_b - overlap)
    # One additional eligible pair is worth more than the largest possible improvement in total IoU.
    bonus = min(len(truth), len(predicted)) + 1
    weights = np.zeros((len(truth), len(predicted) + len(truth)))
    weights[:, :len(predicted)] = np.where(ious >= MIN_IOU, bonus + ious, -1)
    rows, cols = linear_sum_assignment(weights, maximize=True)
    return {int(i): (int(j), float(ious[i,j])) for i, j in zip(rows, cols)
            if j < len(predicted) and ious[i, j] >= MIN_IOU}


def read_predictions(path, method, frame_ids):
    record = load(path)
    check(record["method"] == method, f"Wrong detector in {path}")
    frames = record["frames"]
    check(len(frames) == len(frame_ids) and {r["frame_id"] for r in frames} == frame_ids, f"{method} frame coverage differs")
    check(all(f["inference_ok"] is True for f in frames), f"{method} has unsuccessful frames")
    by_frame = defaultdict(list)
    seen = set()
    for item in record["sightings"]:
        fid = item["frame_id"]
        check(fid in frame_ids and valid_box(item["bbox_xyxy"]), f"Unknown frame or invalid {method} box")
        item = dict(item)
        sid = str(item.get("sighting_id", f"{method}:{fid}:{len(by_frame[fid])+1}"))
        check(sid not in seen, f"Repeated sighting: {sid}")
        seen.add(sid)
        item["sighting_id"] = sid
        check(isinstance(item.get("score"), (int,float)) and math.isfinite(item["score"]) and 0 <= item["score"] <= 1, f"Invalid confidence: {sid}")
        by_frame[fid].append(item)
    for boxes in by_frame.values():
        boxes.sort(key=lambda box: box["sighting_id"])
    return by_frame


def group_for(ecotype, megalodon):
    if ecotype and megalodon:
        return "both"
    if ecotype:
        return "ecotype_only"
    return "megalodon_only" if megalodon else "neither"


def fraction(n, d):
    return n / d if d else None


def score(frames, predictors):
    track_labels = defaultdict(Counter)
    appearances = []
    candidates = []
    for fr in frames:
        fid = fr["frame_id"]
        refs = sorted(fr["annotations"], key=lambda r: int(r["track_id"]))
        check(all(valid_box(r["bbox"]) for r in refs), f"Invalid reference box: {fid}")
        check(len({r["track_id"] for r in refs}) == len(refs), f"Multiple boxes for one reference track in {fid}")
        matches = {}
        for method in METHODS:
            preds = predictors[method].get(fid, [])
            assigned = match(refs, preds)
            by_pred = {j: (refs[i]["track_id"], overlap) for i, (j, overlap) in assigned.items()}
            for j, item in enumerate(preds):
                tid, overlap = by_pred.get(j, (None, None))
                candidates.append({"frame_id": fid, "frame_index": fr["frame_index"], "method": method,
                                   "sighting_id": item["sighting_id"], "label": item.get("label", ""), "score": item["score"],
                                   "reference_track": tid, "iou": overlap, "bbox": item["bbox_xyxy"]})
            matches[method] = {i: (preds[j]["sighting_id"], overlap) for i,(j,overlap) in assigned.items()}
        for i, row in enumerate(refs):
            tid = int(row["track_id"])
            track_labels[tid][row["label"]] += 1
            current = {"frame_id": fid, "frame_index": fr["frame_index"], "track": tid, "label": row["label"], "bbox": row["bbox"]}
            for method in METHODS:
                current[method], current[method+"_iou"] = matches[method].get(i, (None, None))
            current["group"] = group_for(*[current[m] is not None for m in METHODS])
            appearances.append(current)
    by_track = defaultdict(list)
    for r in appearances:
        by_track[r["track"]].append(r)
    track_table = []
    for tid, rows in sorted(by_track.items()):
        rec = {"track": tid, "label": " / ".join(sorted(track_labels[tid])), "appearances": len(rows),
               "first_frame": rows[0]["frame_index"], "last_frame": rows[-1]["frame_index"]}
        for method in METHODS:
            rec[method+"_matched"] = sum(r[method] is not None for r in rows)
            rec[method+"_coverage"] = rec[method+"_matched"] / len(rows)
        rec["either_matched"] = sum(r["group"] != "neither" for r in rows)
        rec["both_matched"] = sum(r["group"] == "both" for r in rows)
        rec["track_group"] = group_for(*[rec[m+"_matched"] > 0 for m in METHODS])
        track_table.append(rec)
    appearance_groups = Counter(r["group"] for r in appearances)
    track_groups = Counter(r["track_group"] for r in track_table)
    metrics = {"frames": len(frames), "iou_threshold": MIN_IOU, "reference_appearances": len(appearances),
               "reference_tracks": len(track_table),
               "appearances_by_agreement": {g: appearance_groups[g] for g in GROUPS},
               "tracks_by_ever_reached": {g: track_groups[g] for g in GROUPS},
               "published_labels": dict(sorted(Counter(r["label"] for r in appearances).items())), "methods": {}}
    for method in METHODS:
        matched = sum(record[method+"_matched"] for record in track_table)
        n = sum(row["method"] == method for row in candidates)
        metrics["methods"][method] = {"predictions": n, "matches": matched, "missed_appearances": len(appearances)-matched,
            "unmatched_predictions": n-matched, "appearance_recall": fraction(matched, len(appearances)),
            "prediction_match_rate": fraction(matched, n), "tracks_reached": sum(r[method+"_matched"] > 0 for r in track_table),
            "median_fraction_of_track_appearances_matched": (statistics.median(r[method+"_coverage"] for r in track_table) if track_table else None)}
    by_taxon = {}
    for label in metrics["published_labels"]:
        rows = [r for r in appearances if r["label"] == label]
        track_ids = {r["track"] for r in rows}
        by_taxon[label] = {"reference_appearances": len(rows), "reference_tracks": len(track_ids),
                           "appearances_missed_by_both": sum(r["group"] == "neither" for r in rows),
                           "tracks_never_reached": len(track_ids - {r["track"] for r in rows if r["group"] != "neither"})}
        for method in METHODS:
            matched = [r for r in rows if r[method] is not None]
            by_taxon[label][method] = {"matches": len(matched), "tracks_reached": len({r["track"] for r in matched})}
    metrics["by_published_taxon"] = by_taxon
    return metrics, track_table, appearances, candidates


def review_cases(appearances, candidates, tracks):
    lookup = {r["track"]: r for r in tracks}
    groups = {}
    for group in GROUPS:
        by_track = defaultdict(list)
        for r in appearances:
            if r["group"] == group:
                by_track[r["track"]].append(r)
        ranked = sorted(by_track, key=lambda t: (group == "neither" and lookup[t]["track_group"] != "neither", -len(by_track[t]), t))
        cases = []
        for tid in ranked[:3]:
            rows = by_track[tid]
            row = rows[(len(rows)-1)//2]
            cases.append(dict(row, group_frames=len(rows), track_frames=lookup[tid]["appearances"],
                              track_group=lookup[tid]["track_group"]))
        groups[group] = cases
    for method in METHODS:
        unmatched = [r for r in candidates if r["method"] == method and r["reference_track"] is None]
        ranked = sorted(unmatched, key=lambda r: (-r["score"],r["frame_index"],r["sighting_id"]))
        frames_seen = set()
        cases = []
        for row in ranked:
            if row["frame_id"] not in frames_seen:
                frames_seen.add(row["frame_id"])
                cases.append(dict(row))
                if len(cases) == 3:
                    break
        groups[method+"_unmatched"] = cases
    return groups


def write_table(path, rows, fields, compressed=False):
    def emit(f):
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    if compressed:
        with path.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as handle:
                emit(handle)
    else:
        with path.open("w", newline="") as handle:
            emit(handle)


def encode_jpeg(img):
    stream = io.BytesIO()
    img.save(stream, format="JPEG", quality=86, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(stream.getvalue()).decode()


def attach_media(groups, frames, blind, predictors, root):
    refs = {f["frame_id"]: f for f in frames}
    images = {}
    for cases in groups.values():
        for case in cases:
            fid = case["frame_id"]
            frame = refs[fid]
            entry = blind[fid]
            case["timestamp"] = frame["timestamp_s"]
            src = root / entry["path"]
            with Image.open(src) as opened:
                image = opened.convert("RGB")
                w, h = image.size
                if fid not in images:
                    check(digest(src) == entry["sha256"], f"Changed review JPEG: {fid}")
                    check((w, h) == (frame["width"], frame["height"]), f"Image geometry differs: {fid}")
                    preview = image.copy()
                    preview.thumbnail((1024, 640))
                    images[fid] = {"image": encode_jpeg(preview), "width": w, "height": h, "layers": {}}
                    fg = images[fid]["layers"]
                    fg["expert"] = [{"box": r["bbox"], "name": str(r["track_id"])} for r in frame["annotations"]]
                    for m in METHODS:
                        fg[m] = [{"box": r["bbox_xyxy"], "name": r["sighting_id"]} for r in predictors[m].get(fid, [])]
                x1,y1,x2,y2 = case["bbox"]
                side = min(max((x2-x1)*1.7, (y2-y1)*1.7, 128), max(w,h))
                cw,ch = min(w, math.ceil(side)), min(h, math.ceil(side))
                x = max(0, min(w-cw, round((x1+x2-cw)/2)))
                y = max(0, min(h-ch, round((y1+y2-ch)/2)))
                crop = image.crop((x,y,x+cw,y+ch))
                crop.thumbnail((420,420))
                case["crop"] = {"image": encode_jpeg(crop), "viewport": [x,y,cw,ch]}
    return images


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference","manifest","ecotype","megalodon","output"):
        parser.add_argument("--"+name,required=True,type=Path)
    parser.add_argument("--miss-details", type=Path, help="Optional post-hoc raw-overlap diagnostics for never-matched expert tracks")
    args = parser.parse_args()
    frames = sorted(load(args.reference)["frames"], key=lambda r:r["frame_index"])
    check([r["frame_index"] for r in frames] == list(range(1,601)), "Expected all 600 publisher frame indices")
    ids = {f["frame_id"] for f in frames}
    manifest = load(args.manifest)["frames"]
    blind = {f["frame_id"]: f for f in manifest}
    check(len(ids) == len(blind) == len(manifest) == 600 and ids == set(blind), "Blind/reference frames differ")
    for f in frames:
        b = blind[f["frame_id"]]
        check(all(f[k]==b[k] for k in ("frame_index","timestamp_s","width","height")), f"Frame metadata mismatch: {f['frame_id']}")
    predictors = {m: read_predictions(getattr(args,m), m, ids) for m in METHODS}
    metrics, tracks, appearances, candidates = score(frames, predictors)
    metrics["input_sha256"] = {k: digest(getattr(args,k)) for k in ("reference","manifest",*METHODS)}
    metrics["software"] = {"scipy": scipy.__version__, "numpy": np.__version__}
    metrics["review_id"] = hashlib.sha256(json.dumps(metrics,sort_keys=True).encode()).hexdigest()[:20]
    groups = review_cases(appearances, candidates, tracks)
    media = attach_media(groups, frames, blind, predictors, args.manifest.parent)
    args.output.mkdir(parents=True, exist_ok=True)
    for filename, data in (("metrics.json", metrics), ("review-cases.json", {k:[{f:v for f,v in r.items() if f!="crop"} for r in g] for k,g in groups.items()})):
        (args.output/filename).write_text(json.dumps(data, indent=2, allow_nan=False)+"\n")
    track_fields = ["track","label","appearances","first_frame","last_frame","ecotype_matched","ecotype_coverage",
                    "megalodon_matched","megalodon_coverage","either_matched","both_matched","track_group"]
    write_table(args.output/"tracks.csv", tracks, track_fields)
    write_table(args.output/"appearances.csv.gz",appearances,["frame_id","frame_index","track","label","bbox","group","ecotype","ecotype_iou","megalodon","megalodon_iou"],True)
    write_table(args.output/"predictions.csv.gz",candidates,["frame_id","frame_index","method","sighting_id","label","score","bbox","reference_track","iou"],True)
    diagnostics = load(args.miss_details) if args.miss_details else []
    if diagnostics:
        never = {r["track"]:r["appearances"] for r in tracks if r["track_group"] == "neither"}
        check(len(diagnostics) == len(never) and {d["track"]:d["appearances"] for d in diagnostics} == never,
              "Post-hoc diagnostics differ from the reference tracks missed by both methods")
    bundle = json.dumps({"metrics":metrics,"tracks":tracks,"groups":groups,"images":media,"miss_details":diagnostics}, separators=(",",":"), allow_nan=False).replace("<","\\u003c")
    template = Path(__file__).with_name("review.html.in").read_text()
    (args.output/"v4277.html").write_text(template.replace("__V4277_BUNDLE__", bundle))
    print(json.dumps(metrics,indent=2))


if __name__ == "__main__":
    main()
