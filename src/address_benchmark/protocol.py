"""Executable v1 protocol checks. Gold never enters an adapter Request."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .io import digest_bytes, identity, require

PROTOCOL = "address-benchmark.adapter/v1"
PREDICTION = "address-benchmark.prediction/v1"
ONTOLOGY = "address-benchmark.us-roles/v1"
NORMALIZE_ONTOLOGY = "address-benchmark.normalized-text/v1"
MATCH_ONTOLOGY = "address-benchmark.delivery-unit-identity/v1"
PARSE_ONTOLOGIES = (ONTOLOGY, "address-benchmark.us-roles/v2")
TASK_ONTOLOGIES = {"parse": ONTOLOGY, "normalize": NORMALIZE_ONTOLOGY, "match": MATCH_ONTOLOGY}
TASK_ONTOLOGIES.update({task: "address-benchmark.utility-output/v1" for task in ("format", "classify", "extract", "infer", "variants", "diagnostics", "stability")})
FINE_TO_COARSE = {
    "house_number": "house_number", "house_number_prefix": "house_number",
    "house_number_suffix": "house_number", "road": "road", "road_name": "road",
    "road_type": "road", "road_direction": "road", "unit": "unit",
    "unit_type": "unit", "unit_id": "unit", "city": "city", "state": "state",
    "postcode": "postcode", "country": "country", "recipient": "recipient",
    "building": "building", "level": "level", "po_box": "po_box",
    "subaddress": "subaddress", "district": "district", "intersection": "intersection",
    "not_address": "not_address",
}


@dataclass(frozen=True)
class Request:
    id: str
    text: str
    input_sha256: str
    country: str
    locale: str
    task: str = "parse"
    profile: str = ""
    other_text: str | None = None
    payload: dict | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        require(set(value) == set(cls.__dataclass_fields__), "input-only request keys differ")
        require(all(isinstance(v, str) for k, v in value.items() if k not in ("other_text", "payload")), "request values must be strings")
        require(value["payload"] is None or isinstance(value["payload"], dict), "input payload must be an object or null")
        require(value["task"] in TASK_ONTOLOGIES, "unsupported task")
        require(value["id"] and value["country"] == "US" and value["locale"], "unsupported country or empty request identity/locale")
        check_payload(value["task"], value["payload"])
        require(isinstance(value["other_text"], str) if value["task"] == "match" else value["other_text"] is None, "task-specific pair input differs")
        require(value["input_sha256"] == request_hash(value["text"], value["other_text"], value["payload"]), "input hash differs")
        require(value["task"] == "parse" or value["profile"], "named profile required")
        return cls(**value)


def check_payload(task, payload):
    if task == "format":
        require(isinstance(payload, dict) and set(payload) == {"fields"} and isinstance(payload["fields"], list), "format payload has only public input fields")
        require(all(isinstance(field, dict) and set(field) == {"role", "value"} and all(isinstance(x, str) for x in field.values()) for field in payload["fields"]), "literal role/value fields required")
    elif task == "stability":
        require(isinstance(payload, dict) and set(payload) == {"texts"} and isinstance(payload["texts"], list) and payload["texts"]
                and all(isinstance(x, str) for x in payload["texts"]), "stability payload has only public input texts")
    else:
        require(payload is None, "this task accepts text inputs only, no arbitrary payload")


def request_hash(text, other_text=None, payload=None):
    if payload is not None:
        return identity({"text": text, "other_text": other_text, "payload": payload})
    return digest_bytes(text.encode("utf-8")) if other_text is None else identity({"text": text, "other_text": other_text})


class Adapter(Protocol):
    metadata: dict[str, Any]

    def parse(self, request: Request) -> dict[str, Any]: ...


def check_metadata(metadata):
    from . import ontologies  # Register the additive fine-role v2 inventory.
    require(isinstance(metadata, dict) and metadata.get("protocol") == PROTOCOL, "adapter protocol differs")
    required = ("name", "version", "ontology", "mapping_version", "role_map", "supported_roles",
                "runtime", "model", "dependency_versions", "threading", "ownership", "tasks",
                "span_support", "token_support")
    require(all(key in metadata for key in required), "incomplete adapter metadata")
    require(isinstance(metadata["tasks"], list) and len(metadata["tasks"]) == 1 and metadata["tasks"][0] in TASK_ONTOLOGIES, "one supported task per adapter configuration required")
    require(metadata["ontology"] in PARSE_ONTOLOGIES if metadata["tasks"] == ["parse"] else metadata["ontology"] == TASK_ONTOLOGIES[metadata["tasks"][0]], "unsupported ontology/task")
    mapping = metadata["role_map"]
    require(isinstance(mapping, dict) and all(isinstance(k, str) and (v is None or v in FINE_TO_COARSE)
                                           for k, v in mapping.items()), "invalid explicit role mapping")
    require(isinstance(metadata["supported_roles"], list), "supported_roles must be a list")
    require(set(metadata["supported_roles"]) == {v for v in mapping.values() if v is not None}, "supported_roles differs from mapping")
    if "active_roles" in metadata:
        require(isinstance(metadata["active_roles"], list) and set(metadata["active_roles"]) <= set(metadata["supported_roles"]), "active model/API roles must be expressible by the declared mapping")
    require(all(type(metadata[k]) is bool for k in ("span_support", "token_support")), "explicit fine capabilities required")
    if metadata["tasks"] != ["parse"]:
        require(isinstance(metadata.get("profiles"), list) and metadata["profiles"] and all(isinstance(x, str) and x for x in metadata["profiles"]), "supported task profiles required")


def check_spans(spans, text):
    require(isinstance(spans, list) and spans, "nonempty span list required")
    raw, end = text.encode("utf-8"), 0
    for span in spans:
        require(isinstance(span, list) and len(span) == 2 and all(type(x) is int for x in span), "span needs integer byte offsets")
        start, stop = span
        require(0 <= start < stop <= len(raw) and start >= end, "invalid/overlapping source spans")
        # A nonempty UTF-8 slice decodes iff both ends are codepoint boundaries.
        raw[start:stop].decode("utf-8")
        end = stop


def check_prediction(prediction, request, metadata):
    require(isinstance(prediction, dict), "prediction object required")
    require(prediction.get("schema") == PREDICTION, "prediction schema differs")
    require(prediction.get("id") == request.id and prediction.get("input_sha256") == request.input_sha256, "prediction identity/order differs")
    require(prediction.get("status") in ("ok", "error", "refused"), "explicit prediction status required")
    require(request.task in metadata["tasks"], "adapter task differs from request")
    require("native" in prediction, "native output required for audit")
    require(isinstance(prediction.get("evidence"), list), "ordered evidence list required")
    for layer in ("inferred", "normalized"):
        require(isinstance(prediction.get(layer), list), f"separate {layer} layer required")
    if request.task != "parse":
        require(request.profile in metadata["profiles"], "adapter does not support requested profile")
        require(not prediction["evidence"] and not prediction.get("tokens"), "task cannot present transformed values as parsed evidence")
        require(prediction.get("profile") == request.profile, "output profile differs")
        if request.task in ("normalize", "format"):
            require(all(isinstance(x, str) for x in prediction["normalized"]), "normalized strings required")
        elif request.task == "match":
            keys = prediction.get("keys")
            valid = isinstance(keys, list) and len(keys) == 2 and all(isinstance(x, str) and x for x in keys) if prediction["status"] == "ok" else keys == []
            require(valid, "matching needs two nonempty native comparison keys")
        else:
            require("result" in prediction, "task-specific native result required")
    else:
        require(not prediction["normalized"], "normalization belongs to a distinct task")
    if prediction["status"] != "ok":
        require(isinstance(prediction.get("message"), str) and prediction["message"], "failure reason required")
        require(not prediction["evidence"], "failed rows cannot supply scored evidence")
        require(not prediction["normalized"], "failed rows cannot commit normalized output")
        require(prediction.get("result") is None, "failed rows cannot commit utility output")
    require(isinstance(prediction.get("tokens"), list), "separate native token list required")
    if prediction["status"] != "ok":
        require(not prediction["tokens"], "failed rows cannot supply scored tokens")
    for item in prediction["evidence"] + prediction["tokens"]:
        require(isinstance(item, dict) and isinstance(item.get("native_role"), str)
                and isinstance(item.get("value"), str), "native role/value strings required")
        require(item["native_role"] in metadata["role_map"], "undeclared native role: " + item["native_role"])
        if item.get("spans") is not None:
            check_spans(item["spans"], request.text)
    for token in prediction["tokens"]:
        require(isinstance(token.get("spans"), list) and len(token["spans"]) == 1, "token needs one native source span")
    return prediction


def prediction(request, evidence=(), *, tokens=(), native=None, status="ok", message=None):
    result = dict(schema=PREDICTION, id=request.id, input_sha256=request.input_sha256,
                  status=status, evidence=list(evidence), tokens=list(tokens), inferred=[], normalized=[], native=native)
    if message:
        result["message"] = message
    if request.task != "parse":
        result["profile"] = request.profile
    if request.task == "match":
        result["keys"] = []
    if request.task not in ("parse", "normalize", "format", "match"):
        result["result"] = None
    return result
