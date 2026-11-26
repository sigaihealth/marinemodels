"""Match original OOI water samples to the closest CTD, fluorometer and weather observations."""
import argparse
import csv
from datetime import datetime, timezone
from io import StringIO
import json
import math
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

HOST = "https://erddap.dataexplorer.oceanobservatories.org/erddap/tabledap/"
IDS = {
    "plims": "ooi-cp10cnsm-rid27-07-plimsa000",
    "ctd": "ooi-cp10cnsm-rid27-03-ctdbpc000",
    "fluorometer": "ooi-cp10cnsm-rid27-02-flortd000",
    "weather": "ooi-cp10cnsm-sbd11-06-metbka000",
}
FIELDS = {
    "plims": ("roipml", "volana"),
    "ctd": ("sea_water_practical_salinity", "sea_water_temperature"),
    "fluorometer": ("mass_concentration_of_chlorophyll_a_in_sea_water",),
    "weather": ("air_pressure", "eastward_wind", "northward_wind"),
}
ARCHIVE = "https://ifcb-data.oceanobservatories.org/api/export_metadata/PioneerMABMoored?start_date=2026-01-29&end_date=2026-02-03"
BEGIN, END = "2026-01-29T00:00:00Z", "2026-02-04T00:00:00Z"


def read_csv(url, cache, name):
    path = cache / (name + ".csv")
    if not path.exists():
        with urlopen(Request(url, headers={"User-Agent": "SIGAI-Ocean-research/1.0"}), timeout=50) as response:
            data = response.read()
        cache.mkdir(exist_ok=True, parents=True)
        path.write_bytes(data)
    return list(csv.DictReader(StringIO(path.read_text(encoding="utf-8-sig"))))


def instant(timestamp):
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def iso(timestamp):
    return timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def erddap_source(key):
    cols = ["time", "latitude", "longitude"]
    for variable in FIELDS[key]:
        cols.extend([variable, variable + "_qc_agg"])
    query = ",".join(cols) + f"&time>={BEGIN}&time<{END}"
    return HOST + IDS[key] + ".csv?" + quote(query, safe=",:=&")


def nearest(rows, target, columns, tolerance=360):
    valid = []
    for row in rows:
        if all(row[k + "_qc_agg"] in {"1", "2"} and math.isfinite(float(row[k])) for k in columns):
            timestamp = instant(row["time"])
            valid.append((abs((timestamp - target).total_seconds()), timestamp, row))
    if not valid:
        return None
    distance, _, row = min(valid, key=lambda x: x[:2])
    return row if distance <= tolerance else None


def value(row, key):
    return float(row[key]) if row else None


def flag(row, key):
    return int(row[key + "_qc_agg"]) if row else None


