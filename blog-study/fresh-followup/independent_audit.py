"""Independent reconstruction from provider bodies and durable journals, no analyze imports."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path


def audit(root):
    load = lambda p: json.loads(p.read_text())
    manifest = load(root/'manifest.json')
    labels = load(root.parent/'categories.json')
    cases = load(root/'cases.json') + load(root/'oos.json')
    gold = {c['id']: c['expected'] for c in cases}
    rows = [load(f) for f in (root/'calls').glob('*.result.json')]
    rows.sort(key=lambda r: r['sequence'])
    paths = [load(f) for f in (root/'paths').glob('*.result.json')]
    assert len(paths) == 1200 and len(gold) == 600
    assert [r['sequence'] for r in rows] == list(range(len(rows)))
    raw_outcomes = {}
    billed = Decimal(0)
    reserved_unknown = Decimal(0)
    failures = Counter()
    versions = Counter()
    for r in rows:
        res = load(root/'calls'/(r['key']+'.reservation.json'))
        assert res['at'] <= r['timestamp']
        assert manifest['createdAt'] <= r['timestamp']
        assert r['timestamp'] < '2026-09-22T09:15:00Z'
        assert r['expected'] == gold[r['caseId']]
        raw = r['response']
        versions[(str(raw.get('model')),str(raw.get('provider')))]+=1
        if 'billedCostUsd' in r:
            assert r['billedCostUsd'] == raw['usage']['cost']
            cost = Decimal(str(raw['usage']['cost']))
            billed += cost
        else:
            cost = Decimal(str(res['amount']))
            reserved_unknown += cost
        assert Decimal(str(r['accountedUsd'])) == cost
        assert cost <= Decimal(str(res['amount']))
        predicted = None
        if r['status'] == 'ok':
            if r['system'] == 'jev':
                a = raw['answers']['intent']
                idx = a['choice']
                assert r['nativeConfidence'] == a['confidence']
                assert r['probability'] == a['probabilities'][idx]
                assert raw['provider'] == 'TypeSafe'
            else:
                a = json.loads(raw['choices'][0]['message']['content'])
                idx = a['intent']
                assert r['probability'] == a['probability']
                assert raw['provider'] == 'Google AI Studio'
            assert idx in [f'I{i:02}' for i in range(77)]
            predicted = labels[int(idx[1:])]
            assert predicted == r['predicted']
        else:
            failures[(r['system'],r['status'])]+=1
        ok = r['status'] == 'ok' and gold[r['caseId']] is not None and predicted == gold[r['caseId']]
        assert ok == r['correct']
        raw_outcomes[r['key']] = (ok,cost,r)
    assert billed + reserved_unknown <= Decimal('8.90')
    assert billed + reserved_unknown + Decimal('1.028709') <= Decimal(10)
    counts = Counter()
    costs = {'cascade': Decimal(0), 'baseline': Decimal(0)}
    used = []
    by_case = {}
    for p in paths:
        components = [raw_outcomes[k] for k in p['components']]
        used += p['components']
        assert p['latencyMs'] >= sum(c[2]['latencyMs'] for c in components)
        cost = sum((c[1] for c in components),Decimal(0))
        assert abs(float(cost)-p['accountedUsd']) < 1e-12
        if p['path'] == 'cascade':
            j = components[0][2]
            assert j['system']=='jev'
            accept = j['status']=='ok' and j.get('nativeConfidence',-1)>=1
            assert len(components)==(1 if accept else 2)
            assert p['jevAccepted']==accept
            if len(components)==2: assert components[1][2]['system']=='gemini'
        else:
            assert len(components)==1 and components[0][2]['system']=='gemini'
        final = components[-1]
        assert final[0] == p['correct']
        assert final[2]['status'] == p['status']
        if p['cohort']=='cases':
            counts[p['path']] += final[0]
            costs[p['path']] += cost
            by_case.setdefault(p['caseId'],{})[p['path']]=final[0]
    assert len(used)==len(set(used))==len(rows)
    bank_j = [r for r in rows if r['cohort']=='cases' and r['system']=='jev']
    counts['jev']=sum(raw_outcomes[r['key']][0] for r in bank_j)
    return {'independent_raw_reconstruction':True,'physical_calls':len(rows),'paths':len(paths),
            'banking_correct':dict(counts),'banking_cost_usd':{k:str(v) for k,v in costs.items()},
            'cascade_gains_vs_separate_gemini':sum(x['cascade'] and not x['baseline'] for x in by_case.values()),
            'cascade_losses_vs_separate_gemini':sum(x['baseline'] and not x['cascade'] for x in by_case.values()),
            'billed_usd':str(billed),'unknown_bill_reservations_usd':str(reserved_unknown),
            'accounted_usd':str(billed+reserved_unknown),
            'failures':{'/'.join(k):v for k,v in failures.items()},
            'returned_identities':{' | '.join(k):v for k,v in versions.items()}}


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument('--out',type=Path)
    a=ap.parse_args()
    result=audit(a.root)
    text=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if a.out: a.out.write_text(text)
    print(text)
