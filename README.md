# Jev versus fast LLMs: BANKING77 follow-up

A small, reproducible English-only comparison of **Jev 1.13, GPT-OSS-120B/Cerebras, Mercury 2.5, and Gemini 3.8 Flash**. Includes the data, exact model responses, frozen confidence thresholds, failures, and analysis—not just a leaderboard.

[Read the full process and blog draft](https://postplan.oikina.com/d/ssfry3bhpmpq) · [Results](blog-study/run-v1/analysis/summary.md) · [Protocol](blog-study/PROTOCOL.md) · [Audit corrections](blog-study/ANALYSIS-AUDIT.md)

## What was tested

500 held-out English BANKING77 messages covering 77 intents, plus 50 development messages, 200 separate threshold-selection messages, and 50 timing repeats per model. **3,200 API attempts total.** Repeats do not increase the independent accuracy sample size. No Sol in this comparison.

| System | Correct / 500 | Accuracy | Valid-response median | Accounted USD / 1,000 test attempts | Failed test calls |
|---|---:|---:|---:|---:|---:|
| Jev 1.13 | 405 | 81.0% | 347 ms | $0.068 | 0 |
| GPT-OSS / Cerebras | 414 | 82.8% | 404 ms | $0.452 | 0 |
| Mercury 2.5 | 366 | 73.2% | 674 ms | $0.084 | 28 |
| Gemini 3.8 Flash | 427 | 85.4% | 1,489 ms | $0.685 | 1 |

Accuracy includes failed calls as incorrect. Latency above is conditional on a valid response. Unknown failed-call bills use conservative reservations, not fabricated charges. Total accounted inference across all phases was **$1.028709**; reported API bills totaled **$1.007308**.

### Confidence was useful, not a guarantee

Cutoffs were chosen on 200 separate messages, before test inference. Jev's native-confidence rule accepted **168/500**, with **5 mistakes (3.0%)**. Gemini's verbalized-probability rule accepted **365/500**, with **15 mistakes (4.1%)**. Both accepted-error intervals extend above the 5% target; neither establishes a production risk bound.

Jev's native confidence is distinct from its chosen-label probability. LLM probabilities are verbalized estimates. Confidence statistics use valid responses only; service failures are always deferred. No calibration model was fitted.

## Images and graphs

[Seven blog visuals in PNG, SVG, and PDF](blog-study/run-v1/analysis/blog-assets): cover, test workflow, accuracy with intervals, median/p95 latency, cost, frozen-rule acceptance, and confidence error ranking. All numerical charts are generated from the frozen metrics, with denominators and limitations in their captions.

Rebuild using the analysis environment:

```bash
python blog-study/blog_visuals.py
python blog-study/build_blog_preview.py
```

The second command writes a self-contained HTML article preview to `blog-study/run-v1/analysis/blog-preview.html`. It makes no model calls. The original v0.1.0 release remains the immutable source/data snapshot; subsequent editorial figures are tracked on main.

## Data and evidence

- [All 3,200 recorded responses, compressed JSONL](data/responses.jsonl.gz): includes every phase and failures, plus original API response bodies.
- [Held-out results, CSV](data/test-results.csv): 2,000 rows, one per model/test-message attempt. Scores left empty for failures where unavailable.
- [Data format](data/README.md).
- [Exact splits and labels](blog-study/splits.json), [category list](blog-study/categories.json), and [source/split hashes](blog-study/data-manifest.json).
- Original [training CSV](blog-study/train.csv) and [test CSV](blog-study/test.csv).
- [Frozen thresholds](blog-study/run-v1/thresholds.json), [provider/prompt manifest](blog-study/run-v1/manifest.json), and [pretest freeze](blog-study/run-v1/final-pretest-freeze.json).
- [Per-call raw records and reservations](blog-study/run-v1/calls).
- [Machine-readable metrics](blog-study/run-v1/analysis/metrics.json), [figures](blog-study/run-v1/analysis), and [descriptive walkthrough checks](blog-study/run-v1/analysis/walkthrough-checks.json).

The [releases page](https://github.com/MohtashamMurshid/jev-speed-test/releases) contains a downloadable source-and-data snapshot.

## Recalculate results without API calls

Requires Python 3.11 or newer. Create an isolated environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r blog-study/analysis-requirements.txt
python blog-study/test_analysis.py
python blog-study/analyze.py
```

This consumes the committed records and writes analysis files. **It does not contact a model API.** Offline replay of the evidence reproduced the reported metrics exactly. Raw outputs are preserved even where later analysis/reporting corrections were necessary.

To verify the TypeScript runner:

```bash
npm ci
npm test
npm run typecheck
```

The Node dependencies are locked in `package-lock.json`; statistical-analysis packages are pinned in `blog-study/analysis-requirements.txt`.

## Live repetition is separate from offline reproduction

Read [the detailed study README](blog-study/README.md) and [protocol](blog-study/PROTOCOL.md) before running inference. The existing `run-v1` contains a completed study and frozen contract. Completed calls are not automatically repeated; the thresholds command deliberately refuses to overwrite its existing file.

A new live run needs an explicitly new output directory/contract and a new budget. Do not delete the recorded failures or overwrite this run just to get fresh calls. Put credentials only in your local environment or a gitignored `.env`; none are included here. Client-side spending guards do not replace provider-enforced account limits.

## Limitations and scope

- One public dataset subset, one host/date, one label order. Training-data contamination is possible.
- The 500 messages are not the full BANKING77 test set or a representative customer-traffic distribution.
- No out-of-scope detection, human annotation project, trained classifier baseline, prompt optimization, or production deployment was tested.
- Four requests in flight maximum, one per pinned endpoint. No retries or provider fallback.
- Provider availability and format failures affect end-to-end accuracy. Conditional latency does not describe failed requests.
- Paired intent-stratified bootstrap comparisons are exploratory, not universal model rankings or paper-level claims.
- The original 30-message synthetic pilot is a different experiment and is not part of these results.

## Dataset attribution and licensing

BANKING77: Iñigo Casanueva, Tadas Temcinas, Daniela Gerz, Matthew Henderson, Ivan Vulić. **Efficient Intent Detection with Dual Sentence Encoders**, ACL ConvAI Workshop 2020. [Paper](https://arxiv.org/abs/2003.04807) · [Original dataset repository](https://github.com/PolyAI-LDN/task-specific-datasets).

The upstream dataset is distributed under **CC BY 4.0**; its [original license](blog-study/LICENSE), attribution, source revision, and hashes are preserved. Dataset text in splits and derived tables retains that attribution. No separate software license has been selected for this repository; public visibility alone is not a software license grant.

## Development and audit trail

The implementation, experiment execution, analysis, and writing were assisted by Ren. A development-only accounting bug and operational error guard were repaired before calibration/test. Post-run audit fixes corrected an eligible-population comparator, hardened an AUROC interval filter, and expanded failure reporting. See [ANALYSIS-AUDIT.md](blog-study/ANALYSIS-AUDIT.md). No labels, model outcomes, or frozen confidence thresholds were changed after seeing the test results.
