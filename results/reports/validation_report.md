# Extended Validation Metrics

These two metrics were built to audit the main pipeline's accuracy score and test two specific failure modes that holistic scoring can miss: **hidden contradictions** and **overconfident claims**.

## Metric 1 — Fact Check Score

> *Does every claim the model makes hold up against the expert answer?*

Each response is split into individual factual claims. Every claim is verified against the gold answer as supported, neutral, or contradicted. Each contradiction costs 25 points — one wrong fact in farming can mean a lost crop.

### Overall Fact Check Scores

| Model | Fact Check Score | Avg Claims | Contradictions |
|-------|-----------------|-----------|----------------|
| gemini-2.5-flash | 56.15 | 25.94 | 0.19 |
| llama-3.3-70b | 51.16 | 23.16 | 0.11 |

### Where Fact Check and Accuracy Disagree

Rows where the gap is large (>10 points) suggest the holistic accuracy score missed a specific factual error — these are the most interesting findings.

| Question | Model | Holistic Accuracy | Fact Check | Δ | Note |
|----------|-------|------------------|-----------|---|------|
| qna_000007 | llama-3.3-70b | 97 | 52.8 | +44 | ⚠️ review |
| qna_000007 | gemini-2.5-flash | 98 | 53.6 | +44 | ⚠️ review |
| qna_000009 | llama-3.3-70b | 94 | 6.2 | +88 | ⚠️ review |
| qna_000024 | llama-3.3-70b | 98 | 75.0 | +23 | ⚠️ review |
| qna_000024 | gemini-2.5-flash | 98 | 88.2 | +10 | ✓ |
| qna_000026 | llama-3.3-70b | 97 | 42.9 | +54 | ⚠️ review |
| qna_000026 | gemini-2.5-flash | 98 | 61.5 | +36 | ⚠️ review |
| qna_000041 | llama-3.3-70b | 92 | 83.3 | +9 | ✓ |
| qna_000043 | llama-3.3-70b | 94 | 89.5 | +4 | ✓ |
| qna_000043 | gemini-2.5-flash | 98 | 10.9 | +87 | ⚠️ review |
| qna_000044 | llama-3.3-70b | 94 | 57.1 | +37 | ⚠️ review |
| qna_000059 | llama-3.3-70b | 94 | 50.0 | +44 | ⚠️ review |
| qna_000059 | gemini-2.5-flash | 98 | 52.0 | +46 | ⚠️ review |
| qna_000067 | llama-3.3-70b | 97 | 43.5 | +54 | ⚠️ review |
| qna_000067 | gemini-2.5-flash | 98 | 55.6 | +42 | ⚠️ review |
| qna_000077 | llama-3.3-70b | 94 | 37.5 | +56 | ⚠️ review |
| qna_000097 | llama-3.3-70b | 97 | 33.3 | +64 | ⚠️ review |
| qna_000097 | gemini-2.5-flash | 98 | 45.9 | +52 | ⚠️ review |
| qna_000112 | llama-3.3-70b | 97 | 77.3 | +20 | ⚠️ review |
| qna_000112 | gemini-2.5-flash | 98 | 91.3 | +7 | ✓ |
| qna_000156 | llama-3.3-70b | 87 | 33.3 | +54 | ⚠️ review |
| qna_000156 | gemini-2.5-flash | 98 | 37.1 | +61 | ⚠️ review |
| qna_000161 | llama-3.3-70b | 95 | 46.4 | +49 | ⚠️ review |
| qna_000161 | gemini-2.5-flash | 98 | 81.2 | +17 | ⚠️ review |
| qna_000169 | llama-3.3-70b | 94 | 42.9 | +51 | ⚠️ review |
| qna_000169 | gemini-2.5-flash | 98 | 38.7 | +59 | ⚠️ review |
| qna_000204 | llama-3.3-70b | 92 | 42.1 | +50 | ⚠️ review |
| qna_000204 | gemini-2.5-flash | 98 | 63.2 | +35 | ⚠️ review |
| qna_000214 | llama-3.3-70b | 94 | 70.6 | +23 | ⚠️ review |
| qna_000214 | gemini-2.5-flash | 98 | 76.5 | +22 | ⚠️ review |
| qna_000299 | llama-3.3-70b | 97 | 51.3 | +46 | ⚠️ review |
| qna_000299 | gemini-2.5-flash | 97 | 84.6 | +12 | ⚠️ review |
| qna_000327 | gemini-2.5-flash | 98 | 30.8 | +67 | ⚠️ review |
| qna_000417 | llama-3.3-70b | 94 | 37.1 | +57 | ⚠️ review |
| qna_000417 | gemini-2.5-flash | 98 | 27.3 | +71 | ⚠️ review |

