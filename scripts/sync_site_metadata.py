"""Sync search and sharing metadata from each published page's title and description."""
import argparse
from html import escape
from html.parser import HTMLParser
import re
import sys
from xml.etree import ElementTree

from sync_navigation import PAGES, SITE, replace_section

ORIGIN = "https://ocean.sig.ai"
START = "<!-- ocean-sharing:start -->"
END = "<!-- ocean-sharing:end -->"
IMAGE = ORIGIN + "/assets/ocean-share.jpg"
IMAGE_ALT = "SIG.AI Ocean research workspaces with an illustrated ocean cross-section."


# Offline report builders supply their own titles. Give the hosted editions descriptive metadata.
REPORT_PAGES = {
    "pioneer_playback": (
        "Pioneer storm playback",
        "Move through Pioneer water samples during Winter Storm Gianna and compare plankton imagery with measurements from the mooring.",
    ),
    "visual-transect": (
        "Underwater transect review",
        "Inspect underwater video frames, animal detections and segmentation masks, and follow individual tracks through a camera sequence.",
    ),
    "v4277": (
        "Ventana V4277 detector comparison",
        "Compare two animal detectors with expert annotations from an ROV Ventana dive and inspect missed animals in the original frames.",
    ),
}


class Head(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.in_title = False
        self.title = ""
        self.descriptions = []
        self.feed(source.split("</head>", 1)[0])

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "meta" and fields.get("name") == "description":
            self.descriptions.append(fields.get("content", ""))

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, value):
        if self.in_title:
            self.title += value


def canonical(slug):
    return ORIGIN + ("/" if slug == "index" else f"/{slug}.html")


def render_page(slug, source):
    if slug in REPORT_PAGES:
        title, description = REPORT_PAGES[slug]
        before, after = source.split("</head>", 1)
        before, matches = re.subn(r"<title>.*?</title>", f"<title>{title} · SIG.AI Ocean</title>",
                                  before, count=1, flags=re.DOTALL)
        if matches != 1:
            raise ValueError(f"{slug} has no HTML title")
        if not Head(before).descriptions:
            before += f'<meta name="description" content="{escape(description, quote=True)}">\n'
        source = before + "</head>" + after
    head = Head(source)
    if not head.title.endswith(" · SIG.AI Ocean") or len(head.descriptions) != 1 or not head.descriptions[0]:
        raise ValueError(f"{slug} needs a branded title and one meta description")
    url = canonical(slug)
    tags = ['<link rel="icon" href="/favicon.ico" type="image/x-icon">',
            f'<link rel="canonical" href="{url}">']
    properties = {"og:type": "website", "og:site_name": "SIG.AI Ocean", "og:title": head.title,
                  "og:description": head.descriptions[0], "og:url": url, "og:image": IMAGE,
                  "og:image:width": "1200", "og:image:height": "630", "og:image:alt": IMAGE_ALT,
                  "twitter:card": "summary_large_image", "twitter:title": head.title,
                  "twitter:description": head.descriptions[0], "twitter:image": IMAGE,
                  "twitter:image:alt": IMAGE_ALT}
    for key, value in properties.items():
        attr = "property" if key.startswith("og:") else "name"
        tags.append(f'<meta {attr}="{key}" content="{escape(value, quote=True)}">')
    if START not in source:
        source = source.replace("</head>", f"{START}\n{END}\n</head>", 1)
    return replace_section(source, "ocean-sharing", "\n".join(tags))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    sitemap = ElementTree.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    outputs = {}
    for slug in sorted(PAGES.keys() - {"404"}, key=lambda s: (s != "index", s)):
        page = SITE / f"{slug}.html"
        outputs[page] = render_page(slug, page.read_text())
        ElementTree.SubElement(ElementTree.SubElement(sitemap, "url"), "loc").text = canonical(slug)
    ElementTree.indent(sitemap)
    outputs[SITE / "sitemap.xml"] = ElementTree.tostring(sitemap, encoding="unicode") + "\n"
    changes = [path for path, expected in outputs.items() if not path.exists() or path.read_text() != expected]
    if args.check and changes:
        sys.exit("Metadata needs regeneration: " + ", ".join(path.name for path in changes))
    for path in changes:
        path.write_text(outputs[path])
    print(f"Search and sharing metadata in sync for {len(sitemap)} canonical pages.")


if __name__ == "__main__":
    main()
