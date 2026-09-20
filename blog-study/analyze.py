"""Analyze the frozen blog follow-up. Never calls model APIs or changes thresholds."""
from pathlib import Path
import json, math, csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
RUN=ROOT/'run-v1'
OUT=RUN/'analysis'; OUT.mkdir(exist_ok=True)
MODELS=['jev','gpt-oss','mercury','gemini']
NAMES={'jev':'Jev 1.13','gpt-oss':'GPT-OSS / Cerebras','mercury':'Mercury 2.5','gemini':'Gemini 3.8 Flash'}
COLORS={'jev':'#B55C35','gpt-oss':'#345B8C','mercury':'#55816A','gemini':'#8263A1'}

def wilson(errors,n):
    if not n:return [None,None]
    p=errors/n;z=1.959963984540054;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    delta=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-delta),min(1,center+delta)]

def nearest(values,q):
    if not values:return None
    return sorted(values)[max(0,math.ceil(len(values)*q)-1)]

def discrimination(correct,scores):
    correct=np.array(correct,dtype=bool);scores=np.array(scores,dtype=float)
    wrong=scores[~correct];right=scores[correct]
    if len(wrong)==0 or len(right)==0:return {'auroc':None,'average_precision':None,'error_prevalence':float((~correct).mean())}
    auc=float(((right[:,None]>wrong[None,:])+0.5*(right[:,None]==wrong[None,:])).mean())
    detect=-scores;ap=0.;last_recall=0
    for cutoff in sorted(set(detect),reverse=True):
        chosen=detect>=cutoff;tp=int((chosen & ~correct).sum())
        recall=tp/len(wrong);precision=tp/int(chosen.sum())
        ap+=(recall-last_recall)*precision;last_recall=recall
    return {'auroc':auc,'average_precision':float(ap),'error_prevalence':float((~correct).mean())}

def macro_f1(rows,labels):
    scores=[]
    for label in labels:
        tp=sum(r['correct'] and r['expected']==label for r in rows)
        fp=sum(r.get('predicted')==label and not r['correct'] for r in rows)
        fn=sum(r['expected']==label and not r['correct'] for r in rows)
        scores.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.)
    return float(np.mean(scores))

def risk_curve(rows,field):
    valid=[r for r in rows if r['status']=='ok' and field in r]
    x=[];y=[]
    for cutoff in sorted({r[field] for r in valid},reverse=True):
        keep=[r for r in valid if r[field]>=cutoff]
        x.append(len(keep)/len(rows));y.append(sum(not r['correct'] for r in keep)/len(keep))
    return x,y

def eligible_scores(rows, field):
    # Failed responses may retain partial scores; never admit those into
    # confidence statistics when point estimates use valid responses only.
    return np.array([r.get(field, float('nan')) if r['status']=='ok' else float('nan') for r in rows], dtype=float)

FAILURE_CATEGORIES = ['upstream_error','api_rejection','parse_error','schema_error','timeout','truncated','refusal','provider_mismatch','other_error']
def failure_category(row):
    if row['status']=='ok': return None
    status=row['status']; message=row.get('error','').lower()
    raw=row.get('response'); raw=raw if isinstance(raw,dict) else {}
    error=raw.get('error'); error=error if isinstance(error,dict) else {}
    code=error.get('code')
    choices=raw.get('choices') or []
    refusal=any(isinstance(c,dict) and isinstance(c.get('message'),dict) and c['message'].get('refusal') for c in choices)
    if status=='provider-mismatch': return 'provider_mismatch'
    if status=='timeout': return 'timeout'
    if status=='truncated' or row.get('finishReason')=='length': return 'truncated'
    if refusal: return 'refusal'
    if isinstance(code,int) and code>=500: return 'upstream_error'
    if isinstance(code,int) and 400<=code<500: return 'api_rejection'
    if 'could not parse' in message: return 'parse_error'
    if 'did not match schema' in message: return 'schema_error'
    return 'other_error'

