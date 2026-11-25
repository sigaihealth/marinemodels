"""Join two sets of provisional ROI predictions for private review. Agreement does not measure accuracy."""

import argparse
import csv
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory


PREDICTION_FIELDS = {
    "whoi": ("roi_sha256", "label_1", "softmax_1"),
    "plankscope": ("image_sha256", "label", "confidence"),
}
OUTPUT_FIELDS = (
    "roi_id", "image_sha256", "whoi_label", "whoi_score", "plankscope_label",
    "plankscope_score", "whoi_group", "plankscope_group", "group_comparison", "review_status",
)


def read_rows(path, required):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        header = reader.fieldnames or []
        if len(header) != len(set(header)) or not set(required).issubset(header):
            raise ValueError(f"{path.name} needs distinct columns including {', '.join(required)}")
        for row in reader:
            if None in row or any(not (row[key] or "").strip() for key in required):
                raise ValueError(f"{path.name} has an incomplete or malformed row at line {reader.line_num}")
            yield reader.line_num, row


def predictions(path, source):
    hash_col, label_col, score_col = PREDICTION_FIELDS[source]
    required = [hash_col, label_col, score_col]
    if source == "whoi":
        required.append("roi_id")
    by_hash = {}
    roi_ids = set()
    for line, row in read_rows(path, required):
        digest = row[hash_col].strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or digest in by_hash:
            raise ValueError(f"{source} has an invalid or duplicate image checksum at line {line}")
        score = row[score_col]
        try:
            valid = 0 <= float(score) <= 1
        except ValueError:
            valid = False
        if not valid:
            raise ValueError(f"{source} score at line {line} must be a number between 0 and 1")
        roi_id = row["roi_id"] if source == "whoi" else ""
        if source == "whoi":
            if re.search(r"[/\\:\x00-\x1f]", roi_id) or roi_id in roi_ids:
                raise ValueError(f"WHOI needs a distinct ROI identifier without a file path at line {line}")
            roi_ids.add(roi_id)
        by_hash[digest] = (roi_id, row[label_col], score)
    if not by_hash:
        raise ValueError(f"{source} contains no predictions")
    return by_hash


def read_crosswalk(path):
    groups = {}
    for line, row in read_rows(path, ("source", "label", "group")):
        source = row["source"].strip().lower()
        key = (source, row["label"])
        if source not in PREDICTION_FIELDS or key in groups:
            raise ValueError(f"Unexpected source or duplicate source/label in crosswalk at line {line}")
        groups[key] = row["group"].strip()
    return groups


def compare(whoi_path, plankscope_path, crosswalk, output):
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Choose a new output file: {output.name}")
    whoi = predictions(whoi_path, "whoi")
    plankscope = predictions(plankscope_path, "plankscope")
    if whoi.keys() != plankscope.keys():
        raise ValueError(f"Unmatched image checksums: WHOI only {len(whoi.keys() - plankscope.keys())}, "
                         f"PlankScope only {len(plankscope.keys() - whoi.keys())}")
    groups = read_crosswalk(crosswalk) if crosswalk is not None else {}
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as staging:
        temporary = Path(staging) / "comparison.csv"
        with temporary.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(OUTPUT_FIELDS)
            for digest, (roi_id, left, left_score) in whoi.items():
                _, right, right_score = plankscope[digest]
                left_group = groups.get(("whoi", left), "")
                right_group = groups.get(("plankscope", right), "")
                status = "pending_crosswalk" if crosswalk is None else "unmapped"
                if left_group and right_group:
                    status = "agree" if left_group == right_group else "disagree"
                writer.writerow((roi_id, digest, left, left_score, right, right_score, left_group,
                                 right_group, status, "unreviewed_model_predictions"))
        temporary.chmod(0o600)
        os.link(temporary, output)
    return len(whoi)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--whoi", required=True, type=Path, help="WHOI gallery prediction CSV")
    parser.add_argument("--plankscope", required=True, type=Path, help="PlankScope standalone crop prediction CSV")
    parser.add_argument("--crosswalk", type=Path, help="optional CSV with source (whoi/plankscope), label, group")
    parser.add_argument("--output", required=True, type=Path, help="new private comparison CSV")
    args = parser.parse_args()
    try:
        count = compare(args.whoi, args.plankscope, args.crosswalk, args.output)
    except (ValueError, csv.Error, OSError) as exc:
        parser.exit(1, f"Comparison failed: {exc}\n")
    print(f"Matched {count} image pairs for private review.")
