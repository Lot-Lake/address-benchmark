"""Build ORIGINAL fictional conformance data. No upstream cases or caches read.

Run from the repository root with PYTHONPATH=src. Editing definitions changes
corpus identity: bump the corpus version before publishing a revised freeze.
"""
from pathlib import Path
import json

from address_benchmark.io import canonical, sha256
from address_benchmark.protocol import FINE_TO_COARSE, ONTOLOGY, NORMALIZE_ONTOLOGY, MATCH_ONTOLOGY, TASK_ONTOLOGIES

ROOT = Path(__file__).resolve().parents[1] / "examples" / "corpora"


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def emit(name, rows, *, task="parse", ontology=ONTOLOGY, profile=None, description=""):
    directory = ROOT / name
    directory.mkdir(parents=True, exist_ok=True)
    data = directory / "cases.jsonl"
    data.write_bytes(b"".join(canonical(row) + b"\n" for row in rows))
    manifest = dict(schema="address-benchmark.corpus/v1", id=name, version="1.0.0", country="US", locale="en-US", task=task,
        ontology=ontology, provenance=dict(source="Original address-benchmark contributor-authored fictional fixtures", upstream_revision="authored-v1", source_sha256=sha256(__file__)),
        license=dict(spdx="MIT", redistribution="allowed", notice="Original fictional examples, licensed with this repository. No upstream rows, private listings, or real delivery claims."),
        construction=["Compose original fixture inputs and explicit task annotations in tools/author_corpora.py", "For parsing, derive UTF-8 byte offsets from literal manually assigned tokens; no parser or gold-selected engine used", description],
        annotation_policy="docs/spec/annotations.md#authored-v1", exposure=dict(status="public-conformance-development-exposed", history=["Authored and used for implementation/tests; not independent heldout evidence"]),
        split_policy="All rows are conformance; future heldouts require separate custody and family/exact-overlap audit.",
        family_policy="Globally namespaced authored source families; rendering siblings retain the same family.",
        resources=[dict(path="cases.jsonl", sha256=sha256(data), bytes=data.stat().st_size)])
    if profile:
        manifest["profile"] = profile
    save(directory / "manifest.json", manifest)


def parse_row(name, text, annotations, *, partial=None, subsets=(), origin="authored", family=None):
    evidence, fine, offset = [], [], 0
    for value, role in annotations:
        start = text.index(value, offset)
        stop = start + len(value)
        span = [len(text[:start].encode("utf-8")), len(text[:stop].encode("utf-8"))]
        fine.append(dict(role=role, span=span))
        evidence.append((role, value))
        offset = stop
    fields, previous = {}, None
    for role, value in evidence:
        coarse = FINE_TO_COARSE[role]
        if coarse == previous:
            fields[coarse][-1] += " " + value
        else:
            fields.setdefault(coarse, []).append(value)
        previous = coarse
    if partial:
        fields = {role: fields[role] for role in partial}
        fine = [x for x in fine if FINE_TO_COARSE[x["role"]] in partial]
    return dict(id=name, text=text, family=family or "address-benchmark:" + name, split="conformance", origin=origin, subsets=list(subsets),
        reference=dict(coverage="partial" if partial else "complete", fields=fields, spans=fine, tokens=fine,
                       spans_coverage="partial" if partial else "complete", tokens_coverage="partial" if partial else "complete"))


def ordinary(name, number, road, city, state, postcode, **kwargs):
    text = f"{number} {road}, {city}, {state} {postcode}"
    road_tokens = road.split()
    annotations = [(number, "house_number")] + [(v, "road_type" if i == len(road_tokens) - 1 else "road_name") for i, v in enumerate(road_tokens)]
    annotations += [(v, "city") for v in city.split()] + [(state, "state"), (postcode, "postcode")]
    return parse_row(name, text, annotations, **kwargs)


