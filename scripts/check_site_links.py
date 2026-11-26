#!/usr/bin/env python3
"""Check static links, catalog actions and two-way navigation from the Ocean home page."""

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


ORIGIN = "https://ocean.sig.ai/"
HOME = "index.html"


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.anchors = set()
        self.references = []
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.anchors.add(attrs["id"])
        if tag == "a" and attrs.get("name"):
            self.anchors.add(attrs["name"])
        if tag in {"a", "area", "link"}:
            key = "href"
        elif tag in {"script", "img", "iframe", "video", "audio", "source"}:
            key = "src"
        else:
            return
        if attrs.get(key):
            self.references.append((attrs[key], tag in {"a", "area"}))


def reachable(graph):
    visited = set()
    pending = [HOME]
    while pending:
        name = pending.pop()
        if name not in visited:
            visited.add(name)
            pending.extend(graph[name] - visited)
    return visited


def audit(root):
    root = root.resolve()
    pages = {
        path.relative_to(root).as_posix(): Page(path.read_text(encoding="utf-8"))
        for path in sorted(root.rglob("*.html"))
    }
    if HOME not in pages:
        raise ValueError(f"Missing {root / HOME}")
    catalog = json.loads((root / "assets/model-catalog.json").read_text(encoding="utf-8"))
    catalog_page = pages["model-catalog.html"]
    catalog_page.anchors.update(lane["slug"] for lane in catalog["lanes"])
    for entry in [*catalog["lanes"], *catalog["models"]]:
        for key in ("actionUrl", "reference", "source", "artifact"):
            if entry.get(key):
                catalog_page.references.append((entry[key], True))

    graph = {name: set() for name in pages}
    inbound = {name: set() for name in pages}
    errors = set()
    local_references = 0
    for source, page in pages.items():
        for href, navigable in page.references:
            url = urlsplit(urljoin(urljoin(ORIGIN, source), href))
            if url.scheme not in {"http", "https"} or url.hostname != "ocean.sig.ai":
                continue
            local_references += 1
            name = unquote(url.path).lstrip("/")
            if not name or name.endswith("/"):
                name += HOME
            path = (root / name).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                errors.add(f"{source} -> {href}: missing file in site/")
                continue
            name = path.relative_to(root).as_posix()
            if name in pages:
                if navigable:
                    graph[source].add(name)
                    inbound[name].add(source)
                if url.fragment and unquote(url.fragment) not in pages[name].anchors:
                    errors.add(f"{source} -> {href}: unknown fragment")
    for name in pages.keys() - reachable(graph):
        errors.add(f"{name}: unreachable from {HOME}")
    for name in pages.keys() - reachable(inbound):
        errors.add(f"{name}: no route back to {HOME}")
    return len(pages), local_references, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[1] / "site")
    args = parser.parse_args()
    count, references, errors = audit(args.site)
    if errors:
        for error in sorted(errors):
            print(error)
        return 1
    print(f"Checked {count} pages and {references} internal references. All pages connect to and from home.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
