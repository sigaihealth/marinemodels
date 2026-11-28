"""Normalize the source atlas data and render it into the page as static HTML and schema.org JSON-LD.

Crawlers and AI assistants that do not run JavaScript read the rendered list. The page script
replaces it with the same markup plus filtering. Run after editing site/assets/ocean-sources.json
or re-checking links with scripts/check_ocean_sources.py.
"""
import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site/assets/ocean-sources.json"
PAGE = ROOT / "site/ocean-sources.html"
URL = "https://ocean.sig.ai/ocean-sources.html"
STATUS = {
    "ok": ("Link answered", "ok"), "needs login": ("Account or access needed", "login"), "api": ("API endpoint", "api"),
    "broken": ("Not found", "bad"), "error": ("Server error", "warn"), "unreachable": ("No answer", "warn"),
    "no link": ("Not a web link", "warn"),
}


def licence_group(text):
    t = str(text or "").lower()
    if re.search(r"-nc|non-?commercial|nc-|academic|all rights|proprietary|permission", t):
        return "Non-commercial or restricted"
    if re.search(r"-sa|share-?alike|gpl", t) and "lgpl" not in t:
        return "Share-alike"
    if re.search(r"cc0|public domain|cc-by|cc by|mit|apache|bsd|eupl|copernicus|us government|open government|unrestricted|no restrictions", t):
        return "Open"
    return "Unclear"


def sign_up(text):
    t = str(text or "").lower()
    return "none" if t.startswith("none") else "restricted" if re.search(r"application|restricted", t) else "account"


def normalize(rows):
    for r in rows:
        r["lane_name"] = re.sub(r"^New lane:\s*", "", str(r.get("lane") or "Other"), flags=re.I)
        r["lane_slug"] = re.sub(r"[^a-z0-9]+", "-", r["lane_name"].lower()).strip("-")
        r["licence_group"] = licence_group(r.get("license"))
        r["sign_up"] = sign_up(r.get("registration"))
    return rows


def web(url):
    # This site's own API endpoints are not pages, so they are listed as text rather than links.
    return url if re.match(r"https?://", str(url or "")) and not str(url).startswith("https://ocean.sig.ai/api/") else ""


def entry(r):
    label, cls = STATUS.get((r.get("check") or {}).get("status"), ("Not checked", "warn"))
    check = r.get("check") or {}
    url, source = web(r.get("access_url")), web(r.get("source_url"))
    name = f'<a href="{escape(url)}" rel="noopener">{escape(r["name"])}</a>' if url else escape(r["name"])
    detail = lambda key, value: f"<dt>{key}</dt><dd>{value}</dd>" if value else ""
    status = (r.get("check") or {}).get("status") or "unchecked"
    data = (f'data-kind="{escape(r["kind"])}" data-licence="{escape(r["licence_group"])}" '
            f'data-signup="{r["sign_up"]}" data-status="{escape(status)}" data-status-label="{escape(label)}"')
    return "".join([
        f'<article class="source" {data}><div>',
        f"<h3>{name}</h3>",
        f'<p class="meta">{escape(" · ".join(x for x in (r.get("operator"), r.get("country_or_region")) if x))}</p>',
        f'<p class="desc">{escape(r.get("description") or "")}</p></div>',
        f'<div class="tags"><span class="tag">{escape(r["kind"])}</span><span class="tag">{escape(r["licence_group"])}</span>',
        f'<span class="tag {cls}">{escape(label)}</span></div>',
        "<details><summary>How to get it</summary><dl>",
        detail("Licence", escape(r.get("license") or "Unclear")),
        detail("Sign-up", escape(r.get("registration") or "Unknown")),
        detail("Access", escape(r.get("access_method") or "")),
        detail("Try it", f"<code>{escape(r['example_access'])}</code>" if r.get("example_access") else ""),
        detail("Link check", escape(label + (f" (HTTP {check['code']})" if check.get("code") else "") + (f", {check['date']}" if check.get("date") else ""))),
        detail("Source", f'<a href="{escape(source)}" rel="noopener">{escape(source)}</a>' if source else ""),
        "</dl></details></article>",
    ])


