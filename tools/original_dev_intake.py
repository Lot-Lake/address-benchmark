"""Install the private original e429 DEV handoff as local-only parse corpora and a replay plan.

Reads the `original-e429-dev-handoff/v1` package (seed, municipal and Wisconsin DEV
plus the gold-defined unit cohorts) and a regenerated GeoSearch DEV `references.jsonl`.
Writes canonical corpus rows and manifests under OUT; nothing is published. Rows carry
subset `unit-target` or `no-unit` from the package's membership files.

    python -E -s tools/original_dev_intake.py PACKAGE GEOSEARCH_REFERENCES LEARNED_PARSER OUT
"""
from pathlib import Path
import json
import subprocess
import sys

from address_benchmark.intake import parse_reference, row_record
from address_benchmark.io import require, sha256, write_json
from address_benchmark.ontologies import ONTOLOGY_V2

CORPORA = ("seed-dev", "municipal-dev", "wisconsin-dev")
# Seed is the usaddress publisher's labeled strings; municipal and Wisconsin render source fields.
ORIGINS = {"seed-dev": "publisher-fixture", "municipal-dev": "source-field-supervised", "wisconsin-dev": "source-field-supervised"}
E429 = "e429c2cf5a1e01abcb6fad02d7f39768d3d8923141dee58b14ce016a889fe965"
LICENSE = dict(spdx="LicenseRef-AssetSpecific-LocalEvaluation", redistribution="local-only",
               notice="Private named-recipient DEV handoff; no redistribution rights granted.")


def manifest(name, resource, source, revision):
    return dict(schema="address-benchmark.corpus/v1", id=name, version="1.0.0", country="US", locale="en-US", task="parse",
                ontology=ONTOLOGY_V2, provenance=dict(source=source, upstream_revision=revision), license=LICENSE,
                construction=["Original e429 DEV rows; publisher token spans and labels kept, no repair"],
                annotation_policy="docs/spec/real-corpora.md",
                exposure=dict(status="development-exposed original DEV", history=["e429 selection DEV"]),
                family_policy="Exact-input hash proxy only.", split_policy="Original task DEV.", resources=[resource])


def main(package, references, binary, out):
    package, out = Path(package).resolve(), Path(out).resolve()
    out.mkdir(parents=True)
    members = {}
    for cohort in ("unit-target", "no-unit"):
        for line in (package / "cohorts" / (cohort + ".jsonl")).open(encoding="utf-8"):
            record = json.loads(line)
            members[(record["corpus"], record["id"])] = (cohort, record["input_sha256"])
    tracks, seen = [], 0
    for name in CORPORA:
        folder = out / "corpora" / name
        folder.mkdir(parents=True)
        rows = []
        stub = dict(id=name)
        for line in (package / "inputs" / (name + ".jsonl")).open(encoding="utf-8"):
            row = json.loads(line)
            require(len(row["tokens"]) == len(row["labels"]), "token/label geometry")
            parts = [(t["value"], label) for t, label in zip(row["tokens"], row["labels"])]
            spans = [[t["span"]["start"], t["span"]["end"]] for t in row["tokens"]]
            cohort, digest = members[(name, row["id"])]
            require(digest == row["input_sha256"], "cohort input identity differs")
            seen += 1
            record = row_record(stub, dict(split="dev", origin=ORIGINS[name]), row["id"], row["input"],
                                parse_reference(row["input"], parts, spans), subsets=["all", cohort])
            rows.append(json.dumps(record, sort_keys=True) + "\n")
        data = folder / "cases.jsonl"
        data.write_text("".join(rows), encoding="utf-8")
        write_json(folder / "manifest.json", manifest(name, dict(path="cases.jsonl", sha256=sha256(data), bytes=data.stat().st_size),
                                                      "original-e429-dev-handoff/v1", sha256(package / "manifest.json")))
        tracks.append(dict(id=name, corpus=f"corpora/{name}/manifest.json", output=f"results/{name}"))
    require(seen == len(members), "cohort membership does not cover the DEV rows")
    references = Path(references).resolve()
    (out / "corpora" / "geo-dev").mkdir()
    write_json(out / "corpora" / "geo-dev" / "manifest.json", manifest("geo-dev", dict(
        external_path=str(references), sha256=sha256(references), bytes=references.stat().st_size, format="geosearch-reference",
        split="dev", origin="source-field-supervised"), "https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark",
        "424f94167c21d1ad3f8e70b50a75174f68dfe1f0"))
    tracks.append(dict(id="geo-dev", corpus="corpora/geo-dev/manifest.json", output="results/geo-dev"))
    meta = json.loads(subprocess.check_output([binary, "--metadata"], text=True))
    require(meta["model_sha256"] == E429, "learned parser is not e429")
    write_json(out / "engines.json", [dict(name="e429", adapter="native-batch", config=dict(
        name="retained-learned-rust", namespace="usaddress", command=[binary, "--batch", "{inputs}", "{outputs}", "{metadata}"],
        model_identity="usa-lexical-locality-unit-boundary28:" + E429, artifact_files=[binary], active_native_roles=meta["labels"],
        role_inventory_basis="learned-parser --metadata labels"))])
    write_json(out / "plan.json", dict(schema="address-benchmark.plan/v1", name="e429-original-dev-baseline", engines="engines.json",
                                       tracks=tracks, execution=dict(timing=False, timeout=3600)))
    print(json.dumps(dict(plan=str(out / "plan.json"), rows=seen, tracks=[t["id"] for t in tracks])))


if __name__ == "__main__":
    main(*sys.argv[1:5])
