"""Fetch and verify MBARI's V4277 sequence or build a separate expert reference."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

REV = "61ecbda8acb2749f3771d7192c51341267da2f37"
EARLY = "2163f4bdd04143222f1eebfe618904f765f6c934"
BASE = "https://huggingface.co/datasets/MBARI-org/DeepSea-MOT/resolve/"
TREE = "https://huggingface.co/api/datasets/MBARI-org/DeepSea-MOT/tree/"
FPS_N, FPS_D = 30000, 1001
WIDTH, HEIGHT, COUNT = 1920, 1080, 600
INDEX_KEYS = {"images":"bde6a38da47f51f2f5c3f0bca2df38055bf985ed","xml":"538c03f07f30ac987a6eba6bb43144f64a7adfcc"}


def check(test, msg):
    if not test:
        raise ValueError(msg)


def atomic(path, content):
    path.parent.mkdir(exist_ok=True, parents=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as fd:
        temp = Path(fd.name)
        try:
            fd.write(content)
            fd.close()
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def as_json(path, obj):
    atomic(path, (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode())


def digest(content, alg):
    if alg == "sha256":
        return hashlib.sha256(content).hexdigest()
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def get(url):
    for attempt in range(6):
        try:
            with urlopen(Request(url,headers={"User-Agent":"SIGAI-DeepSea-MOT-research/1.0"}), timeout=50) as stream:
                return stream.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            if (isinstance(exc, HTTPError) and exc.code not in (408, 429, 500, 502, 503, 504)) or attempt == 5:
                raise
            time.sleep(min(2 ** attempt, 10))


def fetch(path, url, alg, expected, offline=False):
    if path.is_file():
        content = path.read_bytes()
        if digest(content, alg) == expected:
            return content
    if offline:
        raise ValueError(f"Missing or changed cache file: {path}")
    content = get(url)
    check(digest(content, alg) == expected, f"Publisher digest mismatch: {path}")
    atomic(path, content)
    return content


def index(out, kind, offline):
    """Verify the digest of the sorted canonical file listing captured at REV."""
    path = out / "sources" / f"{kind}-index.json"
    data = json.loads(path.read_bytes() if path.is_file() or offline else get(f"{TREE}{REV}/data/BD/{kind}?limit=1000"))
    ordered = sorted(data, key=lambda x:x["path"])
    suffix = ".jpg" if kind == "images" else ".xml"
    names = [f"data/BD/{kind}/BD_{i:03d}{suffix}" for i in range(1, COUNT+1)]
    check([r["path"] for r in ordered] == names, f"Unexpected {kind} members")
    tree = b"".join(b"100644 "+Path(r["path"]).name.encode()+b"\0"+bytes.fromhex(r["oid"]) for r in ordered)
    checksum = hashlib.sha1(b"tree "+str(len(tree)).encode()+b"\0"+tree).hexdigest()
    check(checksum == INDEX_KEYS[kind], "Pinned file inventory checksum mismatch")
    if not offline:
        as_json(path, ordered)
    return ordered


def payload(out, kind, row, offline):
    alg, checksum = ("sha256",row["lfs"]["oid"]) if "lfs" in row else ("git",row["oid"])
    key = row["path"]
    if "lfs" in row:
        pointer = f"version https://git-lfs.github.com/spec/v1\noid sha256:{checksum}\nsize {row['size']}\n".encode()
        check(digest(pointer, "git") == row["oid"], f"Inconsistent Git LFS metadata for {key}")
    local = out / ("blind" if kind == "images" else "sources") / kind / Path(key).name
    content = fetch(local, f"{BASE}{REV}/{key}", alg, checksum, offline)
    check(len(content) == row["size"], f"Size mismatch for {key}")
    return content


def metadata(i):
    # MOV PTS ticks at 1/30000 s start at 0, 874, 1875, ...; the first interval is shorter.
    ticks = 0 if i == 1 else (i - 1) * FPS_D - 127
    return dict(frame_id=f"v4277-{i:04d}", frame_index=i, sequence_id="v4277-bd", dive_id="V4277",
                timestamp_s=round(ticks/FPS_N, 9), width=WIDTH, height=HEIGHT)


def frame_image(data, i):
    return dict(**metadata(i), path=f"images/BD_{i:03d}.jpg",sha256=hashlib.sha256(data).hexdigest())


def frame_labels(data, i):
    root = ET.fromstring(data)
    check(root.findtext("filename") == f"BD_{i:03d}.jpg", "XML frame mismatch")
    check(int(root.findtext("size/width")) == WIDTH and int(root.findtext("size/height")) == HEIGHT,"Geometry mismatch")
    ann = []
    for item in root.findall("object"):
        label, id_text = item.findtext("name").rsplit("-",1)
        coords = [float(item.findtext("bndbox/"+axis)) for axis in ("xmin","ymin","xmax","ymax")]
        # The publisher rounded some border coordinates just outside the image.
        check(-0.01 <= coords[0] < coords[2] <= WIDTH+0.01 and -0.01 <= coords[1] < coords[3] <= HEIGHT+0.01, f"Invalid bounds at {i}: {coords}")
        box = [max(0,coords[0]), max(0,coords[1]), min(WIDTH,coords[2]), min(HEIGHT,coords[3])]
        record = dict(bbox=box, track_id=int(id_text), label=label)
        if box != coords:
            record["source_bbox"] = coords
        ann.append(record)
    check(len({a["track_id"] for a in ann}) == len(ann), f"Duplicate track in frame {i}")
    return dict(**metadata(i),annotations=ann)


def run_frames(out, kind, workers, offline):
    source = index(out, kind, offline)
    transform = frame_image if kind == "images" else frame_labels
    def process(idx_member):
        i, row = idx_member
        return transform(payload(out,kind,row,offline), i)
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(process, enumerate(source,1)))



def verify_reference_support(out, frames, offline):
    """Check the taxon evidence against the publisher's separate MOT-format track table."""
    sources = out / "sources"
    mot = fetch(sources / "gt.txt", f"{BASE}{REV}/data/BD/gt.txt", "sha256",
                "781f5ba506048ea4aac362efe76e542a402b85bcf553cbd0103086bad743d845", offline)
    early = fetch(sources / "BD_001-provenance.xml", f"{BASE}{EARLY}/data/BD/xml/BD_001.xml",
                  "sha256", "c4a1d5b5f92e7b96c5f936950d6e3634e03dc08f48474d86da04a885676d906f", offline)
    original = ET.fromstring(early)
    check(original.findtext("filename") == "Benthic_1_V4277_20200219T211238Z_1.jpg", "Dive provenance mismatch")
    renamed = ET.parse(sources / "xml/BD_001.xml").getroot()
    check([ET.tostring(obj) for obj in original.findall("object")] ==
          [ET.tostring(obj) for obj in renamed.findall("object")], "Renamed source lost original annotations")
    remaining = {(f["frame_index"], a["track_id"]): a.get("source_bbox", a["bbox"]) for f in frames for a in f["annotations"]}
    for row in csv.reader(mot.decode().splitlines()):
        key = (int(row[0]), int(row[1]))
        check(key in remaining, f"Unmatched or duplicated MOT reference {key}")
        x, y, w, h = map(float, row[2:6])
        xyxy = (x, y, x + w, y + h)
        check(max(abs(a-b) for a,b in zip(remaining.pop(key),xyxy)) < 1.01,
              f"MOT box differs from the source XML at {key}")
    check(not remaining, "Objects missing from MOT records")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--stage",choices=("blind","reference","video","all"),default="blind")
    ap.add_argument("--workers",type=int,default=8)
    ap.add_argument("--offline",action="store_true")
    args=ap.parse_args()
    if not 1 <= args.workers <= 24: ap.error("Choose 1 to 24 concurrent downloads.")
    out=args.output
    base=dict(sequence_id="v4277-bd",dive_id="V4277",fps_numerator=FPS_N,fps_denominator=FPS_D,
              timestamp_basis="seconds from clip start", frame_indices="one-based")
    if args.stage in ("blind","all"):
        rows=run_frames(out,"images",args.workers,args.offline)
        as_json(out/"blind"/"manifest.json",{**base,"frames":rows})
        print("Verified and staged",len(rows),"publisher JPEGs.",flush=True)
    if args.stage in ("reference","all"):
        rows=run_frames(out,"xml",args.workers,args.offline)
        verify_reference_support(out, rows, args.offline)
        labels={}
        for row in rows:
            for item in row["annotations"]:
                labels.setdefault(item["track_id"],set()).add(item["label"])
        tracks=[dict(track_id=k,labels=sorted(v)) for k,v in sorted(labels.items())]
        as_json(out/"reference.json",{**base,"source_revision":REV,"bbox_format":"xyxy, publisher XML source pixels","tracks":tracks,"frames":rows})
        print("Verified and staged",sum(len(r["annotations"]) for r in rows),"expert annotations across",len(tracks),"tracks.",flush=True)
    if args.stage in ("video","all"):
        fetch(out/"sources"/"BD.mov",f"{BASE}{REV}/data/BD/BD.mov","sha256","f3ff1f4590777dc775cede0e757ce9c1decbd8fff3fef81e1b12c0131663b7ac",args.offline)
        print("Verified publisher source video.",flush=True)

if __name__ == "__main__":
    main()
