"""Export a personal ten-class IFCB checkpoint for local ONNX Runtime inference.

Requires the training environment and onnx>=1.19,<2. No pretrained model is downloaded.
    python export_plankton_mobilenet.py --checkpoint RUN/model.pt --output RUN/mobilenet-pilot.onnx

The ONNX embeds the checkpoint fingerprint, training manifest fingerprint and ordered labels.
The printed ONNX SHA-256 can be checked by the browser. Keep the file in personal storage.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import onnx
import torch
from torch import nn

from plankton_workspace import PREPROCESSING, VERSION, make_backbone


class MobileNetPilot(nn.Module):
    def __init__(self, checkpoint):
        super().__init__()
        self.encoder = make_backbone(False)
        self.encoder.load_state_dict(checkpoint["backbone"])
        self.register_buffer("mean", checkpoint["mean"])
        self.register_buffer("scale", checkpoint["scale"])
        self.head = nn.Linear(self.mean.numel(), len(checkpoint["labels"]))
        self.head.load_state_dict(checkpoint["head"])

    def forward(self, pixels):
        features = (self.encoder(pixels) - self.mean) / self.scale
        return self.head(features)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def export(checkpoint, output):
    checkpoint, output = Path(checkpoint), Path(output)
    if output.suffix.lower() != ".onnx" or checkpoint.resolve() == output.resolve():
        raise ValueError("Choose a distinct .onnx output file.")
    with checkpoint.open("rb") as stream:
        checkpoint_sha = hashlib.file_digest(stream, "sha256").hexdigest()
        stream.seek(0)
        saved = torch.load(stream, map_location="cpu", weights_only=True)
    if saved["format_version"] != VERSION or saved["preprocessing"] != PREPROCESSING:
        raise ValueError("Unsupported checkpoint format or preprocessing.")
    labels = saved["labels"]
    if len(labels) != 10 or labels != sorted(set(labels)) or any(not isinstance(s, str) for s in labels):
        raise ValueError("This browser export requires ten distinct ordered labels.")
    model = MobileNetPilot(saved).eval()
    if not torch.all(torch.isfinite(model.scale) & (model.scale > 0)):
        raise ValueError("The checkpoint contains an invalid feature normalization scale.")
    metadata = {
        "format": "sigai-ifcb-mobilenet-onnx-v1",
        "checkpoint_sha256": checkpoint_sha,
        "manifest_sha256": saved["manifest_sha256"],
        "labels": labels,
        "preprocessing": PREPROCESSING,
        "outputs": "unnormalized_logits",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=output.parent, suffix=".onnx", delete=False) as temp:
        stage = Path(temp.name)
    try:
        with torch.inference_mode():
            torch.onnx.export(model, (torch.zeros(1, 3, 224, 224),), str(stage),
                              input_names=["pixels"], output_names=["logits"],
                              opset_version=17, dynamo=False, external_data=False)
        portable = onnx.load(stage)
        entry = portable.metadata_props.add()
        entry.key = "sigai_plankton"
        entry.value = json.dumps(metadata, separators=(",", ":"))
        onnx.checker.check_model(portable, full_check=True)
        onnx.save(portable, stage)
        digest = sha256(stage)
        os.replace(stage, output)
    finally:
        stage.unlink(missing_ok=True)
    return {"file": output.name, "bytes": output.stat().st_size, "onnx_sha256": digest, **metadata}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.checkpoint, args.output), indent=2))


if __name__ == "__main__":
    main()
