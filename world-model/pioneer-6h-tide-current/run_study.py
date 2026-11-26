"""Run forward-only six-hour Pioneer tide/current hindcasts from frozen source tables."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform

import numpy as np


H = timedelta(hours=1)
NEW = datetime(2026, 11, 1, tzinfo=timezone.utc)
TARGET = ("temperature_c", "salinity")
MODELS = ("persistence", "tide", "current", "tide_current")


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def stamp(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def read(path):
    raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    return list(csv.DictReader(io.StringIO(raw.decode(), newline="")))


def write(path, rows):
    with path.open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def by_hour(rows):
    indexed = {dt(r["time"]): r for r in rows}
    if len(indexed) != len(rows):
        raise ValueError("Duplicate timestamps")
    return indexed


def extract(t, ctd, tide, current):
    valid = t + 6*H
    a, b = ctd.get(t), ctd.get(valid)
    if not a or not b or a["deployment"] != b["deployment"]:
        return "ctd", None
    for row, nominal in ((a,t), (b,valid)):
        if not timedelta(0) <= nominal-dt(row["source_time"]) <= H/4:
            raise ValueError(f"Unexpected CTD sample age {nominal}")
    heights = [tide.get(t+h*H) for h in (-3,0,3,6)]
    if any(v is None for v in heights):
        return "tide", None
    lag, now, future3, future6 = [float(r["tide_m"]) for r in heights]
    vectors = []
    for h in (-2,-1,0):
        time = t+h*H
        row = current.get(time)
        if not row or row["deployment"] != a["deployment"]:
            return "current", None
        if not H/4 <= time-dt(row["source_time"]) <= 75*H/60:
            raise ValueError(f"Unexpected native velocity timestamp {time}")
        vectors.append([float(row["u_ms"]), float(row["v_ms"])])
    tide_x = np.array([now, now-lag, future3-now, future6-now])
    flow_x = np.r_[vectors[-1], np.mean(vectors, axis=0)]
    x = np.r_[tide_x,flow_x]
    initial, truth = (np.array([float(r[k]) for k in TARGET]) for r in (a,b))
    if not all(np.all(np.isfinite(arr)) for arr in (x, initial, truth)):
        raise ValueError(f"Nonfinite input at {t}")
    return "paired", (x, initial, truth)


def correct(train_x, train_delta, test_x):
    center = train_x.mean(axis=0)
    scale = np.std(train_x, axis=0)
    scale[scale < 1e-10] = 1.
    z = (train_x-center)/scale
    lhs = z.T @ z + np.eye(z.shape[1])*len(z)*.01
    coefficients = np.linalg.solve(lhs, z.T @ train_delta)
    return (test_x-center)/scale @ coefficients


def main(data, output):
    output.mkdir(parents=True, exist_ok=True)
    ctd = by_hour(read(data/"ctd_hourly.csv.gz"))
    tide = by_hour(read(data/"tides.csv.gz"))
    currents = by_hour(read(data/"currents.csv.gz"))
    archive = [dict(r, cohort="archive_complete") for r in read(data/"archive_windows.csv")
               if int(r["prior_ctd_timestamps"]) == 0]
    recent = [dict(r, cohort="later_"+r["status"]) for r in read(data/"fresh_storms.csv")]
    events = archive + recent
    # Cover both predictor histories and verification times in the embargo, including across folds.
    protected = [(dt(r["window_start"])-2*H,dt(r["window_end"])+6*H) for r in events]
    cases = {}
    statuses = {}
    for t in sorted(ctd):
        status,row = extract(t,ctd,tide,currents)
        statuses[t] = status
        if status == "paired":
            cases[t] = row
    possible_train = [t for t in cases if not any(t-2*H <= hi and t+6*H >= lo for lo,hi in protected)]
    coverage, predictions, scores = [], [], []
    for r in events:
        start, end = dt(r["window_start"]), dt(r["window_end"])
        cutoff = (start if r["cohort"] == "archive_complete" else NEW) - 72*H
        train = [t for t in possible_train if t+6*H < cutoff]
        origins = [start+i*H for i in range((end-start)//H+1)]
        test = [t for t in origins if t in cases]
        coverage.append(dict(storm_id=r["storm_id"],cohort=r["cohort"],start=stamp(start),end=stamp(end),
                        peak_wave_m=r["peak_wave_m"],origins=len(origins),
                        missing_ctd=sum(statuses.get(t,"ctd")=="ctd" for t in origins),
                        missing_tide=sum(statuses.get(t)=="tide" for t in origins),
                        missing_currents=sum(statuses.get(t)=="current" for t in origins),
                        paired=len(test), train_hours=len(train),train_last_target=stamp(train[-1]+6*H) if train else "",
                        score_status="scored" if test and len(train)>=72 else "insufficient training" if test else "no paired targets"))
        if not test or len(train)<72:
            continue
        train_x = np.stack([cases[t][0] for t in train])
        train_delta = np.stack([cases[t][2]-cases[t][1] for t in train])
        test_x,base,truth = (np.stack([cases[t][k] for t in test]) for k in range(3))
        columns = (slice(0,4), slice(4,None), slice(None))
        pred = np.stack([base, *[base + correct(train_x[:,c], train_delta, test_x[:,c]) for c in columns]],axis=1)
        err = pred-truth[:,None,:]
        maes = np.mean(np.abs(err),axis=0)
        for k,target in enumerate(TARGET):
            for j,model in enumerate(MODELS):
                scores.append(dict(cohort=r["cohort"],storm_id=r["storm_id"],issue_start=stamp(test[0]),
                                   n=len(test),target=target,model=model,mae=maes[j,k],
                                   rmse=np.sqrt(np.mean(err[:,j,k]**2)),bias=err[:,j,k].mean(),
                                   mae_gain=maes[0,k]-maes[j,k]))
        for i,t in enumerate(test):
            out = dict(cohort=r["cohort"],storm_id=r["storm_id"],issue=stamp(t),valid=stamp(t+6*H),
                       current_source_time=currents[t]["source_time"],ctd_issue_source=ctd[t]["source_time"],
                       ctd_valid_source=ctd[t+6*H]["source_time"],deployment=ctd[t]["deployment"])
            for k,target in enumerate(TARGET):
                out[target]=truth[i,k]
                for j,model in enumerate(MODELS):
                    out[model+"_"+target]=pred[i,j,k]
            predictions.append(out)
    write(output/"coverage.csv",coverage)
    if not predictions:
        raise ValueError("No scorable events")
    write(output/"predictions.csv",predictions)
    write(output/"per_event.csv",scores)
    macro=[]
    for cohort in dict.fromkeys(r["cohort"] for r in scores):
        for target in TARGET:
            for model in MODELS:
                sel=[r for r in scores if (r["cohort"],r["target"],r["model"])==(cohort,target,model)]
                m=np.mean([r["mae"] for r in sel])
                m0=np.mean([r["mae"] for r in scores if (r["cohort"],r["target"],r["model"])==(cohort,target,"persistence")])
                macro.append(dict(cohort=cohort,target=target,model=model,events=len(sel),
                             hours=sum(r["n"] for r in sel),storm_mae=m,gain_vs_persistence=m0-m,
                             events_better=sum(bool(r["mae_gain"]>0) for r in sel)))
    write(output/"scores.csv",macro)
    meta=dict(numpy=np.__version__,python=platform.python_version(),platform=platform.system(),
              inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(data.glob("*")) if p.is_file()},
              scored_hours=len(predictions),scored_events=len({r["storm_id"] for r in scores}))
    (output/"summary.json").write_text(json.dumps(meta,indent=2)+"\n")
    print(json.dumps(meta,indent=2))
    for r in macro:print(r["cohort"],r["target"],r["model"],round(r["storm_mae"],6))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data",type=Path,default=Path("data"))
    p.add_argument("--out",type=Path,default=Path("results"))
    a=p.parse_args()
    main(a.data,a.out)
