"""Declarative experiment plans: references/configuration, never executable DSL."""
from __future__ import annotations

from pathlib import Path
import math
import json
import shutil
import sys

from .io import identity, read_json, require, sha256, within, write_json
from .runner import run, verify, source_pins, check_gate
from .corpus import load_corpus

PLAN = "address-benchmark.plan/v1"
EXECUTION_KEYS = {"timing", "trials", "samples", "min_seconds", "warmup", "timeout", "seed", "baseline", "gate"}


def load_plan(path):
    path = Path(path).resolve()
    value = read_json(path)
    require(isinstance(value, dict) and set(value) <= {"schema", "name", "engines", "tracks", "execution", "pins"}, "unknown benchmark plan keys")
    require(value.get("schema") == PLAN and isinstance(value.get("name"), str) and value["name"], "versioned plan name required")
    require(isinstance(value.get("tracks"), list) and value["tracks"], "nonempty plan tracks required")
    require(isinstance(value.get("execution", {}), dict) and set(value.get("execution", {})) <= EXECUTION_KEYS, "unknown execution settings")
    for key, setting in value.get("execution", {}).items():
        if key == "gate":
            check_gate(setting, [e["name"] for e in read_json(within(path.parent, value["engines"]))], value["execution"].get("baseline"))
        elif key == "timing":
            require(type(setting) is bool, "timing must be boolean")
        elif key in ("trials", "samples", "warmup", "seed"):
            require(type(setting) is int and setting >= (2 if key == "trials" else 1 if key == "samples" else 0), f"invalid integer setting: {key}")
            require(key != "trials" or setting % 2 == 0, "trials must be even")
        elif key in ("min_seconds", "timeout"):
            require(type(setting) in (int, float) and math.isfinite(setting) and setting > 0, f"invalid finite setting: {key}")
        else:
            require(isinstance(setting, str) and setting, "baseline must be an engine name")
    require(within(path.parent, value["engines"]).is_file(), "plan engines unavailable")
    ids, outputs = set(), set()
    for track in value["tracks"]:
        require(isinstance(track, dict) and set(track) == {"id", "corpus", "output"}, "track id/corpus/output required")
        require(isinstance(track["id"], str) and track["id"] and track["id"] not in ids, "unique track IDs required")
        ids.add(track["id"])
        require(within(path.parent, track["corpus"]).is_file(), "plan corpus unavailable")
        output = within(path.parent, track["output"])
        require(output not in outputs and not output.exists(), "distinct fresh track outputs required")
        require(all(not output.is_relative_to(other) and not other.is_relative_to(output) for other in outputs), "track outputs cannot nest")
        outputs.add(output)
    require(not (path.parent / "plan-results.json").exists(), "fresh plan directory required; prior plan receipt exists")
    require(not any((path.parent / ('scores.' + suffix)).exists() for suffix in ('txt', 'md', 'csv', 'json', 'html')), 'fresh score export files required')
    return path, value


def plan_pins(path, plan):
    engines_path = within(path.parent, plan["engines"])
    assets = {}
    for engine in read_json(engines_path):
        # These are the assets the existing adapter contract declares, never an
        # excuse to discover training sources or fetch missing model files.
        interpreter = shutil.which(engine.get("python", sys.executable))
        require(interpreter is not None, "frozen interpreter unavailable")
        command = engine.get("config", {}).get("command", [])
        executable = shutil.which(command[0]) if command else None
        require(not command or executable is not None, "frozen command executable unavailable")
        for asset in [interpreter, *([executable] if executable else []), *engine.get("config", {}).get("artifact_files", [])]:
            location = Path(asset).resolve()
            require(location.is_file(), "declared frozen runtime asset unavailable")
            assets[str(location)] = sha256(location)
    return dict(experiment_sha256=identity({k: v for k, v in plan.items() if k != "pins"}), framework=source_pins(), engines_sha256=sha256(engines_path),
                corpora={t["id"]: sha256(within(path.parent, t["corpus"])) for t in plan["tracks"]}, runtime_assets=assets)


def freeze_plan(path):
    path, plan = load_plan(path)
    require("pins" not in plan, "plan already frozen; create a new experiment to change policy")
    for track in plan["tracks"]:
        load_corpus(within(path.parent, track["corpus"]))
    plan["pins"] = plan_pins(path, plan)
    # Store the exact framework alongside the private plan for later verification.
    snapshot = path.parent / "framework-source"
    require(not snapshot.exists(), "fresh framework snapshot required")
    shutil.copytree(Path(__file__).parent, snapshot / "address_benchmark", ignore=shutil.ignore_patterns("__pycache__"))
    path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dict(status="frozen")


def run_plan(path):
    path, plan = load_plan(path)
    manifests = [load_corpus(within(path.parent, t["corpus"]))[0] for t in plan["tracks"]]
    private = any(m["license"]["redistribution"] == "local-only" for m in manifests)
    require(not private or "pins" in plan, "local-only plans must be frozen before execution")
    if "pins" in plan:
        require(plan["pins"] == plan_pins(path, plan), "frozen plan assets/framework differ")
    frozen = dict(schema="address-benchmark.plan-results/v1", plan_sha256=sha256(path), name=plan["name"], privacy="local-only" if private else "public", status="running", tracks=[])
    runs = []
    stopped = False
    engines = [engine["name"] for engine in read_json(within(path.parent, plan["engines"]))]
    for index, track in enumerate(plan["tracks"]):
        label = f"track-{index + 1}" if private else track["id"]
        if stopped:
            # Do not launch a later public track after a private accuracy failure.
            template = runs[0][1]
            skipped = {key: template[key] for key in ("schema", "task", "scorer", "normalization", "secondary_normalization", "privacy")}
            skipped.update(status="not-executed", accuracy={name: dict(status="not-executed") for name in engines}, trials=[], paired={}, deltas={}, measurements={key: "not-executed" for key in ("timing", "public_evaluation", "memory", "latency")})
            skipped["content_id"] = identity(skipped)
            frozen["tracks"].append(dict(id=track["id"], output=track["output"], status="not-executed", content_id=skipped["content_id"], verification="not-executed", summary=skipped))
            runs.append((track["id"], skipped))
            print(f"track {label}: not-executed; blocked by accuracy gate", flush=True, file=sys.stderr)
            continue
        print(f"track {label}: starting", flush=True, file=sys.stderr)
        output = within(path.parent, track["output"])
        result = run(within(path.parent, track["corpus"]), within(path.parent, plan["engines"]), output, **plan.get("execution", {}))
        verified = verify(output)
        frozen["tracks"].append(dict(id=track["id"], output=track["output"], status=result["status"], content_id=result["content_id"], verification=verified["status"]))
        runs.append((track['id'], result))
        stopped = result.get("gate", {}).get("status") == "failed"
        print(f"track {label}: {result['status']}; artifacts {verified['status']}", flush=True, file=sys.stderr)
    frozen["status"] = "complete" if all(t["status"] == "complete" for t in frozen["tracks"]) else "incomplete"
    if "pins" in plan:
        require(plan["pins"] == plan_pins(path, plan), "frozen plan assets/framework changed during execution")
    require(sha256(path) == frozen["plan_sha256"], "plan changed during run")
    from .tables import scorecard, export_scorecard
    export_scorecard(scorecard(runs, engines=engines, title=plan['name']), path.parent)
    write_json(path.parent / "plan-results.json", frozen)
    return frozen
