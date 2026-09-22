# Reproducing the fresh follow-up

## Offline evidence replay

From the repository root, use Python 3.11 with the pinned packages:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r blog-study/fresh-followup/requirements.txt
python blog-study/fresh-followup/test_analysis.py
python blog-study/fresh-followup/test_uncertainty.py
python blog-study/fresh-followup/reproduce.py --refit-local
```

Installing packages requires network access. The replay itself does not. It copies the released inputs into a new temporary directory, disables socket connections in every replay subprocess, verifies the frozen samples, reconstructs outcomes and costs from original provider bodies, rebuilds the analysis, and checks generated files byte for byte. The optional classifier refit compares all calibration, banking and OOS labels, gates and probabilities. It does not require new timing measurements to match the original CPU timings.

For individual steps:

```bash
python blog-study/fresh-followup/prepare.py
python blog-study/fresh-followup/verify_data.py
python blog-study/fresh-followup/independent_audit.py
python blog-study/fresh-followup/analyze.py --audit
python blog-study/fresh-followup/uncertainty.py
python blog-study/fresh-followup/supplement_plots.py
python blog-study/fresh-followup/export.py
```

`prepare.py` verifies the existing frozen protocol and sample hashes. Do not remove `protocol.json` to regenerate this experiment. That would enter its original sampling branch and require external source downloads.

The original `blog-study/run-v1` is not an output destination for any of these commands. The simple classifier can be refit from `train.csv`, the saved exclusions, fixed configuration, recorded dependency versions and source IDs. No large serialized model is needed.

## Runner checks

With the repository's locked Node dependencies installed:

```bash
npm ci
node --import tsx --test blog-study/fresh-followup/runner.test.ts
npm test
npm run typecheck
```

The follow-up runner tests exercise gates, accounting, exclusive journals, incomplete-path refusal, deadline boundaries, the actual frozen path order, and SDK transports with mock HTTP responses. These mocks are test fixtures, not benchmark evidence. `runner.ts` and its tests can also be typechecked explicitly with the repository TypeScript compiler because the original project's tsconfig may include only its original files.

## Live execution is separate

The committed manifest freezes code, cases, schedule, model/provider metadata, prompts, thresholds and budget. Its paid-request deadline is fixed at 2026-09-22 09:15 UTC. This directory must not be repurposed for new paid inference.

The executed runner used the existing authorized environment file without copying credentials. A parent-held operating-system lock, a runner-exclusive lock, and durable per-request reservations prevented duplicate concurrent work. Resuming a completed path skips it. An unresolved call reservation or incomplete path stops execution rather than retrying a possibly billed request or manufacturing a live timing result.

A new prospective run needs a new directory, explicit approval, a new deadline and budget, a new frozen manifest, and a current endpoint check. Do not delete journals, move cutoffs, rewrite provider responses or overwrite the original release to obtain a cleaner result.

## Artifact boundaries

- `protocol.json`, `cases.json`, `oos.json`, `manifest.json`, `pre-inference-freeze.json`: frozen design and identities.
- `calls/`, `paths/`: durable request and live-path evidence.
- `local/`: original classifier predictions, calibration threshold and training provenance.
- `analysis/`: core deterministic analysis, paired intervals, per-case table and plots.
- `supplement/`: confidence-ranking, matched random-deferral statistics and extra measured plots.
- `data/`: convenient compressed JSONL and CSV exports with a schema.
- `AUDIT.md`: human-readable verification record and disclosed corrections.

Dataset text retains its upstream licenses. See `provenance/ATTRIBUTION.md`. Public repository access is not a separate software license grant.
