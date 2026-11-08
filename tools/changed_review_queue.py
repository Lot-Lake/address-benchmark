#!/usr/bin/env python3
"""Draw a local, bounded review queue from retained native benchmark outputs.

This checks consumed artifact integrity and input/prediction contracts only. It
does not rescore, verify a benchmark run, adjudicate labels, or establish accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import io
import json
import os
from pathlib import Path
import sys

from address_benchmark.io import canonical, digest_bytes, identity, loads, require, within
from address_benchmark.protocol import Request, check_metadata, check_prediction

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "address-benchmark.changed-review/v1"
MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 100_000
MAX_QUEUE = 1_000
FIELDS = ("status", "evidence", "tokens", "inferred", "normalized", "keys",
          "result", "profile", "message", "native")
IDENTITY_FIELDS = {"schema", "id", "input_sha256"}


class Budget:
    def __init__(self):
        self.bytes = 0
        self.rows = 0

    def read(self, path):
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES - self.bytes + 1)
        self.bytes += len(raw)
        require(self.bytes <= MAX_BYTES, "artifact byte limit exceeded")
        return raw


def objects(raw):
    for line in io.BytesIO(raw):
        require(line.strip() and len(line) <= 4 * 1024 * 1024, "invalid JSONL record")
        value = loads(line.decode("utf-8"))
        require(isinstance(value, dict), "JSONL object required")
        yield value


def index_rows(rows):
    result = {}
    for row in rows:
        key = row.get("id")
        require(isinstance(key, str) and key and key not in result, "missing or duplicate row ID")
        result[key] = row
    return result


def run_root(source):
    path = Path(source).resolve()
    return path.parent if path.name == "run.json" and path.is_file() else path


def load_side(root, engine, budget):
    report = loads(budget.read(root / "run.json").decode("utf-8"))
    require(report["schema"] == "address-benchmark.run/v1" and report["status"] in ("complete", "gated"),
            "finalized run required")
    require(report["content_id"] == identity({k: v for k, v in report.items() if k != "content_id"}),
            "run content identity differs")
    require(isinstance(report["source_pins"], dict) and report["source_pins"], "recorded source pins required")
    require(isinstance(engine, str) and engine and engine.isascii()
            and engine.replace("-", "").replace("_", "").isalnum(), "safe engine name required")
    entry = report["accuracy"][engine]
    require(entry["status"] == "ok", "successful retained engine required")

    def artifact(name):
        raw = budget.read(within(root, name))
        require(digest_bytes(raw) == report["artifacts"][name], "consumed artifact hash differs")
        return raw

    manifest = loads(artifact("corpus.json").decode("utf-8"))
    require(all(isinstance(manifest.get(key), str) and manifest[key]
                for key in ("id", "country", "locale", "task", "ontology")), "native corpus identity required")
    require(manifest["id"] == report["corpus"]["id"] and manifest["task"] == report["task"],
            "run corpus identity differs")
    metadata = entry["identity"]["adapter"]
    check_metadata(metadata)
    require(metadata["ontology"] == manifest["ontology"], "adapter ontology differs")
    require(entry["identity_sha256"] == identity(entry["identity"]), "runtime identity differs")
    prefix = engine + "-accuracy/"
    require(loads(artifact(prefix + "identity.json").decode("utf-8")) == entry["identity"], "runtime identity differs")
    require(loads(artifact(prefix + "execution.json").decode("utf-8")) == entry, "execution record differs")
    raw_inputs = artifact("inputs.jsonl")
    require(digest_bytes(raw_inputs) == report["input_sha256"], "input panel hash differs")
    inputs = {}
    for value in objects(raw_inputs):
        budget.rows += 1
        require(budget.rows <= MAX_ROWS, "input row limit exceeded")
        request = Request.from_dict(value)
        require(request.id not in inputs, "duplicate input ID")
        require((request.country, request.locale, request.task, request.profile) ==
                (manifest["country"], manifest["locale"], manifest["task"], manifest.get("profile", "")),
                "request corpus contract differs")
        inputs[request.id] = request
    require(inputs, "nonempty retained inputs required")
    del raw_inputs
    # Only ownership is retained here. Gold and partial-label masks stay in the
    # original hash-pinned references and never enter a review card.
    sources, seen = {}, set()
    for row in objects(artifact("references.jsonl")):
        key = row.get("id")
        require(isinstance(key, str) and key in inputs and key not in seen, "reference identity differs")
        seen.add(key)
        request = inputs[key]
        require((row["text"], row.get("other_text"), row.get("payload")) ==
                (request.text, request.other_text, request.payload), "reference input differs")
        source = row.get("source", f"{row['origin']}/{row['split']}/all")
        require(isinstance(source, str) and source, "source ownership required")
        sources[key] = dict(source=source, family=row["family"], origin=row["origin"], split=row["split"])
        require(all(isinstance(x, str) and x for x in sources[key].values()), "ownership strings required")
    require(seen == set(inputs), "reference population differs")
    predictions = index_rows(objects(artifact(prefix + "predictions.jsonl")))
    require(set(predictions) == set(inputs), "prediction population differs")
    for key, request in inputs.items():
        check_prediction(predictions[key], request, metadata)
    return dict(inputs=inputs, ownership=sources, predictions=predictions,
                contract={k: manifest.get(k, "") for k in ("id", "country", "locale", "task", "profile", "ontology")},
                receipt=dict(run_content_id=report["content_id"], engine=engine, source_pins=report["source_pins"],
                             artifacts={name: report["artifacts"][name] for name in
                                        ("corpus.json", "inputs.jsonl", "references.jsonl", prefix + "predictions.jsonl",
                                         prefix + "identity.json", prefix + "execution.json")}))


def changes(before, after):
    if before is None:
        return ["missing_before"], []
    if after is None:
        return ["missing_after"], []
    fields = sorted(key for key in set(before) | set(after) if key not in IDENTITY_FIELDS
                    and (key not in before or key not in after or canonical(before[key]) != canonical(after[key])))
    categories = [key for key in FIELDS if key in fields]
    if set(fields) - set(FIELDS):
        categories.append("other")
    return categories, fields


def draw(cards, n, seed):
    strata = defaultdict(lambda: defaultdict(list))
    for card in cards:
        strata[card["ownership"]["source"]][tuple(card["changes"])].append(card)
    # Take one source per turn, cycling its complete change combinations. Hash
    # ranks make both levels independent of the order of all input streams.
    rank = lambda value: identity([seed, value])
    sources = sorted(strata, key=rank)
    buckets = {}
    for source in sources:
        buckets[source] = deque(deque(sorted(rows, key=lambda row: rank([row["corpus_id"], row["id"]])))
                                for kinds, rows in sorted(strata[source].items(), key=lambda item: rank(item[0])))
    selected = []
    while len(selected) < n and sources:
        active = []
        for source in sources:
            queue = buckets[source]
            bucket = queue.popleft()
            selected.append(bucket.popleft())
            if bucket:
                queue.append(bucket)
            if queue:
                active.append(source)
            if len(selected) == n:
                break
        sources = active
    return selected


def counts(cards):
    strata = Counter((card["ownership"]["source"], tuple(card["changes"])) for card in cards)
    return [dict(source=source, changes=list(kinds), rows=count) for (source, kinds), count in sorted(strata.items())]


def build_queue(before, after, *, baseline, candidate, output, n=150, seed=1):
    require(type(n) is int and 1 <= n <= MAX_QUEUE and type(seed) is int, "invalid sampling bounds")
    left_root, right_root = run_root(before), run_root(after)
    out = Path(output).absolute()
    local = ROOT / "work"
    # Require lexical and resolved containment: a symlink cannot redirect private
    # output outside the ignored local tree or back into a retained source run.
    require(out.is_relative_to(local) and out.resolve().is_relative_to(local.resolve())
            and local.resolve() == local, "output must remain in the local work tree")
    require(not out.exists() and not out.is_symlink(), "fresh output required")
    out = out.resolve()
    require(all(not out.is_relative_to(root) and not root.is_relative_to(out) for root in (left_root, right_root)),
            "output overlaps retained input")
    budget = Budget()
    left, right = load_side(left_root, baseline, budget), load_side(right_root, candidate, budget)
    require(left["contract"] == right["contract"], "corpus contract differs")
    corpus_id = left["contract"]["id"]
    shared = set(left["inputs"]) & set(right["inputs"])
    for key in shared:
        require(left["inputs"][key] == right["inputs"][key], "shared input identity differs")
        require(left["ownership"][key] == right["ownership"][key], "shared source ownership differs")
    cards = []
    unchanged = 0
    for key in sorted(set(left["inputs"]) | set(right["inputs"])):
        previous, current = left["predictions"].get(key), right["predictions"].get(key)
        categories, fields = changes(previous, current)
        if not categories:
            unchanged += 1
            continue
        side = left if key in left["inputs"] else right
        cards.append(dict(corpus_id=corpus_id, id=key, input_sha256=side["inputs"][key].input_sha256,
                          input=side["inputs"][key].to_dict(), ownership=side["ownership"][key],
                          changes=categories, changed_fields=fields, before=previous, after=current))
    selected = draw(cards, n, seed)
    population = dict(before_rows=len(left["inputs"]), after_rows=len(right["inputs"]), shared_rows=len(shared),
                      before_only=len(left["inputs"]) - len(shared), after_only=len(right["inputs"]) - len(shared),
                      unchanged_rows=unchanged, changed_rows=len(cards), selected_rows=len(selected))
    receipt = dict(schema=SCHEMA, purpose="diagnostic review only; not gold, admission, accuracy, or a representative estimate",
                   validation="consumed artifact hashes, envelope identity, stable-ID joins and native contracts; no rescoring or full run verification",
                   before=left["receipt"], after=right["receipt"], population=population,
                   sampling=dict(method="source round robin, then complete change-combination round robin; SHA-256 ranks",
                                 seed=seed, requested=n), limits=dict(combined_input_rows=MAX_ROWS, consumed_bytes=MAX_BYTES,
                                 queue_rows=MAX_QUEUE), consumed=dict(bytes=budget.bytes, input_rows=budget.rows),
                   population_strata=counts(cards), selected_strata=counts(selected))
    out.mkdir(parents=True, mode=0o700)
    for name, raw in (("queue.jsonl", b"".join(canonical(card) + b"\n" for card in selected)),
                      ("review.json", canonical(receipt) + b"\n")):
        with os.fdopen(os.open(out / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
            stream.write(raw)
    return population


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="retained run directory or run.json")
    parser.add_argument("after", type=Path, help="retained run directory or run.json")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", type=Path, required=True, help="fresh directory under this checkout's ignored work/")
    parser.add_argument("--n", type=int, default=150)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        result = build_queue(args.before, args.after, baseline=args.baseline, candidate=args.candidate,
                             output=args.out, n=args.n, seed=args.seed)
        print(json.dumps(dict(status="written", **result), sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, AttributeError, RuntimeError):
        # Native errors, JSON keys and filesystem exceptions can quote private data.
        print("changed-review: invalid-input-or-output", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
