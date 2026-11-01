"""Adapter process. This module receives ONLY input requests and configuration."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import itertools
from pathlib import Path
import sys
import time
import traceback

from .adapters import AdapterProtocolError, Unavailable, load_adapter
from .io import canonical, digest_bytes, loads, read_json, read_jsonl, require, sha256, write_json, write_jsonl
from .protocol import Request, check_prediction, prediction


def runtime_identity(adapter):
    """Hash imported modules plus installed distributions' code/model assets."""
    distributions = {}
    owners = importlib.metadata.packages_distributions()
    names = {name for module in sys.modules for name in owners.get(module.split(".")[0], [])}
    for name in sorted(names):
        dist = importlib.metadata.distribution(name)
        assets = {}
        for item in dist.files or []:
            path = Path(dist.locate_file(item)).resolve()
            if path.is_file() and path.suffix != ".pyc" and "__pycache__" not in path.parts:
                assets[str(item)] = sha256(path)
        distributions[name] = dict(version=dist.version, files=assets)
    extra = {}
    for name in adapter.metadata.get("artifact_files", []):
        path = Path(name).resolve()
        require(path.is_file(), f"adapter artifact unavailable: {path}")
        extra[str(path)] = sha256(path)
    # Distribution discovery can itself lazily import standard-library modules.
    # Snapshot after it, so the fingerprint does not change from bookkeeping.
    imported = {Path(m.__file__).resolve() for m in list(sys.modules.values())
                if getattr(m, "__file__", None) and Path(m.__file__).is_file()}
    files = {str(p): sha256(p) for p in sorted(imported) if p.suffix != ".pyc"}
    return dict(adapter=loads(canonical(adapter.metadata)), interpreter=dict(path=str(Path(sys.executable).resolve()), sha256=sha256(sys.executable)),
                imported_files=files, distributions=distributions, declared_artifacts=extra,
                coverage="imported files, installed distributions and declared assets; excludes OS/shared libraries not in distribution and undeclared remote services")


def invoke(adapter, request):
    try:
        result = adapter.parse(request)
    except AdapterProtocolError:
        raise
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        result = prediction(request, status="error", message=f"{type(exc).__name__}: {exc}", native={"exception": type(exc).__name__})
    return check_prediction(result, request, adapter.metadata)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--mode", choices=("accuracy", "timing"), required=True)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--min-seconds", type=float, default=.1)
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args(argv)
    adapter = None
    try:
        requests = [Request.from_dict(x) for x in read_jsonl(args.inputs)]
        require(requests, "empty input panel")
        require(args.samples > 0 and args.warmup >= 0 and args.min_seconds > 0, "invalid timing settings")
        started = time.perf_counter_ns()
        adapter = load_adapter(args.spec, read_json(args.config))
        load_ns = time.perf_counter_ns() - started
        initial = runtime_identity(adapter)
        if args.mode == "accuracy":
            if hasattr(adapter, "parse_many"):
                def outputs():
                    for request, result in itertools.zip_longest(requests, adapter.parse_many(requests, Path(args.output).parent)):
                        require(request is not None and result is not None, "batch prediction length differs")
                        yield check_prediction(result, request, adapter.metadata)
                write_jsonl(args.output, outputs())
            else:
                write_jsonl(args.output, (invoke(adapter, request) for request in requests))
            final = runtime_identity(adapter)
            require(initial["adapter"] == final["adapter"], "adapter metadata changed during inference")
            for group in ("imported_files", "distributions", "declared_artifacts"):
                require(all(final[group].get(key) == value for key, value in initial[group].items()), "runtime/model artifact changed during inference")
            write_json(args.identity, final)
            return 0
        for _ in range(args.warmup):
            for request in requests:
                require(invoke(adapter, request)["status"] == "ok", "warmup includes parser error/refusal; timing invalid")
        pins = runtime_identity(adapter)
        write_json(args.identity, pins)
        samples, checksum = [], ""
        for sample in range(args.samples):
            duration_ns, batches = 0, 0
            while duration_ns < args.min_seconds * 1e9:
                start = time.perf_counter_ns()
                outputs = [adapter.parse(request) for request in requests]
                elapsed = time.perf_counter_ns() - start
                # Validation, checksums, and serialization are outside timing.
                for request, output in zip(requests, outputs):
                    check_prediction(output, request, adapter.metadata)
                    require(output["status"] == "ok", "timed parser error/refusal; timing invalid")
                checksum = digest_bytes(canonical(outputs))
                duration_ns += elapsed
                batches += 1
                # Explicit destruction outside timer; allocation remains included.
                del outputs
            count = batches * len(requests)
            samples.append(dict(sample=sample, elapsed_ns=duration_ns, operations=count,
                                batches=batches, ns_per_address=duration_ns / count,
                                addresses_per_second=count * 1e9 / duration_ns))
        require(runtime_identity(adapter) == pins, "runtime changed or lazy assets loaded inside timing; warm up/preload explicitly")
        write_json(args.output, dict(schema="address-benchmark.timing/v1", samples=samples,
                                    adapter_load_ns=load_ns, consumed_sha256=checksum,
                                    panel_sha256=sha256(args.inputs), scope="in-process full-panel parse + public owned output allocation; excludes destruction, contract checks, checksums, I/O, serialization, startup/model load",
                                    backend="stdlib exploratory; not calibrated pyperf", warmup_panels=args.warmup))
        return 0
    except Unavailable as exc:
        print(f"unavailable: {exc}", file=sys.stderr)
        return 69
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1
    finally:
        if adapter is not None and hasattr(adapter, "close"):
            try:
                adapter.close()
            except Exception:
                traceback.print_exc(file=sys.stderr)
                return 1


if __name__ == "__main__":
    raise SystemExit(main())
