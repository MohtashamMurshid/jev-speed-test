# Fresh follow-up data schema

This directory contains only the new prospective experiment, not the original 3,200-call study or its post-hoc replay.

- `responses.jsonl.gz`: one JSON object per physical API attempt, ordered by `sequence`. Jev-only shares the cascade's first call, so it does not appear as a duplicate attempt. Every object retains the provider response fields, request identity, case text and source labels. `cohort=cases` means BANKING77; `cohort=oos` means the CLINC nonbanking stress subset.
- `paths.jsonl.gz`: one object per measured live path. `path=cascade` has one Jev call and, if routed, one Gemini fallback call. `path=baseline` has a separate Gemini-only call. `components` contains exact call keys. `latencyMs` is observed path wall time, not the sum of model-level summary statistics.
- `banking-results.csv`: one row per fresh BANKING77 test case. Model predictions, correctness flags, routing, gates, measured times and separate cost columns. `expected` is the existing BANKING77 category. All chosen cases remain in accuracy denominators.
- `oos-results.csv`: one row per selected nonbanking CLINC message. `sourceCategory` is the original CLINC intent. No BANKING77 class is correct for these cases, so banking correctness fields are blank. Gate acceptance means an inappropriate in-scope acceptance, not correct classification.
- `sha256.json`: integrity hashes for convenient exports.

## Scores and missing values

`nativeConfidence` is Jev's actual provider-returned confidence. `probability` is Jev's chosen-class probability on Jev calls and the model's verbalized correctness estimate on Gemini calls. They are different quantities. `local_score` is the supervised classifier's largest class probability. None is automatically a calibrated correctness probability.

The frozen gates are Jev native confidence 1.0, Gemini verbalized probability 0.95, and the local cutoff recorded in `../local/threshold.json`. A failed response never passes a gate, even if it contains a partial score. The safety cascade uses the actual fallback response, not the separate baseline answer.

Missing JSON fields or null values mean unavailable, not zero. Empty CSV cells mean missing or not applicable. Boolean CSV fields use `True` and `False`.

## Money

`billedCostUsd` is the API response's reported charge. `reservedUsd` is a conservative pre-request budget reservation. The runner's `accountedUsd` uses the reported bill when available and the reservation otherwise. A reservation is not a known bill. Estimated cost is not substituted for an unknown bill in this run.

Per-path `*_billed_subtotal_usd` sums only observed bills and must be read alongside `*_unknown_bill_calls`. `*_accounted_usd` includes the conservative provision for unknown calls. Jev and cascade cost summaries overlap because the first-stage calls are shared; do not add them. The whole follow-up includes both paths and both cohorts. CPU training and inference have zero API charges, but their compute cost was not priced.

## Attribution

BANKING77 text retains the source's CC BY 4.0 license. The selected CLINC150 text retains CC BY 3.0. See [full attribution, source revisions and licenses](../provenance/ATTRIBUTION.md). Source text is unchanged; subsets and derived evaluation fields were added. Public visibility does not grant a separate software license.

Rebuild these exports with `python blog-study/fresh-followup/export.py` after offline analysis. No model calls occur.
