# Jev → Gemini: post-hoc offline simulation

Post-hoc existing-data replay; no new inference, cutoff fitting, or independent validation.

Fixed rule: accept a valid Jev answer with native confidence >= 1; otherwise use Gemini. No threshold tuning.

| System | Correct / 500 | Accuracy | Accounted USD / 1,000 | Valid median ms | Valid p95 ms | Failures |
|---|---:|---:|---:|---:|---:|---:|
| jev | 405 | 81.0% | 0.067546 | 346.8 | 458.1 | 0 |
| gemini | 427 | 85.4% | 0.684659 | 1488.7 | 3238.9 | 1 |
| cascade | 429 | 85.8% | 0.526180 | 1723.0 | 3063.5 | 0 |

Cascade timings/costs are simulated, not measured in a live cascade.

## Paired comparisons
- Versus jev: accuracy difference +4.8 percentage points; exploratory 95% interval [2.7950000000000004, 7.000000000000001]. Gains 34, losses 10. Accounted cost savings -679.0%.
- Versus gemini: accuracy difference +0.4 percentage points; exploratory 95% interval [0.0, 1.0]. Gains 2, losses 0. Accounted cost savings 23.1%.

## Interpretation
The cascade calls Gemini for 332/500 messages and accepts Jev for 168/500. It records two more correct outcomes than Gemini alone: one replaces a valid wrong answer and one avoids an API failure. This is not independent evidence of superior accuracy.
Its simulated median is slower than Gemini alone because most messages require both sequential calls. Cost savings are the promising signal, not a blanket speed improvement.
If the unbilled Gemini failure cost were zero instead of its reservation, simulated savings would be 21.4%. This is a sensitivity check, not a verified invoice.

## Reproduce
Run `python blog-study/cascade_simulation.py --test` and `python blog-study/cascade_simulation.py` in the existing NumPy analysis environment. No API credentials or network calls are required.

## Assumptions and limitations
- Sequential cascade: always call Jev; call Gemini only after a nonaccepted/failed Jev result. No third-stage human-review gate.
- Reuse observed isolated-call responses, prices and durations. Omit orchestration overhead; routing may change caching, load and responses.
- Simulated latency percentiles are computed per message from sums, not by adding medians or p95s. Failures excluded from valid-response timings and counted wrong for accuracy.
- Sampling intervals are exploratory, paired and intent-stratified. They are not a new independent evaluation or a test of noninferiority.
- Reported costs are counterfactual accounting, not actual cascade invoices. Source reservations cover unknown bills. Original raw study remains unchanged.
