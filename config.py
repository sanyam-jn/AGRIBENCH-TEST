"""
Central configuration for the AI-AgriBench evaluation pipeline.
Adjust model IDs, costs, and paths here without touching pipeline logic.
"""

from dataclasses import dataclass


@dataclass
class ModelConfig:
    name: str           # short label used in output files
    provider: str       # "google" | "groq"
    model_id: str       # exact API model identifier
    cost_per_1m_input: float   # USD per 1M input tokens
    cost_per_1m_output: float  # USD per 1M output tokens


# ── Subject models ────────────────────────────────────────────────────────────
# We chose these two because they represent meaningfully different paradigms:
#   - Gemini 1.5 Flash: Google's instruction-tuned frontier model; tends to be
#     verbose, comprehensive, and highly coherent.
#   - Llama 3.3 70B (Groq): Meta's open-source model served by Groq; tends to
#     be more direct but may lack depth on specialized agricultural topics.
# Comparing them lets us probe whether open-source models close the gap on
# domain-specific Q&A and whether verbosity tracks quality.

SUBJECT_MODELS = [
    ModelConfig(
        name="gemini-2.5-flash",
        provider="google",
        model_id="gemini-2.5-flash",
        cost_per_1m_input=0.15,
        cost_per_1m_output=0.60,
    ),
    ModelConfig(
        name="llama-3.3-70b",
        provider="groq",
        model_id="llama-3.3-70b-versatile",
        cost_per_1m_input=0.59,
        cost_per_1m_output=0.79,
    ),
]

# ── Judge model ───────────────────────────────────────────────────────────────
# We use Gemini 2.5 Flash Lite as judge — lighter and distinct from the
# gemini-2.5-flash subject model, reducing same-version self-evaluation bias.
JUDGE_MODEL = ModelConfig(
    name="mistral-small",
    provider="mistral",
    model_id="mistral-small-latest",
    cost_per_1m_input=0.10,
    cost_per_1m_output=0.30,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
QUESTIONS_FILE = "Agribench Task.json"
RESULTS_DIR = "results"
RESPONSES_DIR = f"{RESULTS_DIR}/responses"
SCORES_DIR = f"{RESULTS_DIR}/scores"
REPORTS_DIR = f"{RESULTS_DIR}/reports"

RESPONSES_CHECKPOINT = f"{RESPONSES_DIR}/responses.jsonl"
SCORES_CHECKPOINT = f"{SCORES_DIR}/scores.jsonl"

# ── Retry / rate-limit settings ───────────────────────────────────────────────
MAX_RETRIES = 5
RETRY_MIN_WAIT = 2   # seconds
RETRY_MAX_WAIT = 60  # seconds
