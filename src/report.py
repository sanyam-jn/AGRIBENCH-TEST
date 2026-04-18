"""
Report generation.

Produces:
  1. results/reports/summary.json  — machine-readable full results
  2. results/reports/report.md     — human-readable markdown report

Includes:
  - Overall scores per model (mean ± std for each metric)
  - Per-category breakdown
  - Cost summary
  - Contamination flags (if any)
"""

import json
import statistics
from collections import defaultdict
from pathlib import Path
from datetime import datetime


METRICS = ["accuracy", "relevance", "completeness", "conciseness", "actionability"]


def _mean(values: list) -> float:
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 2) if values else 0.0


def _std(values: list) -> float:
    values = [v for v in values if v is not None]
    return round(statistics.stdev(values), 2) if len(values) > 1 else 0.0


def _aggregate(score_entries: list) -> dict:
    """Return {metric: {mean, std}} for a list of score dicts."""
    by_metric = defaultdict(list)
    for entry in score_entries:
        for metric in METRICS:
            val = entry.get(metric)
            if val is not None:
                by_metric[metric].append(val)
    return {
        m: {"mean": _mean(vals), "std": _std(vals), "n": len(vals)}
        for m, vals in by_metric.items()
    }


def generate_report(responses: list, scores: list, output_dir: str) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Index responses by (qna_id, model_name)
    resp_index = {(r["qna_id"], r["model_name"]): r for r in responses}

    # Group scores by model
    by_model: dict[str, list] = defaultdict(list)
    for s in scores:
        by_model[s["model_name"]].append(s)

    model_names = sorted(by_model.keys())

    # ── Overall aggregation ───────────────────────────────────────────────────
    overall = {model: _aggregate(by_model[model]) for model in model_names}

    # ── Per-category breakdown ────────────────────────────────────────────────
    category_scores: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for s in scores:
        for cat in s.get("categories", []):
            for metric in METRICS:
                val = s.get(metric)
                if val is not None:
                    category_scores[cat][f"{s['model_name']}__{metric}"].append(val)

    category_summary: dict = {}
    for cat, data in category_scores.items():
        category_summary[cat] = {}
        for model in model_names:
            category_summary[cat][model] = {
                m: {"mean": _mean(data.get(f"{model}__{m}", [])),
                    "n": len(data.get(f"{model}__{m}", []))}
                for m in METRICS
            }

    # ── Cost summary ──────────────────────────────────────────────────────────
    cost_by_model: dict[str, float] = defaultdict(float)
    for r in responses:
        cost_by_model[r["model_name"]] += r.get("cost_usd", 0.0)
    judge_cost_total = sum(s.get("judge_cost_usd", 0.0) for s in scores)

    # ── Contamination flags ───────────────────────────────────────────────────
    flagged = [
        {
            "qna_id": r["qna_id"],
            "model_name": r["model_name"],
            "flag_reasons": r.get("contamination", {}).get("flag_reasons", []),
        }
        for r in responses
        if r.get("contamination", {}).get("flagged", False)
    ]

    # ── Write JSON summary ────────────────────────────────────────────────────
    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "models_evaluated": model_names,
        "n_questions": len({r["qna_id"] for r in responses}),
        "overall_scores": overall,
        "category_breakdown": category_summary,
        "cost_summary": {
            "subject_model_costs_usd": dict(cost_by_model),
            "judge_cost_usd": round(judge_cost_total, 6),
            "total_usd": round(sum(cost_by_model.values()) + judge_cost_total, 6),
        },
        "contamination_flags": flagged,
    }

    json_path = Path(output_dir) / "summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # ── Write Markdown report ─────────────────────────────────────────────────
    md_path = Path(output_dir) / "report.md"
    with open(md_path, "w", encoding="utf-8") as f:

        f.write("# AI-AgriBench Evaluation Report\n\n")
        f.write(f"Generated: {summary['generated_at']}  \n")
        f.write(f"Questions evaluated: {summary['n_questions']}  \n")
        f.write(f"Models: {', '.join(model_names)}\n\n")

        # Overall scores table
        f.write("## Overall Scores (0–100)\n\n")
        header = "| Metric | " + " | ".join(model_names) + " |\n"
        sep = "|--------|" + "|".join(["--------"] * len(model_names)) + "|\n"
        f.write(header)
        f.write(sep)
        for metric in METRICS:
            row = f"| **{metric.capitalize()}** |"
            for model in model_names:
                agg = overall[model].get(metric, {})
                row += f" {agg.get('mean', 'N/A')} ± {agg.get('std', 'N/A')} |"
            f.write(row + "\n")
        f.write("\n")

        # Per-category breakdown
        f.write("## Per-Category Breakdown\n\n")
        for cat, model_data in sorted(category_summary.items()):
            f.write(f"### {cat.replace('_', ' ')}\n\n")
            header = "| Metric | " + " | ".join(model_names) + " |\n"
            sep = "|--------|" + "|".join(["--------"] * len(model_names)) + "|\n"
            f.write(header)
            f.write(sep)
            for metric in METRICS:
                row = f"| {metric} |"
                for model in model_names:
                    mean_val = model_data.get(model, {}).get(metric, {}).get("mean", "N/A")
                    n_val = model_data.get(model, {}).get(metric, {}).get("n", 0)
                    row += f" {mean_val} (n={n_val}) |"
                f.write(row + "\n")
            f.write("\n")

        # Cost
        f.write("## Cost Summary\n\n")
        for model, cost in summary["cost_summary"]["subject_model_costs_usd"].items():
            f.write(f"- **{model}** (subject): ${cost:.4f}\n")
        f.write(f"- **Judge**: ${summary['cost_summary']['judge_cost_usd']:.4f}\n")
        f.write(f"- **Total**: ${summary['cost_summary']['total_usd']:.4f}\n\n")

        # Contamination
        f.write("## Contamination Flags\n\n")
        if flagged:
            for flag in flagged:
                f.write(f"- `{flag['qna_id']}` / `{flag['model_name']}`: {'; '.join(flag['flag_reasons'])}\n")
        else:
            f.write("No responses flagged for potential contamination.\n")

    print(f"  Report written to {md_path}")
    print(f"  Summary JSON at  {json_path}")