### Contradicted Claims Found

- **llama-3.3-70b / qna_000161**: _Using kochia-free water sources for irrigation prevents the introduction of kochia seeds into the field._
- **llama-3.3-70b / qna_000007**: _Organic nitrogen-rich amendments release nitrogen quickly, providing an initial boost to potatoes._
- **gemini-2.5-flash / qna_000043**: _Over-irrigation causes sugarcane leaves to wilt despite ample water in the soil._
- **gemini-2.5-flash / qna_000043**: _Over-irrigation causes sugarcane roots to appear dark, mushy, and have a foul odor._
- **gemini-2.5-flash / qna_000007**: _Fresh manure can lead to nitrogen immobilization, weed seeds, pathogens, and nutrient burn._

## Metric 2 — Confidence Check Score

> *Is the model appropriately uncertain, or is it overclaiming?*

Good agricultural advice hedges where uncertainty is real (e.g., 'rates vary by soil test') and is specific where the expert is specific. A model that sounds more confident than the expert is making claims it cannot support. Overclaiming is penalised more than being too vague — vague advice is unhelpful, but overconfident wrong advice can cause crop damage.

### Overall Confidence Check Scores

| Model | Confidence Score | Overclaims | Underclaims | Calibrated |
|-------|-----------------|-----------|------------|------------|
| gemini-2.5-flash | 89.5 | 10 | 0 | 10 |
| llama-3.3-70b | 83.75 | 14 | 0 | 6 |

### Per-Question Confidence Check

