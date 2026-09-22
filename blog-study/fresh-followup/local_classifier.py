#!/usr/bin/env python3
"""Fixed one-thread TF-IDF / multinomial logistic baseline; no paid calls.
Use the supplied sklearn environment or install versions in local/summary.json.
Model is refit from recorded IDs/config rather than shipping a large pickle.
"""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
import json
import platform
import time
import warnings
from collections import Counter
from pathlib import Path
import numpy as np
import scipy
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits, threadpool_info
from prepare import HERE, STUDY, load_rows, norm, sha, text_hash, save, verify


def choose_threshold(rows, grid):
    options = []
    for threshold in grid:
        accepted = [r for r in rows if r['score'] >= threshold]
        errors = sum(not r['correct'] for r in accepted)
        if len(accepted) >= 30 and errors / len(accepted) <= .05:
            options.append({'threshold': threshold, 'accepted': len(accepted), 'errors': errors})
    return sorted(options, key=lambda o: (-o['accepted'], o['threshold']))[0] if options else {
        'threshold': None, 'accepted': 0, 'errors': 0}


def summary(rows):
    accepted = [r for r in rows if r['accepted']]
    banking = all(r['expected'] is not None for r in rows)
    return {'attempted': len(rows), 'correct': sum(r['correct'] for r in rows) if banking else None,
            'accuracy': float(np.mean([r['correct'] for r in rows])) if banking else None,
            'accepted': len(accepted), 'coverage': len(accepted) / len(rows),
            'accepted_errors': sum(not r['correct'] for r in accepted) if banking else len(accepted),
            'selective_error': sum(not r['correct'] for r in accepted) / len(accepted) if banking and accepted else None,
            'cpu_inference_ms_median': float(np.median([r['cpuMs'] for r in rows])),
            'cpu_inference_ms_p95': float(np.percentile([r['cpuMs'] for r in rows], 95)),
            'wall_inference_ms_median': float(np.median([r['wallMs'] for r in rows]))}


