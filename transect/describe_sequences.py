"""Ask Qwen3-VL about an ordered sequence of pictures. No detector or expert labels are supplied."""
import argparse
import json
from pathlib import Path
import urllib.request

from run_models import MODEL, VL_REV, vision_image

PROMPT = (
    "These are sequential ROV video frames from one short interval. Discuss only visible evidence. "
    "Describe the habitat and visibly changing scene, any recurring animal candidate and why it may "
    "be the same animal, and uncertainty from visibility, occlusion or camera movement. If the "
    "images cannot resolve movement or identity, say so. Do not infer absolute location, depth, "
    "dive identity, species identity or population abundance from appearance. For each observation "
    "give one or more of the exact displayed frame IDs. Do not introduce IDs not supplied. "
    'Return a JSON object {"observations":[{"claim":"...","frame_ids":["..."]}],'
    '"uncertainty":"...","suggested_review":"..."}. Provide at most four observations.'
)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--port",type=int,default=18733)
    ap.add_argument("--key-file",type=Path,required=True)
    args=ap.parse_args()
    frames=json.loads(args.manifest.read_text())["frames"]; groups={}
    for frame in frames:
        if frame.get("sequence_id") is None or frame.get("timestamp_s") is None: continue
        groups.setdefault((frame["dive_id"],frame["sequence_id"]),[]).append(frame)
    reports=[]
    for (dive,seq), rows in groups.items():
        rows.sort(key=lambda f:f["timestamp_s"])
        if len(rows)>8:
            rows=[rows[round(i*(len(rows)-1)/7)] for i in range(8)]
        if len(rows)<2: continue
        if len({r["timestamp_s"] for r in rows})<len(rows):
            raise ValueError("Duplicate sequence timestamps")
        # Anonymous input IDs avoid giving the model site or source information via filenames.
        ids={f"F{i+1}":r["frame_id"] for i,r in enumerate(rows)}
        content=[{"type":"text","text":PROMPT}]
        for ident,row in zip(ids,rows):
            content.append({"type":"text","text":f'{ident}, time +{row["timestamp_s"]-rows[0]["timestamp_s"]:.2f}s:'})
            content.append({"type":"image_url","image_url":{"url":vision_image(args.manifest.parent/row["path"],640)}})
        body={"model":MODEL,"messages":[{"role":"user","content":content}],"temperature":0,
              "seed":7,"stream":False,"max_tokens":700,"response_format":{"type":"json_object"}}
        req=urllib.request.Request(f"http://127.0.0.1:{args.port}/v1/chat/completions",
                                   data=json.dumps(body).encode(),headers={"Content-Type":"application/json",
                                   "Authorization":"Bearer "+args.key_file.read_text().strip()})
        item={"dive_id":dive,"sequence_id":seq,"frame_ids":list(ids.values()),"inference_ok":False}
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=180) as res:
                answer=json.load(res)
            choice=answer["choices"][0]
            if answer.get("model")!=MODEL or choice.get("finish_reason")=="length": raise ValueError("Incomplete or wrong-model response")
            obj=json.loads(choice["message"]["content"])
            for observation in obj["observations"]:
                if not isinstance(observation.get("claim"),str) or not observation["frame_ids"]: raise ValueError("Uncited observation")
                observation["frame_ids"]=[ids[x] for x in observation["frame_ids"]]
            if not all(isinstance(obj.get(k),str) for k in ("uncertainty","suggested_review")): raise ValueError("Missing uncertainty/review")
            item.update(obj,inference_ok=True)
        except Exception as exc:
            item["error"]=str(exc)[:400]
        reports.append(item)
        print(seq,"ok" if item["inference_ok"] else item["error"],flush=True)
    result={"model":MODEL,"revision":VL_REV,"method":"qwen-ordered-sequence-review",
            "prompt":PROMPT,"input_long_edge":640,"status":"unreviewed visual hypotheses",
            "sequences":reports}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    temp=args.out.with_suffix(args.out.suffix+".tmp")
    temp.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n"); temp.replace(args.out)
    return 0 if reports and all(x["inference_ok"] for x in reports) else 1

if __name__=="__main__": raise SystemExit(main())
