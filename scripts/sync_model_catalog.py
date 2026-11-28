"""Render the public task lanes and model records from assets/model-catalog.json."""

import argparse
import json
from html import escape
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
START = "<!-- model-catalog:start -->"
END = "<!-- model-catalog:end -->"
FIELDS = (
    ("input", "Input"), ("output", "Output"), ("accessGroup", "Access type"),
    ("access", "Availability"), ("license", "License scope"), ("compute", "Compute"),
    ("benchmark", "Evaluation"), ("notes", "Notes"),
)


def link(label, href, class_name=None):
    style = f' class="{class_name}"' if class_name else ""
    return f'<a href="{escape(href)}"{style}>{escape(label)}</a>'


def model_card(model):
    links = []
    if model.get("actionUrl"):
        links.append(link(model["action"], model["actionUrl"]))
    links.append(link("Primary source", model["source"]))
    if model.get("artifact") and model["artifact"] != model["source"]:
        links.append(link("Repository or release", model["artifact"]))
    fields = [f'        <dt>{label}</dt><dd>{escape(model[key])}</dd>'
              for key, label in FIELDS if model.get(key)]
    return "\n".join([
        f'    <details class="model-card" data-access="{escape(model["accessGroup"])}">',
        f'      <summary><span><strong>{escape(model["name"])}</strong><small>{escape(model["task"])}</small></span></summary>',
        '      <dl>', *fields, '      </dl>',
        f'      <p class="catalog-links">{" ".join(links)}</p>',
        '    </details>',
    ])


def task_lane(lane, models, atlas):
    slug = escape(lane["slug"])
    actions = [link(entry["action"], entry["actionUrl"], "primary") for entry in (lane, *models)
               if entry.get("actionUrl")]
    lines = [
        f'<section class="catalog-lane" id="{slug}" aria-labelledby="{slug}-title">',
        f'  <h2 id="{slug}-title">{escape(lane["name"])}</h2>',
        f'  <p class="lane-description">{escape(lane["workflow"])}</p>',
    ]
    sources = [s for s in atlas if s.get("lane_name") == lane["name"]]
    if sources:
        lines.append(f'  <p class="lane-atlas"><a href="ocean-sources.html#{escape(sources[0]["lane_slug"])}">'
                     f'Browse {len(sources)} datasets, models and services for this task in the source atlas</a></p>')
    if actions:
        lines.append(f'  <div class="lane-actions">{" ".join(actions)}</div>')
    lines.extend([
        '  <div class="comparison">',
        '    <h3>How to compare</h3>',
        f'    <p>{escape(lane["protocol"])}</p>',
    ])
    if lane.get("reference"):
        lines.append("    " + link(lane["reference_name"], lane["reference"]))
    noun = "record" if len(models) == 1 else "records"
    lines.extend([
        '  </div>', f'  <div class="list-tools"><span>{len(models)} {noun}</span></div>',
        '  <div class="model-list">', *(model_card(model) for model in models), '  </div>',
        '</section>',
    ])
    return "\n".join(lines)


def render(data, atlas):
    lanes = data["lanes"]
    lines = [
        '<aside aria-label="Task selection">',
        '  <p class="eyebrow" id="task-label">Task lanes</p>',
        '  <select id="lane-select" class="lane-select" aria-labelledby="task-label" hidden></select>',
        '  <nav id="lanes" aria-labelledby="task-label">',
        *("    " + link(lane["name"], "#" + lane["slug"]) for lane in lanes),
        '  </nav>', '</aside>', '<div id="lane-content">',
        *(task_lane(lane, [m for m in data["models"] if m["lane"] == lane["id"]], atlas) for lane in lanes),
        '</div>',
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = json.loads((SITE / "assets/model-catalog.json").read_text(encoding="utf-8"))
    atlas = json.loads((SITE / "assets/ocean-sources.json").read_text(encoding="utf-8"))
    page = SITE / "model-catalog.html"
    source = page.read_text(encoding="utf-8")
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError(f"Expected one pair of catalog markers in {page}")
    before, section = source.split(START)
    _, after = section.split(END)
    result = f"{before}{START}\n{render(data, atlas)}\n{END}{after}"
    if result != source:
        if args.check:
            print("Catalog HTML is out of date. Run python3 scripts/sync_model_catalog.py.")
            return 1
        page.write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
