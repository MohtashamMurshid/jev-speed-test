# IEEE-style draft technical report

**Confidence-Gated Jev-to-Gemini Cascades: Cost, Latency, and Deferral in Intent Classification**

This is a draft technical report using the unmodified IEEEtran conference class, not an IEEE publication or peer-reviewed paper. No venue, affiliation, email, acceptance, or external human review is asserted. Author/affiliation and venue-specific rules need confirmation before any submission.

The paper separates the preliminary four-system experiment, the post-hoc cascade replay, and the prospective fresh-data experiment. It does not pool their samples or claim that the cascade is more accurate, universally faster, or risk-guaranteed.

## Files

- `jev-confidence-study.pdf`: compiled paper.
- `main.tex`, `references.bib`: editable source.
- `generated/*.tex`: metric-derived tables, already provided for standalone compilation.
- `figures/*.pdf`: vector plots, with PNG previews.
- `generate.py`: regenerates tables/plots from the original saved metrics, without model calls.
- `evidence-manifest.json`: source revision and input SHA-256 hashes.
- `IEEEtran.cls`, `IEEEtran.bst`, `README`: unmodified upstream style files and BibTeX documentation from the [CTAN IEEEtran distribution](https://ctan.org/pkg/ieeetran). Their embedded notices and upstream licenses apply.

## Compile the supplied source

Requires pdfLaTeX, BibTeX, and standard packages `fontenc`, `inputenc`, `cite`, `amsmath`, `amssymb`, `graphicx`, `booktabs`, `hyperref`, and `url`. The IEEEtran class and bibliography style are included.

```bash
bash build.sh
```

No Python, model API, or dataset download is needed to compile the supplied tables and figures.

## Regenerate numerical tables and plots

From a full checkout of this research repository, using its pinned analysis environment:

```bash
python paper/generate.py
cd paper
bash build.sh
```

The generator consumes `blog-study/fresh-followup/analysis/summary.json`, `supplement/uncertainty.json`, `supplement/cost-sensitivity.json`, and the original `run-v1/analysis/metrics.json`. It uses NumPy and Matplotlib. The input evidence is pinned to repository revision `08138146e4a7ae0e73487e411e25765839a3d523`; hashes are retained. It makes no network or model calls.

## Review notes

- Native confidence, verbalized probability, and local class probability are not interchangeable calibrated probabilities.
- The 23.27% request-cost saving assumes the single unbilled baseline failure was free. The reservation-inclusive 55.94% number is only a sensitivity scenario, never an observed invoice saving.
- Actual cascade wall time is distinct from the earlier simulated timing and from local CPU inference time.
- The local classifier uses 9,742 labeled training examples, unlike the zero-shot hosted prompts.
- The 100 OOS cases are clearly nonbanking categories, not an open-world or adversarial evaluation.
- Fresh test messages can still have appeared in model pretraining.
- IEEE formatting alone does not establish submission readiness or scientific novelty.

The underlying datasets retain their original CC BY attribution and licenses in the evidence directories. No inference was performed to create this paper.
