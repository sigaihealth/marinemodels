#!/usr/bin/env python3
"""Prepare a bin-disjoint, class-balanced pilot from the pinned WHOI IFCB release.

Requires Python 3.10+, Pillow and PyArrow. Pass --all-shards for the ten-label
pilot. A local --source-dir is read-only and must contain the named parquet files.
"""

import argparse
import csv
import datetime as dt
import hashlib
import http.client
import io
import json
import os
import re
import tempfile
import time
import urllib.request
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image


DATASET = "https://huggingface.co/datasets/sosiklab/NES-plankton-IFCB-classifier-2022-dataset"
REVISION = "89b22c10739e8ef91bde18e7d5a81c21edddba9b"
SHARDS = {
    "train-00000.parquet": (173506602, "5a0be6cc63dfd76a42f360a9fc885aa90dd7bddd4237b91bf846ea08bb5a4288"),
    "train-00001.parquet": (135519938, "a8295b0d9fe9f081145a4f1478ca5c8a963ef6604c3c4e80203cca4b1ca17d5a"),
    "train-00002.parquet": (232731004, "6e49a5643f3408da311d38048a4fb943985bf299b392f8ae107af29bea37c221"),
    "train-00003.parquet": (159815256, "4ab12255537a58a3a228d16efcb75392b51de7113996c0bb73e61d127d252596"),
    "train-00004.parquet": (214047859, "df6666c3a0d9a8802917a219a5da78aa04c911982e7bb25ccace282f8708c31c"),
    "train-00005.parquet": (175044871, "83113aa02e82664d3d1da79a290c7d49bbe1ae08376685c198eb9973d42bb4eb"),
    "train-00006.parquet": (122570436, "a9e92b0cd09310e34787155be997c0a7083e07e7c039003bbadc3220593b978a"),
    "train-00007.parquet": (46288845, "34e34ee0065048f61eead8fce95d12fc9b60324a15dc06ce6827b93674252127"),
    "validation-00000.parquet": (177038896, "a50922b015c5e28f72e5a1c9bdace4f9530ff581f971b66655aca2ccae8e225d"),
    "validation-00001.parquet": (139780602, "581a46570592e30e9ab310e2cb57c7fe8d81ef7dad12592474041edb918a203c"),
}
QUICK = ("Amphidinium", "Asterionellopsis_glacialis", "Balanion",
         "Cerataulina_pelagica", "Chaetoceros", "Tripos_lineatus")
EXPANDED = ("Balanion", "Dictyocha", "Guinardia_delicatula", "Mesodinium", "Pseudo-nitzschia",
            "Thalassiosira", "Tripos_lineatus", "detritus", "flagellate", "nanoplankton_mix")
FIELDS = ("path", "label", "split", "group", "roi_id", "sha256", "pixel_sha256", "source_shard", "source_row")
MODERN = re.compile(r"(D\d{8}T\d{6}_IFCB\d{3})_(\d+)")
LEGACY = re.compile(r"IFCB(\d+)_(\d{4})_(\d{3})_(\d{6})_(\d+)")


def source_bin(pid):
    modern = MODERN.fullmatch(pid)
    if modern:
        return modern[1], int(modern[2])
    legacy = LEGACY.fullmatch(pid)
    if legacy:
        date = dt.datetime.strptime(legacy[2] + legacy[3], "%Y%j")
        return f"D{date:%Y%m%d}T{legacy[4]}_IFCB{int(legacy[1]):03d}", int(legacy[5])
    return None


def content_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verified(path, spec):
    return path.is_file() and path.stat().st_size == spec[0] and content_hash(path) == spec[1]


