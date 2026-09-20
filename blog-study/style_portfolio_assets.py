"""Apply paper texture to already-plotted figures without changing geometry/data.
Usage: python style_portfolio_assets.py --portfolio /path/to/portfoliowithm --cover /path/to/generated-cover.png
Requires Pillow and NumPy. Source figures live alongside this script in run-v1/analysis.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from PIL import Image,ImageOps
p=argparse.ArgumentParser();p.add_argument('--portfolio',type=Path,required=True);p.add_argument('--cover',type=Path,required=True);args=p.parse_args()
root=Path(__file__).parent/'run-v1/analysis';out=args.portfolio/'public/blog/jev-vs-a-fast-llm';out.mkdir(parents=True,exist_ok=True)
cover=Image.open(args.cover).convert('RGB');print('Original cover:',cover.size)
cover=ImageOps.fit(cover,(1910,820),method=Image.Resampling.LANCZOS);cover.save(out/'cover.webp',quality=94,method=6)
manifest={'cover':'AI-generated conceptual paper-and-pencil illustration; not a plot or measured result.','figures':{}}
for src in list((root/'blog-assets').glob('*.png'))+[root/'03-jev-confidence.png']:
 if src.name.startswith('00-'):continue
 im=Image.open(src).convert('RGB');a=np.asarray(im,dtype=np.float32);bg=a[0,0,:];mask=np.clip(1-np.max(np.abs(a-bg),axis=2)/6,0,1)[...,None]
 rng=np.random.default_rng(60421);grain=rng.normal(0,1.4,a.shape[:2])[...,None]
 # A restrained paper background. Data marks/text/axes remain unwarped.
 paper=np.clip(np.array([245,239,222],dtype=np.float32)+grain,0,255)
 styled=np.clip(a*(1-mask)+paper*mask,0,255).astype(np.uint8)
 dest=out/(src.stem+'.webp');Image.fromarray(styled).save(dest,quality=95,method=6)
 manifest['figures'][dest.name]={'source':str(src.relative_to(root)),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'geometry':'unchanged','treatment':'background-only seeded paper grain; no synthetic data marks'}
(out/'provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Wrote',len(list(out.glob('*.webp'))),'portfolio images; bytes',sum(f.stat().st_size for f in out.glob('*.webp')))
