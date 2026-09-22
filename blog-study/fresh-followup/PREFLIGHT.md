# Prerequisite checks

At 2026-09-22 05:25 UTC, the public checkout was clean on main, synchronized with origin/main. No follow-up run processes or prior follow-up inference journals were found in either checkout. The private and public original directories each contained the same 3,200 original reservations, with accounted cost $1.028708806. These are duplicate copies of one study, not two bills. The new budget uses the brief's rounded original accounted amount $1.028709.

An exclusive create-only follow-up ownership lock was acquired before any new paid work. The paid runner also requires its own exclusive run lock and durable per-request reservations. An unresolved reservation must not be retried automatically.

The live OpenRouter endpoint metadata is archived in `parent-endpoint-check.json`. Both required endpoints were available:

- `typesafe/jev-1.13`, tag `typesafe`, TypeSafe, dated endpoint name `typesafe/jev-1.13-20260917`, input price $0.000000042/token, output price zero.
- `google/gemini-3.8-flash`, tag `google-ai-studio`, Google AI Studio, dated endpoint name `google/gemini-3.8-flash-20260902`, input price $0.00000075/token, output price $0.00000375/token. Structured outputs and reasoning controls were advertised. Flex and priority endpoints were not selected.

These endpoint names, routing tags and prices match the original manifest. The original Jev responses returned the dated model ID. Original successful Gemini responses returned the undated alias, so endpoint metadata does not prove an immutable underlying Gemini model build.

Node v22.22.3. Analysis environment: Python 3.11, numpy 2.4.6, scipy 1.17.1, scikit-learn 1.9.1, matplotlib 3.11.2. The host had about 10 GiB available RAM and 38 GiB free disk at inspection. Local CPU timing remains incomparable to remote network latency as a service-performance claim.

Original run-v1 files were hashed outside the public tree before work for a final immutability check. No portfolio repository is in scope.