def render_list(rows):
    catalog = {l["name"]: l["slug"] for l in json.loads((ROOT / "site/assets/model-catalog.json").read_text(encoding="utf-8"))["lanes"]}
    groups = {}
    for r in rows:
        groups.setdefault(r["lane_name"], []).append(r)
    return "\n".join(
        f'<section class="sources-lane" id="{escape(items[0]["lane_slug"])}"><h2>{escape(name)} <span>{len(items)}</span></h2>'
        + (f'<p class="lane-tested"><a href="model-catalog.html#{escape(catalog[name])}">Tested models for this task in the model workspace</a></p>' if name in catalog else "")
        + "".join(entry(r) for r in items) + "</section>"
        for name, items in sorted(groups.items()))


def render_stats(rows):
    kinds = Counter(r["kind"] for r in rows)
    cells = [(len(rows), "Sources"), *[(n, k + "s") for k, n in kinds.most_common()],
             (sum((r.get("check") or {}).get("status") == "ok" for r in rows), "Links answered"),
             (sum(r["licence_group"] == "Open" for r in rows), "Open licence"),
             (sum(r["sign_up"] == "none" for r in rows), "No sign-up")]
    return "".join(f"<div><b>{n:,}</b><span>{escape(label)}</span></div>" for n, label in cells)


def json_ld(rows):
    date = next(((r.get("check") or {}).get("date") for r in rows if (r.get("check") or {}).get("date")), None)
    datasets = []
    for r in rows:
        if r["kind"] not in ("dataset", "benchmark"):
            continue
        item = {"@type": "Dataset", "name": r["name"], "description": r.get("description") or r["name"]}
        if web(r.get("access_url")):
            item["url"] = r["access_url"]
        if web(r.get("source_url")) and r.get("source_url") != r.get("access_url"):
            item["sameAs"] = r["source_url"]
        if r.get("license"):
            item["license"] = r["license"]
        if r.get("operator"):
            item["creator"] = {"@type": "Organization", "name": r["operator"]}
        item["isAccessibleForFree"] = r["sign_up"] != "restricted"
        datasets.append(item)
    data = {"@context": "https://schema.org", "@type": "DataCatalog", "@id": URL, "url": URL,
            "name": "SIG.AI Ocean source atlas",
            "description": f"{len(rows)} marine datasets, AI models, benchmarks and data services with licences, sign-up requirements and dated link checks.",
            "publisher": {"@type": "Organization", "name": "SIG.AI", "url": "https://sig.ai"},
            "distribution": {"@type": "DataDownload", "encodingFormat": "application/json",
                             "contentUrl": "https://ocean.sig.ai/assets/ocean-sources.json"},
            **({"dateModified": date} if date else {}), "dataset": datasets}
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{text}</script>'


def replace(source, marker, content):
    start, end = f"<!-- {marker}:start -->", f"<!-- {marker}:end -->"
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError(f"Expected one {marker} block in {PAGE.name}")
    head, rest = source.split(start)
    return head + start + "\n" + content + "\n" + end + rest.split(end, 1)[1]


def main():
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--check", action="store_true", help="fail if the data or page would change")
    args = cli.parse_args()
    raw = DATA.read_text(encoding="utf-8")
    rows = normalize(json.loads(raw))
    data = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    page = PAGE.read_text(encoding="utf-8")
    rendered = replace(replace(replace(page, "ocean-sources-stats", render_stats(rows)),
                               "ocean-sources-list", render_list(rows)), "ocean-sources-jsonld", json_ld(rows))
    if args.check:
        stale = [name for name, old, new in ((DATA.name, raw, data), (PAGE.name, page, rendered)) if old != new]
        if stale:
            print("Out of date: " + ", ".join(stale) + ". Run python3 scripts/sync_ocean_sources.py.")
            return 1
    else:
        DATA.write_text(data, encoding="utf-8")
        PAGE.write_text(rendered, encoding="utf-8")
    print(f"Source atlas in sync: {len(rows)} sources rendered into {PAGE.name} ({len(rendered.encode()) // 1024} KB).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
