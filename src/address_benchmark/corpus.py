"""Pinned corpus manifests, conservative admission checks, and overlap audits."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import urllib.request

from .io import digest_bytes, read_json, read_jsonl, require, sha256, within
from .protocol import FINE_TO_COARSE, ONTOLOGY, PARSE_ONTOLOGIES, TASK_ONTOLOGIES, Request, check_spans, request_hash, check_payload
from . import ontologies

CORPUS = "address-benchmark.corpus/v1"


def check_manifest(manifest):
    require(manifest.get("schema") == CORPUS, "corpus schema differs")
    for key in ("id", "version", "country", "locale", "task", "provenance", "license", "construction",
                "ontology", "annotation_policy", "exposure", "resources", "split_policy", "family_policy"):
        require(key in manifest, f"missing corpus field: {key}")
    require(manifest["task"] in TASK_ONTOLOGIES, "unsupported corpus task")
    require(manifest["ontology"] in PARSE_ONTOLOGIES if manifest["task"] == "parse" else manifest["ontology"] == TASK_ONTOLOGIES[manifest["task"]], "unsupported corpus ontology/task")
    require(manifest["country"] == "US", "v1 ontology is US only; add a versioned locale ontology before admitting others")
    require(manifest["task"] == "parse" or isinstance(manifest.get("profile"), str) and manifest["profile"], "named task profile required")
    require(manifest["provenance"].get("upstream_revision") and manifest["provenance"].get("source"), "source revision required")
    require(manifest["license"].get("spdx") and manifest["license"].get("redistribution") in ("allowed", "local-only"), "explicit license/redistribution policy required")
    require(isinstance(manifest["construction"], list) and manifest["construction"], "construction history required")
    require(manifest["exposure"].get("status") and isinstance(manifest["exposure"].get("history"), list), "exposure history required")
    require(isinstance(manifest["resources"], list) and manifest["resources"], "resources required")
    if "row_limit" in manifest:
        require(type(manifest["row_limit"]) is int and manifest["row_limit"] > 0, "positive explicit integration row limit required")
    for resource in manifest["resources"]:
        require(set(resource) <= {"path", "external_path", "sha256", "url", "bytes", "format", "split", "origin", "coverage"}, "unsupported resource field")
        require(("path" in resource) != ("external_path" in resource), "one resource location required")
        if "external_path" in resource:
            require(manifest["license"]["redistribution"] == "local-only" and Path(resource["external_path"]).is_absolute(), "external corpus paths require explicit local-only policy")
        if "coverage" in resource:
            require(manifest["task"] == "parse" and resource["coverage"] == "partial", "resource coverage override may only downgrade parsing references to partial")
        require(isinstance(resource.get("sha256"), str) and len(resource["sha256"]) == 64
                and all(x in "0123456789abcdef" for x in resource["sha256"]), "SHA-256 pin required")


def check_reference(reference, text, task="parse"):
    require(reference.get("coverage") in ("complete", "partial", "none"), "explicit reference coverage required")
    if task != "parse":
        require(reference["coverage"] in ("complete", "none"), "non-parse tasks require complete or absent references")
        if task in ("normalize", "format"):
            require(isinstance(reference.get("values"), list) and all(isinstance(x, str) for x in reference["values"]), "ordered normalized values required")
            require(reference["coverage"] != "none" or not reference["values"], "unlabeled normalization contains values")
        elif task == "match":
            require(type(reference.get("same_entity")) is bool if reference["coverage"] == "complete" else reference.get("same_entity") is None, "independent pair identity assertion required")
            require(reference.get("label_basis") and reference.get("entity_level") == "delivery-unit", "explicit identity level and annotation basis required")
        elif task == "stability":
            checks = reference.get("checks")
            require(isinstance(checks, list) and checks and len(checks) == len(set(checks))
                    and set(checks) <= {"repeat", "scalar_batch", "idempotence", "scalar_stream", "scalar_chunked"}, "explicit supported stability checks required")
        elif task == "variants":
            require(all(isinstance(reference.get(key), list) and all(isinstance(x, str) for x in reference[key]) for key in ("required", "allowed")), "variant assertion lists required")
            require(set(reference["required"]) <= set(reference["allowed"]), "required variants outside permitted inventory")
        else:
            require("expected" in reference, "typed expected task output required")
        return
    fields = reference.get("fields")
    require(isinstance(fields, dict), "reference fields required")
    for role, values in fields.items():
        require(role in set(FINE_TO_COARSE.values()), "unknown coarse reference role")
        require(isinstance(values, list) and all(isinstance(x, str) for x in values), "field values must be ordered strings")
    for kind in ("spans", "tokens"):
        coverage = reference.get(kind + "_coverage")
        require(coverage in ("complete", "partial", "none"), f"explicit {kind} coverage required")
        require(isinstance(reference.get(kind), list), f"{kind} list required")
        require(coverage != "none" or not reference[kind], "unlabeled fine layer contains labels")
        seen = set()
        for item in reference[kind]:
            require(item.get("role") in FINE_TO_COARSE, "unknown fine reference role")
            check_spans([item.get("span")], text)
            key = (item["role"], *item["span"])
            require(key not in seen, "duplicate fine annotation")
            seen.add(key)
    if reference["coverage"] == "none":
        require(not fields and all(reference[k + "_coverage"] == "none" for k in ("spans", "tokens")), "unlabeled row contains reference")
    elif reference["coverage"] == "partial":
        require(fields, "partial coarse coverage needs supplied fields")


def load_corpus(path):
    path = Path(path).resolve()
    manifest = read_json(path)
    check_manifest(manifest)
    rows, seen = [], set()
    for resource in manifest["resources"]:
        data = Path(resource["external_path"]).resolve() if "external_path" in resource else within(path.parent, resource["path"])
        require(data.is_file(), f"dataset unavailable: {data}; use fetch with the pinned manifest")
        require(sha256(data) == resource["sha256"], "corpus resource hash differs")
        if "bytes" in resource:
            require(data.stat().st_size == resource["bytes"], "corpus byte count differs")
        if resource.get("format"):
            from .intake import records
            iterator = records(data, resource, manifest)
        else:
            iterator = read_jsonl(data)
        for row in iterator:
            if manifest.get("row_limit") is not None and len(rows) >= manifest["row_limit"]:
                break
            require(isinstance(row.get("id"), str) and row["id"] and row["id"] not in seen, "missing/duplicate corpus ID")
            seen.add(row["id"])
            if resource.get("coverage") == "partial":
                row["reference"]["coverage"] = "partial"
                for layer in ("tokens", "spans"):
                    if row["reference"][layer + "_coverage"] == "complete":
                        row["reference"][layer + "_coverage"] = "partial"
            require(isinstance(row.get("text"), str), "address text must be a string")
            for key in ("family", "split", "origin"):
                require(isinstance(row.get(key), str) and row[key], f"row {key} required")
            require(row["origin"] in ("natural", "authored", "generated", "source-field-supervised", "publisher-fixture"), "unknown input origin")
            require(isinstance(row.get("subsets"), list) and all(isinstance(x, str) and x for x in row["subsets"]), "subsets must be names")
            require(len(row["subsets"]) == len(set(row["subsets"])), "duplicate subset membership")
            require(isinstance(row.get("other_text"), str) if manifest["task"] == "match" else row.get("other_text") is None, "pair input differs from task")
            require(row.get("payload") is None or isinstance(row["payload"], dict), "input payload must be object/null")
            check_payload(manifest["task"], row.get("payload"))
            if manifest["task"] == "format":
                require(isinstance(row.get("payload", {}).get("fields"), list), "format requires ordered structured fields, not implicit reparsing")
                require(all(isinstance(field, dict) and set(field) == {"role", "value"} and isinstance(field["role"], str) and isinstance(field["value"], str) for field in row["payload"]["fields"]), "literal role/value fields required")
            if manifest["task"] == "stability":
                require(isinstance(row.get("payload", {}).get("texts"), list) and row["payload"]["texts"] and all(isinstance(x, str) for x in row["payload"]["texts"]), "stability requires input text list")
            check_reference(row["reference"], row["text"], manifest["task"])
            rows.append(row)
    require(rows, "corpus has no inputs")
    audit = audit_corpora([(manifest["id"], rows)])
    require(not audit["cross_split_exact"] and not audit["cross_split_families"], "heldout split leakage detected; inspect corpus audit")
    return manifest, rows, audit


def input_requests(manifest, rows):
    return [Request(row["id"], row["text"], request_hash(row["text"], row.get("other_text"), row.get("payload")),
                    manifest["country"], manifest["locale"], manifest["task"], manifest.get("profile", ""), row.get("other_text"), row.get("payload")) for row in rows]


def audit_corpora(corpora):
    exact, families, views = defaultdict(list), defaultdict(list), defaultdict(set)
    total = 0
    for corpus_id, rows in corpora:
        for row in rows:
            total += 1
            item = dict(corpus=corpus_id, id=row["id"], split=row["split"], family=row["family"])
            exact[request_hash(row["text"], row.get("other_text"), row.get("payload"))].append(item)
            families[row["family"]].append(item)
            for subset in row["subsets"]:
                views[(corpus_id, subset)].add(row["id"])
    duplicates = [{"input_sha256": key, "members": members} for key, members in sorted(exact.items()) if len(members) > 1]
    cross_exact = [item for item in duplicates if len({m["split"] for m in item["members"]}) > 1]
    cross_family = [{"family": key, "members": members} for key, members in sorted(families.items())
                    if len({m["split"] for m in members}) > 1]
    keys = sorted(views)
    overlaps = [dict(left=list(a), right=list(b), shared_rows=len(views[a] & views[b]))
                for i, a in enumerate(keys) for b in keys[i + 1:] if a[0] == b[0] and views[a] & views[b]]
    return dict(schema="address-benchmark.overlap/v1", rows=total, distinct_exact_inputs=len(exact),
                distinct_source_families=len(families), exact_duplicates=duplicates,
                cross_split_exact=cross_exact, cross_split_families=cross_family,
                subset_overlaps=overlaps, method="exact UTF-8 SHA-256 plus declared global family IDs; no fuzzy/geographic overlap proof")


def fetch(path, *, max_bytes=256 * 1024 * 1024):
    """Explicit opt-in, no extraction or code execution, hash-before-install download."""
    path = Path(path).resolve()
    manifest = read_json(path)
    check_manifest(manifest)
    installed = []
    for resource in manifest["resources"]:
        require("external_path" not in resource, "external local-only resources are supplied locally, never fetched")
        target = within(path.parent, resource["path"])
        if target.exists():
            require(sha256(target) == resource["sha256"], "existing resource hash differs; refusing overwrite")
            continue
        url = resource.get("url", "")
        require(url.startswith("https://"), "missing HTTPS resource URL; supply private/local dataset yourself")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".partial")
        owned = False
        try:
            with urllib.request.urlopen(url, timeout=30) as response, temporary.open("xb") as output:
                owned = True
                require(response.geturl().startswith("https://"), "HTTPS redirect required")
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    require(size <= max_bytes, "download size limit exceeded")
                    output.write(chunk)
            require(sha256(temporary) == resource["sha256"], "download hash differs")
            if "bytes" in resource:
                require(size == resource["bytes"], "download byte count differs")
            # Exclusive link prevents overwriting a file installed concurrently.
            import os
            os.link(temporary, target)
            installed.append(resource["path"])
        finally:
            # Only delete the temporary file this invocation successfully opened.
            if owned:
                temporary.unlink(missing_ok=True)
    return installed
