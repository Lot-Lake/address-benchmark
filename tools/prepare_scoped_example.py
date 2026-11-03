#!/usr/bin/env python3
"""Prepare a local-only synthetic plan using existing corpus and plan APIs."""
from pathlib import Path
import argparse
import json

from address_benchmark.io import read_json, sha256, write_json, write_jsonl
from address_benchmark.protocol import FINE_TO_COARSE
from address_benchmark.ontologies import ONTOLOGY_V2, US_FINE
from address_benchmark.scoring import SCOPED_SCORER

ROOT = Path(__file__).resolve().parents[1]


def prepare(output, *, engines=None):
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    # Literal authored annotations, independent of candidate execution.
    rows = []
    for number in (1, 2, 3):
        text = f"{number} Maple St, Example, NY 00000"
        fields = dict(house_number=[str(number)], road=["Maple St"], city=["Example"], state=["NY"], postcode=["00000"])
        atoms = [(str(number), "house_number"), ("Maple", "road_name"), ("St", "road_type"), ("Example", "city"), ("NY", "state"), ("00000", "postcode")]
        labels = []
        start = 0
        for token, role in atoms:
            start = text.index(token, start)
            labels.append(dict(role=role, span=[start, start + len(token)]))
            start += len(token)
        rows.append(dict(id=f"synthetic-{number}", family=f"synthetic-family-{number}", text=text,
                         split="conformance", origin="authored", subsets=["synthetic"],
                         reference=dict(coverage="complete", fields=fields, tokens_coverage="complete", spans_coverage="complete", tokens=labels, spans=labels)))
    refused = dict(id="synthetic-refusal", family="synthetic-family-refusal", text="not in the demonstration grammar",
                   split="conformance", origin="authored", subsets=["synthetic"],
                   reference=dict(coverage="partial", fields={"road": ["demonstration"]}, tokens_coverage="none", spans_coverage="none", tokens=[], spans=[]))
    if engines is not None:
        # The existing native-batch adapter uses the v2 usaddress namespace.
        # This is a fixed author-declared ontology translation, never selected
        # using outputs or failures from the completed candidate.
        native = dict(house_number="AddressNumber", road_name="StreetName", road_type="StreetNamePostType",
                      city="PlaceName", state="StateName", postcode="ZipCode")
        for row in rows:
            for kind in ("tokens", "spans"):
                row["reference"][kind] = [{**item, "role": US_FINE[native[item["role"]]]} for item in row["reference"][kind]]
    write_jsonl(out / "complete.jsonl", rows[:2])
    partial = rows[2]
    partial["reference"].update(fields={"road": ["Maple St"]}, tokens=partial["reference"]["tokens"][1:2], spans=partial["reference"]["spans"][1:2])
    # The source ceiling downgrades complete row claims on all three layers.
    write_jsonl(out / "partial.jsonl", [partial, refused])
    full_scope = {kind: dict(coverage="complete", roles=sorted(set(FINE_TO_COARSE.values()) if kind == "fields" else FINE_TO_COARSE), absence=True)
                  for kind in ("fields", "tokens", "spans")}
    partial_scope = {kind: dict(coverage="partial", roles=["road"] if kind == "fields" else [US_FINE["StreetName"] if engines is not None else "road_name"], absence=False)
                     for kind in ("fields", "tokens", "spans")}
    manifest = read_json(ROOT / "examples/corpora/us-core/manifest.json")
    manifest.update(id="synthetic-local-scope", scorer=SCOPED_SCORER, resources=[],
                    preservation_cohorts=[dict(id="supplied-control", row_ids=["synthetic-2", "synthetic-3"], basis="Authored before comparison; fixed identities, not candidate-selected anchors")])
    if engines is not None:
        manifest["ontology"] = ONTOLOGY_V2
    manifest["license"]["redistribution"] = "local-only"
    manifest["construction"] = ["Original fictional synthetic scope/privacy controls; not natural or blind accuracy evidence."]
    for filename, scope in (("complete.jsonl", full_scope), ("partial.jsonl", partial_scope)):
        manifest["resources"].append(dict(path=filename, sha256=sha256(out / filename), source=filename, annotation_scope=scope))
    write_json(out / "manifest.json", manifest)
    configurations = (read_json(engines) if engines is not None else
        [dict(name=variant, adapter="examples.adapters.scoped_demo:Parser", config=dict(variant=variant,
             artifact_files=[str(ROOT / "examples/adapters/scoped_demo.py")])) for variant in ("incumbent", "candidate")])
    write_json(out / "engines.json", configurations)
    write_json(out / "plan.json", dict(schema="address-benchmark.plan/v1", name="Synthetic local scope", engines="engines.json",
               tracks=[dict(id="synthetic", corpus="manifest.json", output="execution")],
               execution=dict(baseline=configurations[0]["name"], timing=False, timeout=30)))
    return out / "plan.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    parser.add_argument("--engines", help="already supplied completed native-batch usaddress configuration; no source acquisition")
    args = parser.parse_args()
    prepare(args.output, engines=args.engines)
    print(json.dumps(dict(status="prepared")))