def build(cache):
    sources = {key: erddap_source(key) for key in FIELDS}
    erddap = {key: read_csv(url, cache, key)[1:] for key, url in sources.items()}
    bins = sorted(read_csv(ARCHIVE, cache, "ifcb"), key=lambda row: row["sample_time"])
    if len(bins) != 42 or len(erddap["plims"]) != 42:
        raise ValueError("Expected 42 recovered acquisitions and 42 matching instrument rows.")
    samples = []
    used = set()
    for row in bins:
        when = instant(row["sample_time"])
        plims = nearest(erddap["plims"], when, FIELDS["plims"], tolerance=59)
        if plims is None or plims["time"] in used:
            raise ValueError(f"Could not pair a unique telemetry row to {row['pid']}")
        used.add(plims["time"])
        count, volume = int(row["n_images"]), float(row["ml_analyzed"])
        if abs(float(plims["roipml"]) - count / volume) > 0.00001 or abs(float(plims["volana"]) - volume) > 0.00001:
            raise ValueError(f"Published ROI concentration or volume disagrees for {row['pid']}")
        ctd = nearest(erddap["ctd"], when, FIELDS["ctd"])
        fluor = nearest(erddap["fluorometer"], when, FIELDS["fluorometer"])
        met = nearest(erddap["weather"], when, ("air_pressure",))
        wind = nearest(erddap["weather"], when, ("eastward_wind", "northward_wind"))
        chl = FIELDS["fluorometer"][0]
        samples.append({
            "time": iso(when), "catalogTime": plims["time"], "binId": row["pid"], "roiCount": count,
            "volumeMl": volume, "roiPerMl": value(plims, "roipml"), "roiQc": flag(plims, "roipml"),
            "volumeQc": flag(plims, "volana"), "pressureMbar": value(met, "air_pressure"), "pressureQc": flag(met,"air_pressure"),
            "pressureTime": met["time"] if met else None,
            "salinity": value(ctd,"sea_water_practical_salinity"), "salinityQc":flag(ctd,"sea_water_practical_salinity"),
            "temperatureC": value(ctd,"sea_water_temperature"),"temperatureQc":flag(ctd,"sea_water_temperature"),
            "ctdTime": ctd["time"] if ctd else None,
            "chlorophyllUgL":value(fluor,chl),"chlorophyllQc": flag(fluor,chl),"fluoroTime":fluor["time"] if fluor else None,
            "windMs": round(math.hypot(value(wind,"eastward_wind"),value(wind,"northward_wind")),6) if wind else None,
            "windEastMs":value(wind,"eastward_wind"),"windNorthMs":value(wind,"northward_wind"),
            "windEastQc":flag(wind,"eastward_wind"),"windNorthQc":flag(wind,"northward_wind"),"windTime":wind["time"] if wind else None,
        })
    pressure = min((r for r in erddap["weather"] if flag(r,"air_pressure") in (1,2) and math.isfinite(value(r,"air_pressure"))),key=lambda r:value(r,"air_pressure"))
    if sum(s["roiCount"] for s in samples) != 123609 or any(float(b["depth"]) != 7 for b in bins):
        raise ValueError("The publisher archive has changed since the 7 m, 123,609-region reference replay.")
    return {"pioneer":{
        "name":"Pioneer Mid-Atlantic Bight Central Surface Mooring", "station":"CP10CNSM", "event":"Winter Storm Gianna",
        "latitude":float(bins[0]["latitude"]),"longitude":float(bins[0]["longitude"]),"intakeDepthM":7,"approximateSeabedDepthM":30,
        "startUtc":BEGIN,"endExclusiveUtc":END,"sampleCount":len(samples),"roiCount":sum(s["roiCount"] for s in samples),
        "units":{"roiPerMl":"image regions/mL","volumeMl":"mL","pressureMbar":"mbar","salinity":"practical salinity (PSS-78)",
                 "temperatureC":"°C","chlorophyllUgL":"µg/L","windMs":"m/s"},
        "matching":"Nearest finite sensor reading with QC 1 or 2 within 6 minutes of the recovered IFCB acquisition time (UTC). Store each source time. Ties use the earlier reading. Absent matches are null. No interpolation.",
        "qc":{"1":"passed automated quality checks","2":"not evaluated by automated quality checks"},
        "windDefinition":"Speed derived from simultaneous eastward and northward wind components using their Euclidean magnitude.",
        "interpretation":"Each image region can contain a cell, chain, detritus or another particle. Regions/mL measures imaged particles and depends on the IFCB trigger. Fluorometer chlorophyll-a is a pigment proxy.",
        "sampleUrlTemplate":"https://ifcb-data.oceanobservatories.org/bin?dataset=PioneerMABMoored&bin={binId}",
        "pressureMinimum":{"time":pressure["time"],"value":value(pressure,"air_pressure"),"qc":flag(pressure,"air_pressure"),"basis":"full minute-resolution station series"},
        "sources":dict(sources,archive=ARCHIVE,station="https://doi.org/10.58046/OOI-CP10CNSM",event="https://oceanobservatories.org/2026/09/ooi-plankton-imagery-and-co-located-environmental-data-now-ready-for-analysis/"),
        "credit":"Data from the NSF Ocean Observatories Initiative, Pioneer Mid-Atlantic Bight Central Surface Mooring.",
        "samples":samples}}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    result=build(args.cache)
    args.out.parent.mkdir(exist_ok=True, parents=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(",",":"))+"\n")
