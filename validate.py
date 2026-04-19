#!/usr/bin/env python3
"""
Extended Validation Metrics
============================
Two additional metrics built on top of the main pipeline results.
Run this AFTER pipeline.py has completed.

    python validate.py

Produces:
  results/reports/validation_report.md   — human-readable findings
  results/validation/fact_check.jsonl    — per-claim fact check results
  results/validation/confidence.jsonl    — per-response confidence analysis

These are presented as experimental metrics that audit and extend the
main pipeline's accuracy score — not replacements for it.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from collections import defaultdict

import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
RESPONSES_FILE = "results/responses/responses.jsonl"
SCORES_FILE    = "results/scores/scores.jsonl"
VAL_DIR        = "results/validation"
REPORTS_DIR    = "results/reports"

FACT_CHECK_FILE  = f"{VAL_DIR}/fact_check.jsonl"
CONFIDENCE_FILE  = f"{VAL_DIR}/confidence.jsonl"

# ── Mistral API helper ────────────────────────────────────────────────────────
MISTRAL_MODEL = "mistral-small-latest"

def call_mistral(prompt: str, retries: int = 4) -> str:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise EnvironmentError("MISTRAL_API_KEY not set.")

    for attempt in range(retries):
        try:
            r = requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MISTRAL_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 800,
                },
                timeout=60,
            )
            if r.status_code in (429, 503, 502, 500):
                wait = int(r.headers.get("Retry-After", 15))
                log.warning(f"HTTP {r.status_code} — waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise
    return ""


def parse_json_response(text: str) -> dict | list:
    """Strip markdown fences and parse JSON."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


# ── Checkpoint helpers ────────────────────────────────────────────────────────
def load_jsonl(filepath: str) -> dict:
    out = {}
    path = Path(filepath)
    if not path.exists():
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entry = json.loads(line)
                out[(entry["qna_id"], entry["model_name"])] = entry
    return out


def append_jsonl(filepath: str, entry: dict):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# METRIC 1 — FACT CHECK SCORE
# ══════════════════════════════════════════════════════════════════════════════

DECOMPOSE_PROMPT = """Break the following response into individual factual claims.
Each claim must express exactly one checkable fact — one sentence, specific and standalone.
Ignore filler phrases, transitions, and general advice with no factual content.
Return ONLY a valid JSON array of strings, no explanation, no markdown.

Response:
{response}"""

VERIFY_PROMPT = """You are checking whether a claim is supported by an expert answer.

Expert answer:
{gold}

Claim to check:
{claim}

Reply with exactly one word:
- "supported" if the expert answer confirms or implies this claim
- "neutral" if the expert answer neither confirms nor contradicts this
- "contradicted" if the expert answer clearly conflicts with this claim"""


def run_fact_check(responses: list, existing: dict) -> list:
    log.info("=== Fact Check Score ===")
    results = []
    CONTRADICTION_PENALTY = 25

    for resp in responses:
        key = (resp["qna_id"], resp["model_name"])
        if key in existing:
            log.info(f"  Skip (cached) {resp['model_name']}/{resp['qna_id']}")
            results.append(existing[key])
            continue

        log.info(f"  Fact-checking {resp['model_name']}/{resp['qna_id']} ...")

        # Step 1 — decompose into claims
        raw = call_mistral(DECOMPOSE_PROMPT.format(response=resp["response"]))
        claims = parse_json_response(raw)
        if not isinstance(claims, list) or not claims:
            log.warning(f"  Could not decompose — skipping")
            continue

        # Step 2 — verify each claim
        supported = 0
        neutral = 0
        contradicted = 0
        claim_results = []

        for claim in claims:
            verdict_raw = call_mistral(
                VERIFY_PROMPT.format(gold=resp["gold_answer"], claim=claim)
            ).strip().lower()

            if "contradicted" in verdict_raw:
                verdict = "contradicted"
                contradicted += 1
            elif "supported" in verdict_raw:
                verdict = "supported"
                supported += 1
            else:
                verdict = "neutral"
                neutral += 1

            claim_results.append({"claim": claim, "verdict": verdict})

        total = len(claims)
        base_score = (supported / total * 100) if total > 0 else 0
        penalty = contradicted * CONTRADICTION_PENALTY
        score = max(0, round(base_score - penalty, 1))

        entry = {
            "qna_id": resp["qna_id"],
            "model_name": resp["model_name"],
            "categories": resp["categories"],
            "total_claims": total,
            "supported": supported,
            "neutral": neutral,
            "contradicted": contradicted,
            "fact_check_score": score,
            "claims": claim_results,
        }

        append_jsonl(FACT_CHECK_FILE, entry)
        results.append(entry)

    return results


