"""Finite guarded driver: contracts, fresh preparation, full JSON plan, receipts."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import hashlib

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--doorplate", required=True)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--utilities", action="store_true")
parser.add_argument("--report-out", type=Path)
args = parser.parse_args()
out = args.out.resolve()
frozen = out.with_name(out.name + "-framework")
frozen.mkdir(parents=True)
for folder, target in ((root/'src/address_benchmark',frozen/'address_benchmark'),(root/'adapters',frozen/'adapters'),(root/'tools',frozen/'tools'),(root/'examples',frozen/'examples')):
    shutil.copytree(folder,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
pins={str(path.relative_to(frozen)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(frozen.rglob('*')) if path.is_file()}
(frozen/'framework-source.json').write_text(json.dumps(dict(schema='address-benchmark.framework-snapshot/v1',files=pins),indent=2)+'\n')
env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(frozen),str(root))), "PYTHONDONTWRITEBYTECODE": "1",
       **dict.fromkeys(("GOMAXPROCS", "RAYON_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "POLARS_MAX_THREADS"), "1")}
receipts = []
commands = [
    ("contracts", [sys.executable, "-m", "unittest", "discover", "-s", str(root/'tests'), "-t", str(root), "-q"]),
    ("prepare", [sys.executable, str(frozen/'tools/prepare_local_matrix.py'), "--source", args.source, "--doorplate", args.doorplate, "--out", str(out)]),
    ("run-plan", [sys.executable, "-m", "address_benchmark", "run-plan", str(out / "plan.json")]),
]
if args.report_out:
    commands.append(('report',[sys.executable,str(frozen/'tools/report_comparison.py'),str(out/'plan.json'),'--out',str(args.report_out.resolve())]))
if args.utilities:
    commands.append(('utilities',[sys.executable,str(frozen/'tools/execute_utility_comparison.py'),'--source',args.source,'--doorplate',args.doorplate,'--out',str(out/'utilities')]))
    if args.report_out:
        commands.append(('utility-report',[sys.executable,str(frozen/'tools/report_utilities.py'),str(out/'utilities'),'--out',str(args.report_out.resolve())]))
for name, command in commands:
    print(name + ": starting", flush=True)
    result = subprocess.run(command, cwd=frozen, env=env)
    receipts.append(dict(stage=name, command=command, exit_code=result.returncode))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
    print(f"{name}: exit {result.returncode}", flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
