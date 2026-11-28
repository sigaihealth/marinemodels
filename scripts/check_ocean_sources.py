"""Re-check the access link of every entry in the source atlas and record the result in place."""
import argparse
import concurrent.futures as cf
import json
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SOURCES = Path(__file__).resolve().parents[1] / "site/assets/ocean-sources.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ocean-sources-linkcheck/1.0)"}
HOSTS = defaultdict(threading.Lock)  # one request at a time per host


def probe(url):
    if not str(url).startswith(("http://", "https://")):
        return {"status": "no link"}
    with HOSTS[urlsplit(url).hostname]:
        for method in ("HEAD", "GET"):
            headers = dict(HEADERS, **({"Range": "bytes=0-1023"} if method == "GET" else {}))
            try:
                with urllib.request.urlopen(urllib.request.Request(url, method=method, headers=headers), timeout=25) as response:
                    return {"status": "ok", "code": response.status}
            except urllib.error.HTTPError as error:
                if method == "HEAD" and error.code in (400, 403, 404, 405, 501):
                    continue  # some servers refuse HEAD; ask again with GET
                if error.code in (400, 405, 406):
                    return {"status": "api", "code": error.code}  # endpoints that accept programmatic requests only
                status = "needs login" if error.code in (401, 403) else "broken" if error.code in (404, 410) else "error"
                return {"status": status, "code": error.code}
            except Exception:
                if method == "GET":
                    return {"status": "unreachable"}
            finally:
                time.sleep(0.5)
    return {"status": "unreachable"}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sources", type=Path, default=SOURCES)
    args = cli.parse_args()
    rows = json.loads(args.sources.read_text(encoding="utf-8"))
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with cf.ThreadPoolExecutor(16) as pool:
        results = list(pool.map(lambda row: probe(row.get("access_url")), rows))
    for row, result in zip(rows, results):
        row["check"] = result | {"date": date}
    args.sources.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Checked {len(rows)} sources on {date}: {dict(Counter(r['status'] for r in results))}")


if __name__ == "__main__":
    main()
