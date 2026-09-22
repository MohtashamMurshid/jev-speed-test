"""Offline confidence audit with one valid-response mask for estimates and intervals."""
import argparse
import json
from pathlib import Path
import math
import numpy as np
from scipy.stats import hypergeom
from sklearn.metrics import roc_auc_score, average_precision_score


def eligible(rows, field):
    return [r for r in rows if r.get('status') == 'ok'
            and isinstance(r.get(field), (int, float))
            and not isinstance(r[field], bool) and math.isfinite(r[field])
            and 0 <= r[field] <= 1]


def calculate(rows, field, cutoff, repetitions=2000):
    valid = eligible(rows, field)
    y = np.array([int(not r['correct']) for r in valid])
    scores = np.array([-r[field] for r in valid])
    accepted = [r for r in valid if cutoff is not None and r[field] >= cutoff]
    n, errors, k = len(valid), int(y.sum()), len(accepted)
    rng = np.random.default_rng(20260922)
    estimates = []
    if len(set(y)) == 2:
        point = float(roc_auc_score(y, scores))
        ap = float(average_precision_score(y, scores))
        for _ in range(repetitions):
            ix = rng.integers(n, size=n)
            if len(set(y[ix])) == 2:
                estimates.append(float(roc_auc_score(y[ix], scores[ix])))
    else:
        point, ap = None, None
    return {'all_attempts': len(rows), 'eligible_valid_scored': n,
            'excluded': len(rows)-n, 'scored_failures_excluded': sum(r.get('status') != 'ok' and isinstance(r.get(field), (int, float)) for r in rows),
            'score_field': field, 'frozen_cutoff': cutoff,
            'error_auroc': point, 'error_auroc_ci95': np.quantile(estimates, [.025,.975]).tolist() if estimates else None,
            'bootstrap_requested': repetitions, 'bootstrap_two_class_samples': len(estimates),
            'bootstrap_population': 'Same valid, finite-score records as the point estimate; iid case resampling, seed 20260922.',
            'error_average_precision': ap, 'valid_error_prevalence': errors/n if n else None,
            'accepted': k, 'accepted_errors': sum(not r['correct'] for r in accepted),
            'accepted_error_rate': sum(not r['correct'] for r in accepted)/k if k else None,
            'all_attempt_coverage': k/len(rows) if rows else None,
            'matched_random_deferral': {'population': n, 'sample_size': k, 'population_errors': errors,
                'expected_accepted_errors': k*errors/n if n else None,
                'expected_error_rate': errors/n if n and k else None,
                'randomization_error_count_interval95': [int(hypergeom.ppf(q,n,errors,k)) for q in [.025,.975]] if n and k else None,
                'rule': 'Uniform sample of exactly accepted-count valid scored responses. All failures deferred in both policies; interval is a randomization interval, not parameter uncertainty.'}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    p = args.root
    rows = [json.loads(f.read_text()) for f in sorted((p/'calls').glob('*.result.json'))]
    bank = [r for r in rows if r['cohort'] == 'cases']
    j = [r for r in bank if r['system'] == 'jev']
    g = [r for r in bank if r['system'] == 'gemini' and r['path'] == 'baseline']
    assert len(j) == len(g) == 500
    local = json.loads((p/'local/banking-predictions.json').read_text())
    cutoff = json.loads((p/'local/threshold.json').read_text())['threshold']
    result = {'jev_native': calculate(j, 'nativeConfidence', 1),
              'gemini_verbalized': calculate(g, 'probability', .95),
              'local_max_class_probability': calculate(local, 'score', cutoff),
              'interpretation': 'AUROC ranks observed mistakes; it is not probability calibration. No score fitting or threshold changes on this sample.'}
    output = args.out or p/'supplement/uncertainty.json'
    output.parent.mkdir(exist_ok=True, parents=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
