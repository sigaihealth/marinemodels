"""Compare a personal ONNX export with the PyTorch run on the same labeled validation crops."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

from plankton_workspace import transform


def validate(dataset, run):
    metadata = json.loads((run / "onnx-export.json").read_text())
    model = run / metadata["file"]
    with model.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != metadata["onnx_sha256"]:
            raise ValueError("The model differs from the export receipt.")
    manifest = dataset / "manifest.csv"
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != metadata["manifest_sha256"]:
        raise ValueError("Validation data differs from the training manifest.")
    with manifest.open() as file:
        rows = [r for r in csv.DictReader(file) if r["split"] == "validation"]
    with (run / "validation_predictions.csv").open() as file:
        reference = {r["roi_id"]: r for r in csv.DictReader(file)}
    if not rows or {r["roi_id"] for r in rows} != set(reference):
        raise ValueError("The two files describe different sets of held-out images.")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    session = ort.InferenceSession(str(model), options, providers=["CPUExecutionProvider"])
    identical, correct, max_delta = 0, 0, 0.0
    for row in rows:
        expected = reference[row["roi_id"]]
        path = dataset / row["path"]
        with path.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        if sha != row["sha256"] or sha != expected["sha256"] or row["label"] != expected["label"]:
            raise ValueError(f"Validation crop or label changed for {row['roi_id']}.")
        with Image.open(path) as image:
            tensor = transform(image).unsqueeze(0).numpy()
        logits = session.run(["logits"], {"pixels": tensor})[0][0]
        probs = np.exp(logits.astype(np.float64) - logits.max())
        probs /= probs.sum()
        if not np.isfinite(probs).all():
            raise ValueError("Invalid scores returned by ONNX.")
        index = int(probs.argmax())
        label = metadata["labels"][index]
        identical += label == expected["predicted_label"]
        correct += label == row["label"]
        max_delta = max(max_delta, abs(probs[index] - float(expected["top_softmax"])))
    return dict(validation_images=len(rows), same_top1=int(identical), correct=int(correct),
                accuracy=correct / len(rows), max_top_softmax_delta=float(max_delta),
                onnx_sha256=metadata["onnx_sha256"], manifest_sha256=metadata["manifest_sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.dataset, args.run)
    print(json.dumps(result, indent=2))
    if result["same_top1"] != result["validation_images"]:
        raise SystemExit(1)
