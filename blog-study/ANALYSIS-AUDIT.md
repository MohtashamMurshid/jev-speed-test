# Analysis verification and presentation corrections

After the frozen run finished, primary accuracy, macro-F1, probability Brier score, error-detection AUROC and average precision were independently cross-checked against scikit-learn. Counts and frozen cutoff selections were independently reconstructed from the raw per-call files. The threshold timestamp precedes every held-out test request.

No requests were retried, no labels were changed, and no threshold or model setting was tuned on test results.

Presentation audit corrections:
- Expanded the first figure's left margin to avoid truncating model names.
- Added Jev's native-confidence operating point to the deferral figure, separately from its chosen-probability operating point.
- Corrected the random-deferral baseline to random selection among valid completed responses, because service/schema failures are always deferred by the confidence-based policy. The original version used the all-attempt failure-inclusive error rate, which would unfairly inflate Mercury's baseline. This changes only that comparator baseline and its plot; model predictions, thresholds, and accepted error counts do not change.
- Clarified that unknown error costs are reserved conservatively, not assumed to be confirmed billed charges.

The pre-correction analysis source is retained as `analyze-before-presentation-audit.py`. The pretest source hash remains in `final-pretest-freeze.json`; the released analysis hash appears in the evidence archive's `SHA256.json`.

Delayed independent audit follow-up:
- Fixed bootstrap confidence eligibility to require both a successful response and a finite score, matching the AUROC point-estimate population. A synthetic failed response retaining a score now cannot contaminate the interval.
- Inspected all 3,200 recorded calls: no failed response retained a probability or native-confidence score. Recomputed every prior metric and interval; they are exactly unchanged.
- Added regression tests for that population mismatch and preserved-error classification.
- Expanded the Markdown report with valid-response latency labels, per-model failed-call counts, and error categories reconstructed from preserved response bodies. Mercury had 21 upstream errors, five parse errors, and two schema errors in the test set. Gemini had one API rejection. No original response was altered.
- The random-deferral baseline finding had already been corrected before the first delivered archive, as documented above.

Metric denominators: headline accuracy is over all 500 attempts per model. Confidence discrimination/calibration uses only successful schema-valid responses with a score, so it measures decision mistakes, not API outage prediction. Deferral coverage is over all 500 attempts, with failures deferred. Accepted error is over accepted valid decisions only. Timing median/p95 excludes terminal failures; failure counts are shown separately. No production risk guarantee follows from the selected empirical cutoff.
