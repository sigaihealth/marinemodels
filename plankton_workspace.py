"""Train and evaluate a supervised IFCB crop classifier with a frozen MobileNetV3 backbone."""

import argparse
import csv
import hashlib
import io
import json
import math
import os
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
import torch
from torch import nn
import torchvision
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small
from torchvision.transforms.functional import normalize, pil_to_tensor


VERSION = 1
BACKBONE = "torchvision MobileNetV3-Small IMAGENET1K_V1"
PREPROCESSING = "grayscale; aspect-preserving bilinear fit and corner-median padding to 224x224; repeated RGB; ImageNet mean/std"
FIELDS = {"path", "label", "split", "group", "roi_id", "sha256", "pixel_sha256"}


def device_for(name):
    if name == "auto":
        name = "cuda" if torch.cuda.is_available() else "cpu"
    if name == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA is unavailable. Select --device cpu or use a CUDA-enabled PyTorch kernel.")
    torch.set_num_threads(min(4, torch.get_num_threads()))
    return torch.device(name)


def read_manifest(dataset):
    manifest = dataset / "manifest.csv"
    raw = manifest.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if not FIELDS.issubset(reader.fieldnames or []):
        raise ValueError("manifest.csv requires " + ", ".join(sorted(FIELDS)))
    rows = list(reader)
    seen_ids, seen_paths = set(), set()
    split_keys = {s: {k: set() for k in ("group", "sha256", "pixel_sha256")} for s in ("train", "validation")}
    for row in rows:
        split = row["split"]
        if split not in split_keys or any(not row[k] for k in FIELDS):
            raise ValueError("Each row needs a label, image identifiers and a train or validation split.")
        path = (dataset / row["path"]).resolve()
        if Path(row["path"]).is_absolute() or not path.is_relative_to(dataset.resolve()):
            raise ValueError("An image path points outside the dataset.")
        if row["roi_id"] in seen_ids or path in seen_paths:
            raise ValueError("An image ID or path occurs more than once in the manifest.")
        seen_ids.add(row["roi_id"])
        seen_paths.add(path)
        row["file"] = path
        for key in split_keys[split]:
            split_keys[split][key].add(row[key])
    for key in split_keys["train"]:
        if split_keys["train"][key] & split_keys["validation"][key]:
            raise ValueError(f"Train and validation overlap in {key}.")
    train = [r for r in rows if r["split"] == "train"]
    validation = [r for r in rows if r["split"] == "validation"]
    labels = sorted({r["label"] for r in train})
    if len(labels) < 2 or not validation:
        raise ValueError("Provide at least two training classes and a nonempty validation set.")
    if {r["label"] for r in validation} - set(labels):
        raise ValueError("A validation label has no training examples.")
    return train, validation, labels, hashlib.sha256(raw).hexdigest()


