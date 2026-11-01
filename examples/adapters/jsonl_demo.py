"""Authored executable wire example, not a third-party engine wrapper."""
import sys

from address_benchmark.adapters import DemoParser
from address_benchmark.io import canonical, loads
from address_benchmark.protocol import Request

adapter = DemoParser({})
for line in sys.stdin.buffer:
    request = Request.from_dict(loads(line.decode("utf-8")))
    sys.stdout.buffer.write(canonical(adapter.parse(request)) + b"\n")
    sys.stdout.buffer.flush()