core = [
    ordinary("core-01", "12", "Alder St", "Exampleville", "NY", "00123", subsets=["postal", "leading-zero"]),
    ordinary("core-02", "7", "Café Ave", "Sampleton", "CA", "90210", subsets=["unicode"]),
    ordinary("core-03", "21", "Silver Birch Rd", "North Example", "ME", "00047", subsets=["multiword", "leading-zero"]),
    ordinary("core-04", "008", "Willow St.", "Test Harbor", "MA", "01234-0007", subsets=["punctuation", "leading-zero"]),
    ordinary("core-05", "64", "St. Elmo St.", "Spec City", "TX", "75000", subsets=["fine-role-contrast", "punctuation"]),
    ordinary("core-06", "19", "Lark Ave.", "New Sample", "OH", "44000", subsets=["postal"]),
    ordinary("core-07", "53", "Juniper Rd.", "Mock Falls", "WA", "98000", subsets=["postal"]),
    ordinary("core-08", "82", "Maple St", "Fixture Bay", "OR", "97000", subsets=["postal"]),
]
emit("us-core", core, description="Eight authored basic forms; no claim of natural sampling, postal validity, or independent accuracy.")

challenge_specs = [
    ("grid", "N 42 W 19 Fir Rd, Trial City, WI 53000", [("N", "house_number_prefix"), ("42", "house_number"), ("W", "house_number_prefix"), ("19", "house_number"), ("Fir", "road_name"), ("Rd", "road_type"), ("Trial", "city"), ("City", "city"), ("WI", "state"), ("53000", "postcode")]),
    ("suffix", "12 A Cedar St, Trial City, WI 53001", [("12", "house_number"), ("A", "house_number_suffix"), ("Cedar", "road_name"), ("St", "road_type"), ("Trial", "city"), ("City", "city"), ("WI", "state"), ("53001", "postcode")]),
    ("unit", "16 Spruce Rd Apt 4, Exampleville, NY 00124", [("16", "house_number"), ("Spruce", "road_name"), ("Rd", "road_type"), ("Apt", "unit_type"), ("4", "unit_id"), ("Exampleville", "city"), ("NY", "state"), ("00124", "postcode")]),
    ("bare-unit", "17 Spruce Rd 4B, Exampleville, NY 00125", [("17", "house_number"), ("Spruce", "road_name"), ("Rd", "road_type"), ("4B", "unit_id"), ("Exampleville", "city"), ("NY", "state"), ("00125", "postcode")]),
    ("recipient", "Example Recipient\n18 Aspen Ave\nMockville NY 00126", [("Example", "recipient"), ("Recipient", "recipient"), ("18", "house_number"), ("Aspen", "road_name"), ("Ave", "road_type"), ("Mockville", "city"), ("NY", "state"), ("00126", "postcode")]),
    ("box", "PO Box 031, Spec City, VT 00031", [("PO", "po_box"), ("Box", "po_box"), ("031", "po_box"), ("Spec", "city"), ("City", "city"), ("VT", "state"), ("00031", "postcode")]),
    ("hierarchy", "Demo Building Fl 2 Apt 9, 20 Elm St, Spec City, VT 00032", [("Demo", "building"), ("Building", "building"), ("Fl", "level"), ("2", "level"), ("Apt", "unit_type"), ("9", "unit_id"), ("20", "house_number"), ("Elm", "road_name"), ("St", "road_type"), ("Spec", "city"), ("City", "city"), ("VT", "state"), ("00032", "postcode")]),
    ("intersection", "Alder St & Birch Ave, Demo City, OR 97001", [("Alder", "road_name"), ("St", "road_type"), ("&", "intersection"), ("Birch", "road_name"), ("Ave", "road_type"), ("Demo", "city"), ("City", "city"), ("OR", "state"), ("97001", "postcode")]),
    ("repeated", "Apt 2, 44 Hazel Rd, Apt 7, Demo City, OR 97002", [("Apt", "unit_type"), ("2", "unit_id"), ("44", "house_number"), ("Hazel", "road_name"), ("Rd", "road_type"), ("Apt", "unit_type"), ("7", "unit_id"), ("Demo", "city"), ("City", "city"), ("OR", "state"), ("97002", "postcode")]),
    ("direction", "46 N Fern St W, Demo City, OR 97003", [("46", "house_number"), ("N", "road_direction"), ("Fern", "road_name"), ("St", "road_type"), ("W", "road_direction"), ("Demo", "city"), ("City", "city"), ("OR", "state"), ("97003", "postcode")]),
    ("delivery", "General Delivery, Trial Bay, AK 99001", [("General", "po_box"), ("Delivery", "po_box"), ("Trial", "city"), ("Bay", "city"), ("AK", "state"), ("99001", "postcode")]),
    ("locality", "Sample Cove, PR 00048", [("Sample", "city"), ("Cove", "city"), ("PR", "state"), ("00048", "postcode")]),
]
challenge = [parse_row("challenge-" + name, text, labels, subsets=[name, "challenge"]) for name, text, labels in challenge_specs]
challenge += [ordinary("challenge-partial", "90", "Partial St", "Unknownville", "NY", "00129", partial=["postcode"], subsets=["partial-reference"])]
emit("us-challenge", challenge, description="Thirteen authored challenges: repeated/nonadjacent occurrences, affixes, units, hierarchy, intersection, locality-only, punctuation, Unicode, partial labels. Ambiguous interpretations are policy fixtures, not natural ground truth.")