def main():
    verify()
    out = HERE / 'local'
    out.mkdir(exist_ok=True)
    protocol = json.loads((HERE / 'protocol.json').read_text())
    config = protocol['localClassifier']
    splits = json.loads((STUDY / 'splits.json').read_text())
    assert len(splits['calibration']) == 200
    excluded = {text_hash(r['text']) for r in load_rows('test') + splits['development'] + splits['calibration']}
    seen = set()
    train = []
    removed = Counter()
    for row in load_rows('train'):
        h = text_hash(row['text'])
        if h in excluded:
            removed['heldout_overlap'] += 1
        elif h in seen:
            removed['duplicate_training_text'] += 1
        else:
            train.append(row)
            seen.add(h)
    assert not seen & excluded
    assert len({r['expected'] for r in train}) == 77
    vec_args = config['vectorizer'].copy()
    vec_args['ngram_range'] = tuple(vec_args['ngram_range'])
    vec = TfidfVectorizer(**vec_args)
    classifier = LogisticRegression(**config['classifier'])
    t0, c0 = time.perf_counter(), time.process_time()
    with threadpool_limits(limits=1), warnings.catch_warnings():
        warnings.simplefilter('error', ConvergenceWarning)
        matrix = vec.fit_transform([r['text'] for r in train])
        classifier.fit(matrix, [r['expected'] for r in train])
    train_wall, train_cpu = time.perf_counter() - t0, time.process_time() - c0
    # Warmup uses retained training data only.
    classifier.predict_proba(vec.transform([train[0]['text']]))

    def infer(rows, threshold=None):
        result = []
        with threadpool_limits(limits=1):
            for row in rows:
                assert text_hash(row['text']) not in seen
                t0, c0 = time.perf_counter_ns(), time.process_time_ns()
                probabilities = classifier.predict_proba(vec.transform([row['text']]))[0]
                j = int(np.argmax(probabilities))
                predicted = str(classifier.classes_[j])
                score = float(probabilities[j])
                cpu = (time.process_time_ns() - c0) / 1e6
                wall = (time.perf_counter_ns() - t0) / 1e6
                result.append({'id': row['id'], 'expected': row['expected'], 'predicted': predicted,
                               'score': score, 'correct': predicted == row['expected'],
                               'accepted': threshold is not None and score >= threshold,
                               'cpuMs': cpu, 'wallMs': wall, 'status': 'ok'})
        return result
    calibration = infer(splits['calibration'])
    threshold = choose_threshold(calibration, config['threshold_grid'])
    # Cutoff persisted BEFORE even loading fresh held-out examples for prediction.
    save(out / 'threshold.json', {**threshold, 'calibration_n': 200, 'rule': config['threshold_rule'],
                                 'protocol_sha256': sha((HERE / 'protocol.json').read_bytes())})
    for r in calibration:
        r['accepted'] = threshold['threshold'] is not None and r['score'] >= threshold['threshold']
    save(out / 'calibration-predictions.json', calibration)
    cases = json.loads((HERE / 'cases.json').read_text())
    oos = json.loads((HERE / 'oos.json').read_text())
    test = infer(cases, threshold['threshold'])
    oos_predictions = infer(oos, threshold['threshold'])
    save(out / 'banking-predictions.json', test)
    save(out / 'oos-predictions.json', oos_predictions)
    save(out / 'training-provenance.json', {
        'training_ids': [r['id'] for r in train],
        'training_normalized_sha256': [text_hash(r['text']) for r in train],
        'train_csv_sha256': sha((STUDY / 'train.csv').read_bytes()),
        'test_csv_sha256': sha((STUDY / 'test.csv').read_bytes()),
        'original_splits_sha256': sha((STUDY / 'splits.json').read_bytes()),
        'protocol_sha256': sha((HERE / 'protocol.json').read_bytes()),
        'code_sha256': sha(Path(__file__).read_bytes()), 'config': config,
        'exclusion_rule': protocol['localTraining'],
        'all_official_test_normalized_overlap': len(seen & {text_hash(r['text']) for r in load_rows('test')}),
        'development_overlap': len(seen & {text_hash(r['text']) for r in splits['development']}),
        'calibration_overlap': len(seen & {text_hash(r['text']) for r in splits['calibration']}),
        'fresh_test_overlap': len(seen & {text_hash(r['text']) for r in cases}),
        'training_rows_retained': len(train), 'rows_removed': dict(removed),
        'classes': list(map(str, classifier.classes_)),
        'vocabulary_size': len(vec.vocabulary_), 'fit_iterations': classifier.n_iter_.tolist(),
        'model_binary': 'Not persisted; deterministic refit from pinned inputs, fixed config, recorded versions.'})
    result = {
        'model': 'word unigram/bigram TF-IDF + L2 multinomial logistic regression',
        'training_n': len(train), 'training_wall_seconds': train_wall, 'training_cpu_seconds': train_cpu,
        'versions': {'python': platform.python_version(), 'sklearn': sklearn.__version__,
                     'numpy': np.__version__, 'scipy': scipy.__version__},
        'platform': platform.platform(), 'thread_limit': 1, 'threadpools': threadpool_info(),
        'threshold': threshold, 'calibration': summary(calibration),
        'banking': summary(test), 'oos': summary(oos_predictions),
        'api_charge_usd': 0, 'compute_cost': 'Not priced; zero API charge does not mean zero compute cost.',
        'timing': 'Per-case single-thread vectorization + predict_proba + argmax, process CPU and wall clock; one warmup on training text; training excluded. Not hosted/network latency.',
        'uncertainty_note': 'Empirical 200-example calibration cutoff, not a risk guarantee; no tuning on test.',
    }
    save(out / 'summary.json', result)
    print(json.dumps({k: result[k] for k in ('training_n', 'threshold', 'banking', 'oos', 'training_wall_seconds')}, indent=2))
    # Regression checks for exact original cutoff rule, ties, and defer-all.
    assert choose_threshold([{'score': .95, 'correct': True}] * 30, config['threshold_grid'])['threshold'] == 0
    assert choose_threshold([{'score': 1, 'correct': False}] * 200, config['threshold_grid'])['threshold'] is None
    assert choose_threshold([{'score': .95, 'correct': True}] * 29, config['threshold_grid'])['threshold'] is None
    assert len(test) == 500 and len(oos_predictions) == 100 and len(calibration) == 200
    assert all(r['predicted'] in protocol['originalContract']['labels'] for r in test + oos_predictions)
    verify()

if __name__ == '__main__':
    main()
