# Verification and correction record

## Completed checks

- The original public checkout was clean and synchronized before this follow-up. The private/public copies represented the same original 3,200 calls, not separate bills. No earlier follow-up spending was found before acquiring the exclusive ownership lock.
- The fresh data/classifier protocol froze before local fitting. The final hosted runner, samples, model metadata, schedule and thresholds were committed and published before the first paid request. See `pre-inference-freeze.json` and commit `546934b`.
- `verify_data.py` independently matched all 500 selected texts and labels to the official BANKING77 CSV, checked the source hashes, all 77 intents, six/seven examples per intent, and zero normalized overlap with prior examples.
- The independent OOS check fetched the pinned CLINC source, verified its hash and CC BY 3.0 license, and matched all 100 source row IDs, texts and category labels. It did not use the native OOS split. See `independent-oos-audit.json`.
- The local fitting audit independently reconstructed the 9,742 training rows, verified zero overlap with development, calibration or any official test text, and independently selected the same 0.25 cutoff from the original 200 calibration records. See `independent-local-audit.json`.
- All 1,200 live paths completed, with 1,630 physical calls and no unresolved reservations. The paid process exited with code zero. Parent OS flock plus the runner's exclusive lock prevented overlapping paid execution. Requests stopped at 06:17 UTC, before the fixed 09:15 UTC cutoff.
- `independent_audit.py` does not import the main analysis. It reconstructs successful labels directly from provider response bodies, checks raw scores against retained scores, rejoins source labels, reconstructs routing, verifies every physical call is referenced once, checks sequential durations and reconciles charges with Decimal arithmetic.
- Independent reconstruction found 399/500 Jev, 425/500 separate Gemini and 424/500 cascade correct. It found three gains and four losses for the cascade against Gemini. It reconciled $0.793283526 in reported API charges and $0.254479500 reserved for one unknown bill.
- Scikit-learn `accuracy_score` and SciPy Wilson intervals independently matched the core accuracy tables. Confidence ranking uses scikit-learn AUROC/average precision directly, with one shared valid finite-score mask for point estimates and bootstrap intervals. See `library-crosscheck.json` and `supplement/uncertainty.json`.
- Twelve follow-up runner tests, twelve core analysis tests and two confidence-population tests passed. The original six runner tests and three original analysis tests also passed during prerequisite checks. The follow-up TypeScript runner, tests and recorded-failure replay script passed an explicit typecheck.
- Recorded Jev OOS errors were replayed through the installed SDK with a mock transport, no network requests. Both reproduced `AI_InvalidResponseDataError`, because the selected option was not a highest-probability option. The records remained failures; validation was not relaxed. See `failure-replay.json` and `replay_failures.ts`.
- `reproduce.py --refit-local` copied the evidence into a new temporary directory, disabled socket connections in all subprocesses, reran the full offline pipeline and required byte-identical analysis, figures and exports. The classifier refit matched all 800 saved predictions, gates and probabilities exactly. Timing measurements were deliberately not compared or replaced. See `offline-reproduction.json`.
- Visual inspection covered accuracy, measured latency, cost, gate and OOS plots. Follow-up styling fixes moved annotations away from confidence whiskers and separated reported charges from the hatched unknown-bill provision. They did not alter numerical outcomes.
- Final prepublication scanning found zero credential patterns, zero occurrences of the actual authorized key, and no private host home paths in 5,735 non-cache follow-up files. The key was used only in memory for the equality scan and was never written into a publication artifact.
- The final check verified all 6,459 original run-v1 file hashes and all eight pre-inference frozen artifact hashes unchanged. The original release and portfolio were not modified.

## Integration repairs before paid requests

The first data/runner implementation drafts disagreed about null OOS labels, whether to reshuffle the already-frozen case order, and a three-versus-four-failure abort rule. Before inference, the runner was changed to honor the existing frozen protocol: null OOS gold, banking then OOS, the recorded per-case path order, and a three-failure stop. Actual-input regression tests now cover these conventions.

SDK mock testing established that this installed evaluation adapter uses `/api/alpha/decisions`, not the chat API's `/api/v1` base. The corrected path was in the final frozen runner. Dependencies resolve relative to the public checkout, and original category ordering is checked against the retained original manifest rather than a private absolute path.

These integration changes did not change any sample, label, threshold or local model outcome. No paid development calls occurred. The first real request belongs to the frozen study.

## Post-run accounting and presentation clarifications

The main cost table is conservative budget accounting. Its reservation basis for a missing bill is not an observed invoice. A separate sensitivity calculation varies unknown charges between zero and their reservations. For this actual run, the cascade still saves 23.27% if the baseline's failed request was free. The larger 55.94% conservative-ledger reduction is not used as the headline observed saving.

The analysis schema gained `missing_bill_calls` to distinguish missing API charges from the older `unknown_calls` field, which means no bill, estimate or reservation is available at all. This clarification changes no selected charge, prediction, count or cutoff.

Absolute shared-library paths were removed from the local environment summary and replaced by library filenames. Predictions, scores, gates and original CPU timings were unchanged. The source classifier remains frozen; fresh refits occur in temporary directories and their host metadata are not published over the archived summary.

## Scope of assurance

These checks establish arithmetic, data joins, recorded-contract behavior and offline reproducibility for the released evidence. They do not prove that the public benchmarks were absent from model training, settle every source-label ambiguity, certify provider billing beyond reported charges, establish immutable model aliases, or provide a production safety guarantee.
