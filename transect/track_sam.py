"""Propagate first-frame Ecotype boxes through one clip with Meta SAM 2.1 Hiera Small."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import torch
from PIL import Image
from sam2.build_sam import build_sam2_video_predictor

from run_models import sha256

DIGEST = "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--detector", type=Path, required=True)
    ap.add_argument("--sequence", required=True)
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()
    if sha256(args.weights) != DIGEST:
        raise ValueError("Unexpected SAM 2.1 checkpoint SHA-256")
    manifest = json.loads(args.manifest.read_text())
    detector = json.loads(args.detector.read_text())
    if detector["metadata"]["manifest_sha256"] != sha256(args.manifest):
        raise ValueError("Detector and tracker must use identical input manifest")
    rows = sorted((f for f in manifest["frames"] if f["sequence_id"] == args.sequence),
                  key=lambda f: f["timestamp_s"])
    if len(rows) < 2 or any(b["timestamp_s"] <= a["timestamp_s"] for a,b in zip(rows, rows[1:])):
        raise ValueError("Tracking requires an ordered sample with distinct times")
    seeds = [s for s in detector["sightings"] if s["frame_id"] == rows[0]["frame_id"]]
    if not seeds:
        raise ValueError("No Ecotype first-frame box seeds")
    if args.device == "cpu": torch.set_num_threads(6)
    net = build_sam2_video_predictor("configs/sam2.1/sam2.1_hiera_s.yaml", str(args.weights),
                                     device=args.device, apply_postprocessing=False)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    mask_dir = args.out.parent / (args.out.stem + "-masks")
    mask_dir.mkdir(exist_ok=True)
    detections = []
    with torch.inference_mode(), TemporaryDirectory() as td:
        frame_dir = Path(td)
        for i, f in enumerate(rows):
            (frame_dir / f"{i:06d}.jpg").symlink_to((args.manifest.parent / f["path"]).resolve())
        state = net.init_state(video_path=td, offload_video_to_cpu=True)
        for i, seed in enumerate(seeds):
            net.add_new_points_or_box(inference_state=state, frame_idx=0, obj_id=i+1,
                                      box=np.asarray(seed["bbox_xyxy"], np.float32))
        for frame_idx, ids, logits in net.propagate_in_video(state, start_frame_idx=0):
            frame = rows[frame_idx]
            print(f"Tracked {len(ids)} seeded objects on {frame['frame_id']}",flush=True)
            for ident, prediction in zip(ids, logits):
                seed = seeds[ident-1]
                mask = (prediction.squeeze(0) > 0.0).cpu().numpy()
                if not mask.any(): continue
                ys, xs = np.where(mask)
                bbox = [int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1]
                mask_path = mask_dir / f"{frame_idx:04d}-{ident:02d}.png"
                Image.fromarray(mask).save(mask_path, optimize=True)
                detections.append({"method":"sam2", "frame_id":frame["frame_id"], "sighting_id":f"sam2:{frame['frame_id']}:{ident}",
                                   "track_id":f"sam2-T{ident:04d}", "label":seed["label"], "bbox_xyxy":bbox,
                                   "mask_path":str(mask_path.relative_to(args.out.parent)),
                                   "mask_area_pixels":int(mask.sum()), "seed_sighting_id":seed["sighting_id"]})
    meta = {"model":"facebook/sam2.1-hiera-small", "model_revision":"ee5bba1d82bb8749febdf90f45e84b687142ba03",
            "source_revision":"2b90b9f5ceec907a1c18123530e92e794ad901a4","weight_sha256":DIGEST,
            "sequence_id":args.sequence, "device":args.device, "seed_frame_id":rows[0]["frame_id"],
            "seed_sightings":[s["sighting_id"] for s in seeds], "mask_threshold_logit":0.0,
            "manifest_sha256":sha256(args.manifest),"detector_sha256":sha256(args.detector)}
    report = {"method":"sam2","metadata":meta,"frames":[{"frame_id":r["frame_id"],"inference_ok":True} for r in rows],
              "sightings":detections}
    temp = args.out.with_suffix(".tmp")
    temp.write_text(json.dumps(report, indent=2)+"\n"); temp.replace(args.out)


if __name__ == "__main__": main()
