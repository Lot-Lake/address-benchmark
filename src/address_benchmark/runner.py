"""Immutable run artifacts and balanced independent-process comparison trials."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import itertools
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

from .corpus import input_requests, load_corpus, reference_comparability
from .io import identity, read_json, read_jsonl, require, sha256, within, write_json, write_jsonl
from .protocol import check_metadata, check_prediction
from .scoring import DELIMITER_POLICY, NORMALIZATION, SCORER, score_case, summarize_views

RUN = "address-benchmark.run/v1"


def source_pins():
    root = Path(__file__).parent
    return {p.name: sha256(p) for p in sorted(root.glob("*.py"))}


def host_identity():
    info = dict(platform=platform.platform(), machine=platform.machine(), processor=platform.processor(),
                python=sys.version, python_compiler=platform.python_compiler(), logical_cpus=os.cpu_count(),
                affinity="not enforced", clock=time.get_clock_info("perf_counter").__dict__)
    if sys.platform == "darwin":
        try:
            values = subprocess.check_output(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string", "hw.physicalcpu", "hw.memsize"], text=True, timeout=5).splitlines()
            if len(values) == 3:
                info.update(cpu_model=values[0], physical_cpus=int(values[1]), memory_bytes=int(values[2]))
        except (OSError, subprocess.SubprocessError, ValueError):
            info["hardware_detail"] = "unavailable; supply explicit hardware supplement"
    elif Path("/proc/cpuinfo").exists():
        model = next((line.partition(":")[2].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")), None)
        info["cpu_model"] = model
        info["memory_bytes"] = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    return info


def launch(command, directory, timeout):
    log = directory / "stderr.log"
    stdout = directory / "stdout.log"
    started = time.monotonic_ns()
    code, status, process = None, "launch-failed", None
    # Set deterministic Python hashing; preserve declared library thread settings.
    env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    with stdout.open("xb") as out, log.open("xb") as err:
        try:
            process = subprocess.Popen(command, stdout=out, stderr=err, env=env, start_new_session=True)
            try:
                code = process.wait(timeout=timeout)
                status = "ok" if code == 0 else "unavailable" if code == 69 else "failed"
            except subprocess.TimeoutExpired:
                # Own process group only; retain actual termination exit code.
                import signal
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    code = process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    code = process.wait()
                status = "timeout"
        except OSError as exc:
            err.write(str(exc).encode("utf-8"))
        except BaseException:
            # The outer workload guard cannot reach our separate worker session.
            # Clean up this owned group on cancellation before propagating it.
            if process is not None and process.poll() is None:
                import signal
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    code = process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    code = process.wait()
                write_json(directory / "interrupted-execution.json", dict(command=command, status="interrupted", exit_code=code))
            raise
    return dict(command=command, status=status, exit_code=code,
                process_wall_ns=time.monotonic_ns() - started,
                environment={k: env.get(k) for k in ("PYTHONHASHSEED", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "POLARS_MAX_THREADS", "RAYON_NUM_THREADS")})


def execute(engine, mode, inputs, directory, *, samples, min_seconds, warmup, timeout):
    directory.mkdir()
    write_json(directory / "config.json", engine.get("config", {}))
    output = directory / ("predictions.jsonl" if mode == "accuracy" else "timing.json")
    command = [engine.get("python", sys.executable), "-m", "address_benchmark.worker", "--spec", engine["adapter"],
               "--config", str(directory / "config.json"), "--inputs", str(inputs), "--output", str(output),
               "--identity", str(directory / "identity.json"), "--mode", mode,
               "--samples", str(samples), "--min-seconds", str(min_seconds), "--warmup", str(warmup)]
    record = launch(command, directory, timeout)
    if record["status"] == "ok":
        try:
            require(output.is_file() and (directory / "identity.json").is_file(), "worker output missing")
            pins = read_json(directory / "identity.json")
            check_metadata(pins["adapter"])
            record["identity_sha256"] = identity(pins)
            record["output"] = str(output.name)
            record["identity"] = pins
        except (ValueError, OSError) as exc:
            record.update(status="invalid", validation_error=str(exc))
    return record


def validate_predictions(rows, requests, predictions, metadata, profiles=()):
    require(len(predictions) == len(rows), "prediction stream length differs")
    require(len(requests) == len(rows), "input stream length differs")
    cases = []
    for row, request, pred in zip(rows, requests, predictions):
        check_prediction(pred, request, metadata)
        cases.append(score_case(row, pred, metadata, profiles))
    return cases


def percentile(values, p):
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    a, b = math.floor(index), math.ceil(index)
    return ordered[a] + (ordered[b] - ordered[a]) * (index - a)


def paired_summary(trials, names, *, seed):
    result = {}
    for left, right in itertools.combinations(names, 2):
        ratios = []
        for trial in trials:
            cells = trial["engines"]
            if all(cells[name]["status"] == "ok" for name in (left, right)):
                a, b = cells[left]["median_ns_per_address"], cells[right]["median_ns_per_address"]
                ratios.append(b / a)  # left / right throughput
        entry = dict(pairs=len(ratios), expected_pairs=len(trials), ratios=ratios,
                     status="measured" if len(ratios) == len(trials) and ratios else "incomplete",
                     interpretation=f"{left}/{right} throughput; >1 favors {left}", median_ratio=None,
                     bootstrap_95_interval=None)
        if ratios and len(ratios) == len(trials):
            entry["median_ratio"] = statistics.median(ratios)
            if len(ratios) >= 4:
                rng = random.Random(seed)
                boot = [statistics.median(rng.choices(ratios, k=len(ratios))) for _ in range(2000)]
                entry["bootstrap_95_interval"] = [percentile(boot, .025), percentile(boot, .975)]
        result[f"{left}/{right}"] = entry
    return result


def run(corpus, engines_path, output, *, timing=False, trials=4, samples=5, min_seconds=.1, warmup=1, timeout=120, seed=20261101, baseline=None):
    manifest, rows, audit = load_corpus(corpus)
    engines = read_json(engines_path)
    require(isinstance(engines, list) and engines, "nonempty engine list required")
    names = [engine.get("name") for engine in engines]
    require(all(isinstance(name, str) and name and name.replace("-", "").replace("_", "").isalnum() and name.isascii()
                for name in names) and len(set(names)) == len(names), "unique safe engine names required")
    require(all(isinstance(e.get("adapter"), str) and isinstance(e.get("config", {}), dict) for e in engines), "adapter/config required")
    require(baseline is None or baseline in names, "comparison baseline must be a selected engine")
    require(trials >= 2 and trials % 2 == 0 and samples > 0 and min_seconds > 0 and warmup >= 0 and timeout > 0,
            "use an even number of >=2 trials, positive samples/duration/timeout and nonnegative warmup")
    out = Path(output).resolve()
    require(not out.exists(), "fresh output directory required")
    out.mkdir(parents=True)
    requests = input_requests(manifest, rows)
    write_jsonl(out / "inputs.jsonl", (x.to_dict() for x in requests))
    write_jsonl(out / "references.jsonl", rows)
    write_json(out / "corpus.json", manifest)
    write_json(out / "engines.json", engines)
    write_json(out / "overlap.json", audit)
    # Immutable run records contain sensitive inputs when the corpus is private.
    report = dict(schema=RUN, created_at=datetime.now(timezone.utc).isoformat(), status="running",
                  task=manifest["task"], corpus=dict(id=manifest["id"], manifest_sha256=sha256(corpus), resources=manifest["resources"], exposure=manifest["exposure"]),
                  scorer=SCORER, normalization=NORMALIZATION, secondary_normalization=DELIMITER_POLICY, source_pins=source_pins(),
                  input_sha256=sha256(out / "inputs.jsonl"), engine_config_sha256=sha256(engines_path),
                  host=host_identity(),
                  settings=dict(timing=timing, trials=trials, samples=samples, min_seconds=min_seconds, warmup=warmup, timeout=timeout, seed=seed,
                                concurrency="one engine process at a time; one caller; runtime helper threads as declared"),
                  accuracy={}, trials=[], paired={}, deltas={},
                  reference_comparability=reference_comparability(rows) if manifest["task"] == "parse" else None,
                  limitations=["No unseen-training claim; exposure is corpus-declared, not independently verified.",
                               "Exact/family audit cannot detect undeclared or fuzzy overlap.",
                               "Subset views overlap; origin/split populations are separate and must not be summed.",
                               "Timing is exploratory on this host; output destruction/checksums/serialization/startup excluded.",
                               "Conditional bootstrap assumes independent paired trials; shared-host autocorrelation/thermal load remain.",
                               "No latency percentiles, memory, batch/streaming or startup-isolation benchmark is implemented."])
    write_json(out / "started.json", {k: v for k, v in report.items() if k not in ("accuracy", "trials", "paired", "deltas")})
    all_cases = {}
    for engine in engines:
        name = engine["name"]
        directory = out / (name + "-accuracy")
        entry = execute(engine, "accuracy", out / "inputs.jsonl", directory, samples=samples,
                        min_seconds=min_seconds, warmup=warmup, timeout=timeout)
        if entry["status"] == "ok":
            try:
                predictions = list(read_jsonl(directory / "predictions.jsonl"))
                require(entry["identity"]["adapter"]["ontology"] == manifest["ontology"], "adapter/corpus ontology differs")
                cases = validate_predictions(rows, requests, predictions, entry["identity"]["adapter"], manifest.get("scoring_profiles", ()))
                write_jsonl(directory / "cases.jsonl", cases)
                all_cases[name] = directory / "cases.jsonl"
                entry["populations"] = summarize_views(cases)
                del cases, predictions
            except (ValueError, OSError, KeyError, TypeError) as exc:
                entry.update(status="invalid", validation_error=str(exc))
        write_json(directory / "execution.json", entry)
        report["accuracy"][name] = entry
    for left, right in itertools.combinations(all_cases, 2):
        if baseline is not None and baseline not in (left, right):
            continue
        file = f"delta-{left}-{right}.jsonl"
        counts = dict(left_only=0, right_only=0)
        def deltas():
            for a, b in itertools.zip_longest(read_jsonl(all_cases[left]), read_jsonl(all_cases[right])):
                require(a is not None and b is not None and a["id"] == b["id"], "comparative case streams differ")
                counts["left_only"] += a["primary_agrees"] is True and b["primary_agrees"] is False
                counts["right_only"] += b["primary_agrees"] is True and a["primary_agrees"] is False
                yield dict(id=a["id"], family=a["family"], coverage=a["coverage"],
                           left_agrees=a["primary_agrees"], right_agrees=b["primary_agrees"],
                           left_mismatched_roles=a.get("mismatched_roles"), right_mismatched_roles=b.get("mismatched_roles"))
        write_jsonl(out / file, deltas())
        report["deltas"][f"{left}/{right}"] = dict(artifact=file, **counts)
    if timing:
        # Freeze the entire corpus as one identical panel; no gold-conditioned filter.
        panel = list(requests)
        random.Random(seed).shuffle(panel)
        write_jsonl(out / "panel.jsonl", (x.to_dict() for x in panel))
        rng = random.Random(seed)
        for number in range(trials):
            if number % 2 == 0:
                order = list(engines)
                rng.shuffle(order)
            else:
                order.reverse()
            trial = dict(trial=number, order=[e["name"] for e in order], engines={})
            for engine in order:
                name = engine["name"]
                directory = out / f"trial-{number:03d}-{name}"
                entry = execute(engine, "timing", out / "panel.jsonl", directory, samples=samples,
                                min_seconds=min_seconds, warmup=warmup, timeout=timeout)
                if entry["status"] == "ok":
                    if entry["identity_sha256"] != report["accuracy"][name].get("identity_sha256"):
                        entry.update(status="invalid", validation_error="runtime identity differs from accuracy cell")
                    else:
                        measurements = read_json(directory / "timing.json")
                        require(measurements["panel_sha256"] == sha256(out / "panel.jsonl"), "timing panel hash differs")
                        values = [x["ns_per_address"] for x in measurements["samples"]]
                        entry["median_ns_per_address"] = statistics.median(values)
                        entry["sample_spread_fraction"] = (max(values) - min(values)) / statistics.median(values)
                        entry["noisy_over_10_percent"] = entry["sample_spread_fraction"] > .1
                write_json(directory / "execution.json", entry)
                trial["engines"][name] = entry
            report["trials"].append(trial)
        report["paired"] = paired_summary(report["trials"], names, seed=seed)
    require(report["source_pins"] == source_pins(), "benchmark source changed during run; artifacts incomplete")
    require(sha256(corpus) == report["corpus"]["manifest_sha256"] and sha256(engines_path) == report["engine_config_sha256"], "run configuration changed during execution")
    cells = list(report["accuracy"].values()) + [e for trial in report["trials"] for e in trial["engines"].values()]
    report["status"] = "complete" if all(e["status"] == "ok" for e in cells) else "incomplete"
    from .report import render
    (out / "report.md").write_text(render(report), encoding="utf-8")
    from .tables import scorecard, export_scorecard
    export_scorecard(scorecard([(manifest['id'], report)], engines=names), out)
    # Hash every artifact except the envelope itself; its identity is external.
    report["artifacts"] = {str(p.relative_to(out)): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}
    report["content_id"] = identity(report)
    write_json(out / "run.json", report)
    return report


def verify(output):
    out = Path(output).resolve()
    report = read_json(out / "run.json")
    require(report.get("schema") == RUN, "run schema differs")
    for name, expected in report["artifacts"].items():
        require(sha256(within(out, name)) == expected, f"artifact changed: {name}")
    expected_id = identity({k: v for k, v in report.items() if k != "content_id"})
    require(report["content_id"] == expected_id, "run content identity differs")
    require(report["source_pins"] == source_pins(), "installed scorer/runner source differs; use the original version to rescore")
    rows = list(read_jsonl(out / "references.jsonl"))
    from .protocol import Request
    requests = [Request.from_dict(x) for x in read_jsonl(out / "inputs.jsonl")]
    require(len(requests) == len(rows), "input/reference stream length differs")
    for row, request in zip(rows, requests):
        require(row["id"] == request.id and row["text"] == request.text and row.get("other_text") == request.other_text
                and row.get("payload") == request.payload, "frozen reference/input differs")
    if report.get("reference_comparability") is not None:
        require(report["reference_comparability"] == reference_comparability(rows), "reference comparability audit differs")
    for name, entry in report["accuracy"].items():
        require(entry == read_json(out / (name + "-accuracy") / "execution.json"), "execution record differs from report")
        if entry["status"] == "ok":
            directory = out / (name + "-accuracy")
            cases = validate_predictions(rows, requests, list(read_jsonl(directory / "predictions.jsonl")), entry["identity"]["adapter"],
                                         read_json(out / "corpus.json").get("scoring_profiles", ()))
            require(cases == list(read_jsonl(directory / "cases.jsonl")), "rescored cases differ")
            require(summarize_views(cases) == entry["populations"], "rescored populations differ")
    for trial in report["trials"]:
        for name, entry in trial["engines"].items():
            require(entry == read_json(out / f"trial-{trial['trial']:03d}-{name}" / "execution.json"), "timing execution differs from report")
    return dict(status="verified", content_id=report["content_id"], artifacts=len(report["artifacts"]),
                scope="artifact integrity and accuracy rescoring; not a cryptographic author signature or runtime reenactment")