def get_shard(path, local_only):
    spec = SHARDS[path.name]
    if verified(path, spec):
        return
    if local_only:
        raise ValueError(f"Missing or incorrect pinned source shard: {path}")
    url = f"{DATASET}/resolve/{REVISION}/data/{path.name}?download=true"
    error = None
    for attempt in range(3):
        try:
            with tempfile.TemporaryDirectory(dir=path.parent) as stage:
                temporary = Path(stage) / path.name
                with urllib.request.urlopen(url, timeout=90) as response, temporary.open("wb") as out:
                    while block := response.read(1024 * 1024):
                        out.write(block)
                        if out.tell() > spec[0]:
                            raise OSError("download exceeded its published size")
                if not verified(temporary, spec):
                    raise OSError("download failed its SHA-256 or byte count")
                os.replace(temporary, path)
            return
        except (OSError, http.client.HTTPException) as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise OSError(f"Could not verify {path.name} after three download attempts") from error


def bin_split(group):
    number = int.from_bytes(hashlib.sha256(group.encode()).digest()[:4], "big")
    return "validation" if number % 5 == 0 else "train"


def collect(paths, labels):
    candidates = defaultdict(list)
    stats = Counter()
    for path in paths:
        split = path.name.split("-")[0]
        offset = 0
        columns = ["classname", "ifcb_roi_pid", "image"]
        for batch in pq.ParquetFile(path).iter_batches(batch_size=128, columns=columns):
            for row in batch.to_pylist():
                index = offset
                offset += 1
                label = row["classname"]
                if label not in labels:
                    continue
                pid = row["ifcb_roi_pid"] or ""
                identity = source_bin(pid)
                if not identity:
                    stats["unparsed_selected_class_rows"] += 1
                    continue
                group, _ = identity
                if bin_split(group) == split:
                    rank = hashlib.sha256(("whoi-nes-v1|" + pid).encode()).digest()
                    candidates[split, label].append((rank, path.name, index, identity, pid, row["image"]["bytes"]))
        stats["source_rows_scanned"] += offset
    return candidates, stats


def write_selected(stage, candidates, labels, quotas):
    records = []
    seen_ids, seen_pixels = set(), set()
    used_groups = defaultdict(set)
    for split, count in quotas.items():
        folder = stage / "images" / split
        folder.mkdir(parents=True)
        for label in labels:
            groups = set()
            for _, name, index, identity, pid, raw in sorted(candidates[split, label], key=lambda row: row[:3]):
                group, _ = identity
                if identity in seen_ids or group in groups:
                    continue
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format != "PNG" or image.mode != "L":
                        raise ValueError(f"Unexpected image format for {pid}")
                    pixel_hash = hashlib.sha256(
                        f"L:{image.width}x{image.height}:".encode() + image.tobytes()
                    ).hexdigest()
                if pixel_hash in seen_pixels:
                    continue
                digest = hashlib.sha256(raw).hexdigest()
                relative = f"images/{split}/{digest}.png"
                (stage / relative).write_bytes(raw)
                records.append({
                    "path": relative, "label": label, "split": split, "group": group,
                    "roi_id": pid, "sha256": digest, "pixel_sha256": pixel_hash,
                    "source_shard": name, "source_row": index,
                })
                seen_pixels.add(pixel_hash)
                seen_ids.add(identity)
                groups.add(group)
                if len(groups) == count:
                    break
            if len(groups) != count:
                raise ValueError(f"{split}/{label} has only {len(groups)} eligible distinct bins, expected {count}")
            used_groups[split].update(groups)
    if used_groups["train"] & used_groups["validation"]:
        raise ValueError("A source bin appears in both splits")
    return records, {split: len(groups) for split, groups in used_groups.items()}


