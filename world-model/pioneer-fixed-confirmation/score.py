"""Score a fixed six-hour salinity predictor against persistence as observations arrive."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
from statistics import fmean
import tempfile

from frozen_predictor import MODEL_SHA256, feature_vector, load_model, predict

H = timedelta(hours=1)
ANCHOR = datetime(2026, 11, 24, 15, tzinfo=timezone.utc)
FIRST_ISSUE = ANCHOR - 12 * H
BASE = Path(__file__).resolve().parent
INPUTS = ("ctd_hourly.csv", "currents.csv", "tides.csv", "events.csv", "wave_hourly.csv")
SEED_SHA256 = "62835f4ba23492c432bca080fe5a0d7a53ba62e21c6c24ae33197c1994ace2b0"
LEDGER_FIELDS = ("issue", "valid", "deployment", "persistence", "fixed", "ctd_source",
                 "current_source", "first_recorded", "origin", "model_sha256")


def dt(value):
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError(f"UTC offset required: {value}")
    return t.astimezone(timezone.utc)


def utc(t):
    return t.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def dump(path, rows, fields):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def keyed(rows, key="time"):
    by_time = {dt(r[key]):r for r in rows}
    if len(by_time) != len(rows):
        raise ValueError(f"Duplicate {key}")
    return by_time


def check_ctd(row, nominal):
    if not timedelta(0) <= nominal - dt(row["source_time"]) <= H/4:
        raise ValueError(f"Stale/future CTD at {utc(nominal)}")
    if not all(math.isfinite(float(row[c])) for c in ("temperature_c","salinity")):
        raise ValueError("CTD values must pass QC and be finite")


def generate(model, t, a, tides, currents, logged):
    check_ctd(a, t)
    levels = [tides.get(t+k*H) for k in (-3,0,3,6)]
    if any(r is None for r in levels):
        return None
    flow = []
    for k in (-2,-1,0):
        when = t+k*H
        r = currents.get(when)
        if r is None or r["deployment"] != a["deployment"]:
            return None
        if not H/4 <= when - dt(r["source_time"]) <= 75*H/60:
            raise ValueError(f"Velocity timestamp inconsistent with preprocessing: {when}")
        flow.append((float(r["u_ms"]),float(r["v_ms"])))
    features = feature_vector(*(float(r["tide_m"]) for r in levels),flow)
    _, salinity = predict(model,features,(float(a["temperature_c"]),float(a["salinity"])))
    return dict(issue=utc(t),valid=utc(t+6*H),deployment=a["deployment"],persistence=a["salinity"],
                fixed=repr(salinity),ctd_source=a["source_time"],current_source=currents[t]["source_time"],
                first_recorded=utc(logged),origin="observation_refresh",model_sha256=MODEL_SHA256)


def errors(rows):
    if not rows:
        return (None,None,None)
    baseline = fmean(abs(float(r["persistence"])-float(r["observed"])) for r in rows)
    fixed = fmean(abs(float(r["fixed"])-float(r["observed"])) for r in rows)
    return baseline, fixed, baseline-fixed


def select_events(raw):
    ordered = sorted(raw,key=lambda r:dt(r["onset"]))
    found = [i for i,r in enumerate(ordered) if dt(r["window_start"]) <= ANCHOR <= dt(r["window_end"])]
    if len(found) != 1:
        raise ValueError("Cannot uniquely identify the registered November storm")
    selected = ordered[found[0]:found[0]+4]
    for a,b in zip(selected,selected[1:]):
        if dt(a["window_end"]) >= dt(b["window_start"]):
            raise ValueError("Event windows overlap")
    return selected


def evaluate_event(slot, event, ledger, ctd):
    start,end = dt(event["window_start"]),dt(event["window_end"])
    n = (end-start)//H+1
    eligible = [(t,ledger[t]) for t in sorted(ledger) if start<=t<=end]
    paired=[]
    for t,p in eligible:
        valid = t+6*H
        target = ctd.get(valid)
        if not target or target["deployment"] != p["deployment"]:
            continue
        check_ctd(target,valid)
        paired.append(dict(slot=slot,event_onset=event["onset"],issue=p["issue"],valid=p["valid"],
                           persistence=p["persistence"],fixed=p["fixed"],observed=target["salinity"],
                           verification_source=target["source_time"],origin=p["origin"],
                           first_recorded=p["first_recorded"]))
    certain = event["sequence_certain"].lower() in {"1","true","yes"}
    if not certain:
        status = "wave coverage under review"
    elif event["status"] != "complete":
        status = "wave window open or unconfirmed"
    elif len(paired) != n:
        status = "wave window closed; incomplete paired observations"
    else:
        status = "fully scored"
    p,f,g = errors(paired)
    extra = [r for r in paired if r["origin"]!="previous_study"]
    ep,ef,eg=errors(extra)
    return dict(slot=slot,onset=event["onset"],window_start=utc(start),window_end=utc(end),status=status,
                hours_in_window=n,forecast_hours=len(eligible),paired=len(paired),missing_pairs=n-len(paired),
                persistence_mae=p,fixed_mae=f,gain=g, additional_pairs=len(extra),additional_persistence_mae=ep,
                additional_fixed_mae=ef,additional_gain=eg,
                recorded_before_valid=sum(bool(r["first_recorded"]) and dt(r["first_recorded"])<dt(r["valid"]) for r in paired)),paired


def fmt(value):
    return "—" if value is None else f"{value:.4f}"


def report(state):
    successor=state["successor_summary"]
    lines=["# Pioneer six-hour salinity confirmation", "",
           "The November event and the next three distinct wave-defined storms use the same frozen tide-and-current model. Persistence carries the latest measured salinity forward. Lower mean absolute error (MAE) is better. A positive gain favors the fixed model.",
           "",f"Wave coverage through **{state['wave_observed_through']}**. Latest usable CTD **{state['ctd_through']}**. Latest usable currents **{state['currents_through']}**.","",
           "| Storm (UTC onset) | Status | Verified / window hours | Persistence MAE | Fixed model MAE | Gain |",
           "|---|---|---:|---:|---:|---:|"]
    for i in range(4):
        title = "November" if i==0 else f"Next {i}"
        if i>=len(state["storms"]):
            lines.append(f"| {title} | Awaiting a qualifying event | — | — | — | — |")
            continue
        r=state["storms"][i]
        lines.append(f"| {title} · {r['onset'][:10]} | {r['status']} | {r['paired']} / {r['hours_in_window']} | {fmt(r['persistence_mae'])} | {fmt(r['fixed_mae'])} | {fmt(r['gain'])} |")
    n=state["storms"][0]
    lines.extend(["",f"**November follow-up.** {n['forecast_hours']} forecasts have been saved for this window. {n['forecast_hours']-n['paired']} still await a usable verification. {n['additional_pairs']} verified hours are additional to the 20 examined when the model was frozen. On those additional hours persistence MAE is {fmt(n['additional_persistence_mae'])} and fixed-model MAE is {fmt(n['additional_fixed_mae'])}. The open-window denominator can grow until the storm closes.","",
                  f"**Independent follow-up.** {successor['complete']}/3 subsequent storms fully scored. {successor['verdict']}"])
    if successor['complete']:
        lines.append(f"Equal-storm average gain across fully scored successors is {fmt(successor['mean_gain'])}. The model leads on {successor['wins']} of them.")
    lines.extend(["","Each reported MAE uses identical, QC-passing verification hours for the two forecasts. A full score requires a closed, sequence-confirmed wave window and all issue–target pairs. Per-storm rows with missing observations remain visible. Overlapping hourly forecasts are not independent storms. Predictions are retained on first capture; observations can arrive late. The ledger records capture time to distinguish backfills from predictions saved before target time.","",
                  "[Registered protocol and model](https://github.com/sigaihealth/marinemodels/tree/main/world-model/pioneer-fixed-confirmation) · [Per-storm scores](per_storm.csv) · [Paired verifying observations](verified.csv) · [Forecast ledger](predictions.csv) · [Run history](https://github.com/sigaihealth/marinemodels/actions/workflows/pioneer-confirm.yml)",""])
    return "\n".join(lines)


def main(data,output):
    output.mkdir(parents=True,exist_ok=True)
    prior_state = json.loads((output/"state.json").read_text()) if (output/"state.json").exists() else None
    if prior_state and prior_state["model_sha256"]!=MODEL_SHA256:
        raise ValueError("Published state uses a different model")
    provenance = json.loads((data/"refresh_provenance.json").read_text())
    for name in INPUTS:
        if hashlib.sha256((data/name).read_bytes()).hexdigest() != provenance["data_sha256"][name]:
            raise ValueError(f"Input snapshot checksum mismatch: {name}")
    if hashlib.sha256((BASE/"initial_forecasts.csv").read_bytes()).hexdigest() != SEED_SHA256:
        raise ValueError("Registered November forecast ledger checksum mismatch")
    model=load_model()
    logged=datetime.now(timezone.utc)
    ctd=keyed(read(data/"ctd_hourly.csv"))
    tide=keyed(read(data/"tides.csv"))
    current=keyed(read(data/"currents.csv"))
    events=select_events(read(data/"events.csv"))
    wave_through=dt(events[0]["observed_through"])
    # Refuse to overwrite a fuller publication with a truncated/corrupt upstream response.
    if prior_state:
        for key,cutoff in (("wave_observed_through",wave_through),("ctd_through",max(ctd)),("currents_through",max(current))):
            if cutoff<dt(prior_state[key]):
                raise ValueError(f"Upstream coverage regressed for {key}")
    seed=keyed(read(BASE/"initial_forecasts.csv"),"issue")
    ledger=keyed(read(output/"predictions.csv"),"issue") if (output/"predictions.csv").exists() else dict(seed)
    for t,r in seed.items():
        if ledger.get(t)!=r:
            raise ValueError("Previously examined November forecast differs from the registered prediction")
    for t,r in ledger.items():
        if r["model_sha256"]!=MODEL_SHA256 or dt(r["valid"])!=t+6*H:
            raise ValueError("Forecast ledger integrity check failed")
    last=dt(events[-1]["window_end"]) if len(events)==4 and events[-1]["status"]=="complete" else max(ctd)
    for t in sorted(ctd):
        if not FIRST_ISSUE<=t<=min(last,logged) or t in ledger:
            continue
        row=generate(model,t,ctd[t],tide,current,logged)
        if row is not None:
            ledger[t]=row
    storms,verified=[],[]
    for i,event in enumerate(events):
        s,pairs=evaluate_event("November" if i==0 else f"Next {i}",event,ledger,ctd)
        storms.append(s)
        verified.extend(pairs)
    completed=[s for s in storms[1:] if s["status"]=="fully scored"]
    wins=sum(s["gain"]>0 for s in completed)
    mean_gain=fmean(s["gain"] for s in completed) if completed else None
    verdict="The three-storm result is pending."
    if len(completed)==3:
        verdict=("The prespecified salinity criterion was met." if mean_gain>0 and wins>=2 else
                 "The prespecified salinity criterion was not met.")
    state=dict(model_sha256=MODEL_SHA256,wave_observed_through=utc(wave_through),ctd_through=utc(max(ctd)),
               currents_through=utc(max(current)),forecast_count=len(ledger),storms=storms,
               successor_summary=dict(complete=len(completed),mean_gain=mean_gain,wins=wins,verdict=verdict),
               study_complete=(len(completed)==3 and storms[0]["status"]=="fully scored"))
    # Stage all outputs first. A failed check or source read leaves the published Git snapshot intact.
    with tempfile.TemporaryDirectory(dir=output) as temp:
        stage=Path(temp)
        dump(stage/"predictions.csv",[ledger[t] for t in sorted(ledger)],LEDGER_FIELDS)
        dump(stage/"per_storm.csv",storms,storms[0].keys())
        dump(stage/"verified.csv",verified,("slot","event_onset","issue","valid","persistence","fixed","observed","verification_source","origin","first_recorded"))
        (stage/"state.json").write_text(json.dumps(state,indent=2,allow_nan=False)+"\n")
        (stage/"REPORT.md").write_text(report(state))
        snap=stage/"observations"
        snap.mkdir()
        for name in INPUTS:
            (snap/(name+".gz")).write_bytes(gzip.compress((data/name).read_bytes(),mtime=0))
        (snap/"refresh_provenance.json").write_bytes((data/"refresh_provenance.json").read_bytes())
        (output/"observations").mkdir(exist_ok=True)
        for f in sorted(stage.rglob("*")):
            if f.is_file():
                f.replace(output/f.relative_to(stage))
    print(f"Verified {len(verified)} event pairs; {len(completed)}/3 subsequent storms fully scored.")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    main(args.data,args.output)