# ══════════════════════════════════════════════════════════════════════════════
# METRIC 2 — CONFIDENCE CHECK SCORE
# ══════════════════════════════════════════════════════════════════════════════

CONFIDENCE_PROMPT = """You are comparing how confident a model response sounds vs. an expert gold answer.

Agricultural advice should match the certainty of experts — not overclaim with universal rules,
and not be so vague it gives no guidance.

Expert gold answer:
{gold}

Model response:
{response}

Rate the model's confidence calibration on a scale of 0–100:
- 90–100: Perfectly matched — hedges where the expert hedges, specific where the expert is specific
- 70–89: Mostly matched — slightly more or less confident in one area
- 50–69: Noticeably miscalibrated — either too vague or overconfident in some areas
- 25–49: Significantly overclaiming or underwhelming — gives universal rules where expert says "it depends", or hedges everything the expert is specific about
- 0–24: Dangerous overclaiming — states specific rates, timings, or rules that the expert does not support, with no hedging

Also note: does the model overclaim (sounds more certain than expert) or underclaim (sounds more vague)?

Respond ONLY with valid JSON, no markdown:
{{
  "confidence_score": <integer 0-100>,
  "direction": "overclaims" | "underclaims" | "calibrated",
  "reason": "<one sentence explaining the calibration>"
}}"""


def run_confidence_check(responses: list, existing: dict) -> list:
    log.info("=== Confidence Check Score ===")
    results = []

    for resp in responses:
        key = (resp["qna_id"], resp["model_name"])
        if key in existing:
            log.info(f"  Skip (cached) {resp['model_name']}/{resp['qna_id']}")
            results.append(existing[key])
            continue

        log.info(f"  Confidence check {resp['model_name']}/{resp['qna_id']} ...")

        raw = call_mistral(
            CONFIDENCE_PROMPT.format(
                gold=resp["gold_answer"],
                response=resp["response"],
            )
        )
        parsed = parse_json_response(raw)

        if not parsed or "confidence_score" not in parsed:
            log.warning(f"  Parse failed — skipping")
            continue

        entry = {
            "qna_id": resp["qna_id"],
            "model_name": resp["model_name"],
            "categories": resp["categories"],
            "confidence_score": parsed.get("confidence_score", 0),
            "direction": parsed.get("direction", "unknown"),
            "reason": parsed.get("reason", ""),
        }

        append_jsonl(CONFIDENCE_FILE, entry)
        results.append(entry)

    return results


# ══════════════════════════════════════════════════════════════════════════════
# REPORT
# ══════════════════════════════════════════════════════════════════════════════