@contextmanager
def preparation_lock(output):
    # Linux JupyterHub and macOS support advisory locks that release on process exit.
    import fcntl
    with (output / ".prepare.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def prepare(output, source_dir, all_shards):
    labels = EXPANDED if all_shards else QUICK
    quotas = {"train": 128, "validation": 25} if all_shards else {"train": 40, "validation": 12}
    names = list(SHARDS) if all_shards else ["train-00000.parquet", "validation-00000.parquet"]
    mode = "expanded" if all_shards else "quick"
    output.mkdir(parents=True, exist_ok=True)
    with preparation_lock(output):
        info_path = output / "provenance.json"
        manifest = output / "manifest.csv"
        if info_path.exists():
            old = json.loads(info_path.read_text())
            if (old.get("dataset_revision"), old.get("pilot_mode"), old.get("selection_version")) != (REVISION, mode, 1):
                raise ValueError("This directory contains a different dataset or pilot. Choose a new output directory.")
        elif manifest.exists() or (output / "images").exists():
            raise ValueError("This output already contains images or a manifest without matching provenance.")
        source = source_dir if source_dir is not None else output / "source_cache"
        if source_dir is None:
            source.mkdir(exist_ok=True)
        paths = [source / name for name in names]
        for path in paths:
            get_shard(path, local_only=source_dir is not None)
        candidates, stats = collect(paths, set(labels))
        with tempfile.TemporaryDirectory(dir=output, prefix=".prepare-") as tmp:
            stage = Path(tmp)
            rows, groups = write_selected(stage, candidates, labels, quotas)
            with (stage / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            provenance = {
                "dataset": DATASET, "dataset_revision": REVISION, "pilot_mode": mode, "selection_version": 1,
                "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "attribution": "Heidi M. Sosik, Emily E. Peacock, Sidney Batchelder and Joe Futrelle (2026), Woods Hole Oceanographic Institution.",
                "doi": "https://doi.org/10.57967/hf/10839", "dataset_card": f"{DATASET}/blob/{REVISION}/README.md",
                "changes": "A class-balanced selection of original grayscale PNGs. Filenames were replaced by content hashes; pixel data and original labels are preserved.",
                "selection": "Preserve source split. Assign canonical IFCB bin to validation if SHA-256(bin) first four bytes as a big-endian integer modulo five equals zero, else train. Within each split and class, rank eligible ROI IDs by SHA-256('whoi-nes-v1|' + native ROI ID). Skip repeated canonical ROI IDs, decoded pixel content and repeated class/bin pairs.",
                "limitations": "Six selected labels in the first train/validation shards." if not all_shards else "Ten selected labels from all ten published shards.",
                "scientific_scope": "Balanced pilot counts are unsuitable for estimating natural prevalence. Bins are disjoint; cruises, dates and instruments can recur across folds. Performance on Pioneer requires independent local labels. The released WHOI classifier trained on source training images.",
                "labels": labels, "images_per_label": quotas, "distinct_bins": groups,
                "image_count": len(rows), "manifest_sha256": content_hash(stage / "manifest.csv"),
                "source_row_indexing": "Zero-based physical row within the named source parquet.",
                "pixel_sha256_definition": "SHA-256 of UTF-8 L:<width>x<height>: followed by original row-major uint8 grayscale pixels.",
                "source_shards": {n: {"bytes": SHARDS[n][0], "sha256": SHARDS[n][1]} for n in names},
                **stats,
            }
            (stage / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
            # Publish the manifest last. Content-addressed files make retries safe.
            os.replace(stage / "provenance.json", info_path)
            for split in quotas:
                (output / "images" / split).mkdir(parents=True, exist_ok=True)
            for row in rows:
                os.replace(stage / row["path"], output / row["path"])
            os.replace(stage / "manifest.csv", manifest)
    return manifest, len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Directory for manifest, provenance and images")
    parser.add_argument("--source-dir", type=Path, help="Use local pinned parquet shards instead of downloading")
    parser.add_argument("--all-shards", action="store_true", help="Select 1,530 images across ten labels; default: 312 across six")
    args = parser.parse_args()
    manifest, count = prepare(args.output.expanduser(), args.source_dir.expanduser() if args.source_dir else None, args.all_shards)
    print(f"Verified and prepared {count} images: {manifest}")


if __name__ == "__main__":
    main()
