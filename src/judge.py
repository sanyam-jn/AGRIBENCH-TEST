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

JUDGE_PROMPT_TEMPLATE = """You are an expert agricultural evaluation judge. Your job is to score a model's response critically and precisely.

IMPORTANT SCORING RULES:
- Use the FULL range 0–100. Do NOT default to round numbers like 90, 95, 100.
- A score of 100 means genuinely flawless — nothing could be improved. This should be rare.
- A score of 80 means good but with clear room for improvement.
- Differentiate scores between metrics — a response can be highly relevant but incomplete.
- Think step by step before scoring.

QUESTION:
{question}

GOLD ANSWER (expert-curated reference):
{gold_answer}

MODEL RESPONSE:
{response}

First, briefly reason about the response (2-3 sentences). Then score each metric.

ACCURACY — factual correctness and alignment with expert consensus
  90-100: Fully correct, precise terminology, zero factual errors
  70-89:  Mostly correct with minor imprecision or missing nuance
  50-69:  Some correct points but notable factual errors or gaps
  25-49:  Multiple errors or contradicts established practice
  0-24:   Largely wrong or contradicts expert consensus

RELEVANCE — whether the response addresses the actual question asked
  90-100: Directly and fully on-topic, no drift
  70-89:  Mostly relevant with minor drift or missed aspect
  50-69:  Partially relevant, misses key aspects of the question
  25-49:  Significantly off-topic
  0-24:   Does not address the question

COMPLETENESS — coverage of key steps, caveats, and conditions a farmer needs
  90-100: All critical points covered including important caveats and edge cases
  70-89:  Covers most key points, one or two notable gaps
  50-69:  Covers the basics but missing important elements
  25-49:  Significant gaps — a farmer would be missing critical information
  0-24:   Fails to address most key elements

CONCISENESS — focused, practical guidance without unnecessary filler
  90-100: Every sentence adds value, no padding or repetition
  70-89:  Mostly focused with minor redundancy
  50-69:  Some unnecessary content but core guidance is present
  25-49:  Noticeably verbose, repetitive, or padded
  0-24:   Extremely rambling with little signal-to-noise

ACTIONABILITY — can a farmer act on this TODAY without further research?
  Checks for: specific quantities/rates, timing windows, ordered steps, decision thresholds
  90-100: Highly specific — farmer knows exactly what to do, how much, and when
  70-89:  Mostly actionable but missing one key specific (e.g., quantity or timing)
  50-69:  Directionally correct but too vague to act on without more research
  25-49:  Some action items mentioned but buried or unclear
  0-24:   Purely conceptual — no implementable guidance whatsoever

Respond ONLY with a valid JSON object, no markdown fences:
{{
  "reasoning": "<2-3 sentences evaluating the response critically>",
  "accuracy": <integer 0-100>,
  "relevance": <integer 0-100>,
  "completeness": <integer 0-100>,
  "conciseness": <integer 0-100>,
  "actionability": <integer 0-100>
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


def _call_mistral_judge(prompt: str) -> tuple:
    import requests as req

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise EnvironmentError("MISTRAL_API_KEY is not set.")

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=cfg.RETRY_MIN_WAIT, max=cfg.RETRY_MAX_WAIT),
        stop=stop_after_attempt(cfg.MAX_RETRIES),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _do_call():
        response = req.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": cfg.JUDGE_MODEL.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 512,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    data = _do_call()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    tokens_in = usage.get("prompt_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0)
    cost = (tokens_in / 1_000_000) * cfg.JUDGE_MODEL.cost_per_1m_input + \
           (tokens_out / 1_000_000) * cfg.JUDGE_MODEL.cost_per_1m_output

    return text, round(cost, 6)


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
    elif cfg.JUDGE_MODEL.provider == "mistral":
        raw, judge_cost = _call_mistral_judge(prompt)
    else:
        raise ValueError(f"Unknown judge provider: {cfg.JUDGE_MODEL.provider}")

    scores = _parse_scores(raw)
    scores["judge_cost_usd"] = judge_cost
    return scores
