"""Evaluate seeded track retention against reference geometry after inference."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from run_models import intersection_over_union


def read(path):
    return json.loads(path.read_text())


def assign(predictions, truth, min_iou=.50):
    pairs = []
    for i, det in enumerate(predictions):
        for j, annotation in enumerate(truth):
            overlap = intersection_over_union(det["bbox_xyxy"], annotation["bbox"])
            if overlap >= min_iou:
                pairs.append((overlap, i, j))
    matches = []
    used_predictions, used_truth = set(), set()
    for overlap, i, j in sorted(pairs, reverse=True):
        if i in used_predictions or j in used_truth:
            continue
        matches.append((predictions[i], truth[j], overlap))
        used_predictions.add(i)
        used_truth.add(j)
    return matches


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "detector", "sam", "out"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args()
    reference, detector, sam = read(args.reference), read(args.detector), read(args.sam)
    frames = [f for f in reference["frames"] if f["sequence_id"] == sam["metadata"]["sequence_id"]]
    ordered = sorted(frames, key=lambda r:r["timestamp_s"])
    by_frame = {}
    for method, result in (("ecotype",detector),("sam2",sam)):
        by_frame[method] = defaultdict(list)
        for item in result["sightings"]:
            by_frame[method][item["frame_id"]].append(item)
    first = ordered[0]
    seed_matches = assign(by_frame["ecotype"][first["frame_id"]],first["annotations"])
    result_rows = []
    for seed, expert, seed_iou in seed_matches:
        gt = expert["track_id"]
        initial = {"ecotype":seed["track_id"],
                   "sam2":next(s["track_id"] for s in sam["sightings"] if s["seed_sighting_id"]==seed["sighting_id"])}
        outcome = {"seed_sighting_id":seed["sighting_id"], "expert_track_id":gt, "expert_label":expert["label"],
                   "seed_label":seed["label"], "seed_iou":round(seed_iou,4), "methods":{}}
        for method, rows in by_frame.items():
            timesteps = []
            for frame in ordered[1:]:
                fid = frame["frame_id"]
                has_reference = any(obj["track_id"] == gt for obj in frame["annotations"])
                matches = assign(rows[fid],frame["annotations"])
                hit = next(((det, overlap) for det,obj,overlap in matches if obj["track_id"]==gt),None)
                other = [obj["track_id"] for det,obj,_ in matches if det["track_id"]==initial[method] and obj["track_id"]!=gt]
                timesteps.append({"frame_id":fid,"reference_present":has_reference,
                                  "matched_track":hit[0]["track_id"] if hit else None, "iou":round(hit[1],4) if hit else None,
                                  "seed_matched_different_id":other})
            observed=[t for t in timesteps if t["reference_present"]]
            all_ids=[initial[method]]+[t["matched_track"] for t in observed if t["matched_track"] is not None]
            retained=[t["matched_track"]==initial[method] for t in observed]
            # A matched run restarts when the same seed identity returns after an observed gap.
            seed_runs=int(bool(retained and retained[0]))
            seed_runs+=sum(a is False and b is True for a,b in zip(retained,retained[1:]))
            outcome["methods"][method]={"later_reference_frames":len(observed),"localized_any_track":len(all_ids)-1,
                "retained_seed_id":sum(retained),"distinct_predicted_ids_including_seed":len(set(all_ids)),
                "id_changes_between_successive_matches_including_seed":sum(a!=b for a,b in zip(all_ids,all_ids[1:])),
                "seed_match_runs_on_later_observations":seed_runs,
                "wrong_identity_frames":sum(bool(t["seed_matched_different_id"]) for t in timesteps),"frames":timesteps}
        result_rows.append(outcome)
    summary = {}
    for method in by_frame:
        rows=[seed["methods"][method] for seed in result_rows]
        summary[method]={k:sum(r[k] for r in rows) for k in ("later_reference_frames","localized_any_track","retained_seed_id",
            "distinct_predicted_ids_including_seed","id_changes_between_successive_matches_including_seed","wrong_identity_frames")}
    report={"sequence_id":sam["metadata"]["sequence_id"],"n_seeds":len(sam["metadata"]["seed_sightings"]),
            "n_expert_matched_seeds":len(result_rows),"iou_threshold":.50,
            "scope":"First-frame detector seeds only. Subsequent matches are class-agnostic and one-to-one. Counts are pooled track-frame observations.",
            "summary":summary,"seeds":result_rows}
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(summary))


if __name__ == "__main__": main()