def mean(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def generate_validation_report(
    fact_results: list,
    conf_results: list,
    scores: list,
    output_dir: str,
):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    models = sorted({r["model_name"] for r in fact_results})

    # Index holistic accuracy scores
    acc_index = {(s["qna_id"], s["model_name"]): s.get("accuracy") for s in scores}

    out = Path(output_dir) / "validation_report.md"
    with open(out, "w") as f:

        f.write("# Extended Validation Metrics\n\n")
        f.write(
            "These two metrics were built to audit the main pipeline's accuracy score "
            "and test two specific failure modes that holistic scoring can miss: "
            "**hidden contradictions** and **overconfident claims**.\n\n"
        )

        # ── Fact Check Summary ────────────────────────────────────────────────
        f.write("## Metric 1 — Fact Check Score\n\n")
        f.write(
            "> *Does every claim the model makes hold up against the expert answer?*\n\n"
            "Each response is split into individual factual claims. "
            "Every claim is verified against the gold answer as supported, neutral, or contradicted. "
            "Each contradiction costs 25 points — one wrong fact in farming can mean a lost crop.\n\n"
        )

        f.write("### Overall Fact Check Scores\n\n")
        f.write("| Model | Fact Check Score | Avg Claims | Contradictions |\n")
        f.write("|-------|-----------------|-----------|----------------|\n")
        for model in models:
            ms = [r for r in fact_results if r["model_name"] == model]
            f.write(
                f"| {model} "
                f"| {mean([r['fact_check_score'] for r in ms])} "
                f"| {mean([r['total_claims'] for r in ms])} "
                f"| {mean([r['contradicted'] for r in ms])} |\n"
            )
        f.write("\n")

        # Divergence table — where fact check and accuracy disagree
        f.write("### Where Fact Check and Accuracy Disagree\n\n")
        f.write(
            "Rows where the gap is large (>10 points) suggest the holistic accuracy score "
            "missed a specific factual error — these are the most interesting findings.\n\n"
        )
        f.write("| Question | Model | Holistic Accuracy | Fact Check | Δ | Note |\n")
        f.write("|----------|-------|------------------|-----------|---|------|\n")

        for r in sorted(fact_results, key=lambda x: x["qna_id"]):
            holistic = acc_index.get((r["qna_id"], r["model_name"]), 0) or 0
            fc = r["fact_check_score"]
            delta = holistic - fc
            flag = "⚠️ review" if abs(delta) > 10 else "✓"
            f.write(
                f"| {r['qna_id']} | {r['model_name']} "
                f"| {holistic} | {fc} | {delta:+.0f} | {flag} |\n"
            )
        f.write("\n")

        # Contradicted claims detail
        contradictions_found = [
            (r, c)
            for r in fact_results
            for c in r.get("claims", [])
            if c["verdict"] == "contradicted"
        ]
        f.write("### Contradicted Claims Found\n\n")
        if contradictions_found:
            for r, c in contradictions_found:
                f.write(f"- **{r['model_name']} / {r['qna_id']}**: _{c['claim']}_\n")
        else:
            f.write("No contradicted claims found across all responses.\n")
        f.write("\n")

        # ── Confidence Check Summary ──────────────────────────────────────────
        f.write("## Metric 2 — Confidence Check Score\n\n")
        f.write(
            "> *Is the model appropriately uncertain, or is it overclaiming?*\n\n"
            "Good agricultural advice hedges where uncertainty is real "
            "(e.g., 'rates vary by soil test') and is specific where the expert is specific. "
            "A model that sounds more confident than the expert is making claims it cannot support. "
            "Overclaiming is penalised more than being too vague — vague advice is unhelpful, "
            "but overconfident wrong advice can cause crop damage.\n\n"
        )

        f.write("### Overall Confidence Check Scores\n\n")
        f.write("| Model | Confidence Score | Overclaims | Underclaims | Calibrated |\n")
        f.write("|-------|-----------------|-----------|------------|------------|\n")
        for model in models:
            ms = [r for r in conf_results if r["model_name"] == model]
            over = sum(1 for r in ms if r["direction"] == "overclaims")
            under = sum(1 for r in ms if r["direction"] == "underclaims")
            cal = sum(1 for r in ms if r["direction"] == "calibrated")
            f.write(
                f"| {model} "
                f"| {mean([r['confidence_score'] for r in ms])} "
                f"| {over} | {under} | {cal} |\n"
            )
        f.write("\n")

        f.write("### Per-Question Confidence Check\n\n")
        f.write("| Question | Model | Score | Direction | Reason |\n")
        f.write("|----------|-------|-------|-----------|--------|\n")
        for r in sorted(conf_results, key=lambda x: (x["qna_id"], x["model_name"])):
            f.write(
                f"| {r['qna_id']} | {r['model_name']} "
                f"| {r['confidence_score']} | {r['direction']} "
                f"| {r['reason'][:80]}... |\n"
            )
        f.write("\n")

        # ── Combined view ─────────────────────────────────────────────────────
        f.write("## Combined View — All Extended Metrics\n\n")
        f.write("| Model | Holistic Accuracy | Fact Check | Confidence Check |\n")
        f.write("|-------|-----------------|-----------|------------------|\n")
        for model in models:
            hol = mean([
                acc_index.get((r["qna_id"], r["model_name"]), 0) or 0
                for r in fact_results if r["model_name"] == model
            ])
            fc = mean([r["fact_check_score"] for r in fact_results if r["model_name"] == model])
            cc = mean([r["confidence_score"] for r in conf_results if r["model_name"] == model])
            f.write(f"| {model} | {hol} | {fc} | {cc} |\n")
        f.write("\n")

        f.write(
            "> **How to read this:** Where Holistic Accuracy and Fact Check agree, "
            "the accuracy score is trustworthy. Where they diverge, inspect the contradicted claims — "
            "that is where hallucinations are hiding. Confidence Check tells you whether the model "
            "is giving advice a farmer can safely act on, or making promises the data does not support.\n"
        )

    print(f"\n  Validation report saved to {out}")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # Load responses and existing scores
    responses = list(load_jsonl(RESPONSES_FILE).values())
    scores = list(load_jsonl(SCORES_FILE).values())

    if not responses:
        print("No responses found. Run pipeline.py first.")
        return

    log.info(f"Loaded {len(responses)} responses, {len(scores)} scores")

    # Load existing validation checkpoints
    existing_fc   = load_jsonl(FACT_CHECK_FILE)
    existing_conf = load_jsonl(CONFIDENCE_FILE)

    # Run metrics
    fact_results = run_fact_check(responses, existing_fc)
    conf_results = run_confidence_check(responses, existing_conf)

    # Generate report
    generate_validation_report(
        fact_results=fact_results,
        conf_results=conf_results,
        scores=scores,
        output_dir=REPORTS_DIR,
    )

    log.info("Done. See results/reports/validation_report.md")


if __name__ == "__main__":
    main()
