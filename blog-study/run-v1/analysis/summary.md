# Fast-model BANKING77 follow-up

500 unique held-out English messages across 77 intents. One prediction per model; 50 timing repeats excluded from accuracy.

| Model | Correct | Accuracy | Failed / 500 | Valid-response median ms | Valid-response p95 ms | USD / 1,000 | Error AUROC | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Jev 1.13 | 405/500 | 81.0% | 0 | 347 | 458 | 0.068 | 0.802 | 0.1300 |
| GPT-OSS / Cerebras | 414/500 | 82.8% | 0 | 404 | 718 | 0.452 | 0.808 | 0.1388 |
| Mercury 2.5 | 366/500 | 73.2% | 28 | 674 | 1093 | 0.084 | 0.753 | 0.1909 |
| Gemini 3.8 Flash | 427/500 | 85.4% | 1 | 1489 | 3239 | 0.685 | 0.843 | 0.1099 |

## Request failure breakdown

Counts below use all 500 test attempts per model. Confidence metrics use valid responses only. Latency in the main table is conditional on a valid response; time-to-terminal-outcome for all attempts is retained in metrics.json.

- Jev 1.13: 0/500 request failures.
- GPT-OSS / Cerebras: 0/500 request failures.
- Mercury 2.5: upstream_error: 21/500 (4.2%); parse_error: 5/500 (1.0%); schema_error: 2/500 (0.4%)
- Gemini 3.8 Flash: api_rejection: 1/500 (0.2%)

No explicit model refusals or timeouts were observed. Failed rows are categorized from the preserved API error code, error message, and response metadata; original records are unchanged.


## Frozen off-test deferral rules

| Model / score | Cutoff | Accepted / 500 | Errors / accepted | Test error | 95% interval |
|---|---:|---:|---:|---:|---:|
| Jev 1.13 / probability | 1 | 198 | 10 | 5.1% | 2.8–9.0% |
| Jev 1.13 / native | 1 | 168 | 5 | 3.0% | 1.3–6.8% |
| GPT-OSS / Cerebras / probability | None | 0 | 0 | NA | NA |
| Mercury 2.5 / probability | None | 0 | 0 | NA | NA |
| Gemini 3.8 Flash / probability | 0.95 | 365 | 15 | 4.1% | 2.5–6.7% |

Total accounted inference across all phases: $1.028709.

Confidence AUROC: higher is better at detecting errors; chance is 0.5. LLM scores are verbalized correctness probabilities. Jev primary score is selected-label probability; its native confidence is evaluated separately. Brier is computed only on probability scores, lower is better.

Thresholds were selected on 200 disjoint calibration examples for empirical <=5% error and at least 30 accepted. This is not a guaranteed risk bound. They were frozen before test inference. Sparse bins and small error counts limit certainty. Public benchmark contamination and one-host/one-date serving effects remain possible.
