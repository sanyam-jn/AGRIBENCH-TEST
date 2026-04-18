"""
Subject model callers.

Each function takes a ModelConfig and a question string, calls the appropriate
API with retry/backoff, and returns a dict with:
  - text:          the model's answer
  - tokens_input:  prompt tokens used
  - tokens_output: completion tokens used
  - cost_usd:      estimated cost in USD
"""

import os
import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

import config as cfg

logger = logging.getLogger(__name__)

SUBJECT_SYSTEM_PROMPT = (
    "You are an expert agricultural advisor. Answer the farmer's question "
    "accurately, completely, and practically. Provide specific, actionable "
    "guidance based on established agronomic best practices. "
    "Do not add unnecessary preamble or filler text."
)


# ── Google Gemini (new google-genai SDK) ──────────────────────────────────────

def _call_gemini(model_config: "cfg.ModelConfig", question: str) -> dict:
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
            model=model_config.model_id,
            contents=f"{SUBJECT_SYSTEM_PROMPT}\n\nQuestion: {question}",
        )

    response = _do_call()
    text = response.text

    usage = getattr(response, "usage_metadata", None)
    tokens_in = getattr(usage, "prompt_token_count", 0) or 0
    tokens_out = getattr(usage, "candidates_token_count", 0) or 0
    cost = (tokens_in / 1_000_000) * model_config.cost_per_1m_input + \
           (tokens_out / 1_000_000) * model_config.cost_per_1m_output

    return {
        "text": text,
        "tokens_input": tokens_in,
        "tokens_output": tokens_out,
        "cost_usd": round(cost, 6),
    }


# ── Groq (Llama / open-source) ────────────────────────────────────────────────

def _call_groq(model_config: "cfg.ModelConfig", question: str) -> dict:
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
            model=model_config.model_id,
            messages=[
                {"role": "system", "content": SUBJECT_SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            temperature=0.2,
            max_tokens=1024,
        )

    completion = _do_call()
    text = completion.choices[0].message.content

    usage = completion.usage
    tokens_in = usage.prompt_tokens if usage else 0
    tokens_out = usage.completion_tokens if usage else 0
    cost = (tokens_in / 1_000_000) * model_config.cost_per_1m_input + \
           (tokens_out / 1_000_000) * model_config.cost_per_1m_output

    return {
        "text": text,
        "tokens_input": tokens_in,
        "tokens_output": tokens_out,
        "cost_usd": round(cost, 6),
    }


# ── Public dispatch ───────────────────────────────────────────────────────────

def call_subject_model(model_config: "cfg.ModelConfig", question: str) -> dict:
    """Route to the correct provider and return a standardised result dict."""
    if model_config.provider == "google":
        return _call_gemini(model_config, question)
    elif model_config.provider == "groq":
        return _call_groq(model_config, question)
    else:
        raise ValueError(f"Unknown provider: {model_config.provider}")