generated = []
for index in range(6):
    row = ordinary(f"generated-{index}-base", str(301 + index), f"Rendered{index} St", "Template Town", "NY", f"004{index:02}", origin="source-field-supervised", family=f"address-benchmark:generated-family-{index}", subsets=["source-field-supervised"])
    generated.append(row)
    for style in ("upper", "lower", "spaces"):
        if style == "upper":
            text = row["text"].upper()
        elif style == "lower":
            text = row["text"].lower()
        else:
            text = row["text"].replace(" ", "  ")
        labels = []
        for item in row["reference"]["tokens"]:
            a, b = item["span"]
            token = row["text"].encode()[a:b].decode()
            labels.append((token.upper() if style == "upper" else token.lower() if style == "lower" else token, item["role"]))
        generated.append(parse_row(f"generated-{index}-{style}", text, labels, origin="source-field-supervised", family=row["family"], subsets=[style, "source-field-supervised"]))
emit("us-rendered", generated, description="24 source-field-supervised renderings from six fictional families; neither 24 independent families nor naturally typed addresses.")

normalizations = []
for i, text in enumerate(["  12 alder Street  apt 04,  Exampleville NY 00123  ", "7 Café Ave.\nSampleton CA 90210", "PO Box 0003", "12A  Fern Rd", "", "St. Éloi AVE", "12 Rd Apt 03", "12 RD APT 3"]):
    expected = ["12 ALDER STREET APT 04, EXAMPLEVILLE NY 00123", "7 CAFÉ AVE. SAMPLETON CA 90210", "PO BOX 0003", "12A FERN RD", "", "ST. ÉLOI AVE", "12 RD APT 03", "12 RD APT 3"][i]
    normalizations.append(dict(id=f"normalize-{i}", text=text, family=f"address-benchmark:normalize-{i}", split="conformance", origin="authored", subsets=["canonical-profile"], reference=dict(coverage="complete", values=[expected])))
emit("us-normalization", normalizations, task="normalize", ontology=NORMALIZE_ONTOLOGY, profile="address-benchmark.uppercase-whitespace/v1", description="Exact named-profile examples: punctuation, accents and leading zeros preserved; not USPS certification.")

