#!/usr/bin/env python3
"""Freeze fresh samples and protocol. No inference, no credential access.
Run once: python prepare.py [--prior-study PATH ...]
Later runs verify immutable hashes instead of resampling.
"""
import argparse
import csv
import hashlib
import json
import random
import re
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
SEED = 20260922
CLINC_COMMIT = '828f8093932c8fe6ca7936c3d2e52903b1c523de'
# Eligibility is chosen by source intent, before any model predictions.
OOS_CATEGORIES = ['weather', 'recipe', 'play_music', 'what_song', 'next_song',
                  'cook_time', 'ingredient_substitution', 'nutrition_info', 'tell_joke', 'smart_home']
LOCAL_CONFIG = {
    'vectorizer': {'ngram_range': [1, 2], 'min_df': 1, 'max_df': 1.0,
                   'sublinear_tf': True, 'lowercase': True, 'strip_accents': None,
                   'norm': 'l2', 'use_idf': True, 'smooth_idf': True,
                   'token_pattern': r'(?u)\b\w\w+\b', 'max_features': None},
    'classifier': {'C': 1.0, 'solver': 'lbfgs', 'max_iter': 1000,
                   'tol': 0.0001, 'class_weight': None, 'fit_intercept': True,
                   'random_state': SEED},
    'threads': 1, 'tuning': 'None; fixed before test predictions',
    'threshold_grid': [i / 20 for i in range(21)],
    'threshold_rule': 'Maximize calibration acceptance with >=30 accepted and <=5% empirical error; tie choose lowest cutoff. Null means defer all. No finite-sample risk guarantee.'}

def norm(s):
    return ' '.join(unicodedata.normalize('NFKC', s).casefold().split())

def sha(b):
    return hashlib.sha256(b).hexdigest()

def text_hash(s):
    return sha(norm(s).encode())

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def load_rows(split):
    with (STUDY / f'{split}.csv').open(newline='') as f:
        return [{'id': f'{split}-{i}', 'text': r['text'], 'expected': r['category']}
                for i, r in enumerate(csv.DictReader(f))]

def fetch(relative):
    url = f'https://raw.githubusercontent.com/clinc/oos-eval/{CLINC_COMMIT}/{relative}'
    with urllib.request.urlopen(url, timeout=30) as r:
        raw = r.read()
    return url, raw

