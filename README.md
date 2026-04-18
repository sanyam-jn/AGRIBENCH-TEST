# AI-AgriBench Evaluation Pipeline

A lightweight, resumable pipeline for evaluating LLMs on agricultural Q&A tasks using an LLM-as-a-Judge approach.

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/sanyam-jn/AGRIBENCH-TEST.git
cd AGRIBENCH-TEST

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set API keys
cp .env.example .env
# Edit .env and fill in GEMINI_API_KEY and GROQ_API_KEY

# 4. Run the pipeline
python pipeline.py

# 5. Results are in results/reports/
```

To resume a partial run, just re-run `python pipeline.py` — completed items are skipped automatically.

---

## Repository Structure

```
AGRIBENCH-TEST/
├── pipeline.py              # Main entry point — run this
├── visualize.py             # Generates charts (called automatically by pipeline.py)
├── config.py                # Model configs, paths, retry settings
├── requirements.txt
├── .env.example             # API key template (copy to .env)
├── written_answers.md       # Part 1 written answers (Q1, Q2, Q4, Q5)
├── Agribench Task.json      # 20-question evaluation dataset
├── src/
│   ├── subject_models.py    # Calls Gemini and Groq APIs with retry/backoff
│   ├── judge.py             # LLM-as-a-Judge scoring (5 metrics)
│   ├── checkpoint.py        # JSONL checkpointing — enables resume
│   ├── contamination.py     # N-gram based contamination flagging
│   └── report.py            # Generates report.md, summary.json, per-question costs
└── results/                 # Created at runtime
    ├── responses/
    │   └── responses.jsonl  # Raw model responses (one JSON object per line)
    ├── scores/
    │   └── scores.jsonl     # Judge scores (one JSON object per line)
    └── reports/
        ├── report.md                        # Human-readable summary
        ├── summary.json                     # Machine-readable full results
        ├── radar_chart.png                  # Spider chart across 5 metrics
        ├── category_bars.png                # Per-category accuracy comparison
        └── conciseness_vs_completeness.png  # Shows the anti-correlation
