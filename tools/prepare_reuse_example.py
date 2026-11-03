#!/usr/bin/env python3
"""Prepare two fresh plans over bundled fictional inputs; no execution or models."""
from pathlib import Path
import argparse
import shutil

from address_benchmark.io import write_json

ROOT = Path(__file__).resolve().parents[1]


def prepare(output):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    for name, engines in [('prior', [dict(name='demo', adapter='demo')]),
                          ('expanded', [dict(name='demo', adapter='demo'), dict(name='refusal', adapter='refusal')])]:
        directory = root / name
        directory.mkdir()
        shutil.copytree(ROOT / 'examples/corpora/us-core', directory / 'corpus')
        write_json(directory / 'engines.json', engines)
        write_json(directory / 'plan.json', dict(schema='address-benchmark.plan/v1', name='Synthetic reuse control',
            engines='engines.json', tracks=[dict(id='core', corpus='corpus/manifest.json', output='run')],
            execution=dict(timing=False, timeout=30)))
    return root


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    prepare(parser.parse_args().output)
    print('{"status":"prepared"}')