def transform(image):
    gray = image.convert("L")
    w, h = gray.size
    corners = sorted(gray.getpixel(p) for p in ((0, 0), (w-1, 0), (0, h-1), (w-1, h-1)))
    size = min(224 / w, 224 / h)
    tile = gray.resize((max(1, round(w * size)), max(1, round(h * size))), Image.Resampling.BILINEAR)
    panel = Image.new("L", (224, 224), (corners[1] + corners[2]) // 2)
    panel.paste(tile, ((224 - tile.width) // 2, (224 - tile.height) // 2))
    rgb = pil_to_tensor(panel.convert("RGB")).float().div_(255)
    return normalize(rgb, [0.485, 0.456, 0.406], [0.229, 0.224, 0.225])


def make_backbone(pretrained):
    weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
    net = mobilenet_v3_small(weights=weights)
    return nn.Sequential(net.features, net.avgpool, nn.Flatten()).eval().requires_grad_(False)


@torch.no_grad()
def embed(backbone, rows, batch_size, device):
    embeddings = []
    for start in range(0, len(rows), batch_size):
        images = []
        for row in rows[start:start + batch_size]:
            raw = row["file"].read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("Image checksum mismatch for " + row["roi_id"])
            with Image.open(io.BytesIO(raw)) as image:
                images.append(transform(image))
        embeddings.append(backbone(torch.stack(images).to(device)))
    return torch.cat(embeddings)


def evaluate(rows, truth, probabilities, labels):
    predicted = probabilities.argmax(dim=1).tolist()
    matrix = [[0 for _ in labels] for _ in labels]
    for actual, guess in zip(truth, predicted):
        matrix[actual][guess] += 1
    per_class = []
    for i, label in enumerate(labels):
        support = sum(matrix[i])
        predicted_count = sum(row[i] for row in matrix)
        hits = matrix[i][i]
        precision = hits / predicted_count if predicted_count else 0.0
        recall = hits / support if support else None
        f1 = 2 * hits / (support + predicted_count) if support else None
        per_class.append(dict(label=label, support=support, predicted=predicted_count,
                              precision=precision, recall=recall, f1=f1))
    scored = [c for c in per_class if c["support"]]
    metrics = dict(accuracy=sum(matrix[i][i] for i in range(len(labels))) / len(rows),
                   macro_f1=sum(c["f1"] for c in scored) / len(scored),
                   balanced_accuracy=sum(c["recall"] for c in scored) / len(scored),
                   per_class=per_class, confusion_matrix=matrix, label_order=labels)
    return metrics, predicted


def train(dataset, output, *, device="auto", seed=42, epochs=40, batch_size=24, learning_rate=0.01):
    dataset, output = Path(dataset), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Choose a new output directory: {output}")
    if min(epochs, batch_size) < 1 or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("Epoch count, batch size and learning rate must be positive.")
    device = device_for(device)
    train_rows, held_out, labels, manifest_hash = read_manifest(dataset)
    index = {label: i for i, label in enumerate(labels)}
    target = torch.tensor([index[r["label"]] for r in train_rows], device=device)
    torch.manual_seed(seed)
    print(f"Encoding {len(train_rows)} labeled training crops on {device} with {BACKBONE}.", flush=True)
    backbone = make_backbone(True).to(device)
    features = embed(backbone, train_rows, batch_size, device)
    mean = features.mean(dim=0)
    scale = features.std(dim=0, unbiased=False).clamp_min(0.01)
    features = (features - mean) / scale
    head = nn.Linear(features.shape[1], len(labels)).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=learning_rate, weight_decay=0.01)
    class_weights = len(train_rows) / (len(labels) * torch.bincount(target, minlength=len(labels)).float())
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)
    for _ in range(epochs):
        optimizer.zero_grad()
        loss = loss_fn(head(features), target)
        if not torch.isfinite(loss):
            raise ValueError("Training produced a nonfinite loss.")
        loss.backward()
        optimizer.step()
    print(f"Evaluating the frozen run on {len(held_out)} validation crops.", flush=True)
    with torch.no_grad():
        embedding = embed(backbone, held_out, batch_size, device)
        probabilities = head.eval()((embedding - mean) / scale).softmax(dim=1).cpu()
    if not torch.isfinite(probabilities).all():
        raise ValueError("Validation produced nonfinite model scores.")
    truth = [index[r["label"]] for r in held_out]
    metrics, predicted = evaluate(held_out, truth, probabilities, labels)
    counts = Counter(r["label"] for r in train_rows)
    majority = max(labels, key=counts.get)
    majority_preds = torch.zeros(len(held_out), len(labels))
    majority_preds[:, index[majority]] = 1
    baseline, _ = evaluate(held_out, truth, majority_preds, labels)
    info = dict(backbone=BACKBONE, preprocessing=PREPROCESSING, manifest_sha256=manifest_hash,
                train_images=len(train_rows), validation_images=len(held_out),
                train_groups=len({r["group"] for r in train_rows}), validation_groups=len({r["group"] for r in held_out}),
                train_class_counts=dict(counts), device=str(device),
                accelerator=torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU",
                torch_version=str(torch.__version__), torchvision_version=str(torchvision.__version__),
                seed=seed, epochs=epochs, learning_rate=learning_rate, feature_batch_size=batch_size,
                last_training_loss=loss.item(), majority_baseline={"label": majority, "accuracy": baseline["accuracy"], "macro_f1": baseline["macro_f1"]})
    metrics.update(info)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent, prefix=".plankton-run-") as tmp:
        stage = Path(tmp) / "run"
        stage.mkdir()
        torch.save(dict(format_version=VERSION, labels=labels, preprocessing=PREPROCESSING,
                        manifest_sha256=manifest_hash, backbone=backbone.cpu().state_dict(), head=head.cpu().state_dict(),
                        mean=mean.cpu(), scale=scale.cpu()), stage / "model.pt")
        (stage / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        with (stage / "validation_predictions.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["roi_id", "group", "sha256", "label", "predicted_label", "top_softmax"])
            for n, row in enumerate(held_out):
                writer.writerow([row["roi_id"], row["group"], row["sha256"], row["label"], labels[predicted[n]], probabilities[n, predicted[n]].item()])
        os.rename(stage, output)
    return metrics


def load_predictor(checkpoint, device="auto"):
    """Load a trusted training checkpoint once and return a function of a crop path."""
    device = device_for(device)
    saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if saved["format_version"] != VERSION or saved["preprocessing"] != PREPROCESSING:
        raise ValueError("Unsupported checkpoint format or crop preprocessing.")
    backbone = make_backbone(False)
    backbone.load_state_dict(saved["backbone"])
    backbone = backbone.to(device)
    labels = saved["labels"]
    head = nn.Linear(saved["mean"].numel(), len(labels))
    head.load_state_dict(saved["head"])
    head = head.eval().to(device)
    mean, scale = saved["mean"].to(device), saved["scale"].to(device)
    manifest_hash = saved["manifest_sha256"]

    @torch.no_grad()
    def classify(image_file):
        raw = Path(image_file).read_bytes()
        with Image.open(io.BytesIO(raw)) as image:
            inputs = transform(image).unsqueeze(0).to(device)
        scores = head((backbone(inputs) - mean) / scale).softmax(dim=1)[0].cpu()
        if not torch.isfinite(scores).all():
            raise ValueError("The checkpoint produced nonfinite model scores.")
        top = scores.argsort(descending=True)[:3].tolist()
        return dict(status="unreviewed_closed_set_prediction", input_sha256=hashlib.sha256(raw).hexdigest(),
                    training_manifest_sha256=manifest_hash, predictions=[dict(label=labels[i], softmax=scores[i].item()) for i in top])
    return classify


def predict(checkpoint, image_file, device="auto"):
    """Classify one image; use load_predictor for repeated calls."""
    return load_predictor(checkpoint, device)(image_file)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    trainer = commands.add_parser("train", help="Train with manifest.csv and evaluate once on its native validation split.")
    trainer.add_argument("--dataset", required=True, type=Path)
    trainer.add_argument("--output", required=True, type=Path)
    trainer.add_argument("--seed", type=int, default=42)
    trainer.add_argument("--epochs", type=int, default=40)
    trainer.add_argument("--batch-size", type=int, default=24)
    trainer.add_argument("--learning-rate", type=float, default=0.01)
    predictor = commands.add_parser("predict", help="Load a saved checkpoint and classify one crop.")
    predictor.add_argument("--checkpoint", required=True, type=Path)
    predictor.add_argument("--image", required=True, type=Path)
    for command in (trainer, predictor):
        command.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "train":
        metrics = train(**args)
        print(json.dumps({k: metrics[k] for k in ["train_images", "validation_images", "accuracy", "macro_f1", "balanced_accuracy", "majority_baseline", "device"]}, indent=2))
    else:
        print(json.dumps(predict(args["checkpoint"], args["image"], args["device"]), indent=2))


if __name__ == "__main__":
    main()
