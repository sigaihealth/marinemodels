"""Build a portable, offline transect reviewer from the frame manifest and model runs."""
import argparse
import base64
import hashlib
import html
import io
import json
import math
from collections import defaultdict
from pathlib import Path

from PIL import Image


METHODS = {"expert": "Reference", "ecotype": "Ecotype", "qwen": "Qwen3-VL", "sam2": "SAM 2.1"}


def valid_box(value, width, height):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"Expected a four-coordinate pixel box, got {value!r}")
    x1, y1, x2, y2 = map(float, value)
    if not all(math.isfinite(v) for v in (x1, y1, x2, y2)) or not (x1 < x2 and y1 < y2):
        raise ValueError(f"Invalid bounding box {value!r}")
    return [max(0, x1), max(0, y1), min(width, x2), min(height, y2)]


def overlap(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    if not intersection:
        return 0.0
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection / union


def match_objects(refs, preds, threshold, same_class=True):
    """Maximum-cardinality one-to-one matching. Prefer larger IoU when traversing edges."""
    edges = {}
    for pred in preds:
        candidates = []
        for ref in refs:
            if not same_class or ref["group"] == pred["group"]:
                iou = overlap(pred["box"], ref["box"])
                if iou >= threshold:
                    candidates.append((iou, ref["id"]))
        edges[pred["id"]] = sorted(candidates, key=lambda item: (-item[0], item[1]))
    assigned = {}

    def augment(pred_id, seen):
        for iou, ref_id in edges[pred_id]:
            if ref_id in seen:
                continue
            seen.add(ref_id)
            if ref_id not in assigned or augment(assigned[ref_id][0], seen):
                assigned[ref_id] = (pred_id, iou)
                return True
        return False

    for pred in preds:
        augment(pred["id"], set())
    return [(ref, pred, iou) for ref, (pred, iou) in assigned.items()]


def display_jpeg(path):
    with Image.open(path) as img:
        width, height = img.size
        img.thumbnail((1200, 900))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
        payload = base64.b64encode(buf.getvalue()).decode("ascii")
    return width, height, "data:image/jpeg;base64," + payload


def model_inputs(logs):
    output = {}
    for log in logs:
        name = log["method"]
        if name not in METHODS or name == "expert" or name in output:
            raise ValueError(f"Unexpected or repeated model run {name}")
        frames = {str(f.get("frame_id", f.get("id"))): f for f in log["frames"]}
        objects = defaultdict(list)
        for s in log["sightings"]:
            fid = str(s["frame_id"])
            if fid not in frames:
                raise ValueError(f"{name} has a sighting outside its frame list: {fid}")
            objects[fid].append(s)
        output[name] = frames, objects
    return output


def strip_images(value):
    return {k: v for k, v in value.items() if k != "src"}


def encode_json(value):
    # Escape HTML-parser tokens even when a source label contains a closing script tag.
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build(manifest_file, run_files, out, threshold, extra, sequences=None, tracking_file=None, track_score=None):
    data = json.loads(manifest_file.read_text())
    logs = [json.loads(p.read_text()) for p in run_files]
    runs = model_inputs(logs)
    tracking = json.loads(tracking_file.read_text()) if tracking_file else {}
    overlays = defaultdict(list)
    for row in tracking.get("sightings",[]):
        overlays[row["frame_id"]].append(row)
    images = []
    ids = set()
    summary = {}
    tracks = defaultdict(lambda: (defaultdict(set), defaultdict(set), defaultdict(set)))
    identities = defaultdict(lambda: (set(), set()))
    by_group = defaultdict(lambda: defaultdict(lambda: {"reference":0,"matched":0,"unmatched":0}))
    for raw in data["frames"]:
        fid = str(raw.get("id", raw.get("frame_id")))
        if fid in ids:
            raise ValueError(f"Duplicate frame {fid}")
        ids.add(fid)
        path = manifest_file.parent / raw["file"]
        width, height, src = display_jpeg(path)
        if (width, height) != (raw.get("width", width), raw.get("height", height)):
            raise ValueError(f"Source dimensions do not match manifest in {fid}")
        dive = str(raw.get("dive") or raw.get("dive_id") or "Dive unspecified")
        series = str(raw.get("sequence_id") or raw.get("sequence") or dive)
        split = str(raw.get("split") or "Unspecified")
        scope = raw.get("annotation_scope") or "unspecified"
        if scope not in ("complete", "partial", "none", "unspecified"):
            raise ValueError(f"Unexpected annotation scope {scope}")
        labels = raw.get("evaluable_labels", [])
        valid_groups = {v.casefold().strip(): v for v in labels}
        maps = raw.get("label_map", data.get("label_map", {}))
        frame = dict(id=fid, dive=dive, sequence=series, split=split, width=width, height=height,
                     frame_index=raw.get("frame_index"), time_s=raw.get("time_s"),
                     utc=raw.get("utc"), source=raw.get("source"), scope=scope,
                     groups=labels, src=src, observations=[], status={})
        frame["notes"]=raw.get("annotation_scope_note",raw.get("notes",""))
        frame["reference_source"]=raw.get("annotation_source")
        frame["sha256"]=raw.get("sha256")
        frame["publisher_split"]=raw.get("publisher_split")
        frame["archive_image"]=raw.get("archive_image")
        frame["archive_annotation"]=raw.get("archive_annotation")

        def add(method, rows):
            for n, row in enumerate(rows):
                name = str(row["label"])
                box = row.get("bbox_xyxy", row.get("bbox"))
                group = row.get("comparison_label", row.get("evaluation_label"))
                if "comparison_label" not in row and "evaluation_label" not in row:
                    aliases = maps.get(method, {}) if isinstance(maps.get(method), dict) else maps
                    group = aliases.get(name, name)
                group = valid_groups.get(str(group).casefold().strip()) if group is not None else None
                track = row.get("track_id")
                frame["observations"].append(dict(id=f"{fid}/{method}/{n}", source_id=row.get("sighting_id", row.get("id")),
                    method=method, label=name, group=group, box=valid_box(box,width,height) if box is not None else None,
                    score=row.get("score"), track=str(track) if track is not None else None, comparisons={}, localizations={}))
        add("expert", raw.get("annotations", []))
        for method, (run_frames, run_objects) in runs.items():
            sample = run_frames.get(fid, {})
            if sample.get("image_sha256") and sample["image_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError(f"{method} input bytes differ in {fid}")
            ok = bool(sample) and sample.get("inference_ok") is True
            frame["status"][method] = {"ok": ok, "error": sample.get("error", "Frame has no verified inference result") if not ok else None}
            add(method, run_objects.get(fid, []))
            key = (series, split, method, scope)
            count = summary.setdefault(key, dict(sequence=series, dive=dive, split=split, method=method, scope=scope, total_frames=0,
                scored_frames=0, inference_frames=0, reference=0, matched=0, unmatched=0, unscored=0, unlocated_reference=0, localized=0, groups=set()))
            count["total_frames"] += 1
            count["inference_frames"] += int(ok)
            objects = frame["observations"]
            preds = [o for o in objects if o["method"] == method]
            gt = [o for o in objects if o["method"] == "expert"]
            if not ok or scope not in ("complete","partial") or not valid_groups:
                count["unscored"] += len(preds)
                continue
            if any(o["group"] and not o["box"] for o in gt):
                count["unlocated_reference"] += sum(1 for o in gt if o["group"] and not o["box"])
                count["unscored"] += len(preds)
                continue
            count["scored_frames"] += 1
            count["groups"].update(labels)
            refs = [o for o in gt if o["box"] and o["group"]]
            eligible = [o for o in preds if o["box"] and o["group"]]
            count["unscored"] += len(preds) - len(eligible)
            lookup = {o["id"]: o for o in objects}
            for o in refs: o["comparisons"][method] = {"result":"Missed reference"}
            for o in eligible: o["comparisons"][method] = {"result":"Unmatched prediction" if scope=="complete" else "Unverified prediction"}
            pairs = match_objects(refs, eligible, threshold)
            # Secondary localization checks use the same mapped reference objects and all located predictions.
            location_pairs=match_objects(refs,[o for o in preds if o["box"]],threshold,same_class=False)
            count["localized"] += len(location_pairs)
            for ref_id,pred_id,iou in location_pairs:
                ref,pred=lookup[ref_id],lookup[pred_id]
                ref["localizations"][method]={"peer":pred_id,"iou":round(iou,3)}
                pred["localizations"][method]={"peer":ref_id,"iou":round(iou,3)}
                if ref["track"] is not None and pred["track"] is not None:
                    ref_map, pred_map, ref_frames = tracks[key]
                    ref_map[ref["track"]].add(pred["track"])
                    pred_map[pred["track"]].add(ref["track"])
                    ref_frames[ref["track"]].add(fid)
            ref_ids,pred_ids=identities[key]
            for group in labels: by_group[key][group]
            for obj in refs:
                by_group[key][obj["group"]]["reference"]+=1
                if obj["track"] is not None: ref_ids.add(obj["track"])
            for obj in eligible:
                by_group[key][obj["group"]]["unmatched"]+=1
                if obj["track"] is not None: pred_ids.add(obj["track"])
            count["reference"] += len(refs)
            count["matched"] += len(pairs)
            count["unmatched"] += len(eligible) - len(pairs)
            for ref_id,pred_id,iou in pairs:
                ref,pred = lookup[ref_id],lookup[pred_id]
                by_group[key][ref["group"]]["matched"]+=1
                by_group[key][pred["group"]]["unmatched"]-=1
                ref["comparisons"][method] = {"result":"Matched","peer":pred_id,"iou":round(iou,3)}
                pred["comparisons"][method] = {"result":"Matched","peer":ref_id,"iou":round(iou,3)}

        if fid in overlays:
            add("sam2",overlays[fid])
            sam=[o for o in frame["observations"] if o["method"]=="sam2"]
            for o,row in zip(sam,overlays[fid]):
                o["seed_id"]=row.get("seed_sighting_id")
                if row.get("mask_path"):
                    with Image.open(tracking_file.parent/row["mask_path"]) as src_mask:
                        if src_mask.size != (width, height):
                            raise ValueError(f"Mask dimensions differ from the source frame {fid}")
                        mask=src_mask.convert("1")
                        # Transparent background, translucent lavender foreground.
                        png=mask.convert("P"); png.putpalette([0,0,0]+[162,118,255]*255)
                        png.info["transparency"]=bytes([0]+[115]*255)
                        buf=io.BytesIO();png.save(buf,format="PNG",optimize=True)
                        o["mask"]="data:image/png;base64,"+base64.b64encode(buf.getvalue()).decode("ascii")
        images.append(frame)
    if not images:
        raise ValueError("The frame manifest is empty.")
    for method,(samples,_) in runs.items():
        extra_frames=set(samples)-ids
        if extra_frames: raise ValueError(f"{method} output contains {len(extra_frames)} frames outside this manifest")
    if set(overlays)-ids: raise ValueError("SAM2 file references a frame outside this manifest")
    rows=[]
    for key,s in summary.items():
        s["groups"]=sorted(s["groups"])
        s["by_group"]=dict(by_group.get(key,{}))
        reference_ids, predicted_ids=identities[key]
        s["reference_track_count"]=len(reference_ids)
        s["predicted_track_count"]=len(predicted_ids)
        if key in tracks:
            refs,preds,frame_counts=tracks[key]
            s["track_audit"]={"matched_reference_tracks":len(refs),"matched_estimated_tracks":len(preds),
                "reference_tracks_matched_multiple_frames":sum(len(v)>1 for v in frame_counts.values()),
                "split_reference_tracks":sum(len(v)>1 for v in refs.values()),"merged_estimated_tracks":sum(len(v)>1 for v in preds.values())}
        rows.append(s)
    sources=data.get("datasets",[])
    clips={}
    for ds in sources:
        if isinstance(ds, dict) and ds.get("id") and ds.get("clip"):
            clip=manifest_file.parent/ds["clip"]
            if clip.is_file():
                clips[ds["id"]]="data:video/mp4;base64,"+base64.b64encode(clip.read_bytes()).decode("ascii")
    content = {"title":data.get("title","Underwater transect review"),
               "description":data.get("description","Inspect model sightings against the published annotations, then follow selected objects across the sampled frames."),"frames":images,"methods":{k:METHODS[k] for k in ["expert",*runs,*(["sam2"] if tracking else [])]},
               "threshold":threshold,"summaries":rows,"sources":data.get("datasets",[]),
               "notes":{"study_protocol":data.get("protocol",""),"label_crosswalk":data.get("label_crosswalk",{}),"units":data.get("units",{}),"notes":data.get("notes",[])},
               "clips":clips,"sequences":sequences or {},"track_score":track_score,"tracking_metadata":tracking.get("metadata",{}),"runs":[{"method":l["method"],"metadata":l.get("metadata",{})} for l in logs],
               "extra":extra}
    fingerprint = {"frames":[strip_images(f) for f in images],"runs":content["runs"],"threshold":threshold}
    content["run_id"]=hashlib.sha256(encode_json(fingerprint).encode()).hexdigest()[:20]
    out.parent.mkdir(parents=True,exist_ok=True)
    template = Path(__file__).with_name("review.html.in").read_text()
    out.write_text(template.replace("{{REPORT_TITLE}}",html.escape(str(content["title"]))).replace("{{DATA}}",encode_json(content)))
    return content


if __name__ == "__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--manifest",type=Path,required=True)
    cli.add_argument("--run",type=Path,action="append",default=[])
    cli.add_argument("--output",type=Path,required=True)
    cli.add_argument("--iou",type=float,default=.5)
    cli.add_argument("--evaluation",type=Path,help="Additional evaluation notes and provenance to show verbatim")
    cli.add_argument("--sequences",type=Path,help="Qwen ordered-sequence observations and referenced frame IDs")
    cli.add_argument("--tracking",type=Path,help="Supplemental SAM2 track and mask output")
    cli.add_argument("--tracking-score",type=Path,help="Independent seed-conditioned identity comparison")
    a=cli.parse_args()
    if not 0 < a.iou <= 1: cli.error("--iou must be in (0,1]")
    report=build(a.manifest,a.run,a.output,a.iou,json.loads(a.evaluation.read_text()) if a.evaluation else None, json.loads(a.sequences.read_text()) if a.sequences else None, a.tracking,json.loads(a.tracking_score.read_text()) if a.tracking_score else None)
    print(json.dumps({"output":str(a.output),"frames":len(report["frames"]),"run_id":report["run_id"],"summaries":report["summaries"]},indent=2))
