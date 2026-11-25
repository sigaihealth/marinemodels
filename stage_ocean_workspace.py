"""Download and verify the pinned IFCB dataset and WHOI classifier in a research workspace."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen


def stage_file(root, record):
    path = root / record["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size == record["bytes"]:
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() == record["sha256"]:
                print("Verified", path.name, flush=True)
                return
    for attempt in range(3):
        with tempfile.TemporaryDirectory(dir=path.parent) as temporary:
            partial = Path(temporary) / "download"
            try:
                digest = hashlib.sha256()
                with urlopen(record["url"], timeout=90) as response, partial.open("wb") as out:
                    while chunk := response.read(1024 * 1024):
                        digest.update(chunk)
                        out.write(chunk)
                if partial.stat().st_size != record["bytes"] or digest.hexdigest() != record["sha256"]:
                    raise ValueError(f"Downloaded data failed verification for {path.name}")
                partial.replace(path)
                print("Staged", path.name, flush=True)
                return
            except (URLError, TimeoutError, ConnectionError, ValueError):
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / "data/ocean-platform")
    args = parser.parse_args()
    records = json.loads(Path(__file__).with_name("workspace_sources.json").read_text())["files"]
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda record: stage_file(args.root, record), records))
    print(f"Verified {len(records)} source files in {args.root}", flush=True)
