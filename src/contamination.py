"""
Simple contamination detection / flagging.

Goal: flag responses where the model may have memorised the gold answer
rather than genuinely reasoning through the question.

Approach:
  1. 5-gram overlap — if a large fraction of the gold answer's 5-grams
     appear verbatim in the response, the model may have seen the exact
     text during training.
  2. Jaccard similarity at the word level — a coarser signal for overall
     vocabulary overlap.

These are heuristic flags, not definitive proof of contamination.
A high score suggests the response warrants human review.

Thresholds:
  5-gram overlap > 0.30 → flagged  (30% of gold 5-grams found in response)
  Jaccard > 0.50         → flagged  (50% word-level overlap)
"""

import re
from typing import Set


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into words."""
    return re.findall(r"[a-z]+", text.lower())


def _get_ngrams(tokens: list[str], n: int) -> Set[tuple]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def check_contamination(
    response: str,
    gold_answer: str,
    ngram_threshold: float = 0.30,
    jaccard_threshold: float = 0.50,
    n: int = 5,
) -> dict:
    """
    Return a contamination assessment dict.

    Keys:
      jaccard_similarity  — word-level Jaccard between response and gold
      ngram_overlap       — fraction of gold n-grams found in response
      flagged             — True if either threshold is exceeded
      flag_reasons        — list of strings describing which checks fired
    """
    response_tokens = _tokenize(response)
    gold_tokens = _tokenize(gold_answer)

    # Jaccard
    response_words = set(response_tokens)
    gold_words = set(gold_tokens)
    union = response_words | gold_words
    jaccard = len(response_words & gold_words) / len(union) if union else 0.0

    # N-gram overlap
    response_ngrams = _get_ngrams(response_tokens, n)
    gold_ngrams = _get_ngrams(gold_tokens, n)
    ngram_overlap = (
        len(response_ngrams & gold_ngrams) / len(gold_ngrams)
        if gold_ngrams
        else 0.0
    )

    flag_reasons = []
    if ngram_overlap > ngram_threshold:
        flag_reasons.append(
            f"{n}-gram overlap {ngram_overlap:.2%} exceeds threshold {ngram_threshold:.0%}"
        )
    if jaccard > jaccard_threshold:
        flag_reasons.append(
            f"Jaccard similarity {jaccard:.2%} exceeds threshold {jaccard_threshold:.0%}"
        )

    return {
        "jaccard_similarity": round(jaccard, 4),
        "ngram_overlap": round(ngram_overlap, 4),
        "flagged": bool(flag_reasons),
        "flag_reasons": flag_reasons,
    }
