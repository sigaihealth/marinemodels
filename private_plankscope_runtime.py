"""Load an operator-installed PlankScope crop classifier in a private Python environment.

Install PyTorch, TorchVision, Pillow and NumPy in the environment. Place the two
authorized artifacts, best.pth and classes.npy, in the private model directory.
This module reads local files and never downloads a model. Importing it does not
load PyTorch or either artifact.

    classify = load_classifier(model_dir, device="auto")
    result = classify("microscope-crop.png")
    python private_plankscope_runtime.py --model-dir PATH --check
"""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path


CHECKPOINT_SHA256 = "9a92f08b9c8c9939bd94b4be332b8c280cb84a281229fc38a4871dc0791da511"
LABELS_SHA256 = "9990f9d11161762ba27a6a30a86aebe1076be680431ca67c36184878fa66813f"
COUNT = 101
DEFAULT_DIR = Path(os.environ.get("OCEAN_WORKSPACE_ROOT", "~/data/ocean-platform")).expanduser() / "models/private-plankscope-v1"


def available(model_dir=DEFAULT_DIR):
    """Return quickly when the private bundle is absent. Integrity is verified on load."""
    directory = Path(model_dir).expanduser()
    return all((directory / name).is_file() for name in ("best.pth", "classes.npy"))


def _verified_file(directory, name, size, digest):
    path = directory / name
    if not path.is_file():
        raise FileNotFoundError(f"Install the authorized {name} in {directory} before using this model.")
    with path.open("rb") as stream:
        data = stream.read(size + 1)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"Private model integrity check failed for {name}.")
    return io.BytesIO(data)


def load_classifier(model_dir=DEFAULT_DIR, device="auto"):
    """Verify and load the local release. Return a callable accepting one opaque PNG crop."""
    import numpy as np
    from PIL import Image
    import torch
    from torch import nn
    from torchvision.models import resnet50
    from torchvision.transforms import functional as transforms

    directory = Path(model_dir).expanduser()
    with _verified_file(directory, "classes.npy", 11844, LABELS_SHA256) as stream:
        array = np.load(stream, allow_pickle=False)
    if array.dtype.kind != "U" or array.shape != (COUNT,):
        raise ValueError("The private label map must contain 101 ordered Unicode strings.")
    labels = array.tolist()
    if len(set(labels)) != COUNT or any(not label.strip() for label in labels):
        raise ValueError("The private label map contains repeated or empty class names.")
    with _verified_file(directory, "best.pth", 95183727, CHECKPOINT_SHA256) as stream:
        state = torch.load(stream, weights_only=True, map_location="cpu")
    if device not in ("cpu", "cuda", "auto"):
        raise ValueError("Choose cpu, cuda or auto.")
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA is unavailable in this PyTorch environment.")
    if device == "cpu":
        torch.set_num_threads(min(4, torch.get_num_threads()))
    model = resnet50(weights=None)
    model.fc = nn.Sequential(nn.Linear(model.fc.in_features, COUNT))
    model.load_state_dict(state, strict=True)
    del state
    model.requires_grad_(False).eval().to(device)

    @torch.inference_mode()
    def classify(image_path):
        path = Path(image_path)
        with path.open("rb") as stream:
            data = stream.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise ValueError("Choose a single PNG microscope crop of up to 16 MiB.")
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "PNG" or image.is_animated or image.mode not in ("L", "RGB") or "transparency" in image.info:
                raise ValueError("Choose an opaque 8-bit grayscale or RGB PNG crop.")
            if image.width * image.height > 4_000_000:
                raise ValueError("Choose a crop of at most four megapixels.")
            # Preserve the byte order produced by the original OpenCV color decoder.
            # For the supported opaque PNG inputs, RGB -> BGR gives those three bands.
            red, green, blue = image.convert("RGB").split()
            frame = Image.merge("RGB", (blue, green, red))
        resized = frame.resize((512, 512), resample=Image.Resampling.BICUBIC)
        crop = transforms.center_crop(resized, [448, 448])
        tensor = transforms.normalize(transforms.to_tensor(crop), [0.5] * 3, [0.5] * 3)
        logits = model(tensor.unsqueeze(0).to(device))
        if logits.shape != (1, COUNT) or not torch.isfinite(logits).all():
            raise ValueError("The private classifier returned unexpected scores.")
        scores = logits[0].softmax(dim=0).cpu()
        indices = scores.argsort(descending=True)[:3].tolist()
        return dict(model="PlankScope ResNet-50", model_revision="private-plankscope-v1",
                    status="provisional_model_prediction_unreviewed", candidate_count=COUNT,
                    score_type="softmax", device=device, input_sha256=hashlib.sha256(data).hexdigest(),
                    checkpoint_sha256=CHECKPOINT_SHA256, labels_sha256=LABELS_SHA256,
                    candidates=[dict(index=i, label=labels[i], softmax=scores[i].item()) for i in indices])
    return classify


def health_check(model_dir=DEFAULT_DIR, device="auto"):
    """Verify the private bundle and execute an unnamed test crop without exposing labels."""
    from PIL import Image
    from tempfile import TemporaryDirectory

    classifier = load_classifier(model_dir, device=device)
    with TemporaryDirectory() as temp:
        sample = Path(temp) / "health-check.png"
        Image.new("L", (32, 32), 128).save(sample)
        result = classifier(sample)
    return dict(status="ready", candidate_count=result["candidate_count"], device=result["device"],
                checkpoint_sha256=CHECKPOINT_SHA256, labels_sha256=LABELS_SHA256)


def main():
    parser = argparse.ArgumentParser(description="Run an authorized, locally installed PlankScope crop model.")
    parser.add_argument("--model-dir", default=DEFAULT_DIR, type=Path)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--check", action="store_true", help="Verify the bundle and run a local health check.")
    choice.add_argument("--image", type=Path, help="Classify one local, opaque grayscale or RGB PNG crop.")
    args = parser.parse_args()
    if args.check:
        result = health_check(args.model_dir, args.device)
    else:
        result = load_classifier(args.model_dir, args.device)(args.image)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
