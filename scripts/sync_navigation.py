"""Render the common navigation into the static site and its standalone report templates."""

import argparse
from html import escape
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PRIMARY = ("world-model", "model-catalog", "plankton-lab", "field-studies", "collaborate")
# Titles and immediate parents define the places visitors can browse.
PAGES = {
    "index": ("Home", None),
    "404": ("Page not found", None),
    "world-model": ("World model", "index"),
    "model-catalog": ("Model workspace", "index"),
    "plankton-lab": ("Plankton lab", "index"),
    "field-studies": ("Field studies", "index"),
    "collaborate": ("Contribute", "index"),
    "sigai-plankton": ("SIG.AI Plankton Classifier", "plankton-lab"),
    "plankscope": ("PlankScope comparison", "plankton-lab"),
    "try-mobilenet": ("MobileNet classifier", "plankton-lab"),
    "try-plankton": ("WHOI classifier", "plankton-lab"),
    "try-trained-plankton": ("Morphology baseline", "plankton-lab"),
    "try-ocean-color": ("Ocean color", "model-catalog"),
    "try-forecast": ("GLONET forecast explorer", "model-catalog"),
    "pioneer-storm": ("Pioneer storm study", "field-studies"),
    "pioneer_playback": ("Storm playback", "pioneer-storm"),
    "visual-transect": ("Underwater transect review", "field-studies"),
    "v4277": ("Ventana V4277", "field-studies"),
}
CATALOG_LANES = {"try-forecast": "ocean-physics", "try-ocean-color": "satellite"}
SECTION_LINKS = {
    "world-model": (("Water column", "water-column"), ("Field evidence", "wm-evidence"), ("Forecast design", "forecast")),
    "pioneer-storm": (("Observations", "observations"), ("Pioneer models", "models"), ("Roadmap", "roadmap")),
}
REPORT_TEMPLATES = {
    "pioneer_playback": ROOT / "pioneer_playback.html.in",
    "visual-transect": ROOT / "transect/review.html.in",
    "v4277": ROOT / "transect/v4277/review.html.in",
}
STANDALONE = {"world-model", *REPORT_TEMPLATES}
STYLES = SITE / "assets/navigation.css"


def link(page, base, current=None, fragment=None):
    label = escape(PAGES[page][0])
    filename = "" if page == "index" else page + ".html"
    href = base + filename if base or filename else "./"
    if fragment:
        href += "#" + fragment
    state = f' aria-current="{current}"' if current else ""
    return f'<a href="{href}"{state}>{label}</a>'


def navigation(page, standalone=False):
    # An error page can render at a nested request path. Portable reports can open from disk.
    base = "https://ocean.sig.ai/" if standalone else "/" if page == "404" else ""
    ancestors = []
    parent = PAGES[page][1]
    while parent and parent != "index":
        ancestors.insert(0, parent)
        parent = PAGES[parent][1]

    home_current = ' aria-current="page"' if page == "index" else ""
    lines = ['<div class="ocean-header"><div class="ocean-bar">',
             f'  <a class="ocean-brand" href="{base or "./"}" aria-label="SIG.AI Ocean home"{home_current}>SIG.AI<span>Ocean</span></a>',
             '  <nav aria-label="Main navigation">']
    for dest in PRIMARY:
        current = "page" if dest == page else "location" if dest in ancestors else None
        lines.append("    " + link(dest, base, current))
    lines.extend(['  </nav>', '</div></div>'])

    if ancestors or page in SECTION_LINKS:
        lines.append('<div class="ocean-context"><div class="ocean-bar">')
        if ancestors:
            entries = [link(ancestor, base, fragment=CATALOG_LANES.get(page)) for ancestor in ancestors]
            entries.append(f'<span class="ocean-current" aria-current="page">{escape(PAGES[page][0])}</span>')
            separator = ' <span class="ocean-separator" aria-hidden="true">/</span> '
            lines.append('  <nav aria-label="Breadcrumb">' + separator.join(entries) + '</nav>')
        if page in SECTION_LINKS:
            choices = [f'<a href="#{fragment}">{label}</a>' for label, fragment in SECTION_LINKS[page]]
            lines.append('  <nav aria-label="On this page"><span class="ocean-local-label">On this page</span> ' + " ".join(choices) + '</nav>')
        lines.append('</div></div>')
    return "\n".join(lines)


def replace_section(source, name, content):
    opening, closing = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
    if source.count(opening) != 1 or source.count(closing) != 1:
        raise ValueError(f"expected one pair of {name} markers")
    before, rest = source.split(opening)
    _, after = rest.split(closing)
    return f"{before}{opening}\n{content}\n{closing}{after}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report outdated outputs without rewriting")
    args = parser.parse_args()
    routes = {p.stem for p in SITE.rglob("*.html")}
    if routes != set(PAGES):
        sys.exit(f"Route inventory differs from PAGES: {sorted(routes ^ set(PAGES))}")

    styles = STYLES.read_text().strip()
    outputs = [(slug, SITE / f"{slug}.html") for slug in PAGES] + list(REPORT_TEMPLATES.items())
    stale = []
    for slug, path in outputs:
        original = path.read_text()
        try:
            updated = replace_section(original, "ocean-nav", navigation(slug, standalone=path.parent != SITE))
            if slug in STANDALONE:
                style = ('<link rel="stylesheet" href="assets/navigation.css">' if path.parent == SITE
                         else f"<style>\n{styles}\n</style>")
                updated = replace_section(updated, "ocean-nav-style", style)
        except ValueError as error:
            sys.exit(f"{path.relative_to(ROOT)}: {error}")
        if original != updated:
            stale.append(str(path.relative_to(ROOT)))
            if not args.check:
                path.write_text(updated)
    if stale and args.check:
        sys.exit("Navigation needs regeneration: " + ", ".join(stale))
    print(f"Navigation in sync across {len(PAGES)} pages and {len(REPORT_TEMPLATES)} report templates.")


if __name__ == "__main__":
    main()
