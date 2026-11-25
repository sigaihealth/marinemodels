"""Run one IFCB crop through the selected local model in an authenticated Jupyter kernel."""

import csv
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from html import escape
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote
from uuid import uuid4

from PIL import Image

REPO = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("OCEAN_WORKSPACE_ROOT", Path.home() / "data/ocean-platform")).expanduser()
PIONEER = ("D20260201T002546_IFCB200_00139", "D20260201T152545_IFCB200_04627")
MODELS = {
    "mobilenet": "MobileNetV3 · 10 WHOI pilot categories",
    "whoi": "WHOI NES v2.4 · 155 categories",
    "pml-image": "PML CLIP · 145 image prototypes",
    "pml-text": "PML CLIP · 145 taxonomic text prototypes",
}
MAX_BYTES = 16 * 1024 * 1024


def read_png(data):
    if len(data) > MAX_BYTES:
        raise ValueError("Choose a PNG of at most 16 MiB.")
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "PNG" or image.width * image.height > 4_000_000:
            raise ValueError("Choose a single PNG crop of at most four megapixels.")
        if image.is_animated or image.mode not in ("L", "RGB"):
            raise ValueError("Use an opaque 8-bit grayscale or RGB PNG.")
        image.load()
        return image.size


@lru_cache(maxsize=6)
def runner(family, root):
    models = root / "models"
    if family == "mobilenet":
        from plankton_workspace import device_for, load_predictor

        device = str(device_for("auto"))
        checkpoint = models / "mobilenet-ifcb-pilot/model.pt"
        with checkpoint.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        predict = load_predictor(checkpoint, device)
        def mobilenet(path, mode):
            record = predict(path)
            record["candidates"] = record.pop("predictions")
            return dict(record, model=MODELS["mobilenet"], score_type="softmax", candidate_count=10,
                        checkpoint_sha256=digest, device=device)
        return mobilenet
    if family == "pml":
        from pioneer_ifcb_prototypes import load_classifier

        classifier = load_classifier(models / "pml-ifcb-clip-lora")
        return lambda path, mode: classifier.predict(path, mode=mode, top_k=3)

    import numpy as np
    import onnxruntime as ort
    from pioneer_classify_gallery import (LABELS_SHA256, MODEL_FILE, MODEL_SHA256, REVISION,
                                           verified_bytes, whoi_input)

    directory = models / "whoi-nes-v2.4"
    labels = json.loads(verified_bytes(directory / "labels.json", LABELS_SHA256))
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 4
    session = ort.InferenceSession(verified_bytes(directory / MODEL_FILE, MODEL_SHA256), opts,
                                   providers=["CPUExecutionProvider"])
    def whoi(path, mode):
        with Image.open(path) as image:
            logits = session.run(["output"], {"input": whoi_input(image)[None]})[0][0]
        if logits.shape != (len(labels),) or not np.isfinite(logits).all():
            raise ValueError("WHOI returned unexpected scores.")
        exp = np.exp(logits.astype(np.float64) - logits.max())
        scores = exp / exp.sum()
        return dict(model=MODELS["whoi"], model_revision=REVISION, checkpoint_sha256=MODEL_SHA256,
                    score_type="softmax", candidate_count=len(labels), device="cpu",
                    candidates=[dict(label=labels[str(i)], softmax=float(scores[i]))
                                for i in np.argsort(-scores)[:3]])
    return whoi


def run_crop(method, path, *, source, root=ROOT, persist=True):
    if method not in MODELS:
        raise ValueError("Select an available model.")
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Choose a PNG of at most 16 MiB.")
    data = path.read_bytes()
    size = read_png(data)
    family, _, mode = method.partition("-")
    result = runner(family, root)(path, mode)
    result.update(method=method, status="provisional_model_prediction_unreviewed",
                  input_sha256=hashlib.sha256(data).hexdigest(), input_size_px=list(size),
                  input_source=source, created_utc=datetime.now(timezone.utc).isoformat())
    destination = None
    if persist:
        directory = root / "results"
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{method}-{uuid4().hex}.json"
        with destination.open("x", encoding="utf-8") as file:
            json.dump(result, file, indent=2, allow_nan=False)
            file.write("\n")
    return result, destination


