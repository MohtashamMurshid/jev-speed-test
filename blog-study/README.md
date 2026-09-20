# BANKING77 fast-model follow-up

This folder contains the English-only blog experiment, separate from the original 30-message synthetic pilot.

## Dataset

BANKING77 by PolyAI, from `PolyAI-LDN/task-specific-datasets`, pinned in `data-manifest.json`. License: Creative Commons Attribution 4.0 International. See `LICENSE`.

Citation: Iñigo Casanueva, Tadas Temcinas, Daniela Gerz, Matthew Henderson, Ivan Vulić. *Efficient Intent Detection with Dual Sentence Encoders*. Proceedings of the 2nd Workshop on NLP for ConvAI, ACL 2020. https://arxiv.org/abs/2003.04807

`train.csv`, `test.csv`, and `categories.json` preserve the fetched source. `splits.json` freezes our subset and original row IDs. Train records overlapping any official test text were removed after casefold/whitespace normalization; within-split normalized duplicates were removed. No semantic deduplication guarantee.

## Systems

- `typesafe/jev-1.13` through `typesafe`
- `openai/gpt-oss-120b` through `cerebras/fp16`, low reasoning
- `inception/mercury-2.5` through `inception`, no reasoning
- `google/gemini-3.8-flash` through `google-ai-studio`, low reasoning

Only standard Gemini serving; Flex/priority ignored. All hosted calls use Vercel AI SDK and the OpenRouter provider. Jev's native confidence is captured from the original HTTP response because AI SDK's normalized Choice answer drops it.

## Reproduce

The existing project root holds pinned npm dependencies. Use `npm ci` there. `OPENROUTER_API_KEY` must be set privately; never add it to source. Existing results resume without repeating completed attempts. Do not delete existing results and accidentally rerun a paid benchmark. A different runner/data contract must use a new explicitly budgeted run.

```sh
npm run typecheck
node --import tsx --test blog-study.test.ts
node --import tsx blog-study.ts prepare
node --env-file=.env --import tsx blog-study.ts development
node --env-file=.env --import tsx blog-study.ts calibration
node --env-file=.env --import tsx blog-study.ts thresholds
node --env-file=.env --import tsx blog-study.ts test
node --env-file=.env --import tsx blog-study.ts repeat
```

The thresholds command is create-only: it deliberately refuses to overwrite a frozen threshold file. Do not rerun it on an already completed study.

Use Python with NumPy and Matplotlib for `python blog-study/analyze.py`. It requires all 500 held-out predictions for every model, including recorded failures. It never makes API calls.

## Measurement

Read `PROTOCOL.md` before interpreting results. Native Jev confidence, Jev class probability, and LLM self-reported probability are not interchangeable quantities. Warmups/development, threshold-selection, test, and repeated timings stay distinct. Failed calls remain failures with conservative unknown-cost reservations. A successful schema is not proof of a correct intent.

The $10 ceiling covers this study's accounted inference, including errors. Reservations protect concurrent dispatch; a real provider-key billing limit remains stronger than client-side estimates. Provider prices and model behavior can change. Resume refuses contract changes or unresolved possibly billed calls.

Development exposed a floating-point reservation residue and intermittent Mercury HTTP502 responses. The guard was repaired before calibration/test, with prior manifests retained. No prompt or label changes were selected from held-out results.
