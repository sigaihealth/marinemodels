"""Fit and evaluate the browser's morphology classifier on a prepared WHOI IFCB subset.

    python train_morphology_baseline.py --dataset /path/to/expanded --output site/assets/ifcb-morphology.json

Requires NumPy and Pillow. Only aggregate parameters and held-out counts are saved.
"""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from PIL import Image


LABELS = sorted(("Balanion", "Dictyocha", "Guinardia_delicatula", "Mesodinium", "Pseudo-nitzschia",
                 "Thalassiosira", "Tripos_lineatus", "detritus", "flagellate", "nanoplankton_mix"))
FEATURES = [
    "log_short_side_px", "log_long_side_px", "border_median", "gray_mean", "gray_sd",
    *[f"gray_{n}_{n+31}_fraction" for n in range(0, 256, 32)],
    "contrast12_fraction", "contrast24_fraction", "contrast48_fraction",
    "contrast24_box_fill", "contrast24_box_elongation", "contrast24_perimeter_per_pixel",
    "contrast24_moment_anisotropy",
]
REVISION = "89b22c10739e8ef91bde18e7d5a81c21edddba9b"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def features(gray):
    """Operate at native pixel size. Keep in sync with morphologyFeatures in the web trial."""
    if gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValueError("Expected an 8-bit grayscale image.")
    h, w = gray.shape
    border = np.zeros((h, w), dtype=bool)
    border[[0, -1], :] = True
    border[:, [0, -1]] = True
    edge = np.sort(gray[border])
    background = int(edge[(len(edge) - 1) // 2])
    counts = np.bincount(gray.ravel(), minlength=256)
    levels = np.arange(256, dtype=np.float64)
    mean = (counts @ levels) / gray.size
    variance = max(0, (counts @ (levels * levels)) / gray.size - mean * mean)
    contrast = np.abs(gray.astype(np.int16) - background)
    mask = contrast >= 24
    ys, xs = np.nonzero(mask)
    box_fill = elongation = perimeter_ratio = anisotropy = 0.0
    if len(xs):
        bh = int(ys.max() - ys.min() + 1)
        bw = int(xs.max() - xs.min() + 1)
        box_fill = len(xs) / (bh * bw)
        elongation = 1 - min(bh, bw) / max(bh, bw)
        adjacent = np.count_nonzero(mask[:, 1:] & mask[:, :-1]) + np.count_nonzero(mask[1:, :] & mask[:-1, :])
        perimeter_ratio = (4 * len(xs) - 2 * adjacent) / len(xs)
        x, y = xs.astype(np.float64), ys.astype(np.float64)
        vx, vy = (x @ x) / len(x) - x.mean()**2, (y @ y) / len(y) - y.mean()**2
        cov = (x @ y) / len(x) - x.mean() * y.mean()
        if vx + vy > 0:
            anisotropy = np.hypot(vx - vy, 2 * cov) / (vx + vy)
    return [
        np.log1p(min(h, w)), np.log1p(max(h, w)), background / 255, mean / 255, np.sqrt(variance) / 255,
        *(counts.reshape(8, 32).sum(axis=1) / gray.size),
        *(np.count_nonzero(contrast >= threshold) / gray.size for threshold in (12, 24, 48)),
        box_fill, elongation, perimeter_ratio, anisotropy,
    ]


def samples(dataset):
    contents = (dataset / "manifest.csv").read_bytes()
    provenance = json.loads((dataset / "provenance.json").read_text())
    if provenance["dataset_revision"] != REVISION or provenance["manifest_sha256"] != sha(contents):
        raise ValueError("Prepared manifest differs from its recorded source or checksum.")
    rows = list(csv.DictReader(io.StringIO(contents.decode("utf-8"))))
    splits = {"train": [], "validation": []}
    seen_groups = {}
    seen_pixels = set()
    seen_rois = set()
    for row in rows:
        split, label, group = (row[k] for k in ("split", "label", "group"))
        if split not in splits or label not in LABELS or not group:
            raise ValueError("Manifest contains an unsupported split, label or acquisition group.")
        if seen_groups.setdefault(group, split) != split:
            raise ValueError("A sampling bin occurs on both sides of the split.")
        if row["roi_id"] in seen_rois or row["pixel_sha256"] in seen_pixels:
            raise ValueError("Repeated ROI or decoded image in manifest.")
        seen_rois.add(row["roi_id"])
        seen_pixels.add(row["pixel_sha256"])
        path = (dataset / row["path"]).resolve()
        if not path.is_relative_to(dataset.resolve()):
            raise ValueError("Image path is outside the prepared dataset.")
        raw = path.read_bytes()
        if sha(raw) != row["sha256"]:
            raise ValueError(f"Image file checksum mismatch for {row['roi_id']}")
        with Image.open(io.BytesIO(raw)) as image:
            if image.mode != "L" or image.format != "PNG":
                raise ValueError("Expected an original 8-bit grayscale PNG.")
            pixel_hash = sha(f"L:{image.width}x{image.height}:".encode() + image.tobytes())
            if pixel_hash != row["pixel_sha256"]:
                raise ValueError(f"Decoded pixel checksum mismatch for {row['roi_id']}")
            splits[split].append((label, features(np.asarray(image))))
    for split, records in splits.items():
        if {label for label, _ in records} != set(LABELS):
            raise ValueError(f"{split} must include all ten labels.")
    split_hashes = {}
    for split in splits:
        ids = sorted((r["group"], r["roi_id"], r["label"], r["pixel_sha256"]) for r in rows if r["split"] == split)
        split_hashes[split] = sha(json.dumps(ids, separators=(",", ":"), ensure_ascii=True).encode())
    return splits, provenance, split_hashes, Counter(seen_groups.values())


def fit(dataset):
    sets, provenance, split_hashes, group_counts = samples(dataset)
    train_y, train_x = zip(*sets["train"])
    train_y, train_x = np.array(train_y), np.asarray(train_x)
    # Population scaling and all centroids are estimated solely from training data.
    mean = np.round(train_x.mean(axis=0), 9)
    scale = np.round(train_x.std(axis=0), 9)
    scale[scale == 0] = 1.0
    standardized = (train_x - mean) / scale
    centers = np.round([standardized[train_y == label].mean(axis=0) for label in LABELS], 9)
    validation_y, validation_x = zip(*sets["validation"])
    val = (np.asarray(validation_x) - mean) / scale
    distances = np.sum((val[:, None, :] - centers[None, :, :])**2, axis=2)
    predicted = distances.argmin(axis=1)
    truth = [LABELS.index(label) for label in validation_y]
    matrix = np.zeros((len(LABELS), len(LABELS)), dtype=int)
    np.add.at(matrix, (truth, predicted), 1)
    denominators = matrix.sum(axis=0) + matrix.sum(axis=1)
    per_f1 = (2 * matrix.diagonal() / denominators).tolist()
    counts = {split: dict(sorted(Counter(label for label, _ in pairs).items())) for split, pairs in sets.items()}
    return {
        "schema": "ifcb-morphology-centroids-v1", "labels": LABELS, "features": FEATURES,
        "mean": mean.tolist(), "scale": scale.tolist(), "centroids": centers.tolist(),
        "distance": "Euclidean distance from the standardized image features to each training centroid. Lower is closer.",
        "source": {key: provenance[key] for key in ("attribution", "doi", "license", "license_url", "dataset_card", "dataset_revision", "selection", "manifest_sha256")},
        "training": {"images": len(train_y), "bins": group_counts["train"], "counts": counts["train"], "split_sha256": split_hashes["train"]},
        "validation": {"images": len(truth), "bins": group_counts["validation"], "counts": counts["validation"],
                       "split_sha256": split_hashes["validation"], "correct": int(matrix.trace()),
                       "accuracy": float(matrix.trace() / len(truth)), "macro_f1": float(np.mean(per_f1)),
                       "f1_by_label": dict(zip(LABELS, per_f1)), "confusion_true_rows_predicted_columns": matrix.tolist()},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", required=True, type=Path, help="Prepared expanded directory containing manifest.csv, provenance.json and images/.")
    p.add_argument("--output", required=True, type=Path, help="Destination for the public aggregate model.")
    args = p.parse_args()
    model = fit(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", dir=args.output.parent, delete=False, encoding="utf-8") as fp:
        stage = Path(fp.name)
        json.dump(model, fp, indent=2, ensure_ascii=False, allow_nan=False)
        fp.write("\n")
    try:
        stage.chmod(0o644)
        stage.replace(args.output)
    finally:
        stage.unlink(missing_ok=True)
    metrics = model["validation"]
    print(f"{args.output}: {metrics['correct']}/{metrics['images']} correct, macro-F1 {metrics['macro_f1']:.4f}")


if __name__ == "__main__":
    main()
