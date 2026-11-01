"""Local finite release check. Run this outer command through the host guard.

Optional wheels are installed only inside work/release-check/venv. Every child
exit is retained; no parent repository/runtime/model is built or changed.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--optional", action="store_true")
parser.add_argument("--out", default="work/release-check")
args = parser.parse_args()
out = (ROOT / args.out).resolve()
out.mkdir(parents=True)
env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
receipts = []


def call(command, *, expected=0, name):
    with (out / (name + ".log")).open("w") as log:
        result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    receipts.append(dict(name=name, command=list(map(str, command)), exit_code=result.returncode, expected_exit=expected))
    (out / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
    print(f"{name}: exit {result.returncode}", flush=True)
    if result.returncode != expected:
        print((out / (name + ".log")).read_text())
        raise SystemExit(1)


call([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], name="contracts")
call([sys.executable, "-m", "address_benchmark", "audit", *sorted((ROOT / "examples/corpora").glob("*/manifest.json"))], name="overlap")
call([sys.executable, "-m", "address_benchmark", "run", "examples/corpora/us-core/manifest.json", "--engines", "examples/adapters/timing.json", "--out", out / "timing", "--timing", "--trials", "4", "--samples", "3", "--min-seconds", ".01"], name="paired-timing")
call([sys.executable, "-m", "address_benchmark", "verify", out / "timing"], name="verify-timing")
if args.optional:
    venv.create(out / "venv", with_pip=True)
    python = out / "venv/bin/python"
    call([python, "-m", "pip", "install", ".[timing,usaddress]"], name="install-optional")
    call([python, "-m", "address_benchmark", "run", "examples/corpora/us-challenge/manifest.json", "--engines", "examples/adapters/usaddress.json", "--out", out / "usaddress"], name="optional-usaddress")
    call([python, "-m", "address_benchmark", "verify", out / "usaddress"], name="verify-usaddress")
    call([python, "-m", "address_benchmark", "export-inputs", "examples/corpora/us-core/manifest.json", "--out", out / "panel.jsonl"], name="export-panel")
    call([python, "tools/bench_pyperf.py", "--adapter", "demo", "--panel", out / "panel.jsonl", "--pins-directory", out / "pyperf-pins", "--processes", "2", "--values", "2", "--warmups", "1", "--loops", "1", "-o", out / "pyperf.json"], name="pyperf-smoke")
    call([python, "-m", "pip", "freeze", "--all"], name="optional-lock")
print(f"Release checks completed; receipts: {out / 'receipts.json'}")
