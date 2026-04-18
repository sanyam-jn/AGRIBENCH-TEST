# AI-AgriBench — Part 1: Written Answers

---

## Q1

**Answer: B**

The primary risk of using GPT-4o-mini (or any LLM) to generate Q&A pairs is that the output reflects the generator model's own training distribution, reasoning tendencies, and blind spots — not the full breadth of the source documents. GPT-4o-mini will naturally gravitate toward aspects of agricultural content that are well-represented in its pretraining data (e.g., common crops, mainstream practices) and will underemphasize edge cases, regionally specific guidance, or nuanced agronomic conditions that appear infrequently in general web text. The questions generated are shaped by what the model finds salient and tractable, not by what is actually most important to a practitioner. This means the benchmark may systematically undertest precisely the areas where LLMs are weakest, producing a falsely optimistic picture of model capability.

---

## Q2

**Answer: B**

Stronger models produce more thorough responses that inherently use more text, which the conciseness rubric penalizes.

**Reasoning:** The AI-AgriBench gold answers are expert-curated to be practical and focused (2–4 paragraphs). Frontier models, however, tend to elaborate beyond that baseline — covering additional caveats, conditions, and edge cases that increase coverage (completeness) but also word count. The conciseness rubric scores responses down for verbosity and "unnecessary complexity," so a model that is more complete by nature will score lower on conciseness. This is a genuine structural tension in the metric design, not a judge artifact or a problem with the gold answers. It reflects a real tradeoff: brevity vs. thoroughness.

---

## Q4

**Why the swap is necessary:**

A model that judges its own outputs introduces self-evaluation bias — it will tend to rate responses that match its own reasoning style, vocabulary, and structural preferences more favorably, regardless of actual quality. This artificially inflates the subject model's scores and undermines the validity of cross-model comparisons.

**One remaining risk even after the swap:**

The replacement judge (e.g., GPT-5.1 in the blog) may have systematically different calibration than the three standard judges (Claude Opus 4.5, Gemini-3-Pro-Preview, Kimi-K2-thinking) — it may score more harshly or leniently across the board, or weight certain rubric dimensions differently. This means the swapped model's scores are not evaluated on an identical scale to the others, making direct comparisons subtly unreliable. The methodology mitigates bias but does not fully resolve inconsistency in judge calibration.

---

## Q5 — Proposed Fifth Metric: **Actionability**

**Definition:** Actionability measures the degree to which a response provides specific, implementable guidance that a farmer can act on without needing to seek further clarification — in terms of concrete quantities, timing windows, decision thresholds, or ordered steps.

**Why it matters for agricultural advisory content specifically:** In agricultural contexts, the gap between technically accurate and operationally useful advice is large. A response that correctly identifies nitrogen deficiency but recommends "apply appropriate nitrogen fertilizer" offers no value to a farmer who needs to know how much, in what form, and when. Vague advice in farming carries real cost: mistimed or mis-dosed applications can damage crops, waste inputs, or miss critical windows entirely. Actionability is distinct from completeness (which measures coverage of concepts) — a complete answer can still be too abstract to act on.

**How to score it:** Using an LLM judge with a structured rubric (0–100 scale): 90–100 if the response includes specific quantities or rates, explicit timing or sequencing, named inputs or products, and clear conditional logic (e.g., "if soil pH < 6.0, apply 2 tons/acre lime before planting"); 70–89 if most of these are present but one is vague; 50–69 if the advice is directionally correct but lacks specifics a farmer needs to act; 0–49 if the response is purely conceptual with no implementable guidance. The judge would be prompted to ask: "Could a farmer with basic training act on this advice today, without further research?"