| Question | Model | Score | Direction | Reason |
|----------|-------|-------|-----------|--------|
| qna_000007 | gemini-2.5-flash | 95 | calibrated | The model provides specific, actionable details (e.g., cover crop species, timin... |
| qna_000007 | llama-3.3-70b | 85 | overclaims | The model provides highly specific rates and methods (e.g., '2-4 tons/ha of comp... |
| qna_000009 | gemini-2.5-flash | 85 | overclaims | The model provides highly specific, actionable guidance (e.g., daily scouting, p... |
| qna_000009 | llama-3.3-70b | 85 | overclaims | The model provides highly specific, actionable advice (e.g., spacing, leaf struc... |
| qna_000024 | gemini-2.5-flash | 95 | calibrated | The model matches the expert's specificity and certainty while avoiding overgene... |
| qna_000024 | llama-3.3-70b | 95 | calibrated | The model matches the expert's specificity and hedging, providing detailed guida... |
| qna_000026 | gemini-2.5-flash | 95 | calibrated | The model provides specific, detailed technical explanations and actionable guid... |
| qna_000026 | llama-3.3-70b | 85 | overclaims | The model provides more specific negative impacts and recommendations than the e... |
| qna_000041 | gemini-2.5-flash | 85 | calibrated | The model provides specific, actionable guidance where the expert is specific, a... |
| qna_000041 | llama-3.3-70b | 85 | calibrated | The model matches the expert's hedging and specificity, with only minor addition... |
| qna_000043 | gemini-2.5-flash | 85 | overclaims | The model provides an overly detailed and structured breakdown of symptoms, whic... |
| qna_000043 | llama-3.3-70b | 85 | overclaims | The model lists 10 specific signs of stress, which is more detailed than the exp... |
| qna_000044 | gemini-2.5-flash | 95 | calibrated | The model matches the expert's specificity and confidence, providing detailed, a... |
| qna_000044 | llama-3.3-70b | 85 | overclaims | The model provides specific rates, timings, and rules (e.g., exact fertilizer am... |
| qna_000059 | gemini-2.5-flash | 95 | calibrated | The model matches the expert's specificity and hedging appropriately, providing ... |
| qna_000059 | llama-3.3-70b | 85 | overclaims | The model provides a highly specific 10-step list of actions, which is more pres... |
| qna_000067 | gemini-2.5-flash | 85 | overclaims | The model provides an exhaustive, highly specific list of factors while the expe... |
| qna_000067 | llama-3.3-70b | 85 | overclaims | The model lists 12 specific factors with high certainty, while the expert provid... |
| qna_000077 | gemini-2.5-flash | 85 | overclaims | The model provides highly specific, actionable guidance (e.g., price comparisons... |
| qna_000077 | llama-3.3-70b | 60 | overclaims | The model lists eight specific factors affecting purchasing decisions, while the... |
| qna_000097 | gemini-2.5-flash | 95 | calibrated | The model matches the expert's specificity and hedging, providing detailed guida... |
| qna_000097 | llama-3.3-70b | 85 | calibrated | The model provides specific, actionable details (e.g., nutrient ranges, pH targe... |
| qna_000112 | gemini-2.5-flash | 95 | calibrated | The model's specificity and hedging closely match the expert's nuanced, conditio... |
| qna_000112 | llama-3.3-70b | 85 | calibrated | The model matches the expert's hedging on uncertainty and specificity while addi... |
| qna_000156 | gemini-2.5-flash | 85 | overclaims | The model provides highly specific, actionable steps (e.g., exact irrigation amo... |
| qna_000156 | llama-3.3-70b | 85 | calibrated | The model provides specific, actionable steps while maintaining appropriate hedg... |
| qna_000161 | gemini-2.5-flash | 85 | overclaims | The model provides highly specific, actionable steps (e.g., daily practices, equ... |
| qna_000161 | llama-3.3-70b | 85 | overclaims | The model provides a highly specific, prescriptive list of daily practices, whil... |
| qna_000169 | gemini-2.5-flash | 85 | overclaims | The model provides highly specific, actionable steps (e.g., 'cycle-and-soak irri... |
| qna_000169 | llama-3.3-70b | 85 | calibrated | The model provides specific, actionable strategies that align with the expert's ... |
| qna_000204 | gemini-2.5-flash | 95 | calibrated | The model provides specific, actionable details where the expert is general, whi... |
| qna_000204 | llama-3.3-70b | 85 | overclaims | The model provides more specific steps and actionable guidance than the expert, ... |
| qna_000214 | gemini-2.5-flash | 85 | overclaims | The model provides highly detailed, prescriptive steps (e.g., specific drainage ... |
| qna_000214 | llama-3.3-70b | 85 | overclaims | The model provides a highly detailed, specific list of factors and actions, whic... |
| qna_000299 | gemini-2.5-flash | 95 | calibrated | The model's specificity and hedging closely match the expert's tone, with no ove... |
| qna_000299 | llama-3.3-70b | 75 | overclaims | The model lists 10 specific risks with detailed explanations, while the expert p... |
| qna_000327 | gemini-2.5-flash | 85 | overclaims | The model provides highly specific technical details (e.g., GDD, de-acclimation)... |
| qna_000327 | llama-3.3-70b | 85 | overclaims | The model provides more specific factors and examples than the expert, making it... |
| qna_000417 | gemini-2.5-flash | 85 | overclaims | The model provides highly specific, actionable data sources and methods, which a... |
| qna_000417 | llama-3.3-70b | 85 | overclaims | The model provides highly specific data sources and actionable steps, which are ... |

## Combined View — All Extended Metrics

| Model | Holistic Accuracy | Fact Check | Confidence Check |
|-------|-----------------|-----------|------------------|
| gemini-2.5-flash | 97.94 | 56.15 | 89.5 |
| llama-3.3-70b | 94.63 | 51.16 | 83.75 |

> **How to read this:** Where Holistic Accuracy and Fact Check agree, the accuracy score is trustworthy. Where they diverge, inspect the contradicted claims — that is where hallucinations are hiding. Confidence Check tells you whether the model is giving advice a farmer can safely act on, or making promises the data does not support.