pairs = [
    ("12 Alder Street Apt 4, Exampleville NY 00123", "12 ALDER ST APARTMENT 4 EXAMPLEVILLE NY 00123", True, "alias"),
    ("12 Alder St Apt 4", "12 Alder St Apt 5", False, "unit-contrast"),
    ("12 Alder St", "13 Alder St", False, "number-contrast"),
    ("12 Alder St, Spec City NY 00123", "12 Alder St Spec City NY 01230", False, "postcode-contrast"),
    ("9 Cedar Rd.", "9 CEDAR ROAD", True, "punctuation"),
    ("PO Box 003", "PO BOX 3", False, "leading-zero-policy"),
    ("18 Café Ave", "18 CAFÉ AVENUE", True, "unicode"),
    ("18 Café Ave", "18 Cafe Ave", False, "accent-policy"),
    ("17 Fern St Apt 03", "17 Fern St Apt 3", False, "unit-width-policy"),
    ("42 N Larch Rd", "42 S Larch Rd", False, "direction-contrast"),
]
matching = [dict(id=f"match-{i}", text=a, other_text=b, family=f"address-benchmark:identity-{i}", split="conformance", origin="authored", subsets=[subset],
                reference=dict(coverage="complete", same_entity=same, entity_level="delivery-unit", label_basis="independent authored fictional identity/contrast; width/accent distinctions are this fixture policy, not universal identity law")) for i, (a, b, same, subset) in enumerate(pairs)]
emit("us-identity", matching, task="match", ontology=MATCH_ONTOLOGY, profile="address-benchmark.delivery-unit-key-equality/v1", description="Ten independently declared same/distinct delivery-unit pairs, not labels derived from an engine's keys. No prevalence/precision claim for real listings.")


def utility_row(task, index, text, reference, payload=None):
    row = dict(id=f"{task}-{index}", text=text, family=f"address-benchmark:{task}-{index}", split="conformance", origin="authored", subsets=[task], reference=dict(coverage="complete", **reference))
    if payload is not None:
        row["payload"] = payload
    return row


utility_cases = {
    "format": [
        utility_row("format", 0, "", dict(values=["12 Alder St\nApt 004\nExampleville NY 00123"]), dict(fields=[dict(role="line1", value="12 Alder St"), dict(role="line2", value="Apt 004"), dict(role="last_line", value="Exampleville NY 00123")])),
        utility_row("format", 1, "", dict(values=["PO Box 0003\nTrial Bay AK 99001"]), dict(fields=[dict(role="line1", value="PO Box 0003"), dict(role="last_line", value="Trial Bay AK 99001")])),
    ],
    "classify": [utility_row("classify", i, text, dict(expected=expected)) for i, (text, expected) in enumerate([("PO Box 018", "po_box"), ("Alder St & Cedar Ave", "intersection"), ("12 Lark Rd", "street"), ("", "unknown")])],
    "extract": [utility_row("extract", i, text, dict(expected=expected)) for i, (text, expected) in enumerate([("0012 Alder St", "0012"), ("14A Spruce Rd", "14A"), ("12 1/2 Fir St", "12 1/2"), ("PO Box 012", None), ("Alder St", None)])],
    "infer": [utility_row("infer", i, text, dict(expected={"state": expected})) for i, (text, expected) in enumerate([("10001", "NY"), ("90210", "CA"), ("not-a-zip", None)])],
    "variants": [utility_row("variants", 0, "12 Alder St Apt 004", dict(required=["12 Alder St Apt 004"], allowed=["12 Alder St Apt 004", "12 ALDER ST APT 004"]))],
    "diagnostics": [utility_row("diagnostics", i, text, dict(expected={"empty_input": empty, "deliverability": "not_checked"})) for i, (text, empty) in enumerate([("", True), ("   ", True), ("12 Mock St", False)])],
    "stability": [utility_row("stability", 0, "", dict(checks=["repeat", "scalar_batch", "idempotence", "scalar_stream", "scalar_chunked"]), dict(texts=[" 12 Alder st  ", "7 Café Ave.", "PO Box 0004", "12 Rd Apt 03", "Odd trailing input"]))],
}
for task, cases in utility_cases.items():
    emit("us-" + task, cases, task=task, ontology=TASK_ONTOLOGIES[task], profile=f"address-benchmark.authored-{task}/v1",
         description="Original task contract controls only. Named authored profile, not external certification or population quality evidence.")

if __name__ == "__main__":
    print("Authored corpus freezes written; review changes before publication.")
