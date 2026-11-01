"""Write a relocatable-by-regeneration command-adapter example (no shell)."""
import argparse
from pathlib import Path
import sys

from address_benchmark.adapters import DemoParser
from address_benchmark.io import write_json

parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True)
args = parser.parse_args()
script = Path(__file__).resolve().parents[1] / "examples/adapters/jsonl_demo.py"
write_json(args.out, [dict(name="wire-demo", adapter="command", config=dict(command=[sys.executable, str(script)], metadata=DemoParser({}).metadata))])