def verify():
    protocol = json.loads((HERE / 'protocol.json').read_text())
    for name, digest in protocol['artifact_sha256'].items():
        assert sha((HERE / name).read_bytes()) == digest, name
    banking = json.loads((HERE / 'cases.json').read_text())
    oos = json.loads((HERE / 'oos.json').read_text())
    exclusions = set(json.loads((HERE / 'provenance/excluded-text-hashes.json').read_text()))
    assert len(banking) == 500 and len(oos) == 100
    assert len({x['expected'] for x in banking}) == 77
    assert len({text_hash(x['text']) for x in banking + oos}) == 600
    assert not ({text_hash(x['text']) for x in banking + oos} & exclusions)
    assert all(x['normalizedSha256'] == text_hash(x['text']) for x in banking + oos)
    assert all(sorted(x['pathOrder']) == ['cascade', 'gemini'] for x in banking + oos)
    print(json.dumps({'verified': True, 'banking': len(banking), 'oos': len(oos),
                      'protocol_sha256': sha((HERE / 'protocol.json').read_bytes())}))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prior-study', action='append', type=Path, default=[])
    args = parser.parse_args()
    if (HERE / 'protocol.json').exists():
        verify()
        return
    manifest = json.loads((STUDY / 'data-manifest.json').read_text())
    for remote, expected_hash in manifest['source_sha256'].items():
        local = STUDY / Path(remote).name
        assert sha(local.read_bytes()) == expected_hash, local
    train, test = load_rows('train'), load_rows('test')
    by_id = {x['id']: x for x in train + test}
    excluded = set()
    scanned = []
    # Scan all saved original JSON/JSONL records, not merely the advertised split.
    # Source IDs resolve to exact canonical text; arbitrary nested text also counts.
    def visit(obj):
        if isinstance(obj, dict):
            for key, val in obj.items():
                if key in ('text', 'input', 'customerText') and isinstance(val, str):
                    excluded.add(text_hash(val))
                if key in ('id', 'caseId', 'case_id') and isinstance(val, str) and val in by_id:
                    excluded.add(text_hash(by_id[val]['text']))
                visit(val)
        elif isinstance(obj, list):
            for val in obj:
                visit(val)
    roots = list(dict.fromkeys([STUDY.resolve()] + [p.resolve() for p in args.prior_study]))
    for root_index, root in enumerate(roots):
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.suffix not in ('.json', '.jsonl'):
                continue
            # Current output provenance is never historical exposure; existing actual
            # follow-up call records are still eligible if present at first freeze.
            if p.is_relative_to(HERE / 'provenance') or p.name in ('protocol.json', 'cases.json', 'oos.json'):
                continue
            raw = p.read_bytes()
            try:
                data = json.loads(raw) if p.suffix == '.json' else [json.loads(l) for l in raw.splitlines() if l.strip()]
            except (ValueError, UnicodeError):
                raise RuntimeError(f'Cannot audit previous record: {p}')
            visit(data)
            scanned.append({'root': root_index, 'path': str(p.relative_to(root)), 'sha256': sha(raw)})
    # Legacy replay CSV also exposes source case IDs.
    for root_index, root in enumerate(roots):
        for p in sorted(root.rglob('*.csv')):
            if p.name in ('train.csv', 'test.csv'):
                continue
            with p.open(newline='') as f:
                for row in csv.DictReader(f):
                    visit(row)
            scanned.append({'root': root_index, 'path': str(p.relative_to(root)), 'sha256': sha(p.read_bytes())})
    splits = json.loads((STUDY / 'splits.json').read_text())
    for rows in splits.values():
        for row in rows:
            assert text_hash(by_id[row['id']]['text']) == text_hash(row['text'])
            assert text_hash(row['text']) in excluded
    rng = random.Random(SEED)
    groups = defaultdict(list)
    seen = set(excluded)
    for row in test:
        h = text_hash(row['text'])
        if h not in seen:
            groups[row['expected']].append(row)
            seen.add(h)
    labels = json.loads((STUDY / 'categories.json').read_text())
    extra = labels.copy()
    rng.shuffle(extra)
    quotas = {label: 6 + (label in extra[:38]) for label in labels}
    selected = []
    for label in labels:
        assert len(groups[label]) >= quotas[label]
        selected += rng.sample(groups[label], quotas[label])
    rng.shuffle(selected)
    for row in selected:
        row.update(dataset='banking77', normalizedSha256=text_hash(row['text']),
                   pathOrder=rng.sample(['cascade', 'gemini'], 2))
    sources = {}
    blobs = {}
    for relative, name in [('data/data_full.json', 'clinc-data-full.json'),
                           ('LICENSE', 'CLINC-LICENSE.txt'), ('README.md', 'CLINC-README.md')]:
        url, raw = fetch(relative)
        sources[relative] = {'url': url, 'sha256': sha(raw)}
        blobs[relative] = raw
        # Full external dataset need not be redistributed to reproduce the subset.
        if relative != 'data/data_full.json':
            (HERE / 'provenance').mkdir(exist_ok=True)
            (HERE / 'provenance' / name).write_bytes(raw)
    assert b'Attribution 3.0 Unported' in blobs['LICENSE']
    data = json.loads(blobs['data/data_full.json'])
    oos_groups = defaultdict(list)
    oos_seen = set(excluded) | {text_hash(x['text']) for x in train + test}
    for i, (text, category) in enumerate(data['test']):
        h = text_hash(text)
        if category in OOS_CATEGORIES and h not in oos_seen:
            oos_groups[category].append({'id': f'clinc-test-{i}', 'text': text,
                'expected': None, 'sourceCategory': category, 'dataset': 'clinc150',
                'inScope': False, 'normalizedSha256': h})
            oos_seen.add(h)
    oos_rng = random.Random(SEED + 1)
    oos = []
    for category in OOS_CATEGORIES:
        oos += oos_rng.sample(oos_groups[category], 10)
    oos_rng.shuffle(oos)
    for row in oos:
        row['pathOrder'] = oos_rng.sample(['cascade', 'gemini'], 2)
    save(HERE / 'cases.json', selected)
    save(HERE / 'oos.json', oos)
    save(HERE / 'provenance/excluded-text-hashes.json', sorted(excluded))
    save(HERE / 'provenance/scanned-records.json', scanned)
    save(HERE / 'provenance/sampling.json', {
        'normalization': 'Unicode NFKC, casefold, collapse all whitespace, SHA256 UTF-8',
        'source': manifest, 'original_split_sha256': sha((STUDY / 'splits.json').read_bytes()),
        'prior_roots': ['public blog-study'] + ['additional original working blog-study' for _ in roots[1:]],
        'scanned_records': len(scanned), 'excluded_normalized_text_count': len(excluded),
        'official_test_rows': len(test), 'eligible_unique_test_rows': sum(map(len, groups.values())),
        'seed': SEED, 'algorithm': '6 per intent plus 1 for first 38 intents after seeded shuffle of original category order; sample each stratum then shuffle; Python random.Random',
        'quotas': quotas, 'oos_seed': SEED + 1, 'oos_eligible_categories': OOS_CATEGORIES,
        'oos_per_category': 10, 'oos_source_commit': CLINC_COMMIT, 'oos_sources': sources,
        'oos_license': 'CC-BY-3.0', 'oos_eligibility': 'Original CLINC150 in-scope test intents explicitly outside banking; NOT its mixed native oos_test split.',
        'oos_ground_truth': 'Existing crowdworker English messages and original category annotations; no LLM-generated labels. BANKING77 out-of-scope mapping is a predeclared domain mapping.',
    })
    (HERE / 'provenance/ATTRIBUTION.md').write_text(
        '# Dataset attribution\n\nBANKING77: PolyAI, Casanueva et al. (2020), Efficient Intent Detection with Dual Sentence Encoders. '
        'https://github.com/PolyAI-LDN/task-specific-datasets ; CC-BY-4.0. Original source revision and hashes: sampling.json. '
        'Text unchanged; subset and metadata added. License: ../.. /LICENSE (blog-study/LICENSE).\n\n'
        'CLINC150: Stefan Larson, Anish Mahendran, Joseph J. Peper, Christopher Clarke, Andrew Lee, Parker Hill, '
        'Jonathan K. Kummerfeld, Kevin Leach, Michael A. Laurenzano, Lingjia Tang, Jason Mars. '
        'An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction (EMNLP-IJCNLP 2019). '
        'https://aclanthology.org/D19-1131/ ; https://github.com/clinc/oos-eval . '
        'CC-BY-3.0, https://creativecommons.org/licenses/by/3.0/ . Full license: CLINC-LICENSE.txt. '
        'Original text unchanged; selected subset, BANKING77 scope mapping and metadata added. '
        'CLINC native OOS split was not used. Source README with authors/citation is preserved.\n')
    original = json.loads((STUDY / 'run-v1/manifest.json').read_text())
    contract = original['contract']
    protocol = {
        'version': 1, 'frozenAt': datetime.now(timezone.utc).isoformat(), 'seed': SEED,
        'bankingCases': 500, 'oosCases': 100, 'caseFiles': {'banking': 'cases.json', 'oos': 'oos.json'},
        'caseSchema': 'JSON arrays: id,text,expected (null for OOS),dataset,normalizedSha256,pathOrder [cascade,gemini] or reverse; OOS also sourceCategory,inScope=false.',
        'design': 'Prospective paired real serial cascade and separate Gemini-only request per case; banking first, OOS second; case order and within-case path order frozen in arrays. No cross-case concurrency.',
        'thresholds': {'jevNative': 1.0, 'geminiProbability': 0.95},
        'cascade': 'Accept valid Jev result iff nativeConfidence >=1. Otherwise issue Gemini with the unchanged original user request, never Jev answer. Jev-only is cascade first stage.',
        'safetyCascade': 'Accept valid Jev at nativeConfidence>=1; else accept valid fallback Gemini at probability>=0.95; otherwise defer to human. Distinct from forced-answer primary accuracy.',
        'geminiOosGate': 'Separate Gemini-only call accepted iff valid and probability>=0.95.',
        'primaryAccuracy': 'All 500 chosen banking cases, including API/contract failures as incorrect; report completion and missing cases explicitly if interrupted. Paired gains/losses, paired uncertainty. OOS has no 77-class correct label.',
        'oosAnalysis': 'Acceptance of an out-of-scope request is an error; report counts/denominators and Wilson 95% intervals. Ungated cascade cannot reject OOS.',
        'latency': 'Measure serial path wall-clock excluding queue wait; retain all component durations and failure statuses. CPU local inference is separate, not comparable hosted latency.',
        'timeoutMs': 30000, 'retries': 0, 'concurrency': 1, 'allowFallbacks': False,
        'budgetUsd': 8.90, 'priorStudyUsd': 1.028709, 'totalStudyCapUsd': 10,
        'stopInitiatingAt': '2026-09-22T09:15:00Z', 'reportDeadline': '2026-09-22T10:00:00Z',
        'billing': 'Durable per-request reservation before call; charge failures/development/comparisons; unknown charge remains reserved, not zero; resume without reissuing attempted requests. Single paid-run lock. Abort after 3 consecutive failed calls.',
        'requiredEndpointPolicy': 'Live strict capability and pinned provider verification; no silent fallback or changed endpoint claimed as matched; returned model/provider/version recorded.',
        'originalContractHash': original['contractHash'],
        'originalContract': {k: contract[k] for k in ['labels','instruction','confidenceInstruction','schema','outputLimit','temperature']},
        'models': [m for m in contract['config'] if m['key'] in ('jev','gemini')],
        'localClassifier': LOCAL_CONFIG,
        'localTraining': 'Official BANKING77 train only; normalized exclusion of original development/calibration and ALL official test texts; deduplicate train exact normalized text. Fit vectorizer solely on retained train. Original 200 calibration only chooses cutoff before fresh test prediction.',
        'limitations': ['Public benchmarks may occur in model pretraining; fresh means unused by this study, not unseen in pretraining.', 'Exact normalized deduplication does not remove semantic paraphrases.', 'Original banking labels may be ambiguous.', 'OOS is deliberately clear-domain stress testing, not a production OOS prevalence estimate.', 'Confidence types are distinct and neither gate implies a population risk guarantee.'],
        'artifact_sha256': {str(p.relative_to(HERE)): sha(p.read_bytes()) for p in
            [HERE/'cases.json', HERE/'oos.json', HERE/'provenance/sampling.json', HERE/'provenance/excluded-text-hashes.json', HERE/'provenance/scanned-records.json', HERE/'prepare.py']},
    }
    save(HERE / 'protocol.json', protocol)
    verify()

if __name__ == '__main__':
    main()
