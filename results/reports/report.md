# AI-AgriBench Evaluation Report

Generated: 2026-04-18T22:59:35.358854Z  
Questions evaluated: 20  
Models: gemini-2.5-flash, llama-3.3-70b  
Judge: Mistral Small (neutral third-party, different family from both subjects)

## Key Findings

Both models score highly on accuracy and relevance (90s), consistent with AI-AgriBench's own finding that frontier models largely saturate factual agricultural knowledge. The most discriminating metric is **Actionability** — the gap between models is largest here and variance within models is highest, revealing qualitative differences that accuracy alone cannot detect.

**Conciseness is the lowest-scoring metric for both models**, confirming the anti-correlation with Completeness reported in the AI-AgriBench methodology — models that cover more ground inevitably use more text, which the conciseness rubric penalises. This is a structural tension in the metric design, not a model failure.

**The largest actionability gap appears in Water Management and Irrigation** (24.0 points difference). This is consistent with the domain: irrigation and water management decisions are inherently site-specific — dependent on local soil type, crop growth stage, and evapotranspiration rates. Models that give generic guidance ('irrigate when soil moisture is low') score poorly; those providing specific thresholds ('apply 1–1.5 inches per week during grain fill') score well. This pattern would be invisible under accuracy or completeness alone.

## Overall Scores (0–100)

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|--------|--------|
| **Accuracy** | 97.75 ± 0.91 | 94.5 ± 2.59 |
| **Relevance** | 98.45 ± 3.38 | 96.75 ± 2.45 |
| **Completeness** | 97.65 ± 1.23 | 92.35 ± 3.99 |
| **Conciseness** | 91.15 ± 3.57 | 88.15 ± 2.92 |
| **Actionability** | 94.3 ± 3.69 | 84.85 ± 8.42 |

## Per-Category Breakdown

> Actionability shows the most variation across categories, reflecting differences in how site-specific each topic area is.

### Crop Nutrition and Fertility Management

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|--------|--------|
| accuracy | 97.56 (n=9) | 94.44 (n=9) |
| relevance | 97.78 (n=9) | 97.22 (n=9) |
| completeness | 97.78 (n=9) | 91.56 (n=9) |
| conciseness | 93.22 (n=9) | 89.44 (n=9) |
| actionability | 94.44 (n=9) | 85.56 (n=9) |

### Horticultural and Agronomic Practices

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|--------|--------|
| accuracy | 98 (n=1) | 92 (n=1) |
| relevance | 99 (n=1) | 95 (n=1) |
| completeness | 97 (n=1) | 88 (n=1) |
| conciseness | 92 (n=1) | 80 (n=1) |
| actionability | 88 (n=1) | 85 (n=1) |

### Pests and Pest Management

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|--------|--------|
| accuracy | 98 (n=1) | 94 (n=1) |
| relevance | 99 (n=1) | 88 (n=1) |
| completeness | 97 (n=1) | 92 (n=1) |
| conciseness | 88 (n=1) | 85 (n=1) |
| actionability | 95 (n=1) | 87 (n=1) |

### Seed Hybrid Rootstock Selection

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|--------|--------|
| accuracy | 97.8 (n=5) | 94.8 (n=5) |
| relevance | 98.4 (n=5) | 97 (n=5) |
| completeness | 97.4 (n=5) | 94.4 (n=5) |
| conciseness | 88.2 (n=5) | 88.2 (n=5) |
| actionability | 93 (n=5) | 82.4 (n=5) |

### Soils and Soil Health

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|--------|--------|
| accuracy | 97.43 (n=7) | 95 (n=7) |
| relevance | 99.29 (n=7) | 97.57 (n=7) |
| completeness | 97.71 (n=7) | 92.71 (n=7) |
| conciseness | 90.71 (n=7) | 89.43 (n=7) |
| actionability | 95 (n=7) | 87.57 (n=7) |

### Water Management and Irrigation

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|--------|--------|
| accuracy | 98 (n=2) | 94 (n=2) |
| relevance | 100 (n=2) | 98 (n=2) |
| completeness | 99 (n=2) | 92 (n=2) |
| conciseness | 90 (n=2) | 88 (n=2) |
| actionability | 94.5 (n=2) | 70.5 (n=2) |

### Weather and Weather Risks

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|--------|--------|
| accuracy | 98 (n=1) | 92 (n=1) |
| relevance | 99 (n=1) | 95 (n=1) |
| completeness | 97 (n=1) | 88 (n=1) |
| conciseness | 92 (n=1) | 80 (n=1) |
| actionability | 88 (n=1) | 85 (n=1) |

### Weeds and Weed Management

| Metric | gemini-2.5-flash | llama-3.3-70b |
|--------|--------|--------|
| accuracy | 98 (n=1) | 95 (n=1) |
| relevance | 100 (n=1) | 98 (n=1) |
| completeness | 97 (n=1) | 92 (n=1) |
| conciseness | 95 (n=1) | 88 (n=1) |
| actionability | 99 (n=1) | 85 (n=1) |

## Cost Summary

- **llama-3.3-70b** (subject): $0.0079
- **gemini-2.5-flash** (subject): $0.0096
- **Judge**: $0.0082
- **Total**: $0.0257

## Per-Question Cost Breakdown

| Question ID | gemini-2.5-flash ($) | llama-3.3-70b ($) |
|-------------|----------|----------|
| qna_000007 | 0.00067 | 0.00050 |
| qna_000009 | 0.00047 | 0.00045 |
| qna_000024 | 0.00064 | 0.00044 |
| qna_000026 | 0.00041 | 0.00040 |
| qna_000041 | 0.00032 | 0.00017 |
| qna_000043 | 0.00038 | 0.00034 |
| qna_000044 | 0.00067 | 0.00045 |
| qna_000059 | 0.00035 | 0.00041 |
| qna_000067 | 0.00052 | 0.00039 |
| qna_000077 | 0.00044 | 0.00037 |
| qna_000097 | 0.00064 | 0.00049 |
| qna_000112 | 0.00047 | 0.00044 |
| qna_000156 | 0.00036 | 0.00030 |
| qna_000161 | 0.00034 | 0.00032 |
| qna_000169 | 0.00049 | 0.00034 |
| qna_000204 | 0.00057 | 0.00051 |
| qna_000214 | 0.00064 | 0.00041 |
| qna_000299 | 0.00029 | 0.00042 |
| qna_000327 | 0.00047 | 0.00041 |
| qna_000417 | 0.00047 | 0.00035 |

## Contamination Flags

No responses flagged for potential contamination.
