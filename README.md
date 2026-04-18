# AI-AgriBench Evaluation Pipeline

A lightweight, resumable pipeline for evaluating LLMs on agricultural Q&A tasks using an LLM-as-a-Judge approach.

---

## Quick Start

```bash
# 1. Clone / unzip the repo
cd agribench-test

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set API keys
cp .env.example .env
# Edit .env and fill in GEMINI_API_KEY and GROQ_API_KEY

# 4. Run the pipeline
python pipeline.py

# 5. Results are in results/reports/
```

---

## Repository Structure

```
agribench-test/
├── pipeline.py              # Main entry point — run this
├── visualize.py             # Bonus: generates charts (called by pipeline.py)
├── config.py                # Model configs, paths, retry settings
├── requirements.txt
├── .env.example             # API key template
├── written_answers.md       # Part 1 written answers
├── Agribench Task.json      # 20-question evaluation set
├── src/
│   ├── subject_models.py    # Calls Gemini and Groq APIs
│   ├── judge.py             # LLM-as-a-Judge scoring (5 metrics)
│   ├── checkpoint.py        # JSONL checkpointing for resume
│   ├── contamination.py     # N-gram based contamination flagging
│   └── report.py            # Generates report.md and summary.json
└── results/                 # Created at runtime
    ├── responses/
    │   └── responses.jsonl  # Raw model responses (one per line)
    ├── scores/
    │   └── scores.jsonl     # Judge scores (one per line)
    └── reports/
        ├── report.md        # Human-readable summary
        ├── summary.json     # Machine-readable full results
        ├── radar_chart.png
        ├── category_bars.png
        └── conciseness_vs_completeness.png
```

---

## API Keys

| Key | Where to get it | Cost |
|-----|----------------|------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) | Free tier available |
| `GROQ_API_KEY` | [Groq Console](https://console.groq.com/keys) | Free tier available |

---

## Design Decisions

### Model Selection

| Role | Model | Why |
|------|-------|-----|
| Subject 1 | `gemini-2.5-flash` (Google) | Google's latest frontier flash model; tends to be verbose and comprehensive — useful baseline for measuring the conciseness/completeness tradeoff |
| Subject 2 | `llama-3.3-70b-versatile` (Groq/Meta) | State-of-the-art open-source model; expected to be more direct but potentially less thorough on specialised agricultural topics |
| Judge | `llama-3.1-8b-instant` (Groq/Meta) | Smaller, faster model from a different generation than both subjects; avoids same-model self-evaluation bias |

These two subject models were chosen specifically to produce **meaningfully different results**: a frontier proprietary model vs. a strong open-source one. Their differences in verbosity, depth, and agricultural specificity make the evaluation informative.

### Evaluation Methodology: LLM-as-a-Judge

We use a single Llama 3.1 8B judge (via Groq) with a structured rubric and JSON-format responses. This approach was chosen over:

- **ROUGE/BERTScore**: Too surface-level for agricultural advisory content where a correct answer may use different terminology than the gold answer.
- **Multi-judge ensemble**: Ideal but 3× more expensive and complex. We document this as a limitation — a production system should use ≥3 judges for cross-validation.
- **Custom NLP scoring**: Requires labelled calibration data we don't have for agricultural Q&A.

The judge prompt includes explicit rubric anchors at 0, 50, and 100 for each metric, ensuring calibration rather than free-form scoring.

### Five Metrics

| Metric | What it measures |
|--------|----------------|
| **Accuracy** | Factual correctness vs. gold answer |
| **Relevance** | Whether the response addresses the question |
| **Completeness** | Coverage of key steps, caveats, and conditions |
| **Conciseness** | Focus; absence of filler and unnecessary content |
| **Actionability** *(5th)* | Whether a farmer can act on the advice immediately — checks for specific quantities, timing, thresholds |

**Why Actionability?** In agricultural advisory content, technically accurate answers can still be useless if they don't tell a farmer *what to do, how much, and when*. This metric captures that gap between knowledge and implementable guidance, which the other four metrics don't directly measure.

### Checkpointing

Every API response and judge score is appended to a JSONL file immediately after it is received. On resume, the pipeline reads the existing checkpoint and skips any (qna_id, model_name) pair already present. This means:

- A network failure or rate-limit crash loses at most one in-flight call.
- Partial runs are fully resumable without any re-spending on the API.

### Contamination Detection

We use a heuristic 5-gram overlap check between each model response and the gold answer. A response is flagged if >30% of the gold answer's 5-grams appear verbatim in the response. This is a signal for human review, not definitive proof of memorisation.

### Cost Tracking

Token usage is recorded for every API call (input + output). Costs are estimated using published per-million-token rates (see `config.py`) and reported in the final summary. The judge's cost is tracked separately.

---

## Resuming a Partial Run

Simply re-run `python pipeline.py`. The checkpoint files in `results/responses/` and `results/scores/` are read at startup and already-completed items are skipped.

---

## Known Limitations

1. **Single judge model**: A production system should use ≥3 independent judges and average scores to reduce variance.
2. **Smaller judge**: Llama 3.1 8B is used as judge for cost/availability reasons. A larger judge would produce more reliable scores.
3. **Gold answer quality**: Scores are relative to the provided gold answers. If a gold answer is incomplete, a more complete model response will be unfairly penalised on conciseness.
4. **LLM judge calibration**: Without human validation, we cannot confirm the judge's scores correlate with true quality. Confidence intervals on scores should be treated as approximate.

---

## Results Summary

Evaluated on 20 agricultural Q&A questions across 8 topic categories. Total cost: **$0.02**.

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|-----------------|---------------|
| Accuracy | 94.0 ± 3.5 | **98.5 ± 3.7** |
| Relevance | 99.5 ± 2.2 | **100.0 ± 0.0** |
| Completeness | 89.3 ± 2.5 | **95.0 ± 9.3** |
| Conciseness | **76.5 ± 9.9** | 75.3 ± 12.6 |
| Actionability *(5th)* | **86.0 ± 16.4** | 56.0 ± 16.1 |

**Key finding:** Llama 3.3 70B scores higher on traditional accuracy/completeness metrics, but Gemini 2.5 Flash leads significantly on Actionability — it provides more specific, implementable guidance (quantities, timing, thresholds) that a farmer can act on immediately. This validates the 5th metric as genuinely discriminating rather than redundant. No contamination was detected in any of the 40 responses.

Charts available in `results/reports/`: radar chart, per-category bar chart, and conciseness vs. completeness scatter plot.
