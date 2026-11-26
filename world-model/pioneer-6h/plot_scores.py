"""Draw the paired six-hour Pioneer forecast errors and storm-by-storm changes."""

import argparse
import csv
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator


MODELS = ("persistence", "history", "weather", "weather_sst")
MODEL_LABELS = ("Persistence", "Mooring history", "History + weather", "History + weather + SST")
COLORS = ("#87949c", "#45586e", "#08786e", "#b86324")
TARGETS = (("temperature_c", "Temperature", "°C"), ("salinity", "Practical salinity", "PSS-78"))
INK = "#162f38"
GRID = "#d8e1df"


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as src:
        return list(csv.DictReader(src))


def read_scores(results):
    summary = {(row["target"], row["model"]): float(row["storm_mae"]) for row in read_rows(results / "metrics.csv")}
    storms = {}
    counts = {}
    for row in read_rows(results / "per_storm.csv"):
        event = row["storm_id"]
        scores = storms.setdefault(event, {})
        key = (row["target"], row["model"])
        if key in scores:
            raise ValueError(f"Duplicate result for {event} {key}.")
        scores[key] = float(row["mae"])
        n = int(row["n"])
        if n <= 0 or counts.setdefault(event, n) != n:
            raise ValueError(f"Unpaired forecast counts for {event}.")
    required = {(k, model) for k, _, _ in TARGETS for model in MODELS}
    if not storms or set(summary) != required or any(set(row) != required for row in storms.values()):
        raise ValueError("Expected results for both targets and all four methods on each scored storm.")
    return summary, storms, counts


def event_label(event, count):
    peak = datetime.strptime(event, "ORE-%Y%m%dT%HZ")
    return f"{peak:%d %b %y}   ·   {count}"


def style_axis(ax):
    ax.set_facecolor("#ffffff")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="both", length=0, pad=5, colors=INK, labelsize=9)
    ax.grid(axis="x", color=GRID, alpha=.75, linewidth=.7)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5))


def summary_panel(ax, summary, key, name, units, show_labels):
    scores = [summary[key, model] for model in MODELS]
    for y, (value, color) in enumerate(zip(scores, COLORS)):
        ax.barh(y, value, height=.47, color=color)
        ax.annotate(f"{value:.3f}", (value, y), xytext=(5, 0), textcoords="offset points",
                    ha="left", va="center", color=INK, fontsize=9)
    ax.set_yticks(range(len(MODELS)), MODEL_LABELS if show_labels else [])
    ax.set_ylim(3.7, -.65)
    ax.set_xlim(0, max(max(scores) * 1.30, .01))
    ax.set_title(name, loc="left", fontsize=15, fontweight="bold", color=INK, pad=12)
    ax.set_xlabel(f"Mean absolute error ({units})", fontsize=10, color=INK)
    style_axis(ax)


def storm_panel(ax, key, units, storm_names, storms, counts, show_labels):
    ax.axvline(0, color="#52636c", linewidth=1.1)
    for y, event in enumerate(storm_names):
        row = storms[event]
        weather_gain = row[key, "history"] - row[key, "weather"]
        sst_gain = row[key, "weather"] - row[key, "weather_sst"]
        ax.axhline(y, color="#e4eae7", linewidth=.6, zorder=0)
        for gain, offset, marker, color in ((weather_gain, -.14, "o", COLORS[2]), (sst_gain, .14, "D", COLORS[3])):
            ax.plot(gain, y + offset, marker, color=color, markersize=5, zorder=3)
    names = [event_label(event, counts[event]) for event in storm_names]
    ax.set_yticks(range(len(storm_names)), names if show_labels else [])
    ax.set_ylim(len(storm_names) - .5, -.5)
    left, right = ax.get_xlim()
    bound = max(abs(left), abs(right), .002)
    ax.set_xlim(-bound, bound)
    ax.set_xlabel(f"Reduction in mean absolute error ({units})", fontsize=10, color=INK)
    style_axis(ax)


def plot(results, output):
    summary, storms, counts = read_scores(results)
    events = sorted(storms)
    storm_height = max(2.6, .38 * len(events))
    height = 6.28 + storm_height
    fig = plt.figure(figsize=(11.2, height), facecolor="white")
    # Place axes in physical inches vertically so panel titles and legends keep their space.
    columns = ((.205, .334), (.626, .334))
    storm_bottom = .84
    storm_top = storm_bottom + storm_height
    fig.text(.035, 1-.26/height, "Six-hour forecasts at Pioneer", fontsize=24,
             fontweight="bold", va="top", color=INK)
    fig.text(.035, 1-.75/height, f"{len(events)} held-out storms  ·  {sum(counts.values()):,} hourly forecasts  ·  Near-surface CTD, nominally 7 m",
             fontsize=11, color="#436069", va="top")
    for col, (key, name, units) in enumerate(TARGETS):
        left, width = columns[col]
        top = fig.add_axes([left, 1 - 3.15 / height, width, 1.68 / height])
        summary_panel(top, summary, key, name, units, show_labels=(col == 0))
        bottom = fig.add_axes([left, storm_bottom / height, width, storm_height / height])
        storm_panel(bottom, key, units, events, storms, counts, show_labels=(col == 0))

    fig.text(.035, (storm_top + 1.18) / height, "What each added source contributed", fontsize=15,
             fontweight="bold", color=INK, va="bottom")
    fig.text(.035, (storm_top + .84) / height,
             "Each mark is one storm. Positive values indicate smaller errors after the source was added.",
             fontsize=10, color="#436069", va="bottom")
    legend_handles = [
        Line2D([], [], marker="o", linestyle="none", color=COLORS[2], label="Winds and waves added to mooring history"),
        Line2D([], [], marker="D", linestyle="none", color=COLORS[3], label="SST maps added to history, winds and waves"),
    ]
    fig.legend(handles=legend_handles, loc="lower left", bbox_to_anchor=(.028, (storm_top + .37) / height),
               frameon=False, ncol=2, handletextpad=.25, columnspacing=2, fontsize=9)
    fig.text(.034, (storm_top + .06) / height, "Peak date · forecasts", color="#436069", fontsize=9, va="bottom")
    fig.text(.035, .14/height, "Upper panels weight each storm equally. SST = sea-surface temperature.  |  SIG.AI Ocean",
             fontsize=9, color="#436069", va="bottom")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight", pad_inches=.2)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True, help="Folder containing metrics.csv and per_storm.csv")
    parser.add_argument("--output", type=Path, required=True, help="Destination PNG")
    args = parser.parse_args()
    plot(args.results, args.output)
