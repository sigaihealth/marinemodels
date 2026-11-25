"""Run one blind inference method on a shared manifest of ROV images."""
import argparse
import base64
from collections import defaultdict
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import sys
import urllib.request

from PIL import Image

LABELS = ["Demersal", "Motile Epifauna", "Planktonic", "Sessile Epifauna"]
DETECTOR_SHA = "7c521bf59be99c1098b2bbc136011e59bc3fed08af69b99063a4264ca72fc427"
DETECTOR_REV = "94e22c9ad7da1f504004276cfc8461e21a73b644"
VL_REV = "f982a07559d4a2f6c8744d840bf6fccab30eea96"
MODEL = "Qwen3-VL-8B-Instruct"
PROMPT = (
    "Inspect this ordered set of underwater research images. In each image locate every "
    "clearly visible individual animal. Look for small animals. Use the tightest plausible "
    "box around each visible animal. Leave geological features, vegetation and equipment out. "
    "Use only these ecological groups: Demersal (bottom-associated fish and other swimmers), "
    "Motile Epifauna (animals moving on the seafloor), Planktonic (drifting in the water column), "
    "Sessile Epifauna (attached animals), or Unresolved (visible animal, group uncertain). "
    "For each image return its integer frame index and objects. Each object must have label "
    "and bbox_2d [left,top,right,bottom] in coordinates 0 to 1000 relative to that image. "
    "Do not invent occluded objects or a box spanning multiple animals. For an empty frame "
    'return an empty objects array. Return JSON only: {"frames":[{"frame":0,"objects":'
    '[{"label":"Demersal","bbox_2d":[12,124,41,180]}]}]}.'
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            digest.update(block)
    return digest.hexdigest()


def intersection_over_union(a, b):
    area = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return area / ((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - area) if area else 0.0


def adjacent(left, right, max_gap):
    a, b = left.get("timestamp_s"), right.get("timestamp_s")
    return (left.get("sequence_id") is not None
            and (left.get("dive_id"), left["sequence_id"]) == (right.get("dive_id"), right.get("sequence_id"))
            and isinstance(a, (float, int)) and isinstance(b, (float, int)) and 0 < b-a <= max_gap)


def link_tracks(frames, observations, method, max_gap):
    by_frame = defaultdict(list)
    for row in observations:
        by_frame[row["frame_id"]].append(row)
        row["track_id"] = None
    next_id = 0
    for i in range(1, len(frames)):
        previous, current = frames[i-1:i+1]
        if not (previous["inference_ok"] and current["inference_ok"] and adjacent(previous,current,max_gap)):
            continue
        left, right = by_frame[previous["frame_id"]], by_frame[current["frame_id"]]
        for row in left:
            if row["track_id"] is None:
                next_id += 1
                row["track_id"] = f"{method}-T{next_id:04d}"
        pairs = [(intersection_over_union(a["bbox_xyxy"], b["bbox_xyxy"]), j, k)
                 for j,a in enumerate(left) for k,b in enumerate(right) if a["label"] == b["label"]]
        used = set()
        for overlap,j,k in sorted(pairs,reverse=True):
            if overlap < .3:
                break
            if j not in used and right[k]["track_id"] is None:
                right[k]["track_id"] = left[j]["track_id"]
                used.add(j)
        for row in right:
            if row["track_id"] is None:
                next_id += 1
                row["track_id"] = f"{method}-T{next_id:04d}"


def vision_image(path, max_edge):
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((max_edge,max_edge), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def vl_call(group, paths, args):
    body = [{"type":"text","text":PROMPT}]
    for index, row in enumerate(group):
        body.append({"type":"text","text":f"Frame {index}:"})
        body.append({"type":"image_url","image_url":{"url":vision_image(paths[row["frame_id"]], args.vl_max_edge)}})
    payload = {"model":MODEL, "messages":[{"role":"user","content":body}],
               "temperature":0.0, "seed":7, "stream":False, "max_tokens":2300,
               "response_format":{"type":"json_object"}}
    headers = {"Content-Type":"application/json"}
    if args.key_file:
        headers["Authorization"] = "Bearer " + args.key_file.read_text().strip()
    req = urllib.request.Request(f"http://127.0.0.1:{args.port}/v1/chat/completions",
                                 data=json.dumps(payload).encode(),headers=headers)
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=240) as response:
        data=json.load(response)
    if data["model"] != MODEL:
        raise ValueError("Unexpected served model alias")
    choice=data["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ValueError("Incomplete output at token limit")
    result = json.loads(choice["message"]["content"])["frames"]
    if not isinstance(result,list) or len(result)!=len(group) or sorted(x["frame"] for x in result)!=list(range(len(group))):
        raise ValueError("Missing, repeated or unrecognized frame")
    outputs = {}
    for item in result:
        row=group[item["frame"]]
        found=[]
        if not isinstance(item["objects"],list):
            raise ValueError("Invalid objects list")
        for obj in item["objects"]:
            label=obj["label"]
            a=obj["bbox_2d"]
            if label not in [*LABELS, "Unresolved"] or not isinstance(a,list) or len(a)!=4:
                raise ValueError("Unrecognized label or missing box")
            if not all(isinstance(x,(int,float)) and math.isfinite(x) and 0<=x<=1000 for x in a) or a[0]>=a[2] or a[1]>=a[3]:
                raise ValueError("Invalid normalized coordinates")
            found.append({"label":label,"bbox_xyxy":[round(val*extent/1000,2)
                          for val,extent in zip(a,[row["width"],row["height"]]*2)]})
        outputs[row["frame_id"]]=found
    return outputs


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("method", choices=["ecotype","qwen"])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--weights", type=Path, default=Path("best.pt"))
    ap.add_argument("--device", default="0", help="Ultralytics device, GPU 0 by default")
    ap.add_argument("--port", type=int, default=18733)
    ap.add_argument("--key-file", type=Path)
    ap.add_argument("--vl-max-edge", type=int, default=1280)
    ap.add_argument("--vl-window", type=int, default=2, choices=[1,2,3])
    ap.add_argument("--max-gap", type=float, default=5.0)
    args=ap.parse_args()
    source=json.loads(args.manifest.read_text())
    frames=[]; paths={}
    for row in source["frames"]:
        frame={k:row.get(k) for k in ("frame_id","path","dive_id","timestamp_s","sequence_id")}
        fid=frame["frame_id"]; path=args.manifest.parent / frame["path"]
        if fid in paths or fid is None:
            raise ValueError("Each frame needs a unique frame_id")
        paths[fid]=path
        with Image.open(path) as image:
            frame["width"],frame["height"]=image.size
        frame.update(inference_ok=False, image_sha256=sha256(path))
        frames.append(frame)
    if not frames: raise ValueError("Empty frame manifest")
    method=args.method
    if method=="ecotype":
        import ultralytics
        if sha256(args.weights)!=DETECTOR_SHA: raise ValueError("Unexpected detector weight SHA-256")
        net=ultralytics.YOLO(str(args.weights))
        if [net.names[i] for i in range(len(net.names))] != LABELS: raise ValueError("Model vocabulary mismatch")
        metadata={"model":"OceanCV/OOI_Ecotype", "revision":DETECTOR_REV, "weight_sha256":DETECTOR_SHA,
                  "ultralytics_version":ultralytics.__version__, "imgsz":1024, "confidence_threshold":.25,
                  "nms_iou":.70, "device":args.device}
    else:
        metadata={"model":MODEL,"gguf_repo":"Qwen/Qwen3-VL-8B-Instruct-GGUF","gguf_revision":VL_REV,
                  "quantization":"Q4_K_M","projector":"F16","image_long_edge":args.vl_max_edge,
                  "max_frames_per_request":args.vl_window, "prompt":PROMPT, "temperature":0., "seed":7}
    metadata.update(tracking="Greedy one-to-one class-consistent neighboring-frame IoU >= 0.30; heuristic, unaudited.",
                    max_tracking_gap_seconds=args.max_gap,manifest_sha256=sha256(args.manifest),box_space="source image pixels; [left,top,right,bottom]")
    observations=[]
    def save():
        link_tracks(frames,observations,method,args.max_gap)
        temp=args.out.with_suffix(args.out.suffix+".tmp")
        temp.write_text(json.dumps({"method":method,"frames":frames,"sightings":observations,"metadata":metadata},indent=2,allow_nan=False)+"\n")
        temp.replace(args.out)
    def record(row,objects,n,err=None):
        row["inference_ok"]=err is None
        row["window_frames"]=n
        if err is not None:
            row["error"]=str(err)[:400]
        for i,det in enumerate(objects):
            observations.append({**det,"method":method,"frame_id":row["frame_id"],
                                 "sighting_id":f"{method}:{row['frame_id']}:{i+1}"})
        print(f"{method} {row['frame_id']}: {len(objects)} sightings" if err is None else f"{method} {row['frame_id']}: ERROR {err}",flush=True)
    i=0
    args.out.parent.mkdir(parents=True,exist_ok=True)
    while i<len(frames):
        row=frames[i]
        if method=="ecotype":
            try:
                pred=net.predict(source=str(paths[row["frame_id"]]), device=args.device, imgsz=1024, conf=.25, iou=.70, verbose=False)[0]
                objects=[{"label":net.names[int(k)],"bbox_xyxy":[round(x,2) for x in box], "score":round(score,6)}
                         for box,k,score in zip(pred.boxes.xyxy.tolist(),pred.boxes.cls.tolist(),pred.boxes.conf.tolist())]
                record(row,objects,1)
            except Exception as exc:
                record(row,[],1,exc)
            i+=1
        else:
            group=[row]; i+=1
            while i<len(frames) and len(group)<args.vl_window and adjacent(group[-1],frames[i],args.max_gap):
                group.append(frames[i]); i+=1
            try:
                result=vl_call(group,paths,args)
                for f in group: record(f,result[f["frame_id"]],len(group))
            except Exception as first:
                print(f"Window retry, individual frames: {first}",flush=True)
                for f in group:
                    try: record(f,vl_call([f],paths,args)[f["frame_id"]],1)
                    except Exception as second: record(f,[],1,second)
        save()
    return 0 if all(s["inference_ok"] for s in frames) else 1

if __name__=="__main__": sys.exit(main())
