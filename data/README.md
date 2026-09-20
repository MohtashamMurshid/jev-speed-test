# Downloadable data

## `responses.jsonl.gz`

Gzip-compressed UTF-8 JSON Lines: **3,200 rows**, one recorded API attempt per row. Includes `development`, `calibration`, `test`, and `repeat`. Each row preserves the original response body and recorded usage/errors; headers and credentials are not included.

- `system`, `model`, `endpoint`: requested system and pinned route.
- `phase`, `caseId`: split and original dataset row reference. Repeated timings have the same case ID but a different phase.
- `expected`, `predicted`, `status`, `correct`: dataset label, returned category when available, request outcome, and end-to-end correctness.
- `probability`: Jev's selected-category probability or the LLM's verbalized probability of correctness.
- `nativeConfidence`: Jev's separate native uncertainty score, not a promised probability of correctness.
- `probabilities`: Jev's complete returned category distribution.
- `latencyMs`: recorded duration to the outcome, including unsuccessful outcomes. Published main latency statistics filter for `status == "ok"`.
- `inputTokens`, `outputTokens`, `reasoningTokens`: returned usage where available; absent does not mean zero.
- `billedCostUsd`, `estimatedCostUsd`, `reservedUsd`: use reported bill first, otherwise usage estimate, otherwise conservative reservation. **Do not sum these three fields.**
- `response`: original API body, including error details and returned model/provider identity where supplied.

Read without contacting a model API:

```python
import gzip, json
with gzip.open('data/responses.jsonl.gz', 'rt') as f:
    rows = [json.loads(line) for line in f]
assert len(rows) == 3200
```

## `test-results.csv`

**2,000 rows**: four model attempts for each of 500 unique held-out messages. Includes the message text, expected/returned category, status, scores, latency, and accounting fields. Missing fields are empty, not zero. Accuracy denominator is all 500 attempts per model. Confidence measures only use successful scored responses.

This CSV and the JSONL are convenience exports of `blog-study/run-v1/calls/`, not additional observations. Development, threshold selection, and repeat rows must not be pooled into held-out accuracy.

## Attribution

Message text and labels are derived from BANKING77, PolyAI, CC BY 4.0. Original license and citation: [dataset license](../blog-study/LICENSE), [repository attribution](../README.md#dataset-attribution-and-licensing). Source revision, file hashes, and exact split IDs are retained in `blog-study/`.
