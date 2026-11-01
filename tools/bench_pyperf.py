"""Optional calibrated Python API experiment; preserves native pyperf JSON.

python tools/bench_pyperf.py --adapter demo --panel /absolute/inputs.jsonl --pins-directory /absolute/pins -o runs/pyperf.json
"""
from pathlib import Path
import sys

import pyperf

from address_benchmark.adapters import load_adapter
from address_benchmark.io import identity, read_json, read_jsonl, require, sha256, write_json
from address_benchmark.protocol import Request, check_prediction
from address_benchmark.worker import runtime_identity


def forward(cmd, args):
    cmd.extend(["--adapter", args.adapter, "--panel", args.panel])
    cmd.extend(["--pins-directory", args.pins_directory])
    if args.config:
        cmd.extend(["--config", args.config])


runner = pyperf.Runner(add_cmdline_args=forward)
runner.argparser.add_argument("--adapter", required=True)
runner.argparser.add_argument("--panel", required=True)
runner.argparser.add_argument("--config")
runner.argparser.add_argument("--pins-directory", required=True)
args = runner.parse_args()
require(Path(args.panel).is_absolute(), "use an absolute input-only panel path")
require(args.config is None or Path(args.config).is_absolute(), "use an absolute config path")
require(Path(args.pins_directory).is_absolute(), "use an absolute runtime pin output directory")
adapter = load_adapter(args.adapter, read_json(args.config) if args.config else {})
panel = [Request.from_dict(x) for x in read_jsonl(args.panel)]
require(panel, "empty panel")
for item in panel:
    require(check_prediction(adapter.parse(item), item, adapter.metadata)["status"] == "ok", "refused/error input invalidates timing")
pins = runtime_identity(adapter)
pin_id = identity(pins)
Path(args.pins_directory).mkdir(parents=True, exist_ok=True)
try:
    write_json(Path(args.pins_directory) / (pin_id + ".json"), pins)
except FileExistsError:
    require(read_json(Path(args.pins_directory) / (pin_id + ".json")) == pins, "runtime identity collision")


def parse_panel():
    # Full API allocation AND output destruction in this backend's callable.
    for item in panel:
        adapter.parse(item)


runner.bench_func("parse-panel", parse_panel, metadata={
    "panel_sha256": sha256(args.panel), "panel_rows": len(panel),
    "runtime_identity_sha256": pin_id,
    "scope": "parse + owned output allocation/destruction; excludes startup/load/JSON audit/validation",
    "adapter": args.adapter,
})
for item in panel:
    require(check_prediction(adapter.parse(item), item, adapter.metadata)["status"] == "ok", "postflight parser error/refusal")
if hasattr(adapter, "close"):
    adapter.close()
