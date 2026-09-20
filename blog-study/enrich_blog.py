"""Add linked figures and source references to the reading preview."""
from pathlib import Path
import re
REPO='https://github.com/MohtashamMurshid/jev-speed-test'
ASSETS=REPO+'/blob/main/blog-study/run-v1/analysis/blog-assets/'
def enrich(html,root):
    def figure(name,caption):
        svg=(root/'run-v1/analysis/blog-assets'/f'{name}.svg').read_text();svg=svg[svg.index('<svg'):]
        svg=re.sub(r'<!--.*?-->','',svg,flags=re.S)
        svg=svg.replace('<svg ',f'<svg role="img" aria-label="{caption}" ',1)
        return f'<figure class="publication-figure"><p class="swipe">Swipe to inspect the full figure, or open the PNG below.</p><div class="figure">{svg}</div><figcaption>{caption} <a href="{ASSETS}{name}.png">Full-size PNG</a> · <a href="{ASSETS}{name}.svg">Editable SVG</a> · <a href="{REPO}/blob/main/blog-study/blog_visuals.py">Plotting code</a></figcaption></figure>'
    insertions=[
      ('</header>','</header>'+figure('00-cover','Editorial cover: the accept-or-review question. This diagram is not a quantitative result.')),
      ('<h3>1. Keep the first experiment',figure('01-workflow','The actual study sequence. Timing repeats do not create additional independent test messages.')+'<h3>1. Keep the first experiment'),
      ('<p>Jev had the lowest observed',figure('02-accuracy','Accuracy over all 500 attempts, including failed requests; intervals preserve the paired, intent-stratified design.')+figure('03-latency','Median and p95 time to a valid answer. Failure counts are reported separately.')+'<p>Jev had the lowest observed'),
      ('<p>Across development, threshold selection',figure('04-cost','Test-stage cost per 1,000 attempts, not the full-study bill. Missing failed-call bills are reserved conservatively.')+'<p>Across development, threshold selection'),
      ('<p>The LLMs had useful signals too.',figure('06-confidence-ranking','Confidence can rank errors without being a calibrated probability. Score sources differ, and these intervals overlap.')+'<p>The LLMs had useful signals too.'),
      ("<p>Jev's native-confidence rule accepted",figure('05-acceptance','Correct, wrong, and deferred cases under frozen off-test rules. Neither accepted-error interval guarantees the 5% target.')+"<p>Jev's native-confidence rule accepted")]
    for old,new in insertions:
        assert old in html,old
        html=html.replace(old,new,1)
    replacements=[
      ('Jev is TypeSafe AI\'s decision model.', 'Jev is <a href="https://docs.typesafe.ai/introduction">TypeSafe AI\'s decision model</a>.'),
      ('All four used OpenRouter through Vercel AI SDK,','All four used <a href="https://openrouter.ai/docs">OpenRouter</a> through <a href="https://ai-sdk.dev/docs/introduction">Vercel AI SDK</a>,'),
      ('Its API supplied a selected choice, the category-probability distribution, and native confidence.', 'Its API supplied a selected choice, the category-probability distribution, and <a href="https://docs.typesafe.ai/confidence">native confidence</a>.'),
    ]
    for old,new in replacements:
        assert old in html,old
        html=html.replace(old,new,1)
    refs='''<section id="sources"><h2>Sources, software, and downloadable figures</h2><p>The graphs above were rendered from the saved metrics with Python and Matplotlib, not generated as pictures of plausible results. The cover is an editorial diagram; the workflow depicts the recorded design. <a href="https://github.com/MohtashamMurshid/jev-speed-test/tree/main/blog-study/run-v1/analysis/blog-assets">All seven new visuals are available as PNG, SVG, and PDF</a>, with <a href="https://github.com/MohtashamMurshid/jev-speed-test/blob/main/blog-study/blog_visuals.py">their plotting source</a>.</p><ul>
<li><strong>Dataset:</strong> <a href="https://github.com/PolyAI-LDN/task-specific-datasets/tree/57ec275d8078af65b7731c2a98be812d844a6d6b/banking_data">the exact BANKING77 source revision</a>, <a href="https://arxiv.org/abs/2003.04807">the dataset paper</a>, <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0 terms</a>, and <a href="https://github.com/MohtashamMurshid/jev-speed-test/blob/main/blog-study/data-manifest.json">our source hashes and sampling manifest</a>.</li>
<li><strong>Systems:</strong> OpenRouter model listings for <a href="https://openrouter.ai/typesafe/jev-1.13">Jev 1.13</a>, <a href="https://openrouter.ai/openai/gpt-oss-120b">GPT-OSS-120B</a>, <a href="https://openrouter.ai/inception/mercury-2.5">Mercury 2.5</a>, and <a href="https://openrouter.ai/google/gemini-3.8-flash">Gemini 3.8 Flash</a>. Those pages can change; the <a href="https://github.com/MohtashamMurshid/jev-speed-test/blob/main/blog-study/run-v1/manifest.json">saved run manifest</a> and raw responses establish what this experiment actually used.</li>
<li><strong>Request stack:</strong> <a href="https://ai-sdk.dev/docs/introduction">Vercel AI SDK</a>, the <a href="https://openrouter.ai/docs/guides/community/vercel-ai-sdk">OpenRouter SDK integration</a>, <a href="https://zod.dev/">Zod</a> for schema validation, and the <a href="https://github.com/MohtashamMurshid/jev-speed-test/blob/main/package-lock.json">exact Node dependency lockfile</a>.</li>
<li><strong>Analysis and drawing:</strong> <a href="https://numpy.org/doc/stable/">NumPy</a>, <a href="https://matplotlib.org/stable/">Matplotlib</a>, and <a href="https://scikit-learn.org/stable/modules/model_evaluation.html">scikit-learn's metric definitions and independent checks</a>. Versions are saved in <a href="https://github.com/MohtashamMurshid/jev-speed-test/blob/main/blog-study/analysis-requirements.txt">analysis-requirements.txt</a>.</li>
<li><strong>Uncertainty references:</strong> <a href="https://docs.typesafe.ai/confidence">TypeSafe's confidence semantics</a>, <a href="https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html">ROC-AUC</a>, <a href="https://scikit-learn.org/stable/modules/generated/sklearn.metrics.brier_score_loss.html">Brier score</a>, and <a href="https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html">a Wilson-interval reference</a>. The last link is explanatory documentation; statsmodels was not a runtime dependency.</li>
<li><strong>Reproducibility:</strong> <a href="https://github.com/MohtashamMurshid/jev-speed-test/blob/main/data/test-results.csv">2,000 held-out results as CSV</a>, <a href="https://raw.githubusercontent.com/MohtashamMurshid/jev-speed-test/main/data/responses.jsonl.gz">all 3,200 response records</a>, <a href="https://github.com/MohtashamMurshid/jev-speed-test/blob/main/blog-study/ANALYSIS-AUDIT.md">the audit trail</a>, and the <a href="https://github.com/MohtashamMurshid/jev-speed-test/releases/tag/v0.1.0">original versioned source-and-data release</a>. The new editorial figures are committed separately in the repository; they do not alter the underlying study.</li></ul></section>'''
    html=html.replace('</article>',refs+'</article>',1)
    return html
