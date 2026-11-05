"""Authored unit-gate controls: a tiny corpus, an input-only synthetic parser and a gate plan.

The parser is NOT a real parser. Each variant's bug is keyed on input text only; it never
sees references, case IDs, cohorts or annotations.
"""
from pathlib import Path
import json

from address_benchmark.adapters import metadata
from address_benchmark.io import require, sha256, write_json
from address_benchmark.protocol import prediction

UNIT_TYPES = {"Apt", "Unit"}
ROAD_TYPES = {"St", "Rd"}
TEXTS = (("unit-01", "12 Alder St Apt 4, Exampleville, NY 00123", "unit-target"),
         ("unit-02", "40 Birch Rd Unit 7, Exampleville, NY 00123", "unit-target"),
         ("unit-03", "15 Cedar St, Exampleville, NY 00123", "unit-negative"),
         ("unit-04", "22 Dogwood Rd, Exampleville, NY 00123", "unit-negative"),
         ("unit-05", "30 Elm St, Exampleville, NY 00123", "unit-negative"))
# Each requirement is named after the plan gate it stands in for (PLAN sections 6-7).
# Whole-address requirements declare `delimiter` explicitly: it is the metric that
# reproduces the e429 record (strict differs on edge-delimited references).
GATES = (("A1-whole", dict(cohort="dev-preservation", metric="delimiter", min_preservation=1)),
         ("A1-unit", dict(cohort="unit-preservation", metric="unit-span/v1", min_preservation=1)),
         ("A2", dict(metric="delimiter", max_losses=0)),
         ("A3-whole", dict(splits=["dev"], metric="delimiter", max_losses=0)),
         ("A3-unit", dict(subset="unit-target", metric="unit-span/v1", max_losses=0)),
         ("A4", dict(metric="unit-negative/v1", max_losses=0)),
         ("C3-false-unit-rows", dict(metric="unit-negative/v1", min_correct=2)),
         ("C3-false-unit-tokens", dict(metric="unit-negative/v1", max_unit_false_positive_tokens=1)),
         ("C3-unit-field", dict(metric="unit-field/v1", max_losses=0)),
         ("C3-units-whole", dict(metric="delimiter", max_losses=0)),
         ("C3-hard-fine", dict(cohort="fine-preservation", metric="fine-exact/v1", min_preservation=1)))
GATE_NAMES = [name for name, _ in GATES]
VARIANTS = ("e429", "whole-regress", "unit-regress", "fine-regress", "token-regress")


def label(text):
    """Gold-shaped labels from the authored grammar: street part, city, state and ZIP."""
    street, city, last = text.split(", ")
    words = street.split(" ")
    unit = next((i for i, w in enumerate(words) if w in UNIT_TYPES), len(words))
    roles = ["house_number"] + ["road_name"] * (unit - 2) + ["road_type"]
    roles += ["unit_type", "unit_id"][:len(words) - unit]
    state, postcode = last.split(" ")
    return list(zip(words + [city, state, postcode], roles + ["city", "state", "postcode"], strict=True))


def tokens(text, labels):
    found, cursor = [], 0
    for value, role in labels:
        start = text.index(value, cursor)
        found.append((value, role, [start, start + len(value)]))
        cursor = start + len(value)
    return found


def reference(text):
    from address_benchmark.protocol import FINE_TO_COARSE
    fields, previous = {}, None
    for value, role in label(text):
        coarse = FINE_TO_COARSE[role]
        if coarse == previous:
            fields[coarse][-1] += " " + value
        else:
            fields.setdefault(coarse, []).append(value)
        previous = coarse
    atoms = [dict(role=role, span=span) for _, role, span in tokens(text, label(text))]
    return dict(coverage="complete", fields=fields, spans=atoms, spans_coverage="complete", tokens=atoms, tokens_coverage="complete")


ROWS = [dict(id=i, family="address-benchmark:" + i, origin="authored", split="dev", subsets=[subset], text=text, reference=reference(text))
        for i, text, subset in TEXTS]


