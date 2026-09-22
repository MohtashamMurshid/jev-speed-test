"""Measured cost and gate plots, kept separate from core deterministic analysis."""
import json
from pathlib import Path
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze import wilson


def main(root):
    s=json.loads((root/'analysis/summary.json').read_text())
    u=json.loads((root/'supplement/uncertainty.json').read_text())
    out=root/'supplement';out.mkdir(exist_ok=True)
    plt.rcParams.update({'svg.hashsalt':'fresh20260922','font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False})
    def save(fig,name):
        fig.tight_layout()
        fig.savefig(out/(name+'.png'),dpi=180,metadata={'Software':'fresh-followup/supplement_plots.py'})
        fig.savefig(out/(name+'.svg'),metadata={'Date':None,'Creator':'fresh-followup/supplement_plots.py'})
        fig.savefig(out/(name+'.pdf'),metadata={'CreationDate':None,'ModDate':None})
        plt.close(fig)
    names=['jev','gemini','cascade']
    costs=[s['systems'][m]['cost']['accounted_total_usd']/s['banking_n']*1000 for m in names]
    known=[s['systems'][m]['cost']['source_totals_usd_not_additive']['billedCostUsd']/s['banking_n']*1000 for m in names]
    unknown=np.array(costs)-np.array(known)
    fig,ax=plt.subplots(figsize=(8,4.8))
    positions=np.arange(3)
    ax.bar(positions,known,color=['#879aa6','#426580','#9b6b4d'],label='Reported API charges')
    ax.bar(positions,unknown,bottom=known,color='none',edgecolor='#555555',hatch='///',label='Unknown bill reservation, not an invoice')
    ax.set_xticks(positions,['Jev first stage','Separate Gemini','Live cascade'])
    for i,v in enumerate(known):
        if unknown[i] > 1e-12:
            ax.text(i,v/2,f'${v:.3f} reported',ha='center',va='center',fontsize=9,color='white')
            ax.text(i,costs[i],f'+${unknown[i]:.3f} reserved',ha='center',va='bottom',fontsize=9)
        else:
            ax.text(i,v,f'${v:.3f} reported',ha='center',va='bottom',fontsize=9)
    ax.set(ylabel='USD per 1,000 banking cases',title=f"Observed requests on {s['banking_n']} cases, normalized to 1,000",ylim=(0,max(costs)*1.4))
    ax.legend(fontsize=8,loc='upper right')
    save(fig,'cost')
    keys=['jev_native','gemini_verbalized','local_max_class_probability']
    names=['Jev gate','Gemini gate','Local gate','Safety cascade']
    accepted=[u[k]['accepted'] for k in keys]+[s['safety_banking']['accepted']['count']]
    errors=[u[k]['accepted_errors'] for k in keys]+[s['safety_banking']['accepted_error']['count']]
    fig,axs=plt.subplots(1,2,figsize=(10,4.8))
    for ax,counts,denoms,title in [(axs[0],accepted,[s['banking_n']]*4,'Banking acceptance'),(axs[1],errors,accepted,'Error among accepted banking cases')]:
        val=np.array([a/b*100 if b else 0 for a,b in zip(counts,denoms)])
        ci=np.array([wilson(a,b) if b else [0,0] for a,b in zip(counts,denoms)])*100
        ax.bar(names,val,color='#426580')
        ax.errorbar(range(4),val,yerr=np.maximum(0,np.array([val-ci[:,0],ci[:,1]-val])),fmt='none',color='#222222',capsize=3)
        ax.set(title=title,ylabel='Percent',ylim=(0,105 if ax is axs[0] else max(12,float(ci.max())+2)))
        ax.tick_params(axis='x',rotation=20)
        for i,(a,b) in enumerate(zip(counts,denoms)):ax.text(i,2 if ax is axs[0] else .35,f'{a}/{b}',ha='center',fontsize=9,color='white')
    axs[1].axhline(5,color='#9b6b4d',ls=':',label='Original calibration target')
    axs[1].legend(fontsize=8)
    fig.suptitle('Frozen gates, 95% Wilson intervals. No production risk guarantee.',fontsize=12)
    save(fig,'gates')
    local=json.loads((root/'local/oos-predictions.json').read_text())
    counts=[s['oos'][k]['count'] for k in ['jev_accept_false_acceptance','gemini_baseline_accept_false_acceptance','safety_accept_false_acceptance']]+[sum(r['accepted'] for r in local)]
    names=['Jev gate','Gemini gate','Safety cascade','Local gate'];n=s['oos_n']
    val=np.array(counts)/n*100; ci=np.array([wilson(k,n) for k in counts])*100
    fig,ax=plt.subplots(figsize=(8,4.5));ax.bar(names,val,color='#9b6b4d')
    ax.errorbar(range(4),val,yerr=np.maximum(0,np.array([val-ci[:,0],ci[:,1]-val])),fmt='none',color='#222222',capsize=4)
    for i,k in enumerate(counts):ax.text(i,ci[i,1]+.4,f'{k}/{n}',ha='center')
    ax.set(ylabel='Nonbanking false acceptance (%)',ylim=(0,max(10,float(ci.max())+2)),title='100 clear-domain stress cases, 95% Wilson intervals')
    save(fig,'oos-all-gates')
    print('Saved cost, gate and OOS plots in PNG/SVG/PDF from saved records.')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    main(ap.parse_args().root)
