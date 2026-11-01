"""Finite utility-plan driver; use one outer workload guard."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--source',required=True)
parser.add_argument('--doorplate',required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
out=args.out.resolve()
env={**os.environ,'PYTHONPATH':os.pathsep.join((str(root/'src'),str(root))),'PYTHONDONTWRITEBYTECODE':'1','RAYON_NUM_THREADS':'1'}
result=subprocess.run([sys.executable,'tools/prepare_utility_comparison.py','--source',args.source,'--doorplate',args.doorplate,'--out',str(out)],cwd=root,env=env)
if result.returncode:raise SystemExit(result.returncode)
receipts=[]
for plan in sorted(out.glob('*/plan.json')):
    result=subprocess.run([sys.executable,'-m','address_benchmark','run-plan',str(plan)],cwd=root,env=env)
    receipts.append(dict(plan=plan.parent.name,actual_exit_code=result.returncode))
    (out/'execution-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
    print(f'{plan.parent.name}: exit {result.returncode}',flush=True)
raise SystemExit(0 if all(x['actual_exit_code']==0 for x in receipts) else 2)