class Parser:
    def __init__(self, config):
        require(set(config) == {"variant"} and config["variant"] in VARIANTS, "select control variant")
        self.variant = config["variant"]
        roles = ("house_number", "road_name", "road_type", "unit_type", "unit_id", "city", "state", "postcode")
        self.metadata = metadata("unit-controls", {r: r for r in roles}, version="control-" + self.variant, spans=True, tokens=True)

    def parse(self, request):
        labels = label(request.text)
        if request.text.startswith(("22 ", "30 ")):
            # Shared incumbent whole-address error, so a later unit bug cannot move strict.
            labels = [(v, "state" if r == "postcode" else r) for v, r in labels]
        if request.text.startswith("30 "):
            # Incumbent false unit token on an already-wrong row (the C3 token cap is 1).
            labels = [(v, "unit_type" if r == "road_type" else r) for v, r in labels]
        if self.variant == "whole-regress":
            labels = [(v, "city" if r == "state" and v == "NY" else r) for v, r in labels]
        elif self.variant == "unit-regress":
            swap = {"unit_type": "unit_id", "unit_id": "unit_type"}
            labels = [(v, swap.get(r, r)) for v, r in labels]
            if request.text.startswith("22 "):
                labels = [(v, "unit_type" if r == "road_type" else r) for v, r in labels]
        elif self.variant == "token-regress":
            # A second false unit token on the same already-wrong row: no row judgment changes.
            if request.text.startswith("30 "):
                labels = [(v, "unit_id" if r == "road_name" else r) for v, r in labels]
        elif self.variant == "fine-regress":
            # Road type read as road name: the coarse road value is unchanged.
            labels = [(v, "road_name" if r == "road_type" else r) for v, r in labels]
        evidence = [dict(native_role=role, value=value, spans=[span]) for value, role, span in tokens(request.text, labels)]
        return prediction(request, evidence, tokens=evidence, native={"variant": self.variant})


def write_control_plan(directory, variant):
    """One single-track plan per variant: run-plan stops later tracks after a failed gate."""
    corpus = Path(directory) / "corpus"
    corpus.mkdir(parents=True)
    data = corpus / "cases.jsonl"
    data.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in ROWS), encoding="utf-8")
    write_json(corpus / "manifest.json", dict(
        schema="address-benchmark.corpus/v1", id="unit-gate-controls", version="1.0.0", country="US", locale="en-US", task="parse",
        ontology="address-benchmark.us-roles/v1", annotation_policy="docs/spec/annotations.md#authored-v1",
        provenance=dict(source="Authored unit-gate controls", upstream_revision="authored-v1"),
        license=dict(spdx="MIT", redistribution="allowed", notice="Original fictional examples."),
        construction=["Authored in tests/unit_controls.py; byte offsets derived from literal tokens"],
        exposure=dict(status="public-conformance-development-exposed", history=["Authored for scorer controls"]),
        split_policy="All rows are dev controls.", family_policy="One authored family per row.",
        resources=[dict(path="cases.jsonl", sha256=sha256(data), bytes=data.stat().st_size)],
        preservation_cohorts=[dict(id="dev-preservation", basis=dict(kind="baseline-correct", metric="delimiter")),
                              dict(id="unit-preservation", basis=dict(kind="baseline-correct", subset="unit-target", metric="unit-span/v1")),
                              dict(id="fine-preservation", basis=dict(kind="baseline-correct", metric="fine-exact/v1"))]))
    engines = [dict(name="e429", adapter="tests.unit_controls:Parser", config=dict(variant="e429")),
               dict(name="successor", adapter="tests.unit_controls:Parser", config=dict(variant=variant))]
    write_json(Path(directory) / "engines.json", engines)
    plan = Path(directory) / "plan.json"
    write_json(plan, dict(schema="address-benchmark.plan/v1", name="unit-gate-controls-" + variant, engines="engines.json",
                          tracks=[dict(id="controls", corpus="corpus/manifest.json", output="run")],
                          execution=dict(baseline="e429", timing=False, timeout=60,
                                         gate=dict(candidate="successor", requirements=[spec for _, spec in GATES]))))
    return plan


def summarize_controls(root):
    """Per-variant, per-gate losses for the receipt; aggregates only."""
    from contextlib import redirect_stderr
    import io
    from address_benchmark.io import read_json
    from address_benchmark.plan import run_plan
    result = {}
    for variant in VARIANTS:
        plan = write_control_plan(Path(root) / variant, variant)
        with redirect_stderr(io.StringIO()):
            receipt = run_plan(plan)
        gate = read_json(plan.parent / "run/run.json")["gate"]
        result[variant] = dict(plan_status=receipt["status"], gate=gate["status"],
                               requirements={name: dict(judged=r["judged_pairs"], losses=r["losses"], correct=r["correct"], status=r["status"])
                                             for name, r in zip(GATE_NAMES, gate["requirements"], strict=True)})
    return result


if __name__ == "__main__":
    import sys
    print(json.dumps(summarize_controls(sys.argv[1]), indent=2, sort_keys=True))
