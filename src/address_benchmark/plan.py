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



def check_execution(execution, engine_names):
    require(isinstance(execution, dict) and set(execution) <= EXECUTION_KEYS, "unknown execution settings")
    for key, setting in execution.items():
        if key == "gate":
            check_gate(setting, engine_names, execution.get("baseline"))
        elif key == "timing":
            require(type(setting) is bool, "timing must be boolean")
        elif key in ("trials", "samples", "warmup", "seed"):
            require(type(setting) is int and setting >= (2 if key == "trials" else 1 if key == "samples" else 0), "invalid integer execution setting")
            require(key != "trials" or setting % 2 == 0, "trials must be even")
        elif key in ("min_seconds", "timeout"):
            require(type(setting) in (int, float) and math.isfinite(setting) and setting > 0, "invalid finite execution setting")
        else:
            require(isinstance(setting, str) and setting in engine_names, "baseline must be a selected engine")

def load_plan(path):
    path = Path(path).resolve()
    value = read_json(path)
    require(isinstance(value, dict) and set(value) <= {"schema", "name", "engines", "tracks", "execution", "pins"}, "unknown benchmark plan keys")
    require(value.get("schema") == PLAN and isinstance(value.get("name"), str) and value["name"], "versioned plan name required")
    require(isinstance(value.get("tracks"), list) and value["tracks"], "nonempty plan tracks required")
    require(isinstance(value.get("execution", {}), dict) and set(value.get("execution", {})) <= EXECUTION_KEYS, "unknown execution settings")
    engine_names = [e["name"] for e in read_json(within(path.parent, value["engines"]))]
    check_execution(value.get("execution", {}), engine_names)
    require(within(path.parent, value["engines"]).is_file(), "plan engines unavailable")
    ids, outputs = set(), set()
    for track in value["tracks"]:
        require(isinstance(track, dict) and {"id", "corpus", "output"} <= set(track) <= {"id", "corpus", "output", "execution"}, "track id/corpus/output and optional execution required")
        require(isinstance(track.get("execution", {}), dict), "track execution object required")
        check_execution({**value.get("execution", {}), **track.get("execution", {})}, engine_names)
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
        from .adapters import command_artifacts
        metadata = engine.get("config", {}).get("metadata", {})
        require(isinstance(metadata, dict), "command metadata object required")
        declared = [*engine.get("config", {}).get("artifact_files", []), *metadata.get("artifact_files", [])]
        command_files = command_artifacts(command, declared) if command else declared
        for asset in [interpreter, *command_files]:
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
    frozen = dict(schema="address-benchmark.plan-results/v1", plan_sha256=sha256(path), plan_file=path.name, name=plan["name"], privacy="local-only" if private else "public", status="running", tracks=[])
    runs = []
    if private and any(m["license"]["redistribution"] == "allowed" for m in manifests):
        print("publication: mixed private/public plan uses aliases for every track", file=sys.stderr, flush=True)
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
        result = run(within(path.parent, track["corpus"]), within(path.parent, plan["engines"]), output, **{**plan.get("execution", {}), **track.get("execution", {})})
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
    frozen['artifacts'] = {f'scores.{suffix}': sha256(path.parent / f'scores.{suffix}') for suffix in ('txt', 'md', 'csv', 'json', 'html')}
    frozen['content_id'] = identity(frozen)
    write_json(path.parent / "plan-results.json", frozen)
    return frozen


def verify_plan(path):
    path = Path(path).resolve()
    if path.is_dir(): path = path / 'plan-results.json'
    value = read_json(path)
    if value.get('schema') == PLAN:
        original = path
        path = path.parent / 'plan-results.json'
        value = read_json(path)
        require(value['plan_sha256'] == sha256(original), 'plan changed since execution')
    require(value.get('schema') == 'address-benchmark.plan-results/v1', 'plan receipt schema differs')
    if 'content_id' in value:
        require(value['content_id'] == identity({k: v for k, v in value.items() if k != 'content_id'}), 'plan receipt identity differs')
    if 'plan_file' in value:
        original = within(path.parent, value['plan_file'])
        require(sha256(original) == value['plan_sha256'], 'plan changed since execution')
        planned = read_json(original)
        require([(t['id'], t['output']) for t in planned['tracks']] == [(t['id'], t['output']) for t in value['tracks']], 'plan track index differs')
    for name, digest in value.get('artifacts', {}).items():
        require(sha256(within(path.parent, name)) == digest, 'plan export artifact differs')
    tracks = []
    for track in value['tracks']:
        if track['status'] == 'not-executed':
            summary = track['summary']
            require(summary['content_id'] == track['content_id'] == identity({k: v for k, v in summary.items() if k != 'content_id'}), 'skipped track identity differs')
            require(not within(path.parent, track['output']).exists(), 'skipped track has execution artifacts')
            tracks.append(dict(status='not-executed'))
        else:
            result = verify(within(path.parent, track['output']))
            require(result['content_id'] == track['content_id'], 'plan/run identity differs')
            tracks.append(dict(status=result['status']))
    return dict(status='verified', scope='plan links, recorded exports, immutable child artifacts and accuracy rescoring', tracks=tracks)
