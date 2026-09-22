"""Fresh-directory offline replay. Never invokes TypeScript or a network/API client."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def run(script, root, *args):
    environment=os.environ.copy()
    environment.pop('OPENROUTER_API_KEY',None)
    environment['PYTHONPATH']=str(root/'offline_guard')
    result=subprocess.run([sys.executable,str(root/script),*map(str,args)],capture_output=True,text=True,env=environment)
    if result.returncode:
        raise RuntimeError(f'{script} failed in offline replay:\n{result.stdout}\n{result.stderr}')
    return result.stdout


def main(source, refit):
    source=source.resolve()
    with tempfile.TemporaryDirectory(prefix='fresh-followup-offline-') as temporary:
        study=Path(temporary)/'blog-study'; root=study/'fresh-followup'
        shutil.copytree(source,root,ignore=shutil.ignore_patterns('analysis','supplement','data','__pycache__','runner.lock','*.tmp'))
        for name in ['train.csv','test.csv','categories.json','splits.json','data-manifest.json','LICENSE']:
            shutil.copy2(source.parent/name,study/name)
        (study/'run-v1').mkdir()
        shutil.copy2(source.parent/'run-v1/manifest.json',study/'run-v1/manifest.json')
        # This verifies an existing frozen selection. It does not enter the network sampling branch.
        run('prepare.py',root)
        run('verify_data.py',root)
        independent=json.loads(run('independent_audit.py',root))
        run('analyze.py',root,'--audit')
        run('uncertainty.py',root)
        run('cost_sensitivity.py',root)
        run('supplement_plots.py',root)
        (root/'data').mkdir()
        shutil.copy2(source/'data/README.md',root/'data/README.md')
        run('export.py',root)
        checked=[]
        for folder in ['analysis','supplement','data']:
            for regenerated in sorted((root/folder).glob('*')):
                if not regenerated.is_file():continue
                original=source/folder/regenerated.name
                if regenerated.read_bytes()!=original.read_bytes():
                    raise AssertionError('Offline byte mismatch: '+str(regenerated.relative_to(root)))
                checked.append(str(regenerated.relative_to(root)))
        refit_result=None
        if refit:
            originals={name:json.loads((root/f'local/{name}-predictions.json').read_text()) for name in ['calibration','banking','oos']}
            threshold=json.loads((root/'local/threshold.json').read_text())
            run('local_classifier.py',root)
            assert json.loads((root/'local/threshold.json').read_text())==threshold
            count=0;largest=0.
            for name,before in originals.items():
                after=json.loads((root/f'local/{name}-predictions.json').read_text())
                assert len(before)==len(after)
                for a,b in zip(before,after):
                    assert all(a[k]==b[k] for k in ['id','expected','predicted','correct','accepted','status'])
                    assert math.isclose(a['score'],b['score'],rel_tol=1e-9,abs_tol=1e-12)
                    largest=max(largest,abs(a['score']-b['score']));count+=1
            refit_result={'matched_predictions':count,'max_probability_absolute_difference':largest,'frozen_threshold_identical':True,'timings_compared':False}
        result={'offline_replay_passed':True,'fresh_temporary_directory':True,'network_calls':0,'network_guard':'Socket connections disabled in all replay subprocesses',
                'byte_identical_artifacts':checked,'independent_audit':independent,'local_refit':refit_result}
        print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument('--refit-local',action='store_true')
    args=ap.parse_args();main(args.root,args.refit_local)
