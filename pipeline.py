#!/usr/bin/env python3
"""
AI-AgriBench Evaluation Pipeline
=================================
Entry point.  Runs three sequential phases:

  Phase 1 — Generate responses from both subject models
  Phase 2 — Score each response with the judge model
  Phase 3 — Produce a summary report

Checkpointing: every API result is written to JSONL immediately, so a
partial run can be resumed safely — completed items are skipped.

Usage:
  python pipeline.py
  python pipeline.py --skip-viz   # skip visualisation step

Dependencies:
  pip install -r requirements.txt

Environment variables (see .env.example):
  GEMINI_API_KEY
  GROQ_API_KEY
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

import config as cfg
from src.checkpoint import load_checkpoint, save_checkpoint
from src.subject_models import call_subject_model
from src.judge import score_response
from src.contamination import check_contamination
from src.report import generate_report

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_questions() -> list[dict]:
    with open(cfg.QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def phase1_generate(questions: list[dict]) -> dict:
    """Call each subject model for every question; checkpoint after each call."""
    log.info("=== Phase 1: Generating model responses ===")

    existing = load_checkpoint(cfg.RESPONSES_CHECKPOINT)
    total = len(questions) * len(cfg.SUBJECT_MODELS)
    done = len(existing)
    log.info(f"  {done}/{total} responses already in checkpoint — skipping those.")

    for model_cfg in cfg.SUBJECT_MODELS:
        for q in questions:
            key = (q["qna_id"], model_cfg.name)
            if key in existing:
                continue

            log.info(f"  Calling {model_cfg.name} for {q['qna_id']} …")
            try:
                result = call_subject_model(model_cfg, q["question"])
            except Exception as exc:
                log.error(f"  FAILED {model_cfg.name}/{q['qna_id']}: {exc}")
                continue

            contamination = check_contamination(result["text"], q["answer"])

            entry = {
                "qna_id": q["qna_id"],
                "model_name": model_cfg.name,
                "question": q["question"],
                "gold_answer": q["answer"],
                "categories": q["categories"],
                "response": result["text"],
                "tokens_input": result.get("tokens_input", 0),
                "tokens_output": result.get("tokens_output", 0),
                "cost_usd": result.get("cost_usd", 0.0),
                "contamination": contamination,
            }

            if contamination["flagged"]:
                log.warning(
                    f"  CONTAMINATION FLAG — {model_cfg.name}/{q['qna_id']}: "
                    f"{contamination['flag_reasons']}"
                )

            save_checkpoint(cfg.RESPONSES_CHECKPOINT, entry)
            existing[key] = entry

    log.info(f"  Phase 1 complete. {len(existing)} responses total.")
    return existing


def phase2_score(responses: dict) -> dict:
    """Judge every response; checkpoint after each score."""
    log.info("=== Phase 2: Scoring responses ===")

    existing_scores = load_checkpoint(cfg.SCORES_CHECKPOINT)
    total = len(responses)
    done = len(existing_scores)
    log.info(f"  {done}/{total} scores already in checkpoint — skipping those.")

    for key, resp_entry in responses.items():
        score_key = (resp_entry["qna_id"], resp_entry["model_name"])
        if score_key in existing_scores:
            continue

        log.info(f"  Judging {resp_entry['model_name']}/{resp_entry['qna_id']} …")
        try:
            scores = score_response(
                question=resp_entry["question"],
                gold_answer=resp_entry["gold_answer"],
                response=resp_entry["response"],
            )
        except Exception as exc:
            log.error(
                f"  FAILED scoring {resp_entry['model_name']}/{resp_entry['qna_id']}: {exc}"
            )
            continue

        score_entry = {
            "qna_id": resp_entry["qna_id"],
            "model_name": resp_entry["model_name"],
            "categories": resp_entry["categories"],
            **scores,
        }

        save_checkpoint(cfg.SCORES_CHECKPOINT, score_entry)
        existing_scores[score_key] = score_entry

    log.info(f"  Phase 2 complete. {len(existing_scores)} scores total.")
    return existing_scores


def phase3_report(responses: dict, scores: dict) -> None:
    """Generate the markdown + JSON summary report."""
    log.info("=== Phase 3: Generating report ===")
    generate_report(
        responses=list(responses.values()),
        scores=list(scores.values()),
        output_dir=cfg.REPORTS_DIR,
    )


def main():
    parser = argparse.ArgumentParser(description="AI-AgriBench evaluation pipeline")
    parser.add_argument(
        "--skip-viz",
        action="store_true",
        help="Skip the visualisation step",
    )
    args = parser.parse_args()

    # Create output directories
    for d in [cfg.RESPONSES_DIR, cfg.SCORES_DIR, cfg.REPORTS_DIR]:
        Path(d).mkdir(parents=True, exist_ok=True)

    questions = load_questions()
    log.info(f"Loaded {len(questions)} questions from {cfg.QUESTIONS_FILE}")

    responses = phase1_generate(questions)
    scores = phase2_score(responses)
    phase3_report(responses, scores)

    if not args.skip_viz:
        try:
            import visualize  # noqa: F401 — runs on import
            visualize.run(scores=list(scores.values()), output_dir=cfg.REPORTS_DIR)
        except Exception as exc:
            log.warning(f"Visualisation skipped (error: {exc})")

    log.info(f"All done! Results in ./{cfg.RESULTS_DIR}/")


if __name__ == "__main__":
    main()
