"""Post-hoc offline replay of Jev -> Gemini. No API calls or threshold selection."""
from pathlib import Path
import json,math,csv,hashlib,unittest
import numpy as np
ROOT=Path(__file__).parent
OUT=ROOT/'followup-cascade'

def accounting(r):
    for k in ['billedCostUsd','estimatedCostUsd','reservedUsd']:
        if r.get(k) is not None:
            v=float(r[k]);assert math.isfinite(v) and v>=0
            return v,k
    raise ValueError('Missing cost accounting')

def route(j,g,t):
    score=j.get('nativeConfidence')
    accept=j['status']=='ok' and isinstance(score,(int,float)) and not isinstance(score,bool) and math.isfinite(score) and score>=t
    chosen=j if accept else g
    cost=accounting(j)[0]+(0 if accept else accounting(g)[0])
    duration=j['latencyMs']+(0 if accept else g['latencyMs'])
    return accept,chosen,cost,duration

def nearest(xs,q):
    a=sorted(xs);return a[max(0,math.ceil(q*len(a))-1)] if a else None

def run():
    threshold_file=ROOT/'run-v1/thresholds.json'
    t=json.loads(threshold_file.read_text())['thresholds']['jev']['native']['threshold']
    assert t==1, 'Unexpected threshold; review protocol rather than silently changing the design'
    splits=json.loads((ROOT/'splits.json').read_text())['test'];ids=sorted(x['id'] for x in splits)
    records={m:{} for m in ['jev','gemini']};digest=hashlib.sha256()
    for f in sorted((ROOT/'run-v1/calls').glob('*.result.json')):
        b=f.read_bytes();r=json.loads(b)
        if r['phase']=='test' and r['system'] in records:
            assert r['caseId'] not in records[r['system']]
            records[r['system']][r['caseId']]=r;digest.update(f.name.encode()+b'\0'+b)
    assert len(ids)==500 and all(set(d)==set(ids) for d in records.values())
    result=[];ys={m:[] for m in ['jev','gemini','cascade']};costs={m:[] for m in ys};times={m:[] for m in ys};valid={m:[] for m in ys}
    for id in ids:
        j=records['jev'][id];g=records['gemini'][id];assert j['expected']==g['expected']
        accepted,chosen,cost,latency=route(j,g,t)
        for m,r,c,d in [('jev',j,accounting(j)[0],j['latencyMs']),('gemini',g,accounting(g)[0],g['latencyMs']),('cascade',chosen,cost,latency)]:
            correct=r['status']=='ok' and r.get('predicted')==r['expected'];assert correct==r['correct']
            ys[m].append(int(correct));costs[m].append(c);times[m].append(d);valid[m].append(r['status']=='ok')
        result.append({'caseId':id,'expected':j['expected'],'route':'jev' if accepted else 'gemini','jev_correct':bool(ys['jev'][-1]),'gemini_correct':bool(ys['gemini'][-1]),'cascade_correct':bool(ys['cascade'][-1]),'chosen_status':chosen['status'],'nativeConfidence':j.get('nativeConfidence'),'accounted_usd':cost,'simulated_ms':latency})
    labels=np.array([records['jev'][id]['expected'] for id in ids]);groups=[np.flatnonzero(labels==c) for c in sorted(set(labels))]
    rng=np.random.default_rng(20260920);boot=np.array([np.concatenate([rng.choice(g,size=len(g),replace=True) for g in groups]) for _ in range(2000)])
    summary={'design':'Post-hoc existing-data replay; no new inference, cutoff fitting, or independent validation.','threshold':t,'test_messages':len(ids),'source_records_sha256':digest.hexdigest(),'threshold_file_sha256':hashlib.sha256(threshold_file.read_bytes()).hexdigest(),'systems':{},'paired_comparisons':{},'routing':{}}
    for m in ys:
        y=np.array(ys[m]);d=[v for v,ok in zip(times[m],valid[m]) if ok]
        summary['systems'][m]={'correct':int(y.sum()),'accuracy':float(y.mean()),'accuracy_ci95':np.quantile(y[boot].mean(axis=1),[.025,.975]).tolist(),'failures':len(ids)-sum(valid[m]),'accounted_usd':sum(costs[m]),'usd_per_1000':sum(costs[m])/len(ids)*1000,'valid_response_median_ms':nearest(d,.5),'valid_response_p95_ms':nearest(d,.95),'all_outcomes_median_ms':nearest(times[m],.5),'all_outcomes_p95_ms':nearest(times[m],.95)}
    for baseline in ['jev','gemini']:
        diff=np.array(ys['cascade'])-np.array(ys[baseline]);saved=sum(costs[baseline])-sum(costs['cascade'])
        summary['paired_comparisons'][baseline]={'accuracy_difference_pp':float(diff.mean()*100),'accuracy_difference_ci95_pp':(np.quantile(diff[boot].mean(axis=1),[.025,.975])*100).tolist(),'gains':int((diff==1).sum()),'losses':int((diff==-1).sum()),'accounted_cost_savings_usd':saved,'accounted_cost_savings_percent':saved/sum(costs[baseline])*100}
    for route_name in ['jev','gemini']:
        a=[r for r in result if r['route']==route_name];summary['routing'][route_name]={'count':len(a),'fraction':len(a)/len(ids),'correct':sum(r['cascade_correct'] for r in a),'wrong_or_failed':sum(not r['cascade_correct'] for r in a),'failures':sum(r['chosen_status']!='ok' for r in a),'gemini_correct_on_same_cases':sum(r['gemini_correct'] for r in a),'jev_correct_on_same_cases':sum(r['jev_correct'] for r in a)}
    summary['cost_basis_counts']={m:{k:sum(accounting(r)[1]==k for r in records[m].values()) for k in ['billedCostUsd','estimatedCostUsd','reservedUsd']} for m in records}
    gains=[r for r in result if r['cascade_correct'] and not r['gemini_correct']]
    reported_gemini=sum(r.get('billedCostUsd',0) for r in records['gemini'].values())
    summary['gemini_comparison_details']={'gain_cases':len(gains),'gain_cases_with_gemini_api_failure':sum(records['gemini'][r['caseId']]['status']!='ok' for r in gains),'gain_cases_with_valid_wrong_gemini_answer':sum(records['gemini'][r['caseId']]['status']=='ok' for r in gains),'cost_savings_percent_if_unbilled_gemini_failure_were_free':100*(reported_gemini-sum(costs['cascade']))/reported_gemini}
    summary['assumptions']=['Sequential cascade: always call Jev; call Gemini only after a nonaccepted/failed Jev result. No third-stage human-review gate.','Reuse observed isolated-call responses, prices and durations. Omit orchestration overhead; routing may change caching, load and responses.','Simulated latency percentiles are computed per message from sums, not by adding medians or p95s. Failures excluded from valid-response timings and counted wrong for accuracy.','Sampling intervals are exploratory, paired and intent-stratified. They are not a new independent evaluation or a test of noninferiority.','Reported costs are counterfactual accounting, not actual cascade invoices. Source reservations cover unknown bills. Original raw study remains unchanged.']
    OUT.mkdir(exist_ok=True);(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (OUT/'case-results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(result[0]),lineterminator='\n');w.writeheader();w.writerows(result)
    lines=['# Jev → Gemini: post-hoc offline simulation','',summary['design'],'','Fixed rule: accept a valid Jev answer with native confidence >= 1; otherwise use Gemini. No threshold tuning.','','| System | Correct / 500 | Accuracy | Accounted USD / 1,000 | Valid median ms | Valid p95 ms | Failures |','|---|---:|---:|---:|---:|---:|---:|']
    for m,s in summary['systems'].items():lines.append(f"| {m} | {s['correct']} | {s['accuracy']:.1%} | {s['usd_per_1000']:.6f} | {s['valid_response_median_ms']:.1f} | {s['valid_response_p95_ms']:.1f} | {s['failures']} |")
    lines+=['','Cascade timings/costs are simulated, not measured in a live cascade.','','## Paired comparisons']
    for baseline,c in summary['paired_comparisons'].items():lines.append(f"- Versus {baseline}: accuracy difference {c['accuracy_difference_pp']:+.1f} percentage points; exploratory 95% interval {c['accuracy_difference_ci95_pp']}. Gains {c['gains']}, losses {c['losses']}. Accounted cost savings {c['accounted_cost_savings_percent']:.1f}%.")
    lines+=['','## Interpretation','The cascade calls Gemini for 332/500 messages and accepts Jev for 168/500. It records two more correct outcomes than Gemini alone: one replaces a valid wrong answer and one avoids an API failure. This is not independent evidence of superior accuracy.','Its simulated median is slower than Gemini alone because most messages require both sequential calls. Cost savings are the promising signal, not a blanket speed improvement.',f"If the unbilled Gemini failure cost were zero instead of its reservation, simulated savings would be {summary['gemini_comparison_details']['cost_savings_percent_if_unbilled_gemini_failure_were_free']:.1f}%. This is a sensitivity check, not a verified invoice.",'','## Reproduce','Run `python blog-study/cascade_simulation.py --test` and `python blog-study/cascade_simulation.py` in the existing NumPy analysis environment. No API credentials or network calls are required.']
    lines+=['','## Assumptions and limitations']+['- '+x for x in summary['assumptions']]
    (OUT/'README.md').write_text('\n'.join(lines)+'\n');print(json.dumps(summary,indent=2))

class Tests(unittest.TestCase):
    def row(self,**overrides):return dict({'status':'ok','nativeConfidence':1,'billedCostUsd':.1,'latencyMs':10},**overrides)
    def test_accept(self):
        j=self.row();g=self.row(billedCostUsd=.5,latencyMs=20);a,r,c,t=route(j,g,1);self.assertTrue(a);self.assertIs(r,j);self.assertAlmostEqual(c,.1);self.assertEqual(t,10)
    def test_fallback(self):
        j=self.row(nativeConfidence=.99);g=self.row(billedCostUsd=.5,latencyMs=20);a,r,c,t=route(j,g,1);self.assertFalse(a);self.assertIs(r,g);self.assertAlmostEqual(c,.6);self.assertEqual(t,30)
    def test_failed_or_missing_score_not_accepted(self):
        for change in [{'status':'error'},{'nativeConfidence':None},{'nativeConfidence':float('nan')},{'nativeConfidence':True}]:self.assertFalse(route(self.row(**change),self.row(),1)[0])
    def test_reservation_is_not_added_to_bill(self):self.assertEqual(accounting(self.row(reservedUsd=100))[0],.1)

if __name__=='__main__':
    import sys
    if '--test' in sys.argv:unittest.main(argv=[sys.argv[0]])
    else:run()
