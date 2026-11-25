"""Rebuild the blind pilot inputs and reproduce the published reference annotations."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ECOTYPES = ["Demersal", "Motile Epifauna", "Planktonic", "Sessile Epifauna"]
BLIND_KEYS = (
    "id", "frame_id", "frame_index", "file", "path", "sequence_id", "dive_id",
    "timestamp_s", "time_s", "width", "height", "sha256",
)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def replace_file(path, contents):
    """Finish writes in a sibling file to avoid partially publishing outputs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        with temp_path.open("wb") as stream:
            contents(stream)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def source_file(cache, key, url, expected, offline):
    path = cache / key
    if path.is_file() and file_hash(path) == expected:
        return path
    if offline:
        raise ValueError(f"Offline source missing or checksum mismatch: {path}")

    def download(stream):
        request = Request(url, headers={"User-Agent": "marinemodels-transect/1.0"})
        with urlopen(request, timeout=120) as response:
            shutil.copyfileobj(response, stream)
        stream.flush()
        check(file_hash(Path(stream.name)) == expected, f"Download checksum mismatch: {url}")

    replace_file(path, download)
    return path


def ooi_annotations(frame, lines):
    result = []
    width, height = frame["width"], frame["height"]
    for line in lines.decode().splitlines():
        label_id, *fields = line.split()
        x, y, w, h = map(float, fields)
        label = ECOTYPES[int(label_id)]
        box = [max(0, (x - w / 2) * width), max(0, (y - h / 2) * height),
               min(width, (x + w / 2) * width), min(height, (y + h / 2) * height)]
        result.append({"label": label, "comparison_label": label,
                       "bbox": [round(value, 4) for value in box], "track_id": None})
    return result


def mbari_annotations(xml, crosswalk):
    result = []
    for obj in ElementTree.parse(xml).findall("object"):
        taxon, track = obj.findtext("name").rsplit("-", 1)
        box = [float(obj.findtext(f"bndbox/{side}"))
               for side in ("xmin", "ymin", "xmax", "ymax")]
        result.append({"label": taxon, "comparison_label": crosswalk[taxon],
                       "bbox": box, "track_id": int(track)})
    return result


def blind_frame(frame):
    record = {key: frame[key] for key in BLIND_KEYS}
    # The inference run predated recovery of the Ventana dive ID from older XML.
    record["dive_id"] = None
    return record


def verify_inputs(output, reference):
    expected = {"frames": [blind_frame(frame) for frame in reference["frames"]]}
    actual = json.loads((output / "manifest.json").read_text())
    check(actual == expected, "Blind manifest differs from the evaluation frame identities or metadata")
    frame_ids = [frame["frame_id"] for frame in actual["frames"]]
    check(len(set(frame_ids)) == len(frame_ids) == 16, "Expected 16 unique evaluation frames")
    for frame in actual["frames"]:
        check(file_hash(output / frame["path"]) == frame["sha256"],
              f"Staged image checksum mismatch: {frame['frame_id']}")
    print("Verified 16 original JPEG digests and a one-to-one blind/reference join.")


def stage(output, cache, reference, checksums, offline):
    frames = reference["frames"]
    archive = source_file(cache, "ecotype.zip", reference["datasets"][0]["source"],
                          checksums["ecotype.zip"], offline)
    with ZipFile(archive) as zipped:
        for frame in frames:
            if frame["sequence_id"] == "ooi-ecotype":
                jpeg = zipped.read(frame["archive_image"])
                annotations = ooi_annotations(frame, zipped.read(frame["archive_annotation"]))
            else:
                image = source_file(cache, frame["path"], frame["source"], frame["sha256"], offline)
                xml_key = f"reference/BS_{frame['frame_index']:03d}.xml"
                xml = source_file(cache, xml_key, frame["annotation_source"], checksums[xml_key], offline)
                jpeg = image.read_bytes()
                annotations = mbari_annotations(xml, reference["label_crosswalk"])

            check(hashlib.sha256(jpeg).hexdigest() == frame["sha256"], f"Invalid JPEG: {frame['id']}")
            check(annotations == frame["annotations"], f"Source annotations differ: {frame['id']}")
            replace_file(output / frame["path"], lambda stream: stream.write(jpeg))

    blind = {"frames": [blind_frame(frame) for frame in frames]}
    encoded = json.dumps(blind, indent=2).encode()
    replace_file(output / "manifest.json", lambda stream: stream.write(encoded))
    ref = (HERE / "reference.json").read_bytes()
    replace_file(output / "reference.json", lambda stream: stream.write(ref))
    total = sum(len(frame["annotations"]) for frame in frames)
    print(f"Reconstructed {total} source boxes and available track IDs from pinned YOLO and XML files.")


def stage_clips(output, cache, reference, checksums, offline):
    sources = {"ooi-ecotype": ("transect_compressed.mp4", 1024, 576, 232),
               "mbari-bs": ("BS.mov", 1280, 720, 480)}
    for dataset in reference["datasets"]:
        key, width, height, count = sources[dataset["id"]]
        original = source_file(cache, key, dataset["video_source"], checksums[key], offline)
        clip = output / dataset["clip"]
        clip.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=clip.parent, suffix=".mp4", delete=False) as tmp:
            temp_path = Path(tmp.name)
        try:
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(original),
                            "-map", "0:v:0", "-frames:v", str(count), "-an",
                            "-vf", f"scale={width}:{height},setsar=1", "-c:v", "libx264",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temp_path)], check=True)
            os.replace(temp_path, clip)
        finally:
            temp_path.unlink(missing_ok=True)
        print(f"Wrote {count} source frames to {clip}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="destination for images/ and the two manifests")
    parser.add_argument("--cache", type=Path, help="reusable source cache (default: OUTPUT/source-cache)")
    parser.add_argument("--offline", action="store_true", help="use verified local sources exclusively")
    parser.add_argument("--with-clips", action="store_true", help="also download the two movies and transcode excerpts using ffmpeg")
    parser.add_argument("--verify-only", action="store_true", help="check existing blind manifest and JPEGs against the git reference without network or writes")
    args = parser.parse_args()
    if args.verify_only and args.with_clips:
        parser.error("--verify-only checks frame inputs; --with-clips generates media")
    reference = json.loads((HERE / "reference.json").read_text())
    checksums = json.loads((HERE / "data_audit.json").read_text())["source_sha256"]
    cache = args.cache or args.output / "source-cache"
    if not args.verify_only:
        stage(args.output, cache, reference, checksums, args.offline)
    verify_inputs(args.output, reference)
    if args.with_clips:
        stage_clips(args.output, cache, reference, checksums, args.offline)


if __name__ == "__main__":
    main()
