"""Run the PML IFCB CLIP-LoRA classifier on an image, with author-supplied prototypes.

On an existing PyTorch/torchvision installation:
    python -m pip install 'open-clip-torch==3.3.0' 'safetensors>=0.5,<1' 'Pillow>=11,<13'
    python pioneer_ifcb_prototypes.py --prepare
    python pioneer_ifcb_prototypes.py sample.png --mode image --top-k 5

In Jupyter, keep the model resident across queries:
    model = load_classifier(device="cuda")
    record = model.predict("sample.png", mode="text", top_k=5)

The neighboring JSON manifest pins the three public artifacts and their hashes.
The default model directory is ~/data/ocean-platform/models/pml-ifcb-clip-lora.
"""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen


DEFAULT_DIR = Path("~/data/ocean-platform/models/pml-ifcb-clip-lora")
MANIFEST = json.loads(Path(__file__).with_name("pioneer_ifcb_prototypes_manifest.json").read_text())


def verify(path, artifact):
    if not path.is_file() or path.stat().st_size != artifact["bytes"]:
        raise ValueError(f"Missing or incomplete {path.name}. Run this script with --prepare.")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != artifact["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {path.name}.")


def prepare(model_dir=DEFAULT_DIR):
    """Download each missing file from its pinned public source and verify existing files."""
    directory = Path(model_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    for artifact in MANIFEST["artifacts"]:
        path = directory / artifact["file"]
        if path.exists():
            verify(path, artifact)
            continue
        request = Request(artifact["url"] + "?download=true", headers={"User-Agent": "marinemodels IFCB"})
        with NamedTemporaryFile(dir=directory, delete=False) as temp:
            staged = Path(temp.name)
            try:
                with urlopen(request, timeout=90) as src:
                    received = 0
                    while chunk := src.read(1024 * 1024):
                        received += len(chunk)
                        if received > artifact["bytes"]:
                            raise ValueError(f"Unexpected download size for {path.name}")
                        temp.write(chunk)
                temp.flush()
                verify(staged, artifact)
                temp.close()
                staged.replace(path)
            finally:
                staged.unlink(missing_ok=True)
    return directory


def _merge_visual_adapters(visual, delta):
    """Fold the authors’ low-rank visual attention updates and final LayerNorm into CLIP."""
    import torch

    modules = dict(visual.named_modules())
    with torch.no_grad():
        for name, weights in delta["lora"].items():
            if not name.startswith("visual."):
                continue
            parent, projection = name.removeprefix("visual.").rsplit(".", 1)
            attention = modules[parent]
            update = (delta["lora_scale"] * weights["B"].float()) @ weights["A"].float()
            if projection == "proj":
                attention.out_proj.weight.add_(update)
            else:
                index = ("q_proj", "k_proj", "v_proj").index(projection)
                start = index * attention.embed_dim
                attention.in_proj_weight.narrow(0, start, attention.embed_dim).add_(update)
        for name, value in delta["ln"].items():
            if name.startswith("visual."):
                parent, parameter = name.removeprefix("visual.").rsplit(".", 1)
                getattr(modules[parent], parameter).copy_(value)


class PrototypeClassifier:
    def __init__(self, visual, transform, prototypes, labels, device):
        self.visual = visual
        self.transform = transform
        self.prototypes = prototypes
        self.labels = labels
        self.device = device

    def predict(self, image_path, mode="image", top_k=5):
        """Return one JSON-compatible record with similarities ranked within the fixed vocabulary."""
        import torch
        from PIL import Image
        from torch.nn.functional import normalize

        if mode not in self.prototypes:
            raise ValueError("mode must be 'image' or 'text'")
        if type(top_k) is not int or not 1 <= top_k <= len(self.labels):
            raise ValueError(f"top_k must be an integer from 1 to {len(self.labels)}")
        image_path = Path(image_path)
        with image_path.open("rb") as src:
            digest = hashlib.file_digest(src, "sha256").hexdigest()
            src.seek(0)
            with Image.open(src) as image:
                width, height = image.size
                tensor = self.transform(image.convert("RGB")).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            embedding = normalize(self.visual(tensor).float(), dim=-1)
            similarities = (embedding @ self.prototypes[mode].T)[0].cpu()
            indices = torch.argsort(similarities, descending=True, stable=True)[:top_k].tolist()
        return {
            "model": MANIFEST["name"],
            "model_revision": MANIFEST["model_revision"],
            "base_revision": MANIFEST["base_revision"],
            "input_name": image_path.name,
            "input_sha256": digest,
            "input_size_px": [width, height],
            "mode": mode,
            "prototype_source": "PML IFCB image class means" if mode == "image" else "Taxonomic lineage text",
            "candidate_count": len(self.labels),
            "score_type": "cosine_similarity",
            "device": str(self.device),
            "candidates": [
                {"rank": rank, "label": self.labels[i], "cosine_similarity": float(similarities[i])}
                for rank, i in enumerate(indices, 1)
            ],
        }


def load_classifier(model_dir=DEFAULT_DIR, device=None):
    """Load verified offline artifacts and return a reusable classifier. Device defaults to CUDA or CPU."""
    import open_clip
    import torch

    directory = Path(model_dir).expanduser()
    for artifact in MANIFEST["artifacts"]:
        verify(directory / artifact["file"], artifact)
    device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    delta = torch.load(directory / "clip_weights.pt", weights_only=True, map_location="cpu")
    ids = json.loads((directory / "id2label.json").read_text())
    labels = [ids[str(i)] for i in range(len(ids))]
    if labels != delta["class_names"] or len(labels) != 145:
        raise ValueError("Prototype labels do not match the published PML vocabulary.")
    if delta["backbone"] != {"model_name": "ViT-B-16", "pretrained": "openai"}:
        raise ValueError("Adapter and base configuration differ.")
    preprocess = MANIFEST["preprocessing"]
    model, _, transform = open_clip.create_model_and_transforms(
        "ViT-B-16", pretrained=str(directory / "open_clip_model.safetensors"),
        image_mean=preprocess["mean"], image_std=preprocess["std"],
        image_interpolation="bicubic", image_resize_mode="shortest",
    )
    visual = model.visual
    del model
    _merge_visual_adapters(visual, delta)
    banks = {}
    for mode in ("image", "text"):
        vectors = delta[f"{mode}_prototypes"].float()
        if vectors.shape != (145, 512) or not torch.allclose(vectors.norm(dim=-1), torch.ones(145), atol=1e-4):
            raise ValueError(f"Unexpected {mode} prototype dimensions or normalization.")
        banks[mode] = vectors.to(device)
    return PrototypeClassifier(visual.eval().to(device), transform, banks, labels, device)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path, nargs="?", help="A local single-specimen image.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--prepare", action="store_true", help="Download and verify missing public model artifacts.")
    parser.add_argument("--device", help="A PyTorch device, for example cuda or cpu.")
    parser.add_argument("--mode", choices=("image", "text"), default="image")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.model_dir)
    if args.image:
        classifier = load_classifier(args.model_dir, args.device)
        print(json.dumps(classifier.predict(args.image, args.mode, args.top_k), indent=2, allow_nan=False))
    elif not args.prepare:
        parser.error("Supply an image path or use --prepare.")


if __name__ == "__main__":
    main()
