"""Plot the four six-hour Pioneer model errors for each scored storm."""

import argparse
import csv
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


MODELS = {
    "persistence": ("Persistence", "#63757e"),
    "tide": ("Tide", "#5777a4"),
    "current": ("Currents", "#008674"),
    "tide_current": ("Tide + currents", "#bd672c"),
}
TARGETS = {
    "temperature_c": "Temperature (°C)",
    "salinity": "Practical salinity (PSS-78)",
}
COHORTS = {
    "archive_complete": "Completed archival storm",
    "later_provisional": "Later storm · provisional",
}
INK = "#193942"
MUTED = "#456068"


def read_results(path):
    events = {}
    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            key = row["cohort"], row["storm_id"]
            if key[0] not in COHORTS:
                raise ValueError(f"Unexpected storm cohort {key[0]}")
            if int(row["n"]) < 1:
                continue
            start = datetime.fromisoformat(row["issue_start"].replace("Z", "+00:00"))
            event = events.setdefault(key, {"start": start, "n": int(row["n"]), "values": {}})
            if (event["n"], event["start"]) != (int(row["n"]), start):
                raise ValueError(f"Inconsistent paired cases for {key}")
            series = (row["target"], row["model"])
            if series in event["values"]:
                raise ValueError(f"Duplicate metric for {key} {series}")
            event["values"][series] = float(row["mae"])
    expected = {(target, model) for target in TARGETS for model in MODELS}
    for key, event in events.items():
        if set(event["values"]) != expected:
            raise ValueError(f"Incomplete model comparison for {key}")
    if not events:
        raise ValueError("No scored storm events to plot")
    return sorted(events.items(), key=lambda item: (list(COHORTS).index(item[0][0]), item[1]["start"]))


def plot(results, output):
    events = read_results(results / "per_event.csv")
    maxima = {
        target: max(event["values"][target, model] for _, event in events for model in MODELS)
        for target in TARGETS
    }
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK})
    height = 1.35 + 2.25 * len(events)
    fig = plt.figure(figsize=(10, height), facecolor="white", layout="constrained")
    grid = fig.add_gridspec(2 * len(events) + 2, 2, height_ratios=[.80] + [.39, 1.73] * len(events) + [.25])
    header = fig.add_subplot(grid[0, :])
    header.set_axis_off()
    header.text(0, .83, "Six-hour Pioneer forecasts with tide and currents",
                transform=header.transAxes, fontsize=19, va="center", weight="bold")
    header.text(0, .31, "Mean absolute error by storm. Lower values indicate more accurate forecasts.",
                transform=header.transAxes, fontsize=11, va="center", color=MUTED)

    for i, ((cohort, _), event) in enumerate(events):
        group = fig.add_subplot(grid[1 + 2 * i, :])
        group.set_axis_off()
        group.plot([0, 1], [.99, .99], lw=.9, color="#c1d2d4", transform=group.transAxes)
        provisional = cohort == "later_provisional"
        group.text(0, .40, COHORTS[cohort], fontsize=12, weight="bold",
                   color="#96511c" if provisional else INK, transform=group.transAxes, va="center")
        start = event["start"].strftime("%d %b %Y, %H:%M UTC")
        group.text(1, .40, f"First issue {start}  ·  {event['n']} forecasts", color=MUTED,
                   transform=group.transAxes, fontsize=10, ha="right", va="center")
        for col, (target, unit) in enumerate(TARGETS.items()):
            ax = fig.add_subplot(grid[2 + 2 * i, col])
            ax.set_title(unit, loc="left", pad=4, fontsize=11, weight="bold")
            largest = max(maxima[target], 0.001)
            for y, (model, (label, color)) in enumerate(MODELS.items()):
                value = event["values"][target, model]
                ax.barh(y, value, color=color, height=.63)
                ax.text(value + .014 * largest, y, f"{value:.3f}", ha="left", va="center",
                        fontsize=9, color=INK)
            ax.set_yticks(range(len(MODELS)), [v[0] for v in MODELS.values()] if col == 0 else [])
            ax.set_ylim(len(MODELS)-.4, -.58)
            ax.set_xlim(0, largest * 1.23)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
            ax.grid(axis="x", lw=.6, color="#d9e4e4")
            ax.set_axisbelow(True)
            ax.tick_params(axis="both", length=0, pad=4, colors=MUTED, labelsize=9)
            for edge in ("top", "left", "right"):
                ax.spines[edge].set_visible(False)
            ax.spines["bottom"].set_color("#b3c6c9")

    note = fig.add_subplot(grid[-1, :])
    note.set_axis_off()
    note.text(0, 0, "OOI Pioneer Central Surface Mooring, nominal 7 m depth  ·  SIG.AI Ocean",
              fontsize=9, color=MUTED, transform=note.transAxes, va="baseline")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--output", type=Path, default=Path("pioneer-tide-current.png"))
    args = parser.parse_args()
    plot(args.results, args.output)
