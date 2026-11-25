"""Check an authorized installation against its original per-image prediction export."""

import argparse
import csv
import json
from pathlib import Path, PureWindowsPath

from private_plankscope_runtime import load_classifier


def compare(directory, images, reference, device):
    classify = load_classifier(directory, device=device)
    with reference.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or len({r["image_sha256"] for r in rows}) != len(rows):
        raise ValueError("Supply a nonempty reference export with distinct image hashes.")
    matches, largest_difference = 0, 0.0
    for original in rows:
        name = PureWindowsPath(original["image"]).name
        result = classify(images / name)
        if result["input_sha256"] != original["image_sha256"]:
            raise ValueError(f"Image checksum differs for {name}")
        if (result["checkpoint_sha256"] != original["model_sha256"]
                or result["labels_sha256"] != original["class_labels_sha256"]):
            raise ValueError("The original run used a different checkpoint or label map.")
        top = result["candidates"][0]
        matches += top["label"] == original["label"]
        largest_difference = max(largest_difference, abs(top["softmax"] - float(original["confidence"])))
    return dict(images=len(rows), same_top1=matches, max_top_softmax_delta=largest_difference,
                device=result["device"], checkpoint_sha256=result["checkpoint_sha256"],
                class_labels_sha256=result["labels_sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--device", required=True, choices=("cpu", "cuda"))
    args = parser.parse_args()
    out = compare(args.model_dir, args.images, args.reference, args.device)
    print(json.dumps(out, indent=2))
    if out["images"] != out["same_top1"]:
        raise SystemExit(1)
