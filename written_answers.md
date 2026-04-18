# AI-AgriBench — Part 1: Written Answers

---

## Q1

**Answer: B**

The primary risk of using GPT-4o-mini (or any LLM) to generate Q&A pairs is that the output reflects the generator model's own training distribution, reasoning tendencies, and blind spots — not the full breadth of the source documents. GPT-4o-mini will naturally gravitate toward aspects of agricultural content that are well-represented in its pretraining data (e.g., common crops like corn and soybeans, mainstream U.S. practices) and will underemphasize edge cases, regionally specific guidance, or nuanced agronomic conditions that appear infrequently in general web text — for example, pest management strategies specific to smallholder farms in humid subtropical climates, or traditional soil amendment practices not widely covered in English-language extension literature.

The questions generated are shaped by what the model finds salient and tractable, not by what is actually most important to a practitioner. This creates a systematic blind spot: the benchmark may undertest precisely the areas where LLMs are weakest, producing a falsely optimistic picture of model capability on the long tail of agricultural knowledge. The expert review stage (23 reviewers, 951 questions filtered to 416) mitigates this somewhat, but it cannot recover topics the generator never produced in the first place.

---

## Q2

**Answer: B**

Stronger models produce more thorough responses that inherently use more text, which the conciseness rubric penalizes.

**Reasoning:** The AI-AgriBench gold answers are expert-curated to be practical and focused (2–4 paragraphs). Frontier models, however, tend to elaborate beyond that baseline — covering additional caveats, conditions, and edge cases that increase coverage (completeness) but also word count. The conciseness rubric scores responses down for verbosity and "unnecessary complexity," so a model that is more complete by nature will score lower on conciseness. This is a genuine structural tension in the metric design, not a judge artifact or a problem with the gold answers — it reflects the real tradeoff between brevity and thoroughness that practitioners face when writing advisory content.

**Confirmed by our own evaluation:** Our pipeline independently reproduced this finding. In our conciseness vs. completeness scatter plot (included in the repository), both Gemini 2.5 Flash and Llama 3.3 70B exhibit a negative slope — questions where a model scored higher on completeness tended to score lower on conciseness. Gemini, which scored 5 points higher on completeness than Llama (97.65 vs. 92.35), also scored slightly lower on conciseness on certain questions, directly mirroring the pattern the benchmark reports. This suggests the anti-correlation is a property of how frontier models approach advisory content, not an artifact of any specific judge.

---

## Q4

**Why the swap is necessary:**

A model that judges its own outputs introduces self-evaluation bias — it will tend to rate responses that match its own reasoning style, vocabulary, and structural preferences more favorably, regardless of actual quality. For example, if Claude Opus 4.5 is both the subject model and a judge, it may rate responses that follow its own preferred structure (e.g., bulleted lists, hedged language) more highly even when the content is identical to a differently formatted response. This artificially inflates the subject model's scores and undermines the validity of cross-model comparisons — the model is essentially grading its own exam.

**One remaining risk even after the swap:**

The replacement judge (GPT-5.1 in the blog) may have systematically different calibration than the three standard judges (Claude Opus 4.5, Gemini-3-Pro-Preview, Kimi-K2-thinking) — it may score more harshly or leniently across the board, or weight certain rubric dimensions differently. This means the swapped model's scores are evaluated on a subtly different scale than all other models, making direct comparisons unreliable. The methodology eliminates within-model bias but introduces between-judge calibration inconsistency — a tradeoff that is difficult to resolve without a formal calibration study using human-annotated reference responses as anchors.

We encountered this exact problem in our own pipeline: when we were forced to use a smaller fallback judge (Llama 3.1 8B) due to quota exhaustion, scores clustered around round numbers (95, 90, 100) rather than using the full rubric range — a clear sign of calibration drift from the primary judge. Switching to Mistral Small as a neutral third-party judge resolved this.

---

## Q5 — Proposed Fifth Metric: **Actionability**

**Definition:** Actionability measures the degree to which a response provides specific, implementable guidance that a farmer can act on without needing to seek further clarification — in terms of concrete quantities, timing windows, decision thresholds, or ordered steps.

**Why it matters for agricultural advisory content specifically:** In agricultural contexts, the gap between technically accurate and operationally useful advice is large and costly. A response that correctly identifies nitrogen deficiency but recommends "apply appropriate nitrogen fertilizer" offers no value to a farmer who needs to know how much, in what form, and when — a mistimed or mis-dosed application can damage the crop, waste hundreds of dollars in inputs, or miss a critical growth window that won't reopen until next season. This is distinct from completeness (which measures coverage of concepts) — a complete answer can still be too abstract to act on. It is also distinct from accuracy — a response can be factually correct and entirely non-actionable.

**How to score it (0–100):** Using an LLM judge with a structured rubric: 90–100 if the response includes specific quantities or rates, explicit timing or sequencing, named inputs or products, and clear conditional logic (e.g., "if soil pH < 6.0, apply 2 tons/acre of dolomitic lime 2–4 weeks before planting"); 70–89 if most of these elements are present but one is vague; 50–69 if the advice is directionally correct but lacks the specifics a farmer needs to act; 0–49 if the response is purely conceptual with no implementable guidance. The judge is prompted to ask: "Could a farmer with basic agronomic training act on this advice today, without consulting any additional resource?"

**Validated by our evaluation:** Actionability proved to be the most discriminating metric in our pipeline, producing the largest gap between models (Gemini 2.5 Flash: 94.3 vs. Llama 3.3 70B: 84.85, a 9.5-point difference) and the highest variance within models (Llama's actionability scores ranged from 65 to 96 across questions). The largest single-category gap appeared in Water Management (94.5 vs. 70.5) — which makes domain sense: irrigation advice is inherently site-specific, requiring local soil type, crop growth stage, and evapotranspiration data to be truly actionable. Models that provide generic guidance ("irrigate when soil moisture is low") score poorly; models that give specific thresholds score well. This pattern would be invisible under accuracy or completeness alone.