```

---

## API Keys

| Key | Where to get it | Cost |
|-----|----------------|------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) | Free tier: 20 req/day |
| `GROQ_API_KEY` | [Groq Console](https://console.groq.com/keys) | Free tier with rate limits |

---

## Design Decisions

### Model Selection

| Role | Model | Why |
|------|-------|-----|
| Subject 1 | `gemini-2.5-flash` (Google) | Google's latest frontier flash model — instruction-tuned, tends to be verbose and comprehensive. Strong baseline for measuring the conciseness/completeness tradeoff. |
| Subject 2 | `llama-3.3-70b-versatile` (Groq/Meta) | State-of-the-art open-source model — expected to be more direct but potentially less thorough on specialised agricultural topics. |
| Judge | `gemini-2.5-flash` (Google) | Different generation and role from the subject use — provides independent scoring. Free tier via Google AI Studio. |

These two subject models were chosen to produce **meaningfully different results**: a frontier proprietary model vs. a strong open-source one. Their differences in verbosity, depth, and agricultural specificity make the evaluation genuinely informative.

### Evaluation Methodology: LLM-as-a-Judge

We use a single judge with a structured rubric and strict JSON-format responses. This approach was chosen over:

- **ROUGE/BERTScore**: Too surface-level for agricultural advisory content where a correct answer may use entirely different terminology than the gold answer. A response saying "apply 120 lbs N/acre" and the gold saying "use 55 kg/ha of nitrogen" are equivalent but score poorly under n-gram overlap.
- **Multi-judge ensemble**: Ideal but 3× more expensive and complex. We document this as a limitation — a production system should use ≥3 judges for cross-validation.
- **Custom NLP scoring**: Requires labelled calibration data we don't have for agricultural Q&A.

The judge prompt uses **five-level rubric anchors** (0–24, 25–49, 50–69, 70–89, 90–100) with an explicit instruction to avoid round numbers and reserve 100 for genuinely flawless responses. This forces more discrimination than simple 0/50/100 anchors.

### Five Metrics

| Metric | What it measures |
|--------|----------------|
| **Accuracy** | Factual correctness vs. expert gold answer |
| **Relevance** | Whether the response addresses the question asked |
| **Completeness** | Coverage of key steps, caveats, and conditions |
| **Conciseness** | Focus; absence of filler and unnecessary content |
| **Actionability** *(5th — bonus)* | Whether a farmer can act on the advice immediately without further research |

**Why Actionability?** In agricultural advisory content, the gap between technically accurate and operationally useful is large. A response that correctly identifies nitrogen deficiency but says "apply appropriate fertiliser" offers zero value to a farmer who needs to know how much, in what form, and when. Actionability captures specificity of guidance — quantities, timing windows, decision thresholds — which none of the other four metrics directly measure. It is also genuinely discriminating: in our evaluation, Gemini 2.5 Flash scored 86 vs. Llama's 56, revealing a meaningful difference that accuracy alone would have missed.

### Checkpointing

Every API response and judge score is appended to a JSONL file immediately after receipt. On resume, the pipeline reads the existing checkpoint and skips any `(qna_id, model_name)` pair already present. This means:

- A network failure or rate-limit crash loses at most one in-flight call.
- Partial runs are fully resumable without re-spending on the API.
- Intermediate files are human-readable and inspectable with `jq` or pandas.

### Contamination Detection

We use a heuristic 5-gram overlap check between each model response and the gold answer. A response is flagged if >30% of the gold answer's 5-grams appear verbatim in the response, or if Jaccard word-level similarity exceeds 50%. These are signals for human review, not definitive proof of memorisation. Zero responses were flagged in this evaluation.

### Cost Tracking

Token usage (input + output) is recorded for every API call. Costs are estimated using published per-million-token rates (see `config.py`) and reported per-model and per-question in the final report. The judge's cost is tracked separately. Total cost for this evaluation: **$0.02**.

---

## Results Summary

Evaluated on 20 agricultural Q&A questions across 8 topic categories.

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|-----------------|---------------|
| Accuracy | 94.0 ± 3.5 | **98.5 ± 3.7** |
| Relevance | 99.5 ± 2.2 | **100.0 ± 0.0** |
| Completeness | 89.3 ± 2.5 | **95.0 ± 9.3** |
| Conciseness | **76.5 ± 9.9** | 75.3 ± 12.6 |
| Actionability *(5th)* | **86.0 ± 16.4** | 56.0 ± 16.1 |

**Key finding:** Llama 3.3 70B scores higher on traditional accuracy/completeness metrics, but Gemini 2.5 Flash leads significantly on Actionability (+30 points). This validates the 5th metric as genuinely discriminating — it surfaces a real qualitative difference (specificity of guidance) that the other four metrics cannot capture.

Charts in `results/reports/`: radar chart, per-category bar chart, and conciseness vs. completeness scatter plot confirming the anti-correlation reported in the AI-AgriBench methodology.

---

## Known Limitations

1. **Single judge**: A production system should use ≥3 independent judges and average scores to reduce variance and detect outliers.
2. **Free-tier judge capacity**: Due to daily API limits (20 req/day per Gemini model), some scoring runs used `llama-3.1-8b-instant` as a fallback judge. Smaller models tend to cluster scores around safe round numbers rather than using the full rubric range, reducing discrimination.
3. **Same-family risk**: When Groq's Llama was used as judge, there is a risk of same-family bias — Llama judging Llama may inflate scores for the Llama subject model. This is the same problem the AI-AgriBench methodology addresses by swapping out judges when a model is both subject and evaluator.
4. **Gold answer quality**: Scores are relative to the provided gold answers. If a gold answer is incomplete, a more complete model response may be unfairly penalised on conciseness.
5. **No human calibration**: Without human spot-checks, we cannot confirm the judge's scores correlate with true quality.

---

## If Cost Were Not a Constraint — What I Would Build

This section describes the ideal pipeline design that free-tier limits prevented us from implementing. It reflects how this system should be built for production use at AI-AgriBench scale.

### 1. Three-Judge Ensemble from Different Model Families

Instead of one judge, use three from entirely different training lineages and average their scores:

| Judge | Model | Why |
|-------|-------|-----|
| Judge A | `claude-opus-4-6` (Anthropic) | Best-in-class reasoning, excellent at structured rubric evaluation, strong calibration |
| Judge B | `gpt-4o` (OpenAI) | Different training data and RLHF pipeline; provides independent signal |
| Judge C | `gemini-2.5-pro` (Google) | Different family from subject models; strong at following complex prompts |

Averaging three judges from different families eliminates same-family bias, reduces individual judge variance, and allows **inter-judge agreement** to be computed. When judges disagree by more than 15 points on a metric, that response gets flagged for human review — a much more honest signal than a single judge's score.

This is exactly how AI-AgriBench's own methodology works: three judges with a swap-out rule when the subject model is also a judge.

### 2. Better Subject Model Comparisons

With budget, I would compare models that represent more meaningfully different capability tiers:

- `claude-sonnet-4-6` — strong reasoning, excellent at following constraints
- `gpt-4o` — OpenAI's frontier, different architecture from both current subjects
- `CropWizard` or a RAG-augmented model — to test whether retrieval helps on agricultural Q&A
- A smaller model like `llama-3.1-8b` — to create a full capability spectrum from small to frontier

### 3. Inter-Judge Agreement Metrics

Compute **Cohen's Kappa** or **Krippendorff's Alpha** across judge scores for each metric. Low agreement on a specific metric (e.g., actionability) would indicate the rubric needs refinement — a signal that's invisible with a single judge.

### 4. Embedding-Based Contamination Detection

Replace n-gram overlap with **semantic similarity** using `sentence-transformers` (e.g., `all-mpnet-base-v2`). This catches cases where a model paraphrases the gold answer rather than reproducing it verbatim — a much harder and more realistic contamination scenario.

### 5. Async Pipeline for Speed

The current pipeline is fully sequential. With `asyncio` and concurrent API calls, both subject models could be queried in parallel per question, cutting Phase 1 time roughly in half. The judge calls could also be batched.

### 6. Human Spot-Check Validation

For a 10% random sample of responses, collect human expert ratings and compute correlation with judge scores. This is the only way to validate that LLM-as-a-Judge scores actually track quality. Without it, high scores are plausible but unverified.

### 7. Calibration Study

Run the judge on a set of deliberately bad responses (e.g., off-topic, factually wrong, copy-pasted unrelated text) and verify it produces low scores. This stress-tests the rubric and catches judges that are systematically lenient.

### 8. Statistical Significance Testing

With only 20 questions, observed score differences between models may not be statistically significant. A production evaluation would use a larger question set and report confidence intervals and p-values on metric differences — especially important when model scores are close.

---

## Resuming a Partial Run

```bash
python pipeline.py
```

The pipeline reads existing checkpoint files and skips completed items. To force a full re-run of the scoring phase only:

```bash
rm results/scores/scores.jsonl
python pipeline.py
```

---

## Bonus Features Implemented

| Feature | Where |
|---------|-------|
| 5th metric (Actionability) | `src/judge.py` — judge prompt + rubric |
| Cost tracking (per-model + per-question) | `src/report.py` — reported in `report.md` and `summary.json` |
| Contamination detection | `src/contamination.py` — n-gram + Jaccard flagging |
| Visualizations | `visualize.py` — radar chart, category bars, scatter plot |
