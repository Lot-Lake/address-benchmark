"""Create a JSON plan from locally installed comparison assets, without copying them.

Only original plan/config manifests are public. Raw upstream data and runtime
assets stay at their existing locations; derived run artifacts remain local.
"""
from pathlib import Path
import argparse
import json
import sys
import subprocess

from address_benchmark.io import read_json, require, sha256, write_json, write_jsonl
from address_benchmark.ontologies import MAILWOMAN_EMITTER_MAP, ONTOLOGY_V2
from address_benchmark.production import adapter_metadata

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True, help="read-only existing address-normalizer checkout")
parser.add_argument("--doorplate", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--smoke", type=int, default=0, help="cap each corpus to first N rows for integration preflight, never label it population evidence")
args = parser.parse_args()
source, out = args.source.resolve(), args.out.resolve()
out.mkdir(parents=True)
(out / "corpora").mkdir()
project = Path(__file__).resolve().parents[1]
runtime_path = source / ".cache/us-common-matrix-20261101/build-v1/runtimes.json"
runtime = read_json(runtime_path)
retained = read_json(source / "experiments/us_parser/retained_model.json")
model = source / retained["artifact"]["path"]
require(sha256(model) == retained["artifact"]["sha256"], "retained model identity differs")
gate = read_json(source / ".cache/us-wisconsin-learning-round-20261101/raw28-v1/native-gate-v1/report.json")
native = Path(gate["steps"][1]["command"][0])
require(sha256(native) == gate["binary_sha256"], "retained native decoder identity differs")

sources = [
    ("geosearch-dev", source / ".cache/us-geosearch-fine-evaluation-20261029/execution-v1/dev/references.jsonl", "geosearch-reference", "dev", "source-field-supervised", "https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark", "424f94167c21d1ad3f8e70b50a75174f68dfe1f0"),
    ("geosearch-test", source / ".cache/us-geosearch-fine-evaluation-20261029/execution-v1/test/references.jsonl", "geosearch-reference", "test", "source-field-supervised", "https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark", "424f94167c21d1ad3f8e70b50a75174f68dfe1f0"),
    ("doorplate-v1", args.doorplate.resolve() / "benchmarks/suite/v1/compare.jsonl.gz", "doorplate-compare", "publisher-evaluation", "source-field-supervised", "https://github.com/jeremeybingham/doorplate", "0a2f1fc748f8747d926490288fac38e19421ae44"),
    ("expanded-usa", source / ".cache/us-benchmark-expansion-20261028/kit-v2/parser.corpus.jsonl", "expanded-parser", "development-exposed", "publisher-fixture", "Multi-source US50 + Senzing public US + libpostal C fixtures", "local-audited-kit-v2"),
]
tracks = []
for name, data, kind, split, origin, url, revision in sources:
    manifest = dict(schema="address-benchmark.corpus/v1", id=name, version="1.0.0", country="US", locale="en-US", task="parse", ontology=ONTOLOGY_V2,
        provenance=dict(source=url, upstream_revision=revision, intake_sha256=sha256(data)),
        license=dict(spdx="LicenseRef-AssetSpecific-LocalEvaluation", redistribution="local-only", notice="Consult upstream asset terms; this manifest grants no redistribution rights. Raw assets are neither copied nor published."),
        construction=["Read the explicitly pinned existing publisher/intake asset in place", "GeoSearch inputs are constructed single-space token joins; Doorplate labels are publisher compatibility annotations; expanded keeps original completeness", "Fine byte spans retain upstream offsets or conservative exact input alignment; unresolved alignment is partial, never repaired"],
        annotation_policy="docs/spec/real-corpora.md", exposure=dict(status="public/development-exposed; no universal unseen claim", history=["Existing comparison populations; model-specific training overlap not cleared"]),
        family_policy="Exact-input hash proxy only; independent upstream source families unavailable. Do not interpret this count as independent sampling units.",
        split_policy="Preserve publisher split; exact/family audit does not establish competitor-training non-exposure.",
        resources=[dict(external_path=str(data), sha256=sha256(data), bytes=data.stat().st_size, format=kind, split=split, origin=origin)])
    if args.smoke:
        manifest["row_limit"] = args.smoke
        manifest["exposure"]["status"] = "first-N integration smoke only; not a population estimate"
    write_json(out / "corpora" / (name + ".json"), manifest)
    tracks.append(dict(id=name, corpus="corpora/" + name + ".json", output="results/" + name))

engines = []
def add(name, adapter, config, python=None):
    engines.append(dict(name=name, adapter=adapter, config=config, **({"python": str(python)} if python else {})))

add("rust-learned", "native-batch", dict(name="retained-learned-rust", namespace="usaddress",
    command=[str(native), "project", str(model), retained["artifact"]["sha256"], "{inputs}", "{outputs}", "{metadata}"],
    model_identity=retained["name"] + ":" + retained["artifact"]["sha256"], artifact_files=[str(native), str(model)],
    active_native_roles=gate["candidate_native"]["labels"], role_inventory_basis="retained model export labels, verified by accepted native gate",
    provenance=dict(retained_manifest_sha256=sha256(source / "experiments/us_parser/retained_model.json"), decoder_gate_sha256=sha256(source / ".cache/us-wisconsin-learning-round-20261101/raw28-v1/native-gate-v1/report.json"), production_default=False)))
add("rust-default", "address-normalizer-default", dict(module_path=str(source / "packages/python/python"), model_identity="installed default embedded deterministic engine", provenance=dict(binding="source-preserving parse_record; extension and wrapper hashes recorded")))
boundary = runtime["commands"]["boundaryboys"]["prefix"][0]
require(sha256(boundary) == runtime["pins"][boundary], "BoundaryBoys executable changed")
add("boundaryboys", "native-batch", dict(name="boundaryboys-local-private", namespace="neutral", command=[boundary, "accuracy", "{inputs}", "{outputs}"], artifact_files=[boundary], active_native_roles=["house_number","road","unit","city","state","postcode"], model_identity="embedded dictionary in pinned executable", provenance=dict(**runtime["revisions"]["boundaryboys"], rights="private locally installed executable; no source redistribution")))
add("doorplate", "python-tokens", dict(library="doorplate", model_identity="installed 0.5.0.dev0 public parse + compatibility tokens, null labels retained", active_native_roles=["AddressNumber","StreetName","StreetNamePostType","StreetNamePostDirectional","StreetNamePreDirectional","StreetNamePreType","OccupancyType","OccupancyIdentifier","PlaceName","StateName","ZipCode","BuildingName","Recipient","USPSBoxType","USPSBoxID","USPSBoxGroupType","USPSBoxGroupID"], role_inventory_basis="public compatibility emitter; omitted fine roles remain unsupported", provenance=runtime["revisions"]["doorplate"]), source / ".cache/us-python-library-matrix-20261029/venv/bin/python")
us_labels = json.loads(subprocess.check_output([runtime["commands"]["usaddress"]["prefix"][0], "-B", "-c", "import usaddress,json;print(json.dumps(usaddress.TAGGER.labels()))"],text=True))
for name in ("usaddress", "fastaddress"):
    python = runtime["commands"][name]["prefix"][0]
    add(name, "python-tokens", dict(library=name, model="v1", active_native_roles=us_labels, role_inventory_basis="loaded usaddress CRF labels; fastaddress v1 declares the same upstream model lineage", model_identity="upstream usaddress 0.5.16 CRF lineage; runtime/package/model file hashes recorded"), python)
models = source / ".cache/us-leaderboard-20261028/competitors/models"
library = source / ".cache/us-leaderboard-20261028/competitors/libpostal-install/lib/libpostal.1.dylib"
for name in ("default", "senzing"):
    folder = models / name
    if (folder / "libpostal").is_dir():
        folder /= "libpostal"
    files = [library] + [p for p in sorted(folder.rglob("*")) if p.is_file()]
    add("libpostal-" + name, "libpostal", dict(name="libpostal-" + name, library=str(library), data_dir=str(folder), artifact_files=list(map(str, files)), active_native_roles=["house","category","near","house_number","road","unit","level","staircase","entrance","po_box","postcode","suburb","city_district","city","island","state_district","state","country_region","country","world_region"], model_identity="libpostal model=" + name))

node, _, mail_runtime = runtime["commands"]["mailwoman"]["prefix"]
mail_files = [p for p in sorted(Path(mail_runtime).rglob("*")) if p.is_file() and p.suffix != ".pyc" and "__pycache__" not in p.parts]
bridge = project / "adapters/mailwoman_batch.mjs"
meta = adapter_metadata("mailwoman-neural-10.7.0", "neutral", dict(artifact_files=[node, str(bridge), *map(str, mail_files)], model_identity="@mailwoman/neural-weights-en-us@10.7.0; CPU; one intra-op thread", provenance=dict(api="createRuntimePipeline + treeToParseMatches + toLibpostalComponents; native tree retained")))
meta["role_map"].update(MAILWOMAN_EMITTER_MAP)
meta["supported_roles"] = sorted({v for v in meta["role_map"].values() if v is not None})
meta["mapping_version"] = "mailwoman-emitter-native/v1"
meta["dependency_versions"] = {name: read_json(Path(mail_runtime) / "node_modules" / name / "package.json")["version"] for name in ("mailwoman", "@mailwoman/neural", "@mailwoman/neural-weights-en-us", "@mailwoman/libpostal")}
meta["provenance"]["node_version"] = subprocess.check_output([node, "--version"], text=True).strip()
card = read_json(Path(mail_runtime) / "node_modules/@mailwoman/neural-weights-en-us/model-card.json")
emitted = {"region":"state","locality":"city","dependent_locality":"suburb","subregion":"state_district","venue":"house","street":"road","intersection_a":"road","intersection_b":"road"}
native_tags = {tag[2:] for tag in card["labels"] if tag.startswith(("B-", "I-"))}
active_mail_roles = sorted({meta["role_map"][emitted.get(tag,tag)] for tag in native_tags if meta["role_map"].get(emitted.get(tag,tag)) is not None})
add("mailwoman", "adapters.mailwoman_batch:Factory", dict(name="mailwoman-neural", namespace="neutral", command=[node, str(bridge), mail_runtime, "{inputs}", "{outputs}"],
    artifact_files=meta["artifact_files"], model_identity=meta["model"], provenance=meta["provenance"], dependency_versions=meta["dependency_versions"], active_roles=active_mail_roles, accuracy_workers=4))
write_json(out / "engines.json", engines)
write_json(out / "plan.json", dict(schema="address-benchmark.plan/v1", name="production-parsing-comparison", engines="engines.json", tracks=tracks,
    execution=dict(baseline="rust-learned", timing=False, timeout=3600)))
print(json.dumps(dict(plan=str(out / "plan.json"), engines=[e["name"] for e in engines], tracks=[t["id"] for t in tracks], smoke=args.smoke)))