def make_analysis():
    rows=[json.loads(p.read_text()) for p in sorted((RUN/'calls').glob('*.result.json'))]
    test=[r for r in rows if r['phase']=='test']
    thresholds=json.loads((RUN/'thresholds.json').read_text())['thresholds']
    labels=json.loads((ROOT/'categories.json').read_text())
    groups={m:sorted([r for r in test if r['system']==m],key=lambda r:r['caseId']) for m in MODELS}
    for m,rs in groups.items():
        assert len(rs)==500,(m,len(rs))
        assert len({r['caseId'] for r in rs})==500
        assert all(r['caseId']==t['caseId'] for r,t in zip(rs,groups['jev']))
    # Paired, stratified-by-intent bootstrap preserves the fixed sampling design.
    rng=np.random.default_rng(20260920)
    indices=[np.array([i for i,r in enumerate(groups['jev']) if r['expected']==label]) for label in labels]
    samples=np.stack([np.concatenate([rng.choice(x,len(x),replace=True) for x in indices]) for _ in range(2000)])
    base=np.array([r['correct'] for r in groups['jev']],dtype=float)
    stats={};selective={};reliability={}
    for m,rs in groups.items():
        valid=[r for r in rs if r['status']=='ok'];ok=np.array([r['correct'] for r in rs],dtype=float)
        prob=np.array([r['probability'] for r in valid]);correct=np.array([r['correct'] for r in valid],dtype=float)
        lat=[r['latencyMs'] for r in valid]
        modelrows=[r for r in rows if r['system']==m]
        billed=[r.get('billedCostUsd') for r in modelrows];billedtest=[r.get('billedCostUsd') for r in rs]
        costs=[r.get('billedCostUsd',r.get('estimatedCostUsd',r['reservedUsd'])) for r in rs]
        allcost=[r.get('billedCostUsd',r.get('estimatedCostUsd',r['reservedUsd'])) for r in modelrows]
        repeats=[r['latencyMs'] for r in modelrows if r['phase']=='repeat' and r['status']=='ok']
        stats[m]={'name':NAMES[m],'test_n':len(rs),'correct':int(ok.sum()),'accuracy':float(ok.mean()),'accuracy_ci95':np.quantile(ok[samples].mean(axis=1),[.025,.975]).tolist(),'paired_accuracy_difference_vs_jev':float((ok-base).mean()),'paired_difference_ci95':np.quantile((ok-base)[samples].mean(axis=1),[.025,.975]).tolist(),'macro_f1':macro_f1(rs,labels),'failures':len(rs)-len(valid),'valid_responses':len(valid),'failure_breakdown':{cat:sum(failure_category(r)==cat for r in rs) for cat in FAILURE_CATEGORIES},'median_terminal_outcome_ms':nearest([r['latencyMs'] for r in rs],.5),'p95_terminal_outcome_ms':nearest([r['latencyMs'] for r in rs],.95),'median_ms':nearest(lat,.5),'p95_ms':nearest(lat,.95),'cost_per_1000_usd':sum(costs)/len(rs)*1000,'cost_per_correct_decision_usd':sum(costs)/int(ok.sum()) if ok.sum() else None,'cost_basis':'provider billed' if all(x is not None for x in billedtest) else 'billed where available, otherwise usage estimate/reservation','all_phase_accounted_usd':sum(allcost),'all_phase_calls':len(modelrows),'all_phase_billed_usd':sum(billed) if all(x is not None for x in billed) else None,'brier':float(np.mean((prob-correct)**2)),'probability_error_detection':discrimination(correct,prob),'timing_repeat_median_ms':nearest(repeats,.5),'timing_repeat_p95_ms':nearest(repeats,.95)}
        if m=='jev':stats[m]['native_error_detection']=discrimination(correct,[r['nativeConfidence'] for r in valid])
        # Bootstrap discrimination, retaining tied scores and undefined samples as NA.
        for field,label in [('probability','probability'),*([('nativeConfidence','native')] if m=='jev' else [])]:
            scores=eligible_scores(rs,field);aucs=[]
            for ix in samples:
                y=ok[ix];s=scores[ix];mask=np.isfinite(s)
                w=s[mask & (y==0)];c=s[mask & (y==1)]
                if len(w) and len(c):aucs.append(float(((c[:,None]>w)+.5*(c[:,None]==w)).mean()))
            stats[m][label+'_error_detection']['auroc_ci95']=np.quantile(aucs,[.025,.975]).tolist() if aucs else [None,None]
        selective[m]={}
        for field,label in [('probability','probability'),*([('nativeConfidence','native')] if m=='jev' else [])]:
            threshold=thresholds[m][label]['threshold']
            accepted=[] if threshold is None else [r for r in valid if r[field]>=threshold]
            errors=sum(not r['correct'] for r in accepted)
            selective[m][label]={'threshold':threshold,'calibration':thresholds[m][label],'accepted':len(accepted),'coverage':len(accepted)/len(rs),'errors':errors,'accepted_error':errors/len(accepted) if accepted else None,'accepted_error_ci95':wilson(errors,len(accepted)),'accept_all_error':1-float(ok.mean()),'random_deferral_expected_error':sum(not r['correct'] for r in valid)/len(valid) if valid else None}
        bins=[]
        for low,high in zip(np.arange(0,1,.2),np.arange(.2,1.01,.2)):
            selected=[r for r in valid if r['probability']>=low and (r['probability']<high or high>.999 and r['probability']<=1)]
            k=sum(r['correct'] for r in selected)
            bins.append({'low':float(low),'high':float(high),'n':len(selected),'mean_probability':float(np.mean([r['probability'] for r in selected])) if selected else None,'accuracy':k/len(selected) if selected else None,'ci95':wilson(k,len(selected)),'sparse':len(selected)<20})
        reliability[m]=bins
    result={'run':'BANKING77 blog follow-up v1','stats':stats,'selective':selective,'reliability':reliability,'total_accounted_usd':sum(v['all_phase_accounted_usd'] for v in stats.values()),'bootstrap':'2000 paired stratified-by-intent replicates, seed 20260920. Exploratory comparisons; no multiplicity-adjusted significance claims.'}
    (OUT/'metrics.json').write_text(json.dumps(result,indent=2))
    lines=['# Fast-model BANKING77 follow-up','', '500 unique held-out English messages across 77 intents. One prediction per model; 50 timing repeats excluded from accuracy.', '', '| Model | Correct | Accuracy | Failed / 500 | Valid-response median ms | Valid-response p95 ms | USD / 1,000 | Error AUROC | Brier |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m,s in stats.items():lines.append(f"| {s['name']} | {s['correct']}/500 | {100*s['accuracy']:.1f}% | {s['failures']} | {s['median_ms']:.0f} | {s['p95_ms']:.0f} | {s['cost_per_1000_usd']:.3f} | {s['probability_error_detection']['auroc']:.3f} | {s['brier']:.4f} |")
    lines += ['', '## Request failure breakdown', '', 'Counts below use all 500 test attempts per model. Confidence metrics use valid responses only. Latency in the main table is conditional on a valid response; time-to-terminal-outcome for all attempts is retained in metrics.json.', '']
    for model, stat in stats.items():
        pieces=[f"{category}: {count}/500 ({count/5:.1f}%)" for category,count in stat['failure_breakdown'].items() if count]
        lines.append(f"- {stat['name']}: " + ('; '.join(pieces) if pieces else '0/500 request failures.'))
    lines += ['', 'No explicit model refusals or timeouts were observed. Failed rows are categorized from the preserved API error code, error message, and response metadata; original records are unchanged.', '']
    lines+=['','## Frozen off-test deferral rules','','| Model / score | Cutoff | Accepted / 500 | Errors / accepted | Test error | 95% interval |','|---|---:|---:|---:|---:|---:|']
    for m,variants in selective.items():
        for name,v in variants.items():
            risk='NA' if v['accepted_error'] is None else f"{100*v['accepted_error']:.1f}%"
            ci='NA' if v['accepted']==0 else f"{100*v['accepted_error_ci95'][0]:.1f}–{100*v['accepted_error_ci95'][1]:.1f}%"
            lines.append(f"| {NAMES[m]} / {name} | {v['threshold']} | {v['accepted']} | {v['errors']} | {risk} | {ci} |")
    lines += ['',f"Total accounted inference across all phases: ${result['total_accounted_usd']:.6f}.",'','Confidence AUROC: higher is better at detecting errors; chance is 0.5. LLM scores are verbalized correctness probabilities. Jev primary score is selected-label probability; its native confidence is evaluated separately. Brier is computed only on probability scores, lower is better.','', 'Thresholds were selected on 200 disjoint calibration examples for empirical <=5% error and at least 30 accepted. This is not a guaranteed risk bound. They were frozen before test inference. Sparse bins and small error counts limit certainty. Public benchmark contamination and one-host/one-date serving effects remain possible.']
    (OUT/'summary.md').write_text('\n'.join(lines)+'\n')
    return result,groups

def plots(result,groups):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','figure.facecolor':'#fafaf7','axes.facecolor':'#fafaf7','savefig.facecolor':'#fafaf7','pdf.fonttype':42,'svg.fonttype':'none'})
    names=[NAMES[m] for m in MODELS];colors=[COLORS[m] for m in MODELS]
    fig,axs=plt.subplots(1,3,figsize=(15,7));fig.subplots_adjust(top=.76,bottom=.27,left=.155,right=.98,wspace=.40)
    fig.suptitle('Four fast models, one harder routing test',fontsize=23,y=.96)
    fig.text(.5,.88,'500 English messages • 77 banking intents • real API calls',ha='center',fontsize=13,color='#555555')
    data=[[result['stats'][m]['accuracy']*100 for m in MODELS],[result['stats'][m]['median_ms']/1000 for m in MODELS],[result['stats'][m]['cost_per_1000_usd'] for m in MODELS]]
    titles=['Correct intent (%) ↑','Median time (seconds) ↓','USD per 1,000 requests ↓']
    for ax,values,title in zip(axs,data,titles):
        bars=ax.barh(np.arange(4),values,color=colors,height=.55);ax.set_yticks(np.arange(4),names if ax==axs[0] else ['Jev','GPT-OSS','Mercury','Gemini']);ax.invert_yaxis();ax.set_title(title,fontsize=12,pad=15);ax.set_xlim(0,(100 if ax==axs[0] else max(values)*1.28));ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
        for bar,v in zip(bars,values):ax.text(v+.01*ax.get_xlim()[1],bar.get_y()+bar.get_height()/2,f'{v:.1f}' if ax==axs[0] else f'{v:.3f}',va='center',fontsize=11)
    fig.text(.065,.13,'Latency includes network and schema validation. One outstanding call per provider, four providers in parallel.\nCosts use reported charges where available; otherwise usage estimates or error reservations. Timing repeats and development excluded.\nFailed calls count as incorrect. Latency is for valid answers only. One dataset, one host, one run.',fontsize=10.5,linespacing=1.6,color='#555555')
    save(fig,'01-results')
    fig,axs=plt.subplots(2,2,figsize=(13,9));fig.subplots_adjust(top=.83,bottom=.16,left=.085,right=.97,hspace=.45,wspace=.28)
    fig.suptitle('Do lower scores actually flag mistakes?',fontsize=23,y=.97)
    fig.text(.5,.915,'Error-detection curves on the 500 held-out messages; cutoffs were chosen elsewhere.',ha='center',fontsize=11.5)
    for ax,m in zip(axs.ravel(),MODELS):
        x,y=risk_curve(groups[m],'probability');ax.plot(np.array(x)*100,np.array(y)*100,color=COLORS[m],linewidth=2,label='Probability score')
        if m=='jev':
            x,y=risk_curve(groups[m],'nativeConfidence');ax.plot(np.array(x)*100,np.array(y)*100,color='#292721',ls='--',linewidth=1.4,label='Native confidence');ax.legend(frameon=False,fontsize=9)
        baseline=100*result['selective'][m]['probability']['random_deferral_expected_error'];ax.axhline(baseline,color='#999999',ls=':',linewidth=1)
        ax.axhline(5,color='#999999',ls='--',linewidth=.8)
        if m=='jev':
            native=result['selective'][m]['native']
            if native['accepted']:ax.scatter([native['coverage']*100],[native['accepted_error']*100],marker='D',s=60,color='#292721',edgecolor='white',zorder=5)
        op=result['selective'][m]['probability']
        if op['accepted']:ax.scatter([op['coverage']*100],[op['accepted_error']*100],s=60,color=COLORS[m],edgecolor='white',zorder=4)
        ax.set_title(NAMES[m],fontsize=12);ax.set_xlabel('Requests accepted (%)');ax.set_ylabel('Wrong among accepted (%)');ax.set_xlim(0,100);ax.set_ylim(0,30);ax.grid(alpha=.15)
    fig.text(.085,.065,'Circle: probability rule; diamond: Jev native rule. Cutoffs frozen on 200 separate messages. Dashed line: 5% target.\nDotted line: random deferral among valid responses; request failures always deferred. Curves are descriptive only.',fontsize=10.5,color='#555555',linespacing=1.5)
    save(fig,'02-deferral')
    fig,axs=plt.subplots(1,2,figsize=(13,7));fig.subplots_adjust(top=.77,bottom=.23,left=.075,right=.97,wspace=.27)
    fig.suptitle("Jev's confidence versus its actual mistakes",fontsize=23,y=.96)
    fig.text(.5,.885,'Native confidence and selected-answer probability are different outputs.',ha='center',fontsize=12)
    for ax,field,title in zip(axs,['nativeConfidence','probability'],['Native confidence','Probability of selected intent']):
        correct=[r[field] for r in groups['jev'] if r['status']=='ok' and r['correct']];wrong=[r[field] for r in groups['jev'] if r['status']=='ok' and not r['correct']]
        for vals,color,label in [(correct,'#345B8C',f'Correct, n={len(correct)}'),(wrong,'#B55C35',f'Wrong, n={len(wrong)}')]:
            vals=sorted(vals);ax.step(vals,np.arange(1,len(vals)+1)/len(vals),where='post',color=color,linewidth=2,label=label)
        ax.set_xlabel(title);ax.set_ylabel('Fraction at or below this score');ax.set_xlim(0,1);ax.set_ylim(0,1);ax.legend(frameon=False,fontsize=10);ax.grid(alpha=.15)
    fig.text(.075,.1,'A curve further left means lower scores. Separation shows whether the score helps rank mistakes.\nA native confidence of 0.9 does not itself mean a 90% chance of being right. No fitted calibration was used.',fontsize=11,color='#555555',linespacing=1.5)
    save(fig,'03-jev-confidence')
    fig,axs=plt.subplots(2,2,figsize=(12,9));fig.subplots_adjust(top=.84,bottom=.14,left=.08,right=.97,wspace=.28,hspace=.38)
    fig.suptitle('Do stated probabilities match observed accuracy?',fontsize=21,y=.97)
    fig.text(.5,.915,'Five fixed probability bins. Bars show Wilson 95% intervals, not model uncertainty.',ha='center',fontsize=11)
    for ax,m in zip(axs.ravel(),MODELS):
        ax.plot([0,1],[0,1],ls='--',color='#999999');ax.set_xlim(0,1);ax.set_ylim(0,1.1);ax.set_title(NAMES[m],fontsize=12)
        for b in result['reliability'][m]:
            if not b['n']:continue
            x=b['mean_probability'];y=b['accuracy'];lo,hi=b['ci95']
            ax.errorbar(x,y,yerr=[[y-lo],[hi-y]],fmt='o',color=COLORS[m],mfc='white' if b['sparse'] else COLORS[m],capsize=3)
            ax.annotate(f"n={b['n']}",(x,y),xytext=(-4,10),textcoords='offset points',ha='right',fontsize=8)
        ax.set_xlabel('Mean predicted probability');ax.set_ylabel('Observed fraction correct');ax.grid(alpha=.15)
    fig.text(.08,.045,'Hollow points: fewer than 20 examples. LLMs report verbalized probabilities; Jev supplies class probabilities.\nSparse bins and public-dataset contamination limit conclusions. Native Jev confidence is not used in this plot.',fontsize=10,color='#555555',linespacing=1.5)
    save(fig,'04-reliability')

def save(fig,name):
    for ext in ['png','pdf','svg']:fig.savefig(OUT/f'{name}.{ext}',dpi=180)
    plt.close(fig)

if __name__=='__main__':
    result,groups=make_analysis();plots(result,groups)
    print(json.dumps(result['stats'],indent=2));print('TOTAL',result['total_accounted_usd'])
