# AI-AgriBench Evaluation Pipeline

A  pipeline for evaluating LLMs on agricultural Q&A tasks using an LLM-as-a-Judge approach.

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
# Edit .env and fill in the API keys

# 4. Run the pipeline
python pipeline.py

# 5. Results are in results/reports/
```

To resume a partial run, just re-run `python pipeline.py` — completed items are skipped automatically.

---

## Repository Structure

```
AGRIBENCH-TEST/
├── pipeline.py              # Main entry point - run this
├── visualize.py             # Generates charts (called automatically by pipeline.py)
├── validate.py              # Extended validation metrics (run after pipeline.py)
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
    ├── validation/          # Created by validate.py
    │   ├── fact_check.jsonl     # Per-claim fact check results (checkpointed)
    │   └── confidence.jsonl     # Per-response confidence analysis (checkpointed)
    └── reports/
        ├── report.md                        # Human-readable summary
        ├── summary.json                     # Machine-readable full results
        ├── validation_report.md             # Extended validation findings
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
| `MISTRAL_API_KEY` | [Mistral Console](https://console.mistral.ai/) | Free tier available |

---

## Design Decisions

### Model Selection

| Role | Model | Why |
|------|-------|-----|
| Subject 1 | `gemini-2.5-flash` (Google) | Google's latest frontier flash model instruction-tuned, tends to be verbose and comprehensive. Strong baseline for measuring the conciseness/completeness tradeoff. |
| Subject 2 | `llama-3.3-70b-versatile` (Groq/Meta) | State-of-the-art open-source model expected to be more direct but potentially less thorough on specialised agricultural topics. |
| Judge | `mistral-small-latest` (Mistral AI) | Completely different model family from both subjects eliminates same-family bias entirely. Free tier available. Produces well-calibrated scores with real variance across the 0–100 range. |

These two subject models were chosen to produce **meaningfully different results**: a frontier proprietary model vs. a strong open-source one. Their differences in verbosity, depth, and agricultural specificity make the evaluation genuinely informative.

### Evaluation Methodology: LLM-as-a-Judge

I use a single judge with a structured rubric and strict JSON-format responses. This approach was chosen over:

- **ROUGE/BERTScore**: Too surface-level for agricultural advisory content where a correct answer may use entirely different terminology than the gold answer. A response saying "apply 120 lbs N/acre" and the gold saying "use 55 kg/ha of nitrogen" are equivalent but score poorly under n-gram overlap.
- **Multi-judge ensemble**: Ideal but 3× more expensive. I document this as a limitation a production system should use ≥3 judges for cross-validation.
- **Custom NLP scoring**: Requires labelled calibration data I don't have for agricultural Q&A.

The judge prompt uses **five-level rubric anchors** (0–24, 25–49, 50–69, 70–89, 90–100) with an explicit instruction to avoid round numbers and reserve 100 for genuinely flawless responses. This forces more discrimination than simple 0/50/100 anchors.

### Five Metrics

| Metric | What it measures |
|--------|----------------|
| **Accuracy** | Factual correctness vs. expert gold answer |
| **Relevance** | Whether the response addresses the question asked |
| **Completeness** | Coverage of key steps, caveats, and conditions |
| **Conciseness** | Focus; absence of filler and unnecessary content |
| **Actionability**  | Whether a farmer can act on the advice immediately without further research |

**Why Actionability?** In agricultural advisory content, the gap between technically accurate and operationally useful is large. A response that correctly identifies nitrogen deficiency but says "apply appropriate fertiliser" offers zero value to a farmer who needs to know how much, in what form, and when. Actionability captures specificity of guidance quantities, timing windows, decision thresholds which none of the other four metrics directly measure. It is also genuinely discriminating: in my evaluation, Gemini 2.5 Flash scored 94.3 vs. Llama's 84.85, a 9.5 point gap that was invisible under accuracy (97.75 vs. 94.5). The gap was largest in Water Management (94.5 vs. 70.5) where irrigation advice must be site-specific to be actionable.

### Checkpointing

Every API response and judge score is appended to a JSONL file immediately after receipt. On resume, the pipeline reads the existing checkpoint and skips any `(qna_id, model_name)` pair already present. This means:

- A network failure or rate-limit crash loses at most one in-flight call.
- Partial runs are fully resumable without re-spending on the API.
- Intermediate files are human-readable and inspectable with `jq` or pandas.

### Contamination Detection

I use a heuristic 5-gram overlap check between each model response and the gold answer. A response is flagged if >30% of the gold answer's 5-grams appear verbatim in the response, or if Jaccard word-level similarity exceeds 50%. These are signals for human review, not definitive proof of memorisation. Zero responses were flagged in this evaluation.

### Cost Tracking

Token usage (input + output) is recorded for every API call. Costs are estimated using published per-million-token rates (see `config.py`) and reported per-model and per-question in the final report. The judge's cost is tracked separately.

All three APIs (Gemini, Groq, Mistral) were used on their **free tiers** — actual spend was **$0.00**. The estimated cost of **$0.026** reflects what this evaluation would cost at paid-tier rates, which is useful for understanding the pipeline's economics at production scale.

---

## Results Summary

Evaluated on 20 agricultural Q&A questions across 8 topic categories.  
Judge: `mistral-small-latest` neutral third party, different family from both subject models.

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|-----------------|---------------|
| **Accuracy** | **97.75 ± 0.91** | 94.5 ± 2.59 |
| **Relevance** | **98.45 ± 3.38** | 96.75 ± 2.45 |
| **Completeness** | **97.65 ± 1.23** | 92.35 ± 3.99 |
| **Conciseness** | **91.15 ± 3.57** | 88.15 ± 2.92 |
| **Actionability** *(5th)* | **94.3 ± 3.69** | 84.85 ± 8.42 |

**Key findings:**
- Gemini 2.5 Flash wins on all 5 metrics when judged by a neutral third-party model (Mistral Small)
- **Actionability** is the most discriminating metric 9.5-point gap vs. only 3.25-point gap on accuracy
- The largest single-category gap is Water Management actionability (94.5 vs. 70.5), consistent with the domain: irrigation advice must be site-specific to be implementable
- **Conciseness is the lowest-scoring metric for both models**, confirming the anti-correlation with Completeness reported in the AI-AgriBench methodology
- No contamination detected across all 40 responses
- Total pipeline cost: **$0.00** (all free tiers) — estimated paid-tier equivalent: **$0.026**

Charts in `results/reports/`: radar chart, per-category bar chart, and conciseness vs. completeness scatter plot directly confirming the anti-correlation from Q2 of the written answers.

---

## Known Limitations

1. **Single judge**: A production system should use ≥3 independent judges and average scores to reduce variance and detect outliers. I used one (Mistral Small) due to free-tier constraints.
2. **Judge calibration drift (documented and resolved)**: Early scoring runs used `llama-3.1-8b-instant` as a fallback judge when Gemini's free quota was exhausted. That run produced clustered round-number scores (95, 90, 100) a textbook sign of an under-calibrated judge. I identified this problem, switched to Mistral Small (a different model family with no overlap with either subject model), rewrote the judge prompt with five-level rubric anchors, and re-scored all 40 responses. Final scores show proper variance and no same-family bias.
3. **Gold answer quality**: Scores are relative to the provided gold answers. If a gold answer is incomplete, a more complete model response may be unfairly penalised on conciseness.
4. **No human calibration**: Without human spot-checks, I cannot confirm the judge's scores correlate with true quality. This is the most honest remaining gap.
5. **20-question sample size**: Score differences between models may not reach statistical significance. A production evaluation would use a larger set and report p-values on metric deltas.

---

## If Cost Were Not a Constraint — What I Would Build

This section describes the ideal pipeline design that free-tier limits prevented me from implementing. It reflects how this system should be built for production use at AI-AgriBench scale.

### 1. Three-Judge Ensemble from Different Model Families

Instead of one judge, I would use three from entirely different training lineages and average their scores:

| Judge | Model | Why |
|-------|-------|-----|
| Judge A | `claude-opus-4-6` (Anthropic) | Best-in-class reasoning, excellent at structured rubric evaluation, strong calibration |
| Judge B | `gpt-4o` (OpenAI) | Different training data and RLHF pipeline; provides independent signal |
| Judge C | `gemini-2.5-pro` (Google) | Different family from subject models; strong at following complex prompts |

Averaging three judges from different families eliminates same-family bias, reduces individual judge variance, and allows **inter-judge agreement** to be computed. When judges disagree by more than 15 points on a metric, that response gets flagged for human review a much more honest signal than a single judge's score.



### 2. Better Subject Model Comparisons

With budget, I would compare models that represent more meaningfully different capability tiers:

- `claude-sonnet-4-6` — strong reasoning, excellent at following constraints
- `gpt-4o` — OpenAI's frontier, different architecture from both current subjects
- `CropWizard` or a RAG-augmented model to test whether retrieval helps on agricultural Q&A
- A smaller model like `llama-3.1-8b` to create a full capability spectrum from small to frontier

### 3. Inter-Judge Agreement Metrics

Compute **Cohen's Kappa** or **Krippendorff's Alpha** across judge scores for each metric. Low agreement on a specific metric (e.g., actionability) would indicate the rubric needs refinement a signal that's invisible with a single judge.

### 4. Embedding-Based Contamination Detection

Replace n-gram overlap with **semantic similarity** using `sentence-transformers` (e.g., `all-mpnet-base-v2`). This catches cases where a model paraphrases the gold answer rather than reproducing it verbatim a much harder and more realistic contamination scenario.

### 5. Async Pipeline for Speed

The current pipeline is fully sequential. With `asyncio` and concurrent API calls, both subject models could be queried in parallel per question, cutting Phase 1 time roughly in half. The judge calls could also be batched.

### 6. Human Spot-Check Validation

For a 10% random sample of responses, collect human expert ratings and compute correlation with judge scores. This is the only way to validate that LLM-as-a-Judge scores actually track quality. Without it, high scores are plausible but unverified.

### 7. Calibration Study

Run the judge on a set of deliberately bad responses (e.g., off-topic, factually wrong, copy-pasted unrelated text) and verify it produces low scores. This stress-tests the rubric and catches judges that are systematically lenient.

### 8. Statistical Significance Testing

With only 20 questions, observed score differences between models may not be statistically significant. A production evaluation would use a larger question set and report confidence intervals and p-values on metric differences especially important when model scores are close.

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

---

## Extended Validation Metrics (Beyond the Assignment)

After completing the main pipeline, I built two additional metrics in `validate.py`. These were not part of the original requirement they came from a question I asked myself: *my accuracy scores look good, but how do I know the judge isn't missing hidden errors?*

Run after the main pipeline:

```bash
python validate.py
```

Produces `results/reports/validation_report.md` and raw data in `results/validation/`.

---

### Metric 1 — Fact Check Score

*Does every claim the model makes hold up against the expert answer?*

The main pipeline scores accuracy holistically a judge reads the whole response and forms an overall impression. That works most of the time, but it can miss one confidently-stated wrong fact buried in an otherwise good response. In agriculture, one wrong fact the wrong nitrogen rate, the wrong pesticide timing can damage a crop. The impression that a response is "mostly right" is not good enough.

So I built claim-level verification. Each response is broken into individual factual sentences. Every sentence is checked against the gold answer supported, neutral, or contradicted. Each contradiction costs 25 points, applied as a hard penalty on top of the base score. A response with 9 correct claims and 1 contradiction scores around 64, not 89. That is intentional.

The most useful output is the divergence table where Fact Check and holistic Accuracy disagree by more than 10 points, that is exactly where hallucinations are hiding.

---

### Metric 2 — Confidence Check Score

*Is the model appropriately uncertain, or is it overclaiming?*

Agricultural advice is never one-size-fits-all. Soil type, region, growth stage, and weather all change what a farmer should do. Good advisors say "typically 100–150 lbs/acre depending on your soil test" not "apply 150 lbs/acre." A model that sounds more certain than the expert is making claims it cannot support.

This metric compares the hedging level of the model response against the hedging level of the gold answer. Overclaiming is penalized more than being too vague because vague advice is unhelpful, but overconfident wrong advice can cause real damage. The output also flags the direction: does the model overclaim, underclaim, or match the expert's confidence level?

This is something none of the four standard metrics can detect. A response can score 95 on accuracy and still be dangerously overconfident.

---

### Results

#### Fact Check Score

| Model | Fact Check Score | Avg Claims per Response | Contradictions Found |
|-------|-----------------|------------------------|---------------------|
| gemini-2.5-flash | 56.15 | 25.9 | 0.19 avg (3 total) |
| llama-3.3-70b | 51.16 | 23.2 | 0.11 avg (2 total) |

The lower Fact Check scores are expected and explained: model responses are much longer than the gold answers (frontier models generate 25+ claims vs. the expert's focused 2–4 paragraphs). Most extra claims are "neutral" not in the gold, not contradicted. The real signal is the contradictions found:

**Actual contradicted claims across all 40 responses:**
- `llama / qna_000161` — *"Using kochia-free water sources for irrigation prevents the introduction of kochia seeds"* (not supported by the expert answer)
- `llama / qna_000007` — *"Organic nitrogen-rich amendments release nitrogen quickly"* (expert says mineralization is gradual)
- `gemini / qna_000043` — *"Over-irrigation causes sugarcane leaves to wilt despite ample water"* (expert does not make this claim)
- `gemini / qna_000043` — *"Over-irrigation causes roots to appear dark, mushy, and have a foul odor"* (not in expert answer)
- `gemini / qna_000007` — *"Fresh manure can lead to nitrogen immobilization, weed seeds, pathogens, and nutrient burn"* (expert does not mention these risks)

Only 5 contradictions across 40 responses this actually **validates the holistic accuracy scores**. The models are not hallucinating facts; they are adding extra neutral information beyond the gold answer.

#### Confidence Check Score

| Model | Confidence Score | Overclaims | Underclaims | Calibrated |
|-------|-----------------|-----------|------------|------------|
| gemini-2.5-flash | **89.5** | 10 | 0 | 10 |
| llama-3.3-70b | 83.75 | 14 | 0 | 6 |

**Key finding:** Neither model ever underclaims both are always at least as specific as the expert. Llama overclaims more often (14/20 questions) it tends to give prescriptive numbered lists with specific rates the expert did not provide. Gemini is better calibrated, matching the expert's level of certainty on 10/20 questions.

**Zero underclaiming** is an interesting domain finding: frontier models are systematically more confident than agricultural experts. In a real advisory context, this matters a farmer trusting a confident-sounding model may not seek the local expertise they actually need.

#### Combined View

| Model | Holistic Accuracy | Fact Check | Confidence Check |
|-------|-----------------|-----------|------------------|
| **gemini-2.5-flash** | **97.75** | **56.15** | **89.5** |
| llama-3.3-70b | 94.5 | 51.16 | 83.75 |

Gemini wins across all three views. The Fact Check and Confidence Check results together tell a consistent story: both models are factually sound (only 5 contradictions total), but Llama tends to overclaim more and is less well-calibrated to the expert's level of certainty.
