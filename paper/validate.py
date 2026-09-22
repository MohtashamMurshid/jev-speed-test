"""Independent count/accounting checks plus compiled-paper QA. No API calls."""
from pathlib import Path
from decimal import Decimal
import csv,json,hashlib,subprocess,re
P=Path(__file__).parent;F=P.parent/'blog-study/fresh-followup'
a=list(csv.DictReader((F/'data/banking-results.csv').open()));o=list(csv.DictReader((F/'data/oos-results.csv').open()))
assert len(a)==500 and len(o)==100
counts={k:sum(r[k+'_correct']=='True' for r in a) for k in ['jev','gemini','cascade','local']}
assert counts=={'jev':399,'gemini':425,'cascade':424,'local':425}
assert sum(r['route']=='jev' for r in a)==170
assert sum(r['safety_accept']=='True' for r in a)==374
assert sum(r['safety_accept']=='True' and r['cascade_correct']=='False' for r in a)==23
for key,value in [('jev_accept',0),('gemini_baseline_accept',0),('safety_accept',0),('local_accepted',2)]:assert sum(r[key]=='True' for r in o)==value
cascade=sum(Decimal(r['cascade_billed_subtotal_usd']) for r in a)
baseline=sum(Decimal(r['baseline_billed_subtotal_usd']) for r in a)
saving=(1-cascade/baseline)*100
assert round(saving,2)==Decimal('23.27')
for name,digest in json.loads((P/'evidence-manifest.json').read_text())['inputs'].items():assert hashlib.sha256((P.parent/name).read_bytes()).hexdigest()==digest
info=subprocess.check_output(['pdfinfo',str(P/'jev-confidence-study.pdf')],text=True)
text=subprocess.check_output(['pdftotext','-layout',str(P/'jev-confidence-study.pdf'),'-'],text=True)
assert 'Pages:           5' in info
for token in ['424/500','425/500','399/500','23.27%','374','9742']:
 assert token in text.replace(',',''),token
assert '??' not in text
log=(P/'main.log').read_text()
assert 'Overfull' not in log and 'undefined' not in log and 'LaTeX Error' not in log
assert (P/'main.bbl').read_text().count('\\bibitem')==9
out={'paper_status':'Draft technical report, not peer reviewed or accepted by IEEE','pages':5,'independent_csv_counts':counts,'banking_rows':len(a),'oos_rows':len(o),'reported_charge_saving_zero_unknown_bill_percent':str(saving),'references':9,'undefined_references':0,'overfull_boxes':0,'input_hashes_verified':True,'pdf_sha256':hashlib.sha256((P/'jev-confidence-study.pdf').read_bytes()).hexdigest()}
(P/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
