# Fresh follow-up status

Updated 2026-09-22T06:30:49Z. **Completed: yes.**

Stages completed: frozen protocol; prospective live cascades and separate baselines; local classifier; licensed OOS stress test; independent raw-response reconstruction; library cross-check; network-disabled fresh-directory reproduction; measured plots; sanitized publication; anonymous report/data verification.

All 1,200 planned paths completed over 500 fresh BANKING77 cases and 100 CLINC nonbanking cases. Physical API attempts: 1,630. Component failures: one Gemini banking HTTP 503 and two Jev OOS response-validation failures. No retries or unresolved reservations. Paid process exited zero. Last request began 2026-09-22T06:17:28.380Z, before the 09:15 UTC cutoff and 10:00 UTC report deadline.

New reported API charges: $0.793283526. Unknown-bill provision: $0.254479500. New conservative accounted spend: $1.047763026. Original accounted: $1.028709. **Combined accounted: $2.076472026**, below $10. The unknown-bill provision is not a known invoice.

Results: Jev 399/500; separate Gemini 425/500; actual cascade 424/500; local classifier 425/500. Cascade banking request cost saving survives even if the unknown failed Gemini call was free, 23.27%. Median latency is slower, 1,867 versus 1,638 ms. Safety cascade deferred all 100 nonbanking cases, but accepted banking error was 23/374, so this is not a production risk guarantee.

Report: https://github.com/MohtashamMurshid/jev-speed-test/blob/main/blog-study/fresh-followup/README.md

API data: https://raw.githubusercontent.com/MohtashamMurshid/jev-speed-test/main/blog-study/fresh-followup/data/responses.jsonl.gz

Banking CSV: https://raw.githubusercontent.com/MohtashamMurshid/jev-speed-test/main/blog-study/fresh-followup/data/banking-results.csv

OOS CSV: https://raw.githubusercontent.com/MohtashamMurshid/jev-speed-test/main/blog-study/fresh-followup/data/oos-results.csv

Public evidence commit: 48880db51588e49ecb5bb5967ebc2b5a287645fc. Anonymous downloads returned HTTP 200 and matched local SHA-256 hashes; JSONL and CSV row counts verified. See public-verification.json for pinned verified URLs.

Offline replay reproduced 27 artifacts byte for byte with network disabled. Local refit reproduced 800 predictions and probabilities exactly. All original run-v1 hashes and pre-inference frozen hashes unchanged. No requested core component blocked. No portfolio changes, deployment or new scheduled jobs.
