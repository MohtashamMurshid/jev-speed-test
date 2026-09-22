# Interpretation rules frozen before new inference

The primary question is whether a frozen Jev-first policy reduces request cost on a fresh BANKING77 subset, and what happens to accuracy and measured end-to-end latency. No equivalence or noninferiority claim is planned. A small accuracy difference is not proof of superiority.

## Comparisons

Each banking case has two serial, interleaved paths in deterministic randomized order. One path calls Jev, accepts only a valid response with native confidence at least 1.0, and otherwise calls Gemini on the original text. The other path makes a separate Gemini-only request. Jev-only reuses the cascade's first stage and is not a third paid request. All service errors count against primary accuracy. Failed responses never pass a confidence gate.

Cost comparisons charge Jev on every cascade case and Gemini only on routed cases. The separate Gemini baseline has its own observed response and bill. These are observed request costs, not a replay invoice estimate. Missing bills must be separated from token estimates and unresolved reservations. New inference total includes both experimental paths and stress cases; cost-per-case comparisons use the matching banking population only.

Measured cascade latency is the elapsed time of an actually executed path, including first-stage inference, routing, and fallback if used. Offline addition of component durations cannot replace missing live path timing. Timing reports must name their valid-response population and list excluded failures. CPU prediction timing for the local classifier excludes API/network service overhead and is a different execution environment.

The paired bootstrap resamples case IDs within intent. It estimates uncertainty for this stratified subset, not population-wide performance across tasks, prompts, providers, or dates. The same eligible set must feed any score statistic and its interval. Repeated calls are not new independent test examples.

## Frozen scores

Jev native confidence is a provider-returned decision score, not a validated probability of correctness. Gemini's returned probability is a verbalized correctness estimate. Neither frozen cutoff establishes a production risk guarantee. The original calibration target was at most 5% empirical accepted error with at least 30 accepted examples, not a finite-sample guarantee. No test-label cutoff tuning is permitted.

A safety cascade is a separate selective policy: accept a valid Jev response at its frozen gate; otherwise accept a valid fallback Gemini response at 0.95; otherwise defer to a human. The primary, forced-answer cascade does not have an out-of-scope option and cannot reject nonbanking requests. The stress test measures inappropriate acceptance of known nonbanking categories, not comprehensive open-world OOS detection, adversarial robustness, or financial-domain near-miss rejection. Category labels come from the source dataset, not a new LLM judge.

## Boundaries

- Fresh means not used in the earlier experiment. Public BANKING77 and any OOS source may still have appeared in model training.
- Normalized exact text exclusions do not remove semantic paraphrases or source-level annotation ambiguity.
- Fixed prompts, label order, one host and one execution window limit generalization.
- A model alias and a dated provider endpoint name do not establish an immutable underlying model build.
- The classifier uses fixed hyperparameters, with a separate existing calibration split for its gate. This is a simple reference, not a tuned state-of-the-art supervised model.
- No fresh human relabeling, production deployment, real customer traffic, or portfolio publication is part of this follow-up.

## Original sources

BANKING77: Casanueva et al., Efficient Intent Detection with Dual Sentence Encoders, 2020. https://arxiv.org/abs/2003.04807 . Dataset source and CC BY 4.0 attribution are preserved in the parent study directory.

Provider API metadata is archived with the new protocol. The implementation uses the pinned AI SDK and OpenRouter provider packages recorded in the repository package lock. Native decision scores are captured from the original provider response because SDK normalization can omit native confidence.
