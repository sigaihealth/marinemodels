"""Run one pinned detector on a label-blind ordered manifest of ROV frames."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import tempfile
import time
import urllib.request

MODELS = {
    "ecotype": {
        "repo": "OceanCV/OOI_Ecotype",
        "revision": "94e22c9ad7da1f504004276cfc8461e21a73b644",
        "filename": "best.pt",
        "sha256": "7c521bf59be99c1098b2bbc136011e59bc3fed08af69b99063a4264ca72fc427",
        "bytes": 136762931,
        "license": "MIT (checkpoint repository)",
        "classes": ["Demersal", "Motile Epifauna", "Planktonic", "Sessile Epifauna"],
    },
    "megalodon": {
        "repo": "FathomNet/megalodon-2024-yolov11",
        "revision": "403704d2d4dba9903ffbdd215648c3fc8ae6f377",
        "filename": "mbari-megalodon-yolo11x.pt",
        "sha256": "27ab91d07fa61d6ae1af9a2c18e29d6b89044254aec7d38b1a4331cbb9b3a450",
        "bytes": 114390802,
        "license": "CC BY 4.0",
        "classes": ["item"],
    },
}
PARAMS = dict(imgsz=1024, conf=0.25, iou=0.70, max_det=300, rect=True,
              agnostic_nms=False, half=False, augment=False)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verified_weights(path, spec, fetch):
    if not path.is_file() and fetch:
        url = f"https://huggingface.co/{spec['repo']}/resolve/{spec['revision']}/{spec['filename']}"
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
            incoming = Path(tmp) / "weights.pt"
            with urllib.request.urlopen(url, timeout=90) as remote, incoming.open("wb") as out:
                shutil.copyfileobj(remote, out, length=2**20)
            if incoming.stat().st_size != spec["bytes"] or digest(incoming) != spec["sha256"]:
                raise ValueError("Downloaded checkpoint failed byte-size or SHA-256 verification")
            incoming.replace(path)
    if path.stat().st_size != spec["bytes"] or digest(path) != spec["sha256"]:
        raise ValueError(f"Checkpoint failed verification: {path.name}")


def read_frames(manifest):
    raw = json.loads(manifest.read_text())
    frames = []
    image_paths = []
    seen = set()
    for row in raw["frames"]:
        frame = {k: row[k] for k in ("frame_id", "frame_index", "timestamp_s", "width", "height", "path", "sha256")}
        if frame["frame_id"] in seen:
            raise ValueError(f"Duplicate frame {frame['frame_id']}")
        seen.add(frame["frame_id"])
        path = (manifest.parent / frame["path"]).resolve()
        if digest(path) != frame["sha256"]:
            raise ValueError(f"Image SHA-256 mismatch: {frame['frame_id']}")
        frame["inference_ok"] = False
        frames.append(frame)
        image_paths.append(str(path))
    if not frames:
        raise ValueError("Empty input manifest")
    return frames, image_paths


def run(args):
    import torch
    import ultralytics

    spec = MODELS[args.method]
    verified_weights(args.weights, spec, args.fetch)
    frames, image_paths = read_frames(args.manifest)
    model = ultralytics.YOLO(str(args.weights))
    labels = [model.names[k] for k in sorted(model.names)]
    if labels != spec["classes"]:
        raise ValueError(f"Unexpected checkpoint classes: {labels}")
    if args.device.isdecimal() and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")

    start = time.monotonic()
    sightings = []
    for offset in range(0, len(frames), args.batch):
        batch = image_paths[offset:offset + args.batch]
        predictions = model.predict(source=batch, batch=args.batch, device=args.device,
                                    verbose=False, save=False, **PARAMS)
        if len(predictions) != len(batch):
            raise ValueError("Detector returned wrong batch length")
        for j, pred in enumerate(predictions):
            idx = offset + j
            frame = frames[idx]
            if (Path(pred.path).name != Path(batch[j]).name or
                    tuple(pred.orig_shape) != (frame["height"], frame["width"])):
                raise ValueError(f"Frame geometry or image order mismatch on {frame['frame_id']}")
            values = pred.boxes.data.detach().cpu().tolist()
            for n, (x1, y1, x2, y2, conf, cls) in enumerate(values, 1):
                if not (0 <= x1 < x2 <= frame["width"] and 0 <= y1 < y2 <= frame["height"] and 0 <= conf <= 1):
                    raise ValueError(f"Invalid model box on {frame['frame_id']}")
                sightings.append({"frame_id":frame["frame_id"], "sighting_id":f"{args.method}:{frame['frame_id']}:{n}",
                                  "label":labels[int(cls)], "score":conf, "bbox_xyxy":[x1, y1, x2, y2]})
            frame.update(inference_ok=True, detection_count=len(values), at_cap=len(values) >= PARAMS["max_det"])
        if offset == 0 or (offset // args.batch + 1) % 10 == 0 or offset + len(batch) == len(frames):
            print(f"{args.method}: {offset + len(batch)}/{len(frames)} frames", flush=True)
    metadata = dict(checkpoint=spec, parameters=PARAMS, batch=args.batch, device=args.device,
                    gpu=torch.cuda.get_device_name(int(args.device)) if args.device.isdecimal() else None,
                    torch=str(torch.__version__), ultralytics=ultralytics.__version__, python=platform.python_version(),
                    cuda=torch.version.cuda, duration_s=round(time.monotonic()-start, 3),
                    max_allocated_mib=round(torch.cuda.max_memory_allocated(int(args.device))/2**20, 2) if args.device.isdecimal() else None,
                    blind_manifest_sha256=digest(args.manifest), frame_count=len(frames), count_at_cap=sum(f["at_cap"] for f in frames))
    output = dict(method=args.method, metadata=metadata, frames=frames, sightings=sightings)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=args.out.parent, mode="w", delete=False) as tmp:
        temp_path=Path(tmp.name)
        try:
            json.dump(output, tmp, separators=(",",":"), allow_nan=False)
            tmp.write("\n")
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
    temp_path.replace(args.out)
    print(f"Saved {args.out}: {len(sightings)} boxes; {metadata['count_at_cap']} capped frames", flush=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("method", choices=MODELS)
    cli.add_argument("--manifest", required=True, type=Path)
    cli.add_argument("--weights",required=True,type=Path)
    cli.add_argument("--fetch",action="store_true",help="Download absent weights from the pinned publisher before verification")
    cli.add_argument("--out",required=True,type=Path)
    cli.add_argument("--device",default="0",help="CUDA device index, or cpu")
    cli.add_argument("--batch",type=int,default=4)
    args=cli.parse_args()
    if args.batch<1:
        cli.error("--batch must be positive")
    run(args)
