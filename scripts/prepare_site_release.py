"""Stage the Ocean website and its versioned public assets in the existing Vercel project."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

SITE = Path(__file__).resolve().parents[1] / "site"
CACHE = "public, max-age=31536000, immutable"
# Include this build transform in the bundle fingerprint so a URL always identifies the same bytes.
ASSET_START = re.compile(r"""(?P<quote>["'`])(?P<origin>https://ocean\.sig\.ai)?/?assets/(?!reports/)""")
STATIC_EXTENSIONS = {".js", ".mjs", ".css", ".json"}
REPORT_NAME = re.compile(r"([a-f0-9]{16})\.(jpg|png|mp4)")


def versioned_references(source, prefix):
    def rewrite(match):
        return match["quote"] + (match["origin"] or "") + prefix
    return ASSET_START.sub(rewrite, source)


def version_assets(public):
    assets = SITE / "assets"
    digest = hashlib.sha256(Path(__file__).read_bytes())
    ordinary = []
    for path in sorted(p for p in assets.rglob("*") if p.is_file()):
        name = path.relative_to(assets)
        raw = path.read_bytes()
        if name.parts[0] == "reports":
            match = REPORT_NAME.fullmatch(name.name)
            if not match or hashlib.sha256(raw).hexdigest()[:16] != match[1]:
                raise ValueError(f"Report asset does not match its content hash: {name}")
            continue
        ordinary.append((name, path))
        digest.update(name.as_posix().encode() + b"\0" + hashlib.sha256(raw).digest())
    version = digest.hexdigest()[:24]
    prefix = f"/_static/{version}/"
    target = public / "_static" / version
    for name, path in ordinary:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in STATIC_EXTENSIONS:
            dest.write_text(versioned_references(path.read_text(), prefix))
        else:
            shutil.copyfile(path, dest)
    return prefix


def merge_rule(rules, rule):
    previous = next((item for item in rules if item["source"] == rule["source"]), None)
    if previous is None:
        rules.append(rule)
    elif previous != rule:
        raise ValueError(f"Resolve existing Vercel rule for {rule['source']} before publishing")


def stage(release):
    config_path = release / "vercel.json"
    config = json.loads(config_path.read_text())
    if config.get("outputDirectory") != "public":
        raise ValueError("Expected the existing static Vercel outputDirectory public")
    public = release / "public"
    if public.resolve().is_relative_to(SITE):
        raise ValueError("Stage outside the site source directory")
    # Keep stable URLs for external publications, source downloads and existing bookmarks.
    shutil.copytree(SITE, public, dirs_exist_ok=True)
    prefix = version_assets(public)
    for page in SITE.glob("*.html"):
        (public / page.name).write_text(versioned_references(page.read_text(), prefix))
    for source in ("/_static/:path*", "/assets/reports/:path*"):
        merge_rule(config.setdefault("headers", []), {
            "source": source, "headers": [{"key": "Cache-Control", "value": CACHE}],
        })
    merge_rule(config.setdefault("redirects", []), {"source": "/index.html", "destination": "/", "permanent": True})
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Staged public assets at {prefix} with immutable caching.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True, help="linked hosting project with vercel.json")
    stage(parser.parse_args().release)
