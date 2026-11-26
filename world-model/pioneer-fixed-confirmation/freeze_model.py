"""One-time reconstruction and independent verification of the previous November fit.

The live scorer uses frozen_predictor.py only. Executing this audit never replaces
an existing artifact. A new verification copy can be written with --output.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

from frozen_predictor import FEATURES, TARGETS, MODEL_NAME, load_model, predict


BASE_COMMIT = "5bda50c631d909c5bcc19a37b0473f83458bc8a1"
BASE_HASHES = {
    "run_study.py": "87d2bbf4e1a40b9ebb9b5baede8cff277cc0527c50d837e128a71b6ea422a8cb",
    "results/summary.json": "2df61bc0c24ec5916c117ccb510e0360c0f7dfb1390a3c1b07b3e6589d54311e",
    "results/predictions.csv": "58d95d74103c5962f8a2a5fc213901802a2412c2db6230f3fcbc34dba0680aa6",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_study(root):
    for filename, expected in BASE_HASHES.items():
        if digest(root / filename) != expected:
            raise ValueError(f"Previous experiment file changed: {filename}")
    hashes = json.loads((root/"results/summary.json").read_bytes())["inputs"]
    for filename, expected in hashes.items():
        if digest(root/"data"/filename) != expected:
            raise ValueError(f"Previous study input changed: {filename}")
    spec = importlib.util.spec_from_file_location("previous",root/"run_study.py")
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    return previous, hashes


def reconstruct(root):
    study, hashes = load_study(root)
    data = root/"data"
    ctd, tides, currents = [study.by_hour(study.read(data/(name+".csv.gz")))
                            for name in ("ctd_hourly","tides","currents")]
    events = [r for r in study.read(data/"archive_windows.csv") if int(r["prior_ctd_timestamps"]) == 0]
    events += study.read(data/"fresh_storms.csv")
    protected = [(study.dt(r["window_start"])-2*study.H, study.dt(r["window_end"])+6*study.H) for r in events]
    target_cutoff = study.NEW - 72*study.H
    hours, design, changes = [], [], []
    for t in sorted(ctd):
        valid = t+6*study.H
        if valid >= target_cutoff or any(t-2*study.H <= hi and valid >= lo for lo,hi in protected):
            continue
        status, row = study.extract(t,ctd,tides,currents)
        if status == "paired":
            x, initial, truth = row
            hours.append(study.stamp(t))
            design.append(x)
            changes.append(truth-initial)
    if len(hours) != 14820 or hours[-1] != "2026-10-28T17:00:00Z":
        raise ValueError("Training sample differed from the registered November fold")
    x, y = np.stack(design), np.stack(changes)
    means, scales = x.mean(axis=0), x.std(axis=0)
    scales[scales < 1e-10] = 1.
    z = (x-means)/scales
    coefficients = np.linalg.solve(z.T@z + np.eye(z.shape[1])*len(z)*.01, z.T@y)
    manifest = {
        "name":MODEL_NAME, "source_commit":BASE_COMMIT, "study":"world-model/pioneer-6h-tide-current",
        "model":"tide_current", "lead_hours":6, "features":list(FEATURES), "targets":list(TARGETS),
        "forecast":"issue-time target values plus standardized predictors times coefficients",
        "means":means.tolist(),"scales":scales.tolist(),"coefficients":coefficients.tolist(),
        "intercept":[0.0,0.0],"ridge_penalty_per_row":0.01,"train_rows":len(hours),
        "first_train_issue":hours[0],"last_train_issue":hours[-1],
        "last_train_target":study.stamp(study.dt(hours[-1])+6*study.H),
        "exclusive_train_target_cutoff":study.stamp(target_cutoff),"embargo_hours":72,
        "training_issues_sha256":hashlib.sha256(("\n".join(hours)+"\n").encode()).hexdigest(),
        "previous_study_input_sha256":hashes,"source_and_output_sha256":BASE_HASHES,
    }
    replay = []
    with (root/"results/predictions.csv").open() as f:
        for r in csv.DictReader(f):
            if r["cohort"] != "later_provisional":
                continue
            status, row = study.extract(study.dt(r["issue"]),ctd,tides,currents)
            if status != "paired":
                raise ValueError(f"Previously scored origin no longer paired: {r['issue']}")
            replay.append((row[0],row[1],[float(r["tide_current_"+k]) for k in TARGETS]))
    if len(replay) != 20:
        raise ValueError("Expected exactly 20 previously scored November forecast origins")
    return manifest,replay


def check_replay(model,replay):
    worst = np.max([np.abs(np.asarray(predict(model,x,initial))-expected)
                    for x,initial,expected in replay],axis=0)
    if not np.all(worst < 1e-10):
        raise ValueError(f"Model drift: {worst}")
    return worst.tolist()


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous",type=Path,default=here.parent/"pioneer-6h-tide-current")
    parser.add_argument("--output",type=Path,help="new path for a reconstruction; defaults to verifying the registered model")
    args = parser.parse_args()
    reconstructed,replay = reconstruct(args.previous)
    reconstructed_errors = check_replay(reconstructed,replay)
    if args.output:
        with args.output.open("x") as f:
            json.dump(reconstructed,f,indent=2,allow_nan=False)
            f.write("\n")
        path = args.output
        errors = reconstructed_errors
    else:
        path = here/"frozen_model.json"
        stored = load_model(path)
        for key in ("means","scales","coefficients"):
            np.testing.assert_allclose(stored[key],reconstructed[key],atol=1e-12,rtol=1e-12)
        for key in reconstructed.keys()-{"means","scales","coefficients"}:
            if stored[key] != reconstructed[key]:
                raise ValueError(f"Registered metadata differs for {key}")
        errors = check_replay(stored,replay)
    print(json.dumps({"sha256":digest(path),"train_rows":reconstructed["train_rows"],
                      "replayed_forecasts":len(replay),"maximum_absolute_difference":dict(zip(TARGETS,errors))},
                     indent=2))


if __name__ == "__main__":
    main()
