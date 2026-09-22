#!/usr/bin/env python3
"""Offline fresh-follow-up analysis. Never sends requests or changes input records.

Run with the project's numpy/matplotlib environment. Complete-input validation is
intentional: interrupted cases must not silently disappear from denominators.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import tempfile
import numpy as np

SEED = 20260922
BOOTSTRAPS = 10000
SYSTEMS = ('jev', 'gemini', 'cascade')
COST_FIELDS = ('billedCostUsd', 'estimatedCostUsd', 'reservedUsd')


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def wilson(k, n):
    if not 0 <= k <= n:
        raise ValueError('Invalid binomial counts')
    if not n:
        return [None, None]
    z = 1.959963984540054
    p = k / n
    d = 1 + z*z/n
    center = (p + z*z/(2*n))/d
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return [max(0., center-half), min(1., center+half)]


def rate(k, n):
    return {'count': int(k), 'n': int(n), 'rate': k/n if n else None, 'wilson_ci95': wilson(k, n)}


def gate(record, system):
    field, threshold = ('nativeConfidence', 1.0) if system == 'jev' else ('probability', .95)
    v = record.get(field)
    return record.get('status') == 'ok' and finite(v) and v >= threshold


def correct(record, expected):
    return record.get('status') == 'ok' and expected is not None and record.get('predicted') == expected


def paired_bootstrap(a, b, strata, repetitions=BOOTSTRAPS, seed=SEED):
    """Paired within-intent resampling preserves every observed stratum size."""
    a, b, strata = np.asarray(a, dtype=int), np.asarray(b, dtype=int), np.asarray(strata)
    if not len(a) or len(a) != len(b) or len(a) != len(strata):
        raise ValueError('Nonempty paired aligned samples required')
    if not set(a).issubset({0, 1}) or not set(b).issubset({0, 1}):
        raise ValueError('Binary outcomes required')
    if repetitions < 1:
        raise ValueError('Positive bootstrap count required')
    difference = a - b
    rng = np.random.default_rng(seed)
    samples = np.zeros(repetitions)
    for label in sorted(set(strata.tolist())):
        values = difference[strata == label]
        samples += rng.choice(values, size=(repetitions, len(values)), replace=True).sum(axis=1)
    samples /= len(a)
    return {'n': len(a), 'difference_pp': float(difference.mean()*100),
            'ci95_pp': (np.quantile(samples, [.025, .975])*100).tolist(),
            'gains': int((difference == 1).sum()), 'losses': int((difference == -1).sum()),
            'both_correct': int(((a == 1) & (b == 1)).sum()),
            'both_wrong_or_failed': int(((a == 0) & (b == 0)).sum()),
            'bootstrap_repetitions': repetitions, 'seed': seed}


def timing(values, valid):
    if len(values) != len(valid):
        raise ValueError('Timing alignment mismatch')
    def summarize(xs):
        observed = [float(v) for v in xs if finite(v) and v >= 0]
        return {'n': len(observed), 'missing': len(xs)-len(observed),
                'median_ms': float(np.median(observed)) if observed else None,
                'p95_ms': float(np.quantile(observed, .95, method='higher')) if observed else None}
    return {'all_outcomes': summarize(values),
            'valid_chosen_response_only': summarize([v for v, ok in zip(values, valid) if ok])}


def cost_summary(records):
    """Raw source totals overlap. Accounted basis uses bill > estimate > reserve.

    A reservation is a budget provision, never an invoice. Unknown amounts remain
    unknown. Failed calls are included on exactly the same basis as successes.
    """
    totals = {k: 0. for k in COST_FIELDS}
    observed = {k: 0 for k in COST_FIELDS}
    basis = {k: 0 for k in COST_FIELDS}
    subtotal = 0.
    unknown = 0
    for r in records:
        for k in COST_FIELDS:
            v = r.get(k)
            if v is not None:
                if not finite(v) or v < 0:
                    raise ValueError(f'Invalid {k}')
                totals[k] += v
                observed[k] += 1
        selected = next((k for k in COST_FIELDS if r.get(k) is not None), None)
        if selected is None:
            unknown += 1
        else:
            basis[selected] += 1
            subtotal += r[selected]
    return {'calls': len(records), 'source_totals_usd_not_additive': totals,
            'source_observed_counts': observed, 'accounted_basis_counts': basis,
            'missing_bill_calls': len(records)-observed['billedCostUsd'],
            'unknown_calls': unknown, 'unknown_calls_definition': 'No bill, estimate or reservation available; distinct from missing_bill_calls.', 'accounted_known_subtotal_usd': subtotal,
            'accounted_total_usd': subtotal if unknown == 0 else None}


def analyze_cases(cases, repetitions=BOOTSTRAPS):
    """Canonical case has id, cohort, expected, jev, gemini, fallback,
    cascadeWallMs, baselineWallMs. Gemini is the separate matched baseline call.
    Local records are optional but must cover all banking cases if present.
    """
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate case IDs')
    banking = [c for c in cases if c['cohort'] == 'banking']
    oos = [c for c in cases if c['cohort'] == 'oos']
    if not banking:
        raise ValueError('No banking cases')
    if len(banking) + len(oos) != len(cases):
        raise ValueError('Unknown cohort')
    if any('local' in c for c in banking) and not all('local' in c for c in banking):
        raise ValueError('Partial local baseline')
    systems = list(SYSTEMS) + (['local'] if all('local' in c for c in banking) else [])
    outcomes = {m: [] for m in systems}
    validity = {m: [] for m in systems}
    durations = {m: [] for m in systems}
    costs = {m: [] for m in SYSTEMS}
    rows, physical = [], []
    component = {'jev': [], 'fallback_gemini': [], 'baseline_gemini': []}
    for c in sorted(cases, key=lambda x: x['id']):
        j, g, f = c['jev'], c['gemini'], c.get('fallback')
        accepted = gate(j, 'jev')
        if accepted and f is not None:
            raise ValueError(f"Unexpected fallback on accepted case {c['id']}")
        if not accepted and f is None:
            raise ValueError(f"Missing required fallback for {c['id']}")
        chosen = j if accepted else f
        physical.extend([j, g] + ([] if accepted else [f]))
        component['jev'].append(j)
        component['baseline_gemini'].append(g)
        if f is not None:
            component['fallback_gemini'].append(f)
        safety_accept = accepted or gate(chosen, 'gemini')
        row = {'caseId': c['id'], 'cohort': c['cohort'], 'expected': c.get('expected'),
               'route': 'jev' if accepted else 'gemini', 'jev_accept': accepted,
               'gemini_baseline_accept': gate(g, 'gemini'), 'safety_accept': safety_accept,
               'safety_human_defer': not safety_accept, 'chosen_status': chosen['status'],
               'cascade_wall_ms': c.get('cascadeWallMs'), 'baseline_wall_ms': c.get('baselineWallMs'),
               'jev_component_ms': j.get('latencyMs'),
               'fallback_component_ms': f.get('latencyMs') if f else None,
               'baseline_component_ms': g.get('latencyMs'),
               'native_confidence': j.get('nativeConfidence'),
               'gemini_probability': g.get('probability'),
               'fallback_probability': f.get('probability') if f else None}
        for m, r in [('jev', j), ('gemini', g), ('cascade', chosen)]:
            row[m+'_correct'] = correct(r, c.get('expected')) if c['cohort'] == 'banking' else None
            row[m+'_status'] = r['status']
            row[m+'_predicted'] = r.get('predicted')
        if c['cohort'] == 'banking':
            if c.get('expected') is None:
                raise ValueError('Missing banking gold label')
            records = {'jev': j, 'gemini': g, 'cascade': chosen}
            if 'local' in systems:
                records['local'] = c['local']
            for m, r in records.items():
                is_correct = correct(r, c['expected'])
                outcomes[m].append(is_correct)
                validity[m].append(r['status'] == 'ok')
                row[m+'_correct'] = is_correct
                row[m+'_status'] = r['status']
                row[m+'_predicted'] = r.get('predicted')
                duration = c.get('cascadeWallMs') if m == 'cascade' else c.get('baselineWallMs') if m == 'gemini' else r.get('latencyMs')
                durations[m].append(duration)
            costs['jev'].append(j)
            costs['gemini'].append(g)
            costs['cascade'].extend([j] + ([] if accepted else [f]))
        rows.append(row)
    banking_rows = [r for r in rows if r['cohort'] == 'banking']
    strata = [r['expected'] for r in banking_rows]
    summary = {'seed': SEED, 'banking_n': len(banking), 'oos_n': len(oos), 'systems': {},
               'physical_calls_all_cohorts': cost_summary(physical), 'comparisons': {}, 'oos': {}}
    for m in systems:
        summary['systems'][m] = {'accuracy_all_attempts': rate(sum(outcomes[m]), len(banking)),
                                'failures': len(banking)-sum(validity[m]),
                                'timing': timing(durations[m], validity[m]),
                                'timing_kind': 'CPU local inference' if m == 'local' else 'first-stage API component' if m == 'jev' else 'measured path wall time',
                                'cost': cost_summary(costs[m]) if m != 'local' else {'api_charge_usd': 0, 'compute_cost_usd': None}}
    for m in systems:
        if m != 'cascade':
            cmp = paired_bootstrap(outcomes['cascade'], outcomes[m], strata, repetitions)
            cmp['gains_against_failed_baseline'] = sum(a and not b and not ok for a, b, ok in zip(outcomes['cascade'], outcomes[m], validity[m]))
            if m in costs:
                a = summary['systems']['cascade']['cost']['accounted_total_usd']
                b = summary['systems'][m]['cost']['accounted_total_usd']
                cmp['accounted_cost_savings_usd'] = b-a if a is not None and b is not None else None
                cmp['accounted_cost_savings_percent'] = (b-a)/b*100 if a is not None and b else None
            summary['comparisons']['cascade_minus_'+m] = cmp
    summary['component_call_timing_all_cohorts'] = {k: timing([r.get('latencyMs') for r in rs], [r['status'] == 'ok' for r in rs]) for k, rs in component.items()}
    summary['routing_banking'] = {}
    for route in ('jev', 'gemini'):
        subset = [r for r in banking_rows if r['route'] == route]
        summary['routing_banking'][route] = {'n': len(subset), 'accuracy': rate(sum(r['cascade_correct'] for r in subset), len(subset)),
            'conditional_path_timing': timing([r['cascade_wall_ms'] for r in subset], [r['chosen_status'] == 'ok' for r in subset])}
    for field in ('jev_accept', 'gemini_baseline_accept', 'safety_accept'):
        subset = [r for r in rows if r['cohort'] == 'oos']
        summary['oos'][field+'_false_acceptance'] = rate(sum(r[field] for r in subset), len(subset))
    summary['oos']['human_defer'] = rate(sum(r['safety_human_defer'] for r in rows if r['cohort'] == 'oos'), len(oos))
    accepted = [r for r in banking_rows if r['safety_accept']]
    summary['safety_banking'] = {'accepted': rate(len(accepted), len(banking)),
        'accepted_error': rate(sum(not r['cascade_correct'] for r in accepted), len(accepted)),
        'human_defer_count': len(banking)-len(accepted)}
    return summary, rows


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def render(summary, rows, output):
    """Deterministic artifacts; no timestamps or absolute filesystem paths."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({'svg.hashsalt': str(SEED), 'font.family': 'DejaVu Sans',
                                'axes.spines.top': False, 'axes.spines.right': False})
    output.mkdir(parents=True, exist_ok=True)
    write_json(output/'summary.json', summary)
    with (output/'case-results.csv').open('w', newline='') as f:
        fields = sorted(set().union(*(r.keys() for r in rows)))
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    def save(fig, name):
        fig.tight_layout()
        fig.savefig(output/(name+'.svg'), metadata={'Date': None, 'Creator': 'fresh-followup/analyze.py'})
        fig.savefig(output/(name+'.png'), dpi=160, metadata={'Software': 'fresh-followup/analyze.py'})
        plt.close(fig)
    names = list(summary['systems'])
    rates = [summary['systems'][m]['accuracy_all_attempts'] for m in names]
    ys = np.array([r['rate']*100 for r in rates])
    intervals = np.array([r['wilson_ci95'] for r in rates])*100
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(names, ys, color='#426580')
    ax.errorbar(names, ys, yerr=np.maximum(0, np.stack([ys-intervals[:, 0], intervals[:, 1]-ys])), fmt='none', color='#202020', capsize=4)
    ax.set(ylabel='All-attempt accuracy (%)', ylim=(0, 105), title=f"Fresh banking, n={summary['banking_n']}; 95% Wilson intervals")
    for i, r in enumerate(rates):
        ax.text(i, 2, f"{r['count']}/{r['n']}", ha='center', color='white')
    save(fig, 'accuracy')
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, (m, field) in enumerate([('Jev component', 'jev_component_ms'), ('Gemini baseline wall', 'baseline_wall_ms'), ('Cascade wall', 'cascade_wall_ms')]):
        xs = sorted(r[field] for r in rows if r['cohort'] == 'banking' and finite(r[field]))
        if xs:
            ax.step(xs, np.arange(1, len(xs)+1)/len(xs), where='post', label=f'{m}, n={len(xs)}')
    ax.set(xlabel='Measured milliseconds, including failed outcomes', ylabel='Empirical cumulative fraction', title='Path wall time is not a sum of component medians')
    if ax.lines:
        ax.legend()
    save(fig, 'latency')
    if summary['oos_n']:
        keys = ['jev_accept_false_acceptance', 'gemini_baseline_accept_false_acceptance', 'safety_accept_false_acceptance']
        rr = [summary['oos'][k] for k in keys]
        ys = np.array([r['rate']*100 for r in rr]); ci = np.array([r['wilson_ci95'] for r in rr])*100
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar(['Jev native >= 1', 'Gemini verbalized >= .95', 'Safety cascade'], ys, color='#8a594e')
        ax.errorbar(range(3), ys, yerr=np.maximum(0, np.stack([ys-ci[:, 0], ci[:, 1]-ys])), fmt='none', color='#202020', capsize=4)
        ax.set(ylabel='Out-of-scope false acceptance (%)', ylim=(0, 105), title=f"Out-of-scope n={summary['oos_n']}; 95% Wilson intervals")
        save(fig, 'oos')
    lines = ['# Fresh follow-up results', '',
             'Fresh paired evaluation. Failures count as incorrect in every primary accuracy denominator. No threshold was fitted on these results.', '',
             '| System | Correct / attempted | Accuracy and 95% Wilson CI | Failures | All-outcome median ms | Valid-only median ms |',
             '|---|---:|---:|---:|---:|---:|']
    for m, s in summary['systems'].items():
        r = s['accuracy_all_attempts']; lo, hi = r['wilson_ci95']; t = s['timing']
        lines.append(f"| {m} | {r['count']}/{r['n']} | {r['rate']:.1%} [{lo:.1%}, {hi:.1%}] | {s['failures']} | {t['all_outcomes']['median_ms']} | {t['valid_chosen_response_only']['median_ms']} |")
    lines += ['', '## Paired differences', '', 'Intervals use paired intent-stratified percentile bootstrap resampling, seed 20260922. Nonsignificance does not establish equivalence.']
    for name, c in summary['comparisons'].items():
        lines.append(f"- {name}: {c['difference_pp']:+.2f} percentage points, 95% CI {c['ci95_pp']}; gains {c['gains']}, losses {c['losses']}. Gains against failed baseline calls: {c['gains_against_failed_baseline']}.")
    lines += ['', '## Accounting', '', 'Billed amounts, token estimates and request reservations are separate fields. Source totals overlap and must not be added. Accounted totals select bill, otherwise estimate, otherwise reservation per call. Missing amounts remain unknown. Shared Jev calls are not billed again for the Jev-only comparison.', '', '```json', json.dumps(summary['physical_calls_all_cohorts'], indent=2), '```', '', '| Banking system | Accounted USD | Billed subtotal USD | Estimated subtotal USD | Reserved subtotal USD |', '|---|---:|---:|---:|---:|']
    for m in SYSTEMS:
        c = summary['systems'][m]['cost']; v = c['source_totals_usd_not_additive']
        lines.append(f"| {m} | {c['accounted_total_usd']} | {v['billedCostUsd']} | {v['estimatedCostUsd']} | {v['reservedUsd']} |")
    lines += ['', '## Out-of-scope safety', '', 'The forced-answer cascade cannot reject out-of-scope input. The separate safety policy accepts valid Jev native confidence >= 1, otherwise accepts the actual fallback Gemini call only when its verbalized probability >= .95; otherwise it defers to a human. Native confidence is not a calibrated correctness probability. The standalone Gemini gate uses its separate matched call.', '', '```json', json.dumps(summary['oos'], indent=2), '```', '', 'Banking safety coverage and accepted error:', '```json', json.dumps(summary['safety_banking'], indent=2), '```', '', '## Timing and limitations', '', '- Cascade and Gemini wall times come from measured path records, not sums of isolated call durations. Missing wall times are not imputed.', '- Jev-only timing is the observed first-stage API component. Conditional valid-response timing excludes failed chosen answers and is not the all-attempt latency.', '- Local CPU inference, if present, is not comparable to hosted network latency. Zero API charges do not mean zero compute cost.', '- OOS rejection is a stress check on the frozen non-banking categories, not universal OOS detection.', '- Public benchmark contamination and ambiguous labels remain possible. Sampling intervals do not cover dataset shift, model drift, or provider load variation.', '- See summary.json for per-route conditional timings, missing observations, cost basis counts, and physical-call accounting.']
    if 'budget_accounting' in summary:
        lines += ['', '## Whole-study budget accounting', '', '```json', json.dumps(summary['budget_accounting'], indent=2), '```']
    if 'local_metadata' in summary:
        lines += ['', '## Local baseline provenance', '', '```json', json.dumps(summary['local_metadata'], indent=2), '```']
    lines += ['', '## Reproduce', '', 'Run `analyze.py --root <fresh-followup> --out <new-directory> --audit` in the NumPy/Matplotlib environment. The audit rerenders to a temporary directory and requires identical bytes for every export. No network calls are made.', '', '![All-attempt accuracy](accuracy.png)', '', '![Measured latency](latency.png)']
    if summary['oos_n']:
        lines += ['', '![OOS false acceptance](oos.png)']
    (output/'README.md').write_text('\n'.join(lines)+'\n')
    files = sorted(p for p in output.iterdir() if p.is_file() and p.name != 'artifact-sha256.json')
    write_json(output/'artifact-sha256.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files})


# The disk adapter below is wired to the fresh runner schema, not run-v1 records.
def load_inputs(root):
    root = Path(root)
    fingerprints = {}
    def read(path):
        data = path.read_bytes()
        fingerprints[str(path.relative_to(root))] = hashlib.sha256(data).hexdigest()
        return json.loads(data)
    protocol = read(root/'protocol.json')
    bank, oos = read(root/'cases.json'), read(root/'oos.json')
    if len(bank) != 500 or len(oos) != 100:
        raise ValueError('Frozen scope requires 500 banking and 100 OOS cases')
    if protocol['seed'] != SEED or protocol['thresholds'] != {'jevNative': 1.0, 'geminiProbability': .95}:
        raise ValueError('Unexpected seed or thresholds')
    manifest = read(root/'manifest.json')
    for name, value in [('cases', bank), ('oos', oos), ('protocol', protocol)]:
        if manifest['contract'][name] != value:
            raise ValueError('Frozen manifest differs from current '+name)
    calls, reservations = {}, {}
    for p in sorted((root/'calls').glob('*.result.json')):
        r = read(p)
        if r['key'] in calls or p.name != r['key']+'.result.json':
            raise ValueError('Duplicate or mislabeled call')
        calls[r['key']] = r
    for p in sorted((root/'calls').glob('*.reservation.json')):
        r = read(p)
        reservations[r['key']] = r
    if set(calls) != set(reservations):
        raise ValueError('Unsettled reservation or orphan call result')
    for key, r in calls.items():
        amount = reservations[key]['amount']
        if r['reservedUsd'] != amount:
            raise ValueError('Reservation amount mismatch')
        conservative = r.get('billedCostUsd', amount)
        if not finite(conservative) or conservative < 0 or conservative > amount or r.get('fatal'):
            raise ValueError('Invalid/fatal call accounting')
        if not math.isclose(r['accountedUsd'], conservative, abs_tol=1e-12):
            raise ValueError('Runner call accounting mismatch')
    if sorted(r['sequence'] for r in calls.values()) != list(range(len(calls))):
        raise ValueError('Noncontiguous or duplicated call sequence')
    paths = {}
    for p in sorted((root/'paths').glob('*.result.json')):
        r = read(p)
        key = (r['cohort'], r['caseId'], r['path'])
        if key in paths or r['timing'] != 'measured-live-sequential':
            raise ValueError('Duplicate path or nonmeasured timing')
        if not finite(r['latencyMs']) or r['latencyMs'] < 0:
            raise ValueError('Invalid path wall time')
        if not (root/'paths'/(r['key']+'.start.json')).exists():
            raise ValueError('Missing path-start journal')
        read(root/'paths'/(r['key']+'.start.json'))
        paths[key] = r
    if len(paths) != 1200:
        raise ValueError(f'Incomplete run: {len(paths)}/1200 path results; do not analyze an available-case subset')
    if len(list((root/'paths').glob('*.start.json'))) != len(paths):
        raise ValueError('Orphan/incomplete path-start journal')
    used = []
    normalized = []
    for cohort, items in [('cases', bank), ('oos', oos)]:
        for case in items:
            cp, bp = [paths[(cohort, case['id'], path)] for path in ('cascade', 'baseline')]
            def components(p):
                rs = [calls[k] for k in p['components']]
                if not rs:
                    raise ValueError('Empty path')
                for r in rs:
                    if (r['cohort'], r['caseId'], r['path'], r['expected']) != (cohort, case['id'], p['path'], case['expected']):
                        raise ValueError('Component identity or gold mismatch')
                    if r['correct'] != correct(r, case['expected']):
                        raise ValueError('Raw correct flag mismatch')
                if not math.isclose(sum(r['accountedUsd'] for r in rs), p['accountedUsd'], abs_tol=1e-12):
                    raise ValueError('Path cost mismatch')
                if p['latencyMs'] + 1e-6 < sum(r['latencyMs'] for r in rs):
                    raise ValueError('Wall time smaller than sequential components')
                final = rs[-1]
                for k in ('status', 'predicted', 'correct'):
                    if p.get(k) != final.get(k):
                        raise ValueError('Path final outcome mismatch')
                used.extend(p['components'])
                return rs
            cr, br = components(cp), components(bp)
            if [r['system'] for r in br] != ['gemini'] or cr[0]['system'] != 'jev':
                raise ValueError('Wrong component system')
            accepted = gate(cr[0], 'jev')
            if [r['system'] for r in cr] != (['jev'] if accepted else ['jev', 'gemini']):
                raise ValueError('Wrong cascade routing')
            if cp['jevAccepted'] != accepted or cp['safetyAccepted'] != (accepted or gate(cr[-1], 'gemini')):
                raise ValueError('Path gate mismatch')
            normalized.append({'id': case['id'], 'cohort': 'banking' if cohort == 'cases' else 'oos',
                'expected': case['expected'], 'jev': cr[0], 'gemini': br[0],
                'fallback': cr[1] if len(cr) == 2 else None,
                'cascadeWallMs': cp['latencyMs'], 'baselineWallMs': bp['latencyMs']})
    if len(used) != len(set(used)) or set(used) != set(calls):
        raise ValueError('Reused or unreferenced physical calls')
    ledger = sum(r.get('billedCostUsd', reservations[k]['amount']) for k, r in calls.items())
    metadata = {'input_sha256': fingerprints, 'contract_hash': manifest['contractHash'],
        'budget_accounting': {'original_study_accounted_usd': protocol['priorStudyUsd'],
            'fresh_runner_conservative_usd': ledger,
            'combined_conservative_usd': protocol['priorStudyUsd'] + ledger,
            'fresh_cap_usd': protocol['budgetUsd'], 'whole_study_cap_usd': protocol['totalStudyCapUsd'],
            'basis': 'Runner ledger uses billed amount else reservation, not token estimate. Covers every journal in this run; external development spend must be supplied separately.'},
        'returned_identities': sorted({(str(r.get('returnedModel')), str(r.get('returnedProvider'))) for r in calls.values()})}
    local_dir = root/'local'
    if local_dir.exists():
        threshold = read(local_dir/'threshold.json')
        provenance = read(local_dir/'training-provenance.json')
        local_summary = read(local_dir/'summary.json')
        if provenance['protocol_sha256'] != fingerprints['protocol.json'] or threshold['protocol_sha256'] != fingerprints['protocol.json']:
            raise ValueError('Local baseline protocol hash mismatch')
        for field in ('all_official_test_normalized_overlap', 'development_overlap', 'calibration_overlap', 'fresh_test_overlap'):
            if provenance[field] != 0:
                raise ValueError('Local fitting overlap: '+field)
        local_metrics = {}
        for cohort, filename, gold in [('banking', 'banking-predictions.json', bank), ('oos', 'oos-predictions.json', oos)]:
            records = read(local_dir/filename)
            local = {r['id']: r for r in records}
            if len(local) != len(records) or set(local) != {c['id'] for c in gold}:
                raise ValueError('Local results do not cover exact '+cohort+' set')
            for c in normalized:
                if c['cohort'] != cohort:
                    continue
                r = local[c['id']]
                if r['expected'] != c['expected'] or r['correct'] != correct(r, c['expected']):
                    raise ValueError('Local gold/outcome mismatch')
                expected_accept = r['status'] == 'ok' and threshold['threshold'] is not None and r['score'] >= threshold['threshold']
                if r['accepted'] != expected_accept:
                    raise ValueError('Local gate mismatch')
                c['local'] = dict(r, latencyMs=r['cpuMs'])
            accepted = [r for r in records if r['accepted']]
            local_metrics[cohort] = {'accepted': rate(len(accepted), len(records)),
                'accepted_error': rate(sum(not r['correct'] for r in accepted), len(accepted)),
                'all_case_cpu_timing': timing([r['cpuMs'] for r in records], [r['status'] == 'ok' for r in records]),
                'all_case_wall_timing': timing([r['wallMs'] for r in records], [r['status'] == 'ok' for r in records])}
        metadata['local_metadata'] = {'threshold': threshold, 'config': provenance['config'],
            'training_rows_retained': provenance['training_rows_retained'],
            'training_provenance_sha256': fingerprints['local/training-provenance.json'],
            'versions': local_summary['versions'], 'timing': local_summary['timing'],
            'metrics_recomputed': local_metrics, 'compute_cost': local_summary['compute_cost']}
    metadata['input_sha256'] = fingerprints
    return normalized, metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).parent)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--bootstrap', type=int, default=BOOTSTRAPS)
    parser.add_argument('--audit', action='store_true')
    args = parser.parse_args()
    cases, metadata = load_inputs(args.root)
    summary, rows = analyze_cases(cases, args.bootstrap)
    summary.update(metadata)
    output = args.out or args.root/'analysis'
    render(summary, rows, output)
    if args.audit:
        with tempfile.TemporaryDirectory(prefix='fresh-analysis-audit-') as tmp:
            repeat = Path(tmp)
            # Re-read and recompute, not just rerender the same summary object.
            cases2, metadata2 = load_inputs(args.root)
            summary2, rows2 = analyze_cases(cases2, args.bootstrap)
            summary2.update(metadata2)
            render(summary2, rows2, repeat)
            for p in repeat.iterdir():
                if p.read_bytes() != (output/p.name).read_bytes():
                    raise RuntimeError('Determinism audit failed: '+p.name)
    print(json.dumps({'output': str(output), 'banking_n': summary['banking_n'], 'oos_n': summary['oos_n'], 'audit': args.audit}))


if __name__ == '__main__':
    main()
