"""Blind Qwen technical retry with mandatory output slots fixed to the input frame order."""
import argparse
import json
import math
from pathlib import Path
import sys
import urllib.request

from PIL import Image
from run_models import MODEL, LABELS, VL_REV, adjacent, link_tracks, sha256, vision_image


GROUPS = LABELS + ["Unresolved"]
INSTRUCTION = (
    "Inspect the underwater research images in order. For each clearly visible individual animal, "
    "place a tight bounding box around the animal. Look for small animals. Omit geological features, "
    "equipment and vegetation. Omit invisible or fully occluded individuals. Each box represents "
    "one individual. Use Demersal for bottom-associated fish and other swimmers, Motile Epifauna "
    "for animals moving on the seafloor, Planktonic for drifting animals in the water column, "
    "Sessile Epifauna for attached animals, and Unresolved for a visible animal with an uncertain "
    "group. Report [left,top,right,bottom] relative to its own image on a 0 to 1000 grid. "
    "The response has a named slot per input image. Use [] for an image without visible animals."
)


def schema(slots, cap):
    coord = {"type":"integer","minimum":0,"maximum":1000}
    box = {"type":"array","items":coord,"minItems":4,"maxItems":4}
    det = {"type":"object","properties":{"label":{"type":"string","enum":GROUPS},"bbox_2d":box},
           "required":["label","bbox_2d"],"additionalProperties":False}
    return {"type":"object","properties":{s:{"type":"array","items":det,"maxItems":cap} for s in slots},
            "required":slots,"additionalProperties":False}


def parse(raw, group, cap):
    slots = [f"frame_{i}" for i in range(len(group))]
    if set(raw)!=set(slots): raise ValueError("Response slots do not match input positions")
    observations=[]
    for slot, frame in zip(slots,group):
        objects = raw[slot]
        if not isinstance(objects,list) or len(objects) >= cap:
            raise ValueError("Incomplete result at object cap or malformed slot")
        detections=[]
        for obj in objects:
            label, box = obj["label"], obj["bbox_2d"]
            if label not in GROUPS or len(box)!=4 or not all(type(x) is int and 0 <= x <= 1000 for x in box):
                raise ValueError("Invalid class or coordinate range")
            if box[0]>=box[2] or box[1]>=box[3]:
                raise ValueError("Degenerate normalized box")
            coords=[round(c*e/1000,2) for c,e in zip(box,[frame["width"],frame["height"]]*2)]
            detections.append({"frame_id":frame["frame_id"],"method":"qwen","label":label,"bbox_xyxy":coords,
                               "sighting_id":f"qwen:{frame['frame_id']}:{len(detections)+1}"})
        observations += detections
    return observations


def get_boxes(group, paths, key, port, cap):
    slots = [f"frame_{i}" for i in range(len(group))]
    content = [{"type":"text","text":INSTRUCTION}]
    for slot, row in zip(slots,group):
        content += [{"type":"text","text":slot},
                    {"type":"image_url","image_url":{"url":vision_image(paths[row["frame_id"]],1280)}}]
    body = {"model":MODEL,"messages":[{"role":"user","content":content}],"temperature":0,"seed":7,
            "stream":False,"max_tokens":3400,
            "response_format":{"type":"json_schema","json_schema":{"name":"transect_sightings",
                               "strict":True,"schema":schema(slots,cap)}}}
    req=urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",data=json.dumps(body).encode(),
                               headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=300) as response:
        data=json.load(response)
    choice=data["choices"][0]
    if data.get("model")!=MODEL or choice.get("finish_reason")!="stop":
        raise ValueError("Incomplete completion or wrong served model")
    raw=json.loads(choice["message"]["content"])
    return parse(raw,group,cap)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--key-file",type=Path,required=True)
    ap.add_argument("--port",type=int,default=18733)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args(); key=args.key_file.read_text().strip()
    args.out.parent.mkdir(exist_ok=True,parents=True)
    frames=[]; paths={}; sightings=[]; attempts=[]
    for row in json.loads(args.manifest.read_text())["frames"]:
        f={k:row.get(k) for k in ("frame_id","dive_id","sequence_id","timestamp_s","path")}
        if f["frame_id"] in paths: raise ValueError("Repeated input frame")
        p=args.manifest.parent/f["path"]; paths[f["frame_id"]]=p
        with Image.open(p) as image: f["width"],f["height"]=image.size
        f.update(image_sha256=sha256(p),inference_ok=False)
        frames.append(f)
    metadata={"model":MODEL,"gguf_revision":VL_REV,"quantization":"Q4_K_M","projector":"F16","image_long_edge":1280,
              "prompt":INSTRUCTION,"manifest_sha256":sha256(args.manifest),"temperature":0,"seed":7,
              "format":"schema-constrained technical retry; keyed positional slots; independent of ground truth",
              "tracking":"Adjacent-frame same-label one-to-one IoU >= 0.30 where sample interval is at most 5 seconds",
              "box_space":"source image pixels [left,top,right,bottom]","initial_object_cap":48,
              "single_retry_object_cap":72,"token_cap":3400}
    def save():
        link_tracks(frames,sightings,"qwen",5)
        tmp=args.out.with_suffix(args.out.suffix+".tmp")
        tmp.write_text(json.dumps({"method":"qwen","frames":frames,"sightings":sightings,
                                  "metadata":metadata,"attempts":attempts},indent=2)+"\n")
        tmp.replace(args.out)
    def infer(group,cap):
        ids=[f["frame_id"] for f in group]
        try:
            found=get_boxes(group,paths,key,args.port,cap)
        except Exception as exc:
            err=str(exc)[:300]
            attempts.append({"frame_ids":ids,"ok":False,"error":err})
            print("Window failed:",ids,err,flush=True)
            for f in group: f["error"]=err
            return False
        sightings.extend(found); attempts.append({"frame_ids":ids,"ok":True})
        for f in group:
            f.pop("error",None); f["inference_ok"]=True; f["window_frames"]=len(group)
        print("Window complete:",ids,len(found),"sightings",flush=True)
        return True
    i=0
    while i<len(frames):
        group=frames[i:i+1]; i+=1
        if i<len(frames) and adjacent(group[0],frames[i],5): group.append(frames[i]);i+=1
        if not infer(group,48):
            for f in group: infer([f],72)
        save()
    return 0 if frames and all(f["inference_ok"] for f in frames) else 1


if __name__=="__main__": sys.exit(main())
