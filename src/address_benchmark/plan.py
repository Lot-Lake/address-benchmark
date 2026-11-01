"""Declarative experiment plans: references/configuration, never executable DSL."""
from __future__ import annotations

from pathlib import Path
import math
import sys

from .io import read_json, require, sha256, within, write_json
from .runner import run, verify

PLAN = "address-benchmark.plan/v1"
EXECUTION_KEYS = {"timing", "trials", "samples", "min_seconds", "warmup", "timeout", "seed", "baseline"}


def load_plan(path):
    path = Path(path).resolve()
    value = read_json(path)
    require(isinstance(value, dict) and set(value) <= {"schema", "name", "engines", "tracks", "execution"}, "unknown benchmark plan keys")
    require(value.get("schema") == PLAN and isinstance(value.get("name"), str) and value["name"], "versioned plan name required")
    require(isinstance(value.get("tracks"), list) and value["tracks"], "nonempty plan tracks required")
    require(isinstance(value.get("execution", {}), dict) and set(value.get("execution", {})) <= EXECUTION_KEYS, "unknown execution settings")
    for key, setting in value.get("execution", {}).items():
        if key == "timing":
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


def run_plan(path):
    path, plan = load_plan(path)
    frozen = dict(schema="address-benchmark.plan-results/v1", plan_sha256=sha256(path), name=plan["name"], status="running", tracks=[])
    runs = []
    for track in plan["tracks"]:
        print(f"track {track['id']}: starting", flush=True, file=sys.stderr)
        output = within(path.parent, track["output"])
        result = run(within(path.parent, track["corpus"]), within(path.parent, plan["engines"]), output, **plan.get("execution", {}))
        verified = verify(output)
        frozen["tracks"].append(dict(id=track["id"], output=track["output"], status=result["status"], content_id=result["content_id"], verification=verified["status"]))
        runs.append((track['id'], result))
        print(f"track {track['id']}: {result['status']}; artifacts {verified['status']}", flush=True, file=sys.stderr)
    frozen["status"] = "complete" if all(t["status"] == "complete" for t in frozen["tracks"]) else "incomplete"
    require(sha256(path) == frozen["plan_sha256"], "plan changed during run")
    from .tables import scorecard, export_scorecard
    engines = [engine['name'] for engine in read_json(within(path.parent, plan['engines']))]
    export_scorecard(scorecard(runs, engines=engines, title=plan['name']), path.parent)
    write_json(path.parent / "plan-results.json", frozen)
    return frozen
