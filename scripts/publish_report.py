"""Build the public web edition of a portable scientific report, using its recorded data."""

import argparse
import base64
import hashlib
from html import escape
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
REPORTS = {
    "visual-transect": ("transect/review.html.in", "{{DATA}}", "payload"),
    "v4277": ("transect/v4277/review.html.in", "__V4277_BUNDLE__", "payload"),
    "pioneer_playback": ("pioneer_playback.html.in", "__REPLAY_JSON__", "data"),
}
EXTENSIONS = {"data:image/jpeg;base64": "jpg", "data:image/png;base64": "png", "data:video/mp4;base64": "mp4"}


def web_media(page, data, site):
    directory = site / "assets" / "reports" / page
    directory.mkdir(parents=True, exist_ok=True)

    def asset(uri):
        header, encoded = uri.split(",", 1)
        content = base64.b64decode(encoded, validate=True)
        digest = hashlib.sha256(content).hexdigest()[:16]
        path = directory / f"{digest}.{EXTENSIONS[header]}"
        path.write_bytes(content)
        return path.relative_to(site).as_posix()

    if page == "visual-transect":
        for frame in data["frames"]:
            frame["src"] = asset(frame["src"])
            for observation in frame["observations"]:
                if observation.get("mask"):
                    observation["mask"] = asset(observation["mask"])
        data["clips"] = {key: asset(uri) for key, uri in data["clips"].items()}
        return "frame", data["frames"][0]["src"]
    if page == "v4277":
        for frame in data["images"].values():
            frame["image"] = asset(frame["image"])
        for cases in data["groups"].values():
            for case in cases:
                case["crop"]["image"] = asset(case["crop"]["image"])
        # Use the same order as the viewer's case selector.
        for group in ("neither", "ecotype_only", "megalodon_only", "both", "ecotype_unmatched", "megalodon_unmatched"):
            if data["groups"][group]:
                first = data["groups"][group][0]
                return "photo", data["images"][first["frame_id"]]["image"]
    else:
        for sample in data["pictures"]:
            for crop in sample["crops"]:
                crop["png"] = asset(crop["png"])
    return None


def publish(page, source, site):
    template, token, payload_id = REPORTS[page]
    tag = f'<script id="{payload_id}" type="application/json">'
    report = source.read_text(encoding="utf-8")
    if report.count(tag) != 1:
        raise ValueError(f"Expected one {payload_id} data block in the portable {page} report")
    data = json.loads(report.split(tag, 1)[1].split("</script>", 1)[0])
    first_frame = web_media(page, data, site)
    html = (ROOT / template).read_text(encoding="utf-8")
    if first_frame:
        image_id, url = first_frame
        html = html.replace(f'<img id="{image_id}"', f'<img id="{image_id}" src="{url}" fetchpriority="high"')
    # The portable templates include their styles. The public edition caches
    # those styles independently and loads the same typefaces as other pages.
    style = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
    css_path = site / "assets" / f"{page}.css"
    css_path.write_text(style.group(1).strip() + "\n", encoding="utf-8")
    stylesheets = f'<link rel="stylesheet" href="assets/ocean.css">\n<link rel="stylesheet" href="assets/{page}.css">'
    html = html[:style.start()] + stylesheets + html[style.end():]
    html = re.sub(r"(<!-- ocean-nav-style:start -->).*?(<!-- ocean-nav-style:end -->)",
                  r'\1\n<link rel="stylesheet" href="assets/navigation.css">\n\2', html, flags=re.DOTALL)
    # Site-local links continue to work on preview hosts and under local HTTP.
    html = html.replace('href="https://ocean.sig.ai/"', 'href="./"').replace('href="https://ocean.sig.ai/', 'href="')
    payload = json.dumps(data, ensure_ascii=True, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    html = html.replace("{{REPORT_TITLE}}", escape(data.get("title", ""))).replace(token, payload)
    (site / f"{page}.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("page", choices=REPORTS)
    cli.add_argument("report", type=Path, help="self-contained HTML file produced by the scientific report builder")
    cli.add_argument("--site", type=Path, default=ROOT / "site")
    args = cli.parse_args()
    publish(args.page, args.report, args.site)
