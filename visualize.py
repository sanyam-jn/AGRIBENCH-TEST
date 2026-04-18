"""
Visualisation module (bonus).

Generates three charts saved to results/reports/:
  1. radar_chart.png   — spider/radar chart comparing models across 5 metrics
  2. category_bars.png — grouped bar chart of mean scores per topic category
  3. conciseness_vs_completeness.png — scatter showing the anti-correlation

Call via:  python visualize.py
Or from pipeline.py which calls run() directly.
"""

import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless rendering
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

METRICS = ["accuracy", "relevance", "completeness", "conciseness", "actionability"]
COLORS = ["#2196F3", "#FF9800"]  # blue for model 1, orange for model 2


def _load_scores(reports_dir: str) -> list[dict]:
    summary_path = Path(reports_dir) / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"summary.json not found in {reports_dir}")
    with open(summary_path) as f:
        return json.load(f)


def _radar_chart(overall_scores: dict, output_dir: str) -> None:
    models = list(overall_scores.keys())
    n = len(METRICS)
    angles = [2 * math.pi * i / n for i in range(n)]
    angles += angles[:1]  # close the polygon

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    for i, model in enumerate(models):
        values = [overall_scores[model].get(m, {}).get("mean", 0) for m in METRICS]
        values += values[:1]
        ax.plot(angles, values, color=COLORS[i % len(COLORS)], linewidth=2, label=model)
        ax.fill(angles, values, color=COLORS[i % len(COLORS)], alpha=0.15)

    ax.set_thetagrids(
        [a * 180 / math.pi for a in angles[:-1]],
        [m.capitalize() for m in METRICS],
        fontsize=11,
    )
    ax.set_ylim(0, 100)
    ax.set_title("Model Comparison — All Metrics", pad=20, fontsize=13, fontweight="bold")
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

    out = Path(output_dir) / "radar_chart.png"
    fig.savefig(out, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  Saved {out}")


def _category_bars(category_breakdown: dict, output_dir: str) -> None:
    categories = sorted(category_breakdown.keys())
    if not categories:
        return

    models = list(next(iter(category_breakdown.values())).keys())
    metric = "accuracy"  # show accuracy per category

    x = np.arange(len(categories))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(10, len(categories) * 1.5), 6))

    for i, model in enumerate(models):
        means = [
            category_breakdown[cat].get(model, {}).get(metric, {}).get("mean", 0)
            for cat in categories
        ]
        ax.bar(x + i * width, means, width, label=model, color=COLORS[i % len(COLORS)], alpha=0.85)

    short_cats = [c.replace("_", "\n") for c in categories]
    ax.set_xticks(x + width * (len(models) - 1) / 2)
    ax.set_xticklabels(short_cats, fontsize=8)
    ax.set_ylabel("Mean Accuracy (0–100)")
    ax.set_title("Accuracy by Topic Category", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    out = Path(output_dir) / "category_bars.png"
    fig.savefig(out, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  Saved {out}")


def _conciseness_vs_completeness(scores: list[dict], output_dir: str) -> None:
    models = sorted({s["model_name"] for s in scores})
    fig, ax = plt.subplots(figsize=(7, 6))

    for i, model in enumerate(models):
        model_scores = [s for s in scores if s["model_name"] == model]
        x = [s.get("completeness") for s in model_scores if s.get("completeness") is not None]
        y = [s.get("conciseness") for s in model_scores if s.get("conciseness") is not None]
        if x and y:
            ax.scatter(x, y, label=model, color=COLORS[i % len(COLORS)], alpha=0.7, s=60)
            # trend line
            if len(x) > 1:
                z = np.polyfit(x, y, 1)
                p = np.poly1d(z)
                xs = np.linspace(min(x), max(x), 100)
                ax.plot(xs, p(xs), color=COLORS[i % len(COLORS)], linestyle="--", alpha=0.5)

    ax.set_xlabel("Completeness", fontsize=12)
    ax.set_ylabel("Conciseness", fontsize=12)
    ax.set_title("Conciseness vs. Completeness\n(expect anti-correlation for strong models)",
                 fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_xlim(0, 105)
    ax.set_ylim(0, 105)

    out = Path(output_dir) / "conciseness_vs_completeness.png"
    fig.savefig(out, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  Saved {out}")


def run(scores: list[dict], output_dir: str) -> None:
    """Called programmatically from pipeline.py after Phase 3."""
    print("\n=== Visualisation ===")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    summary = _load_scores(output_dir)
    overall = summary.get("overall_scores", {})
    category = summary.get("category_breakdown", {})

    _radar_chart(overall, output_dir)
    _category_bars(category, output_dir)
    _conciseness_vs_completeness(scores, output_dir)
    print("  Visualisation complete.")


if __name__ == "__main__":
    import sys
    import config as cfg

    # Load raw scores from checkpoint for scatter plot
    scores_path = Path(cfg.SCORES_CHECKPOINT)
    raw_scores = []
    if scores_path.exists():
        with open(scores_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    raw_scores.append(json.loads(line))

    run(scores=raw_scores, output_dir=cfg.REPORTS_DIR)
