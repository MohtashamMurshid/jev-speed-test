"""Build a public evidence archive from explicit allowlists; never include .env."""
from pathlib import Path
import json, zipfile, re, hashlib
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
RUN=ROOT/'run-v1'
OUT=RUN/'analysis'
rows=[json.loads(p.read_text()) for p in (RUN/'calls').glob('*.result.json')]
assert len(rows)==3200, f'Refusing incomplete package: {len(rows)} attempts'
for model in ['jev','gpt-oss','mercury','gemini']:
 assert sum(r['system']==model for r in rows)==800
files=[]
for name in ['blog-study.ts','blog-study.test.ts','package.json','package-lock.json','tsconfig.json']:
 files.append((PROJECT/name,Path('source')/name))
for name in ['README.md','analysis-requirements.txt','PROTOCOL.md','ANALYSIS-AUDIT.md','analyze-before-presentation-audit.py','data-manifest.json','build_blog_preview.py','enrich_blog.py','blog_visuals.py','process-walkthrough.html','methods-walkthrough.html','test_analysis.py','splits.json','categories.json','train.csv','test.csv','LICENSE','analyze.py','package_evidence.py']:
 files.append((ROOT/name,Path('study')/name))
for p in RUN.glob('*.json'):files.append((p,Path('run')/p.name))
for p in (RUN/'calls').glob('*.json'):files.append((p,Path('run/calls')/p.name))
for p in OUT.rglob("*"):
 if p.suffix in ['.json','.md','.png','.pdf','.svg','.csv']:files.append((p,Path('analysis')/p.relative_to(OUT)))
manifest={}
with zipfile.ZipFile(OUT/'banking77-fast-model-evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
 for path,dest in files:
  data=path.read_bytes()
  assert path.name!='.env'
  assert not re.search(rb'sk-or-v1-[A-Za-z0-9_-]{32,}',data), f'Potential credential in {path.name}'
  z.writestr(str(dest),data);manifest[str(dest)]=hashlib.sha256(data).hexdigest()
 z.writestr('SHA256.json',json.dumps(manifest,indent=2))
 z.writestr('START-HERE.md','''# Evidence bundle\n\nThis is the recorded English BANKING77 blog follow-up, not a paper or a production-risk certification. No credentials are included.\n\nRead `analysis/summary.md`, `study/PROTOCOL.md`, and `study/README.md`. Source dataset attribution and license are in `study/`. Every included file is hashed in `SHA256.json`. The requested model/provider configuration and development-only repairs are recorded in run manifests.\n\nFor replay without paid inference: put `study/` next to `source/` or adjust the analysis root, copy `run/` into `study/run-v1/`, install NumPy and Matplotlib, and run `python study/analyze.py`. It consumes stored model outputs and does not call APIs.\n\nFor paid reproduction: place the files in `source/` at a project root and rename `study/` to `blog-study/`. Run `npm ci`, review `blog-study/README.md`, and create a separate explicitly budgeted run. Never remove old recorded outcomes to quietly rerun mistakes.\n''')
print('Packaged files',len(files),'Bytes',(OUT/'banking77-fast-model-evidence.zip').stat().st_size)
