"""
LLM-as-a-Judge scoring module.

Design rationale:
  We use a single Gemini 2.0 Flash judge with structured JSON output.
  Using a single judge keeps costs low and ensures consistent calibration
  across all (question, model) pairs.  The judge is a different model
  generation from both subject models, reducing (but not eliminating)
  same-family bias for the Gemini subject model.

  The judge is prompted with rubric anchors at 0, 50, and 100 for each
  metric so that scores are calibrated rather than free-form.  Requesting
  JSON output minimises parsing failures.

Metrics scored (0–100 each):
  - accuracy:      factual alignment with the gold answer
  - relevance:     degree to which the response addresses the question
  - completeness:  coverage of key steps, caveats, and conditions
  - conciseness:   focus and absence of filler/unnecessary content
  - actionability: specificity of implementable guidance (5th metric)
"""

import json
import logging
import os
import re

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

import config as cfg

logger = logging.getLogger(__name__)

# ── Judge prompt ──────────────────────────────────────────────────────────────

JUDGE_PROMPT_TEMPLATE = """You are an expert agricultural evaluation judge.
Score the MODEL RESPONSE against the GOLD ANSWER for the given QUESTION.

QUESTION:
{question}

GOLD ANSWER:
{gold_answer}

MODEL RESPONSE:
{response}

Score each metric from 0 to 100 using these anchors:

ACCURACY — factual correctness and alignment with expert consensus
  100: Fully correct, right terminology, no factual errors
   50: Partially correct; some errors or imprecision
    0: Contradicts expert consensus or is entirely wrong

RELEVANCE — whether the response addresses the actual question
  100: Directly and fully on-topic
   50: Mostly relevant but drifts or misses key aspects
    0: Does not address the question

COMPLETENESS — coverage of key steps, caveats, and conditions
  100: All critical points covered including caveats
   50: Covers main points but has notable gaps
    0: Fails to address most key elements

CONCISENESS — focused, practical, free of unnecessary filler
  100: Precise and actionable, no padding
   50: Some redundancy but generally focused
    0: Extremely verbose, rambling, or padded

ACTIONABILITY — specificity of implementable guidance (5th metric)
  Measures whether a farmer can act on this response TODAY without
  needing to look anything else up.
  100: Includes specific quantities/rates, timing, ordered steps, thresholds
   50: Gives general steps but lacks specifics needed to act
    0: Purely conceptual — no implementable guidance

Respond ONLY with a valid JSON object, no markdown fences:
{{
  "accuracy": <integer 0-100>,
  "relevance": <integer 0-100>,
  "completeness": <integer 0-100>,
  "conciseness": <integer 0-100>,
  "actionability": <integer 0-100>,
  "reasoning": "<one sentence explaining the overall assessment>"
}}"""


# ── Gemini judge call ─────────────────────────────────────────────────────────

def _call_gemini_judge(prompt: str) -> tuple:
    from google import genai
    from google.genai import errors as genai_errors

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)

    @retry(
        retry=retry_if_exception_type((genai_errors.APIError, Exception)),
        wait=wait_exponential(multiplier=1, min=cfg.RETRY_MIN_WAIT, max=cfg.RETRY_MAX_WAIT),
        stop=stop_after_attempt(cfg.MAX_RETRIES),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _do_call():
        return client.models.generate_content(
            model=cfg.JUDGE_MODEL.model_id,
            contents=prompt,
        )

    response = _do_call()

    usage = getattr(response, "usage_metadata", None)
    tokens_in = getattr(usage, "prompt_token_count", 0) or 0
    tokens_out = getattr(usage, "candidates_token_count", 0) or 0
    cost = (tokens_in / 1_000_000) * cfg.JUDGE_MODEL.cost_per_1m_input + \
           (tokens_out / 1_000_000) * cfg.JUDGE_MODEL.cost_per_1m_output

    return response.text, round(cost, 6)


def _call_groq_judge(prompt: str) -> tuple:
    from groq import Groq, RateLimitError, APIStatusError

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set.")

    client = Groq(api_key=api_key)

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIStatusError)),
        wait=wait_exponential(multiplier=1, min=cfg.RETRY_MIN_WAIT, max=cfg.RETRY_MAX_WAIT),
        stop=stop_after_attempt(cfg.MAX_RETRIES),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _do_call():
        return client.chat.completions.create(
            model=cfg.JUDGE_MODEL.model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
        )

    completion = _do_call()
    text = completion.choices[0].message.content

    usage = completion.usage
    tokens_in = usage.prompt_tokens if usage else 0
    tokens_out = usage.completion_tokens if usage else 0
    cost = (tokens_in / 1_000_000) * cfg.JUDGE_MODEL.cost_per_1m_input + \
           (tokens_out / 1_000_000) * cfg.JUDGE_MODEL.cost_per_1m_output

    return text, round(cost, 6)


# ── JSON parsing with fallback ────────────────────────────────────────────────

def _parse_scores(raw: str) -> dict:
    """
    Parse the judge's JSON response.  Strips markdown fences if present,
    then tries json.loads.  Falls back to regex extraction on failure.
    """
    # Strip ```json ... ``` fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Regex fallback: extract individual integer scores
    metrics = ["accuracy", "relevance", "completeness", "conciseness", "actionability"]
    scores = {}
    for metric in metrics:
        match = re.search(rf'"{metric}"\s*:\s*(\d+)', cleaned)
        scores[metric] = int(match.group(1)) if match else None

    reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]+)"', cleaned)
    scores["reasoning"] = reasoning_match.group(1) if reasoning_match else "parse error"

    return scores


# ── Public API ────────────────────────────────────────────────────────────────

def score_response(question: str, gold_answer: str, response: str) -> dict:
    """
    Score a single (question, gold_answer, response) triple.

    Returns a dict with keys:
      accuracy, relevance, completeness, conciseness, actionability,
      reasoning, judge_cost_usd
    """
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        question=question,
        gold_answer=gold_answer,
        response=response,
    )

    if cfg.JUDGE_MODEL.provider == "google":
        raw, judge_cost = _call_gemini_judge(prompt)
    elif cfg.JUDGE_MODEL.provider == "groq":
        raw, judge_cost = _call_groq_judge(prompt)
    else:
        raise ValueError(f"Unknown judge provider: {cfg.JUDGE_MODEL.provider}")

    scores = _parse_scores(raw)
    scores["judge_cost_usd"] = judge_cost
    return scores
