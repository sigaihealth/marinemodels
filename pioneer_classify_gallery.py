"""Classify a Pioneer IFCB image gallery on CPU with WHOI's Northeast Shelf model."""

import argparse
import csv
import hashlib
from io import BytesIO
from itertools import islice
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import onnxruntime as ort
from PIL import Image


# https://huggingface.co/sosiklab/NES-plankton-IFCB-classifier-2022
REVISION = "71bc362e8c75014c27692a8f10637d36f411962e"
MODEL_FILE = "20220209_Jan2022_NES_2.4.onnx"
MODEL_SHA256 = "d95db6614d7ccb94738404cf3250506b15b55e853fad09c8a87debdf0e2a0901"
LABELS_SHA256 = "e20ed2a59c672b2af10b1cda6743694f52ce728412d9c344ef90c5cb2cc02d03"
FIELDS = ["bin_id", "sample_utc", "roi_id", "source_url", "roi_sha256", "status", "model_revision"]
for rank in (1, 2, 3):
    FIELDS.extend([f"label_{rank}", f"index_{rank}", f"softmax_{rank}"])


def verified_bytes(path, expected_hash):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError(f"SHA-256 mismatch: {path}")
    return data


def whoi_input(image):
    # WHOIGit/ifcb-inference v0.4.0, IfcbBinImageTransformer (Pillow path).
    gray = image.convert("L").resize((299, 299), Image.Resampling.BICUBIC)
    rgb = np.asarray(gray.convert("RGB"), dtype=np.float32)
    return rgb.transpose(2, 0, 1) / np.float32(255.0)


def iter_gallery(gallery):
    manifest = json.loads((gallery / "pioneer-ifcb-manifest.json").read_text(encoding="utf-8"))
    for sample in manifest["bins"]:
        for entry in sample["images"]:
            path = gallery / entry["filename"]
            data = verified_bytes(path, entry["sha256"])
            with Image.open(BytesIO(data)) as image:
                tensor = whoi_input(image)
            row = {
                "bin_id": sample["id"], "sample_utc": sample["time_utc"], "roi_id": path.stem,
                "source_url": entry["source_url"], "roi_sha256": entry["sha256"],
                "status": "provisional_model_prediction_unreviewed", "model_revision": REVISION,
            }
            yield row, tensor


def classify(gallery, weights, output, batch_size):
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}")
    label_map = json.loads(verified_bytes(weights / "labels.json", LABELS_SHA256))
    labels = [label_map[str(i)] for i in range(len(label_map))]
    model = verified_bytes(weights / MODEL_FILE, MODEL_SHA256)
    session = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
    images = iter_gallery(gallery)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with TemporaryDirectory(dir=output.parent, prefix=".pioneer-predictions-") as staging:
        completed = Path(staging) / "predictions.csv"
        with completed.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            while batch := list(islice(images, batch_size)):
                rows, arrays = zip(*batch)
                logits = session.run(["output"], {"input": np.stack(arrays)})[0]
                if logits.shape != (len(rows), len(labels)) or not np.isfinite(logits).all():
                    raise ValueError("Unexpected scores from the classifier")
                exp = np.exp(logits - logits.max(axis=1, keepdims=True), dtype=np.float64)
                for row, scores in zip(rows, exp / exp.sum(axis=1, keepdims=True)):
                    for rank, index in enumerate(np.argsort(-scores)[:3], start=1):
                        row[f"label_{rank}"] = labels[index]
                        row[f"index_{rank}"] = int(index)
                        row[f"softmax_{rank}"] = format(scores[index], ".9g")
                    writer.writerow(row)
                count += len(rows)
        if not count:
            raise ValueError("The gallery has no images")
        # Atomic no-overwrite publication, including when two runs finish together.
        os.link(completed, output)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ifcb-dir", type=Path, required=True, help="directory containing the gallery manifest and crops")
    parser.add_argument("--weights-dir", type=Path, required=True, help=f"directory containing {MODEL_FILE} and labels.json")
    parser.add_argument("--output", type=Path, required=True, help="new CSV for the top three provisional labels per image")
    parser.add_argument("--batch-size", type=int, default=16, help="number of images per CPU inference batch (default 16)")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    try:
        count = classify(args.ifcb_dir, args.weights_dir, args.output, args.batch_size)
    except (KeyError, ValueError, OSError) as exc:
        parser.exit(1, f"Classification failed: {exc}\n")
    print(f"Wrote provisional predictions for {count} images to {args.output}")


if __name__ == "__main__":
    main()
