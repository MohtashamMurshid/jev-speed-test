"""Separate reported charges from unknown-bill sensitivity, never call reserves invoices."""
import json
from pathlib import Path
import argparse


def main(root):
    rows=[json.loads(p.read_text()) for p in (root/'calls').glob('*.result.json')]
    bank=[r for r in rows if r['cohort']=='cases']
    groups={'cascade':[r for r in bank if r['path']=='cascade'],
            'gemini_baseline':[r for r in bank if r['path']=='baseline'],
            'jev_first_stage':[r for r in bank if r['system']=='jev']}
    result={}
    for name,group in groups.items():
        assert len({r['caseId'] for r in group})==500
        missing=[r for r in group if 'billedCostUsd' not in r]
        known=sum(r.get('billedCostUsd',0) for r in group)
        reserve=sum(r['reservedUsd'] for r in missing)
        result[name]={'cases':500,'calls':len(group),'reported_bills_usd':known,
                      'unknown_bill_calls':len(missing),'unknown_bill_reservations_usd':reserve,
                      'unknown_cases':[{'caseId':r['caseId'],'status':r['status'],'httpStatus':r.get('httpStatus'),'reservation_usd':r['reservedUsd']} for r in missing]}
    c,g=result['cascade'],result['gemini_baseline']
    low_g=g['reported_bills_usd'];high_c=c['reported_bills_usd']+c['unknown_bill_reservations_usd']
    high_g=g['reported_bills_usd']+g['unknown_bill_reservations_usd'];low_c=c['reported_bills_usd']
    result['sensitivity']={'lower_saving_percent':(low_g-high_c)/low_g*100 if low_g else None,
        'upper_saving_percent':(high_g-low_c)/high_g*100 if high_g else None,
        'definition':'Vary every missing bill from zero to its conservative reservation. For the lower saving, assign cascade missing bills their reserves and baseline missing bills zero; reverse for upper saving. These are scenarios, not known invoices or statistical confidence intervals.',
        'reported_only_difference_usd':g['reported_bills_usd']-c['reported_bills_usd']}
    output=root/'supplement/cost-sensitivity.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    main(ap.parse_args().root)
