"""Publication figures from frozen metrics. No API calls; no invented observations."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
ROOT=Path(__file__).parent
M=json.loads((ROOT/'run-v1/analysis/metrics.json').read_text())
OUT=ROOT/'run-v1/analysis/blog-assets';OUT.mkdir(exist_ok=True)
KEYS=['jev','gpt-oss','mercury','gemini']
NAMES=['Jev 1.13','GPT-OSS / Cerebras','Mercury 2.5','Gemini 3.8 Flash']
C=['#41697c','#838b84','#aa8469','#786888'];BG='#f2eee5';INK='#292721';RED='#a45d50'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'figure.facecolor':BG,'axes.facecolor':BG,'text.color':INK,'axes.labelcolor':INK,'xtick.color':INK,'ytick.color':INK,'svg.fonttype':'none','savefig.facecolor':BG})
def save(fig,name):
    for ext in ['png','svg','pdf']:fig.savefig(OUT/f'{name}.{ext}',dpi=180)
    plt.close(fig)
def clean(ax):
    for s in ax.spines.values():s.set_visible(False)
    ax.tick_params(axis='both',length=0)
    ax.set_axisbelow(True);ax.grid(axis='x',color='#dcd5c9',linewidth=.7)
def base(title,sub,foot):
    f,a=plt.subplots(figsize=(10,6));f.subplots_adjust(left=.27,right=.91,top=.72,bottom=.25)
    f.text(.045,.91,title,fontsize=24,fontfamily='DejaVu Serif')
    f.text(.045,.83,sub,fontsize=11)
    f.text(.045,.065,foot,fontsize=10,linespacing=1.6)
    clean(a);a.set_yticks(range(4),NAMES);a.invert_yaxis()
    return f,a
# Editorial cover: deliberately not a quantitative graph.
f,a=plt.subplots(figsize=(12,6.3));a.set_axis_off()
f.text(.065,.83,'JEV / FAST LLMS',fontsize=12,color='#78736a')
f.text(.065,.53,'Can a model tell\nwhen it is wrong?',fontsize=40,fontfamily='DejaVu Serif',linespacing=1.12)
f.text(.065,.29,'500 held-out banking messages. Four API systems.\nConfidence tested on answers the cutoff rule had not seen.',fontsize=13,linespacing=1.6)
for yy,txt in [(.64,'accept'),(.34,'review')]:
    a.annotate('',xy=(.91,yy),xytext=(.70,.49),xycoords='axes fraction',arrowprops={'arrowstyle':'->','color':C[0] if yy>.5 else RED,'lw':2})
    a.text(.93,yy,txt,transform=a.transAxes,ha='left',va='center',fontsize=12)
a.scatter([.70],[.49],s=130,color=INK,transform=a.transAxes)
f.text(.065,.09,'A reproducible experiment, not a production-risk guarantee.',fontsize=10,color='#78736a')
save(f,'00-cover')
# Process diagram, counts are independent messages per model except repeats.
f,a=plt.subplots(figsize=(10,8));a.set_axis_off()
f.text(.07,.91,'The test, in order',fontsize=28,fontfamily='DejaVu Serif')
f.text(.07,.85,'BANKING77 · English only · four pinned model/provider pairs',fontsize=12)
steps=[('50','Development','Check requests, parsing, confidence capture, and budget logic.'),('200','Choose cutoffs','Separate training-split messages. Freeze the acceptance rules.'),('500','Held-out test','Official test-split subset. Do not change the frozen cutoffs.'),('50','Timing repeats','Repeat a fixed subset. Not additional accuracy evidence.')]
for i,(num,title,desc) in enumerate(steps):
    y=.75-i*.17
    f.text(.08,y,num,fontsize=29,color=C[0]);f.text(.24,y+.015,title,fontsize=17)
    f.text(.24,y-.035,desc,fontsize=11)
    if i<3:a.annotate('',xy=(.113,y-.10),xytext=(.113,y-.04),xycoords=f.transFigure,arrowprops={'arrowstyle':'->','color':'#aba396'})
f.text(.07,.06,'Counts are per model. 3,200 API attempts total; 500 independent test messages.\nNo retries or fallback. No AI-generated answer key for this follow-up.',fontsize=11,linespacing=1.7)
save(f,'01-workflow')
f,a=base('How often did each system get it right?','One attempt per system on the same 500 held-out messages.','Bars: accuracy over all 500 attempts. Lines: 95% paired, intent-stratified bootstrap intervals.\nFailures count as incorrect: Jev 0, GPT-OSS 0, Mercury 28, Gemini 1.')
v=np.array([M['stats'][k]['accuracy']*100 for k in KEYS]);cis=np.array([M['stats'][k]['accuracy_ci95'] for k in KEYS])*100
assert np.all(cis[:,0]<=v) and np.all(cis[:,1]>=v)
a.barh(range(4),v,color=C,height=.48);a.errorbar(v,range(4),xerr=np.array([v-cis[:,0],cis[:,1]-v]),fmt='none',ecolor=INK,capsize=4)
for i,x in enumerate(v):a.text(cis[i,1]+1.5,i,f'{x:.1f}%',va='center',fontsize=12)
a.set_xlim(0,100);a.set_xlabel('Correct answers (%)')
save(f,'02-accuracy')
f,a=base('How long did a valid answer take?','End-to-end response time, including networking and validation.','Median and p95 use valid responses only; faster errors are not counted as fast answers.\nOne host and one run. These are hosted-system timings, not pure model-compute timings.')
y=np.arange(4);med=np.array([M['stats'][k]['median_ms'] for k in KEYS])/1000;p95=np.array([M['stats'][k]['p95_ms'] for k in KEYS])/1000
for i in range(4):
 a.barh(i-.14,med[i],height=.24,color=C[i]);a.barh(i+.14,p95[i],height=.24,color=C[i],alpha=.35)
 a.text(med[i]+.035,i-.14,f'{med[i]:.3f}',va='center',fontsize=10)
 a.text(p95[i]+.035,i+.14,f'{p95[i]:.3f}',va='center',fontsize=10)
a.set_xlim(0,max(p95)*1.18);a.set_xlabel('Seconds · solid: median / pale: 95th percentile')
save(f,'03-latency')
f,a=base('What did the requests cost?','Test-stage accounting, scaled to 1,000 attempts. Lower is cheaper.','Reported API charges where available; conservative reservations for missing failed-call bills.\nExcludes development, cutoff selection, and repeats. Prices are specific to this run.')
v=[M['stats'][k]['cost_per_1000_usd'] for k in KEYS];a.barh(range(4),v,color=C,height=.48)
for i,x in enumerate(v):a.text(x+.012,i,f'${x:.3f}',va='center')
a.set_xlim(0,max(v)*1.22);a.set_xlabel('Accounted USD per 1,000 test attempts')
save(f,'04-cost')
# Acceptance must not confuse retained accuracy with the whole dataset.
f,ax=plt.subplots(2,1,figsize=(10,8),gridspec_kw={'height_ratios':[1.25,1]});f.subplots_adjust(left=.24,right=.94,top=.76,bottom=.19,hspace=.65)
f.text(.045,.92,'What did the frozen rules accept?',fontsize=26,fontfamily='DejaVu Serif')
f.text(.045,.855,'Cutoffs selected on 200 separate messages; evaluated on 500 unseen messages.\nJev uses native confidence. Gemini uses its reported probability.',fontsize=11,linespacing=1.7)
for i,(model,score,label) in enumerate([('jev','native','Jev / native'),('gemini','probability','Gemini / probability')]):
 d=M['selective'][model][score];good=d['accepted']-d['errors'];bad=d['errors'];defer=500-d['accepted'];assert good+bad+defer==500
 ax[0].barh(i,good,color=C[0],height=.45);ax[0].barh(i,bad,left=good,color=RED,height=.45);ax[0].barh(i,defer,left=good+bad,color='#d7d0c3',height=.45)
 ax[0].text(good/2,i,str(good),ha='center',va='center',color='white');ax[0].text(good+bad+defer/2,i,f'{defer} deferred',ha='center',va='center',fontsize=11)
 ax[0].text(good+bad/2,i-.30,f'{bad} wrong',ha='center',fontsize=10,color=RED)
 v=d['accepted_error']*100;lo,hi=np.array(d['accepted_error_ci95'])*100
 ax[1].errorbar(v,i,xerr=[[v-lo],[hi-v]],fmt='o',color=C[0],capsize=5);ax[1].text(hi+.2,i,f'{v:.1f}% ({lo:.1f}–{hi:.1f}%)',va='center',fontsize=11)
for a in ax:clean(a);a.set_yticks([0,1],['Jev / native','Gemini / probability']);a.invert_yaxis()
ax[0].set_xlim(0,500);ax[0].set_xlabel('Messages · blue: accepted/correct · red: accepted/wrong · gray: deferred')
ax[1].set_xlim(0,12);ax[1].axvline(5,color=RED,linestyle='--',alpha=.7);ax[1].set_xlabel('Errors among accepted answers (%) · lines: Wilson 95% intervals')
f.text(.045,.045,'Both intervals extend above the 5% target (dashed line). Neither rule establishes a risk guarantee.\nGPT-OSS and Mercury found no qualifying cutoff on calibration; this does not mean their scores cannot rank errors.',fontsize=10,linespacing=1.6)
save(f,'05-acceptance')
f,a=base('Could confidence distinguish mistakes?','Error-detection AUROC: 0.5 is chance; larger means better ranking.','Jev: native confidence. Others: verbalized correctness probability. Lines: bootstrap 95% intervals.\nValid scored responses only. Overlapping intervals do not support a unique Jev advantage.')
for i,k in enumerate(KEYS):
 d=M['stats'][k]['native_error_detection' if k=='jev' else 'probability_error_detection'];v=d['auroc'];lo,hi=d['auroc_ci95']
 a.errorbar(v,i,xerr=[[v-lo],[hi-v]],fmt='o',color=C[i],capsize=5,markersize=8);a.text(hi+.017,i,f'{v:.3f}',va='center')
a.axvline(.5,color='#968c7e',linestyle='--');a.set_xlim(0,1);a.set_xlabel('Error-detection AUROC (not classification accuracy)')
save(f,'06-confidence-ranking')
(OUT/'README.md').write_text('# Blog visual assets\n\nGenerated by `blog-study/blog_visuals.py` from the frozen `analysis/metrics.json`. PNG, editable SVG, and PDF versions are provided.\n\n00-cover is an editorial diagram, not quantitative evidence. 01-workflow depicts the actual study design. Figures 02–06 are calculated from recorded metrics. No new model calls.\n\nThe confidence rules have different score sources and realized error rates. Do not describe them as a matched-risk superiority comparison. Counts, confidence intervals, and failure denominators are retained in captions.\n')
print('Generated',len(list(OUT.glob('*.png'))),'figures in PNG/SVG/PDF:',OUT)
