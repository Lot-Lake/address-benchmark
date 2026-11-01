from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

from .adapters import load_adapter
from .corpus import audit_corpora, fetch, input_requests, load_corpus
from .io import read_json, read_jsonl, require, write_jsonl
from .protocol import check_prediction
from .runner import run, verify


def main(argv=None):
    parser = argparse.ArgumentParser(description="Independent address parser evaluation; no bundled external corpora or models")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate pinned corpus and inspect annotation coverage")
    validate.add_argument("corpus")
    audit = commands.add_parser("audit", help="audit exact/family overlap across corpus manifests")
    audit.add_argument("corpora", nargs="+")
    download = commands.add_parser("fetch", help="explicitly download hash-pinned HTTPS corpus resources")
    download.add_argument("corpus")
    export = commands.add_parser("export-inputs", help="export ONLY input requests for timing/native adapters")
    export.add_argument("corpus")
    export.add_argument("--out", required=True)
    conform = commands.add_parser("conform", help="validate an adapter on authored input-only contract probes")
    conform.add_argument("adapter")
    conform.add_argument("--config")
    execute = commands.add_parser("run", help="fresh auditable accuracy run with optional paired exploratory timing")
    execute.add_argument("corpus")
    execute.add_argument("--engines", required=True)
    execute.add_argument("--out", required=True)
    execute.add_argument("--timing", action="store_true")
    execute.add_argument("--trials", type=int, default=4)
    execute.add_argument("--samples", type=int, default=5)
    execute.add_argument("--min-seconds", type=float, default=.1)
    execute.add_argument("--warmup", type=int, default=1)
    execute.add_argument("--timeout", type=float, default=120)
    execute.add_argument("--seed", type=int, default=20261101)
    execute.add_argument("--baseline")
    planned = commands.add_parser("run-plan", help="run and verify a versioned declarative JSON experiment plan")
    planned.add_argument("plan")
    for command in (execute, planned):
        command.add_argument('--json', action='store_true', help='emit the original machine-readable run/plan result instead of a console table')
    from .tables import FORMATS, METRICS
    report = commands.add_parser('report', help='export clean score tables from a recorded run or executed plan; no engines rerun')
    report.add_argument('source', help='run/plan JSON file or result directory')
    report.add_argument('--format', choices=FORMATS, default='console')
    report.add_argument('--metric', choices=METRICS, default='strict')
    report.add_argument('--subsets', nargs='+', default=[], help='include named views, e.g. natural hard hand')
    report.add_argument('--counts', action='store_true', help='include correct/denominator or TP/FP/FN in text tables')
    report.add_argument('--width', type=int, default=None, help='console width; wide tables split into column groups')
    report.add_argument('--color', choices=('auto', 'always', 'never'), default='auto')
    report.add_argument('--ascii', action='store_true', help='use ASCII console separators')
    report.add_argument('--title', default='Address benchmark')
    report.add_argument('--out', help='write a fresh export file instead of stdout')
    check = commands.add_parser("verify", help="rehash frozen artifacts and rescore accuracy with original source")
    check.add_argument("run")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            result = run(args.corpus, args.engines, args.out, timing=args.timing, trials=args.trials,
                         samples=args.samples, min_seconds=args.min_seconds, warmup=args.warmup, timeout=args.timeout, seed=args.seed, baseline=args.baseline)
            if args.json:
                print(json.dumps(dict(status=result["status"], content_id=result["content_id"], report=str(Path(args.out).resolve() / "report.md"))))
            else:
                from .tables import load_scorecard, render_console
                print(render_console(load_scorecard(args.out), terminal_width=max(40, shutil.get_terminal_size((120, 24)).columns), color=sys.stdout.isatty() and 'NO_COLOR' not in os.environ and os.environ.get('TERM') != 'dumb'), end='')
            return 0 if result["status"] == "complete" else 2
        if args.command == "run-plan":
            from .plan import run_plan
            result = run_plan(args.plan)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                from .tables import load_scorecard, render_console
                print(render_console(load_scorecard(args.plan), terminal_width=max(40, shutil.get_terminal_size((120, 24)).columns), color=sys.stdout.isatty() and 'NO_COLOR' not in os.environ and os.environ.get('TERM') != 'dumb'), end='')
            return 0 if result["status"] == "complete" else 2
        if args.command == 'report':
            from .tables import load_scorecard, render
            card = load_scorecard(args.source, metric=args.metric, subsets=args.subsets, title=args.title)
            use_color = args.color == 'always' or (args.color == 'auto' and sys.stdout.isatty() and not args.out and 'NO_COLOR' not in os.environ and os.environ.get('TERM') != 'dumb')
            output = render(card, args.format, counts=args.counts, terminal_width=args.width if args.width is not None else max(40, shutil.get_terminal_size((120, 24)).columns), color=use_color, ascii=args.ascii)
            if args.out:
                with Path(args.out).open('x', encoding='utf-8', newline='') as stream:
                    stream.write(output)
            else:
                print(output, end='')
            return 0
        if args.command == "validate":
            manifest, rows, result = load_corpus(args.corpus)
            from collections import Counter
            result["coverage"] = dict(Counter(row["reference"]["coverage"] for row in rows))
            result["corpus"] = manifest["id"]
        elif args.command == "audit":
            corpora = []
            for path in args.corpora:
                manifest, rows, _ = load_corpus(path)
                corpora.append((manifest["id"], rows))
            result = audit_corpora(corpora)
        elif args.command == "fetch":
            result = dict(installed=fetch(args.corpus))
        elif args.command == "verify":
            result = verify(args.run)
        elif args.command == "export-inputs":
            manifest, rows, _ = load_corpus(args.corpus)
            write_jsonl(args.out, (x.to_dict() for x in input_requests(manifest, rows)))
            result = dict(output=args.out, rows=len(rows))
        else:
            from .conformance import conform_adapter
            result = conform_adapter(args.adapter, read_json(args.config) if args.config else {})
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        print(f"address-benchmark: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