def show_workspace(root=ROOT):
    import ipywidgets as widgets
    from IPython.display import HTML, display

    sources = {}
    for i, roi in enumerate(PIONEER):
        sources[f"Pioneer · {'00:25 UTC · ROI 139' if i == 0 else '15:25 UTC · ROI 4627'}"] = (
            REPO / "site/assets" / f"{roi}.png", f"https://ifcb-data.oceanobservatories.org/data/{roi}.png")
    dataset = root / "datasets/whoi-nes-2022/pilot"
    manifest = dataset / "manifest.csv"
    if manifest.is_file():
        with manifest.open() as file:
            for row in csv.DictReader(file):
                if row["split"] == "validation":
                    sources.setdefault(f"WHOI validation · {row['label']}",
                                       (dataset / row["path"], f"WHOI NES 2022 · {row['roi_id']}"))
    style = {"description_width": "60px"}
    layout = widgets.Layout(width="auto")
    model = widgets.Dropdown(description="Model", options=[(v, k) for k, v in MODELS.items()],
                             style=style, layout=layout)
    source = widgets.Dropdown(description="Image", options=[*sources, "My uploaded PNG"], style=style, layout=layout)
    upload = widgets.FileUpload(accept=".png,image/png", multiple=False, description="Choose PNG")
    run = widgets.Button(description="Classify crop", button_style="primary", icon="play")
    output = widgets.Output()

    def choose_file(change):
        if change["new"]:
            source.value = "My uploaded PNG"
    upload.observe(choose_file, names="value")

    def click(_):
        output.clear_output(wait=True)
        run.disabled = True
        with output, TemporaryDirectory() as temporary:
            try:
                if source.value == "My uploaded PNG":
                    if not upload.value:
                        raise ValueError("Choose a PNG first.")
                    item = upload.value[0]
                    if len(item["content"]) > MAX_BYTES:
                        raise ValueError("Choose a PNG of at most 16 MiB.")
                    path = Path(temporary) / "upload.png"
                    path.write_bytes(item["content"])
                    origin = "User upload"
                else:
                    path, origin = sources[source.value]
                result, destination = run_crop(model.value, path, source=origin, root=root)
                display(widgets.Image(value=path.read_bytes(), format="png", layout=widgets.Layout(max_width="280px", max_height="160px")))
                score = result["score_type"]
                rows = "".join(f"<tr><td>{escape(r['label'])}</td><td>{r[score]:.4f}</td></tr>"
                               for r in result["candidates"])
                display(HTML(f"<table><caption>Top suggestions · {escape(result['device'])}</caption>"
                             f"<thead><tr><th>Category</th><th>{escape(score.replace('_', ' '))}</th></tr></thead>"
                             f"<tbody>{rows}</tbody></table>"))
                print(f"Provisional identification. Saved {destination}")
                prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX")
                if prefix and destination.is_relative_to(Path.home()):
                    url = prefix.rstrip("/") + "/files/" + quote(destination.relative_to(Path.home()).as_posix())
                    display(HTML(f'<a href="{escape(url, quote=True)}" download>Download result JSON</a>'))
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                print(f"Could not classify this crop. {exc}")
            finally:
                run.disabled = False

    run.on_click(click)
    controls = [model, source, widgets.HBox([upload, run]), output]
    receipt = root / "models/mobilenet-ifcb-pilot/onnx-export.json"
    prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX")
    if prefix and receipt.is_file() and receipt.is_relative_to(Path.home()):
        metadata = json.loads(receipt.read_text())
        portable = receipt.with_name("mobilenet-pilot.onnx")
        digest = metadata["onnx_sha256"]
        if portable.is_file() and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest):
            url = prefix.rstrip("/") + "/files/" + quote(portable.relative_to(Path.home()).as_posix())
            controls.append(widgets.HTML(
                f'<p>To use this trained MobileNet on your own device, '
                f'<a href="{escape(url, quote=True)}?download=1" download>download your ONNX model</a>, then '
                f'<a href="https://ocean.sig.ai/try-mobilenet.html#sha256={digest}" target="_blank" '
                f'rel="noopener">open the local browser runner</a>.</p>'))
    return widgets.VBox(controls)
