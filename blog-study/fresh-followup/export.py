"""Build deterministic convenient exports from completed immutable records."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import argparse


def export(root, out):
    out.mkdir(parents=True, exist_ok=True)
    cases = json.loads((root/'cases.json').read_text()) + json.loads((root/'oos.json').read_text())
    by_id = {c['id']: c for c in cases}
    calls = [json.loads(f.read_text()) for f in (root/'calls').glob('*.result.json')]
    calls.sort(key=lambda x:x['sequence'])
    by_key = {r['key']:r for r in calls}
    paths = [json.loads(f.read_text()) for f in (root/'paths').glob('*.result.json')]
    assert len(paths)==1200
    manifest = json.loads((root/'manifest.json').read_text())
    response_bytes = b''.join((json.dumps(dict(r, text=by_id[r['caseId']]['text'],
        sourceCategory=by_id[r['caseId']].get('sourceCategory'), contractHash=manifest['contractHash']),
        ensure_ascii=False, sort_keys=True, separators=(',',':'))+'\n').encode() for r in calls)
    (out/'responses.jsonl.gz').write_bytes(gzip.compress(response_bytes,mtime=0))
    path_bytes = b''.join((json.dumps(r,sort_keys=True,separators=(',',':'))+'\n').encode() for r in sorted(paths,key=lambda r:(r['cohort'],r['caseId'],r['path'])))
    (out/'paths.jsonl.gz').write_bytes(gzip.compress(path_bytes,mtime=0))
    wide = list(csv.DictReader((root/'analysis/case-results.csv').open()))
    path_by_id = {(r['caseId'],r['path']):r for r in paths}
    local = {r['id']:r for name in ['banking','oos'] for r in json.loads((root/f'local/{name}-predictions.json').read_text())}
    for row in wide:
        item = by_id[row['caseId']]
        row['text'] = item['text']
        row['sourceCategory'] = item.get('sourceCategory','')
        row['dataset'] = item['dataset']
        row['frozen_path_order'] = ','.join(item['pathOrder'])
        row['local_accepted'] = local[row['caseId']]['accepted']
        row['local_score'] = local[row['caseId']]['score']
        for path in ['cascade','baseline']:
            p = path_by_id[row['caseId'],path]
            physical = [by_key[k] for k in p['components']]
            row[path+'_accounted_usd'] = p['accountedUsd']
            row[path+'_billed_subtotal_usd'] = sum(r.get('billedCostUsd',0) for r in physical)
            row[path+'_unknown_bill_calls'] = sum('billedCostUsd' not in r for r in physical)
    for cohort,name in [('banking','banking-results.csv'),('oos','oos-results.csv')]:
        chosen = [r for r in wide if r['cohort']==cohort]
        with (out/name).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=sorted(wide[0]),lineterminator='\n')
            writer.writeheader();writer.writerows(chosen)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name!='sha256.json'}
    (out/'sha256.json').write_text(json.dumps(hashes,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'physical_calls':len(calls),'paths':len(paths),'banking_cases':sum(c['dataset']=='banking77' for c in cases),'oos_cases':sum(c['dataset']=='clinc150' for c in cases),'output':str(out)}))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument('--out',type=Path)
    args=ap.parse_args();export(args.root,args.out or args.root/'data')
