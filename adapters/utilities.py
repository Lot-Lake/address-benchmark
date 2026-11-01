"""Versioned public-API utility projections. No reference data enters this module."""
from __future__ import annotations

from dataclasses import asdict
import importlib
import json
import sys

from address_benchmark.adapters import Unavailable, metadata
from address_benchmark.io import canonical, require
from address_benchmark.protocol import MATCH_ONTOLOGY, NORMALIZE_ONTOLOGY, TASK_ONTOLOGIES, prediction

CLASS_PROFILE = "address-benchmark.publisher-address-types/v1"
NORMAL_PROFILE = "address-benchmark.normalized-five-field-json/v1"
STABILITY_PROFILE = "address-benchmark.real-input-stability/v1"
IDENTITY_PROFILE = "address-benchmark.delivery-unit-key-equality/v1"
FIELDS = ("address_line_1", "address_line_2", "city", "state", "postal_code")


def line(values):
    values = [str(v) for v in values if v is not None and v != ""]
    return " ".join(" ".join(values).upper().split()) if values else None


def component_record(native, library):
    """Common renderer: joins/uppercases native canonical values, never repairs them."""
    if library == "address_normalizer":
        first = [native.get(k) for k in ("number", "fraction", "prefix", "street", "street_type", "suffix")]
        second = [native.get(k) for k in ("unit_prefix", "unit")]
        postcode = native.get("postal_code")
    else:
        first = [native.get(k) for k in ("street_number", "street_dir_prefix", "street_name", "street_suffix", "street_dir_suffix")]
        second = [native.get(k) for k in ("unit_type", "unit_number", "second_unit_type", "second_unit_number")]
        postcode = native.get("zip5")
        if native.get("zip4"):
            postcode = (postcode + "-" + native["zip4"]) if postcode else native["zip4"]
    return dict(address_line_1=line(first), address_line_2=line(second), city=line([native.get("city")]),
                state=line([native.get("state")]), postal_code=postcode)


def postal_text(parts):
    return "\n".join(parts[key] for key in ("line1", "line2", "last_line") if parts.get(key))


class Factory:
    def __init__(self, config):
        self.config = config
        self.library_name, self.task = config["library"], config["task"]
        require(self.library_name in ("address_normalizer", "doorplate"), "unsupported utility library")
        require(self.task in ("classify", "normalize", "match", "stability"), "unsupported utility task")
        if config.get("module_path"):
            sys.path.insert(0, config["module_path"])
        try:
            self.library = importlib.import_module(self.library_name)
        except ImportError as exc:
            raise Unavailable(f"install {self.library_name} in the selected runtime") from exc
        if self.library_name == "doorplate":
            self.parser = self.library.Parser()
        profile = {"classify": CLASS_PROFILE, "normalize": NORMAL_PROFILE, "match": IDENTITY_PROFILE, "stability": STABILITY_PROFILE}[self.task]
        self.metadata = metadata(self.library_name + ":" + self.task, {})
        self.metadata.update(tasks=[self.task], ontology=TASK_ONTOLOGIES[self.task], profiles=[profile],
                             options=dict(delivery_unit_key=True, normalization="common uppercase renderer over native normalized fields", format_mode="usps"),
                             identity_scope="delivery-unit; independent pair labels, no key-derived gold",
                             classification_mapping={"standard": "street", "rural_route": "rural"},
                             classification_limit="Doorplate native street includes highways; no gold-based highway subtype reconstruction")
        if self.library_name == "address_normalizer":
            self.metadata["artifact_files"] = [self.library.__file__, self.library._native.__file__]

    def scalar(self, text):
        if self.library_name == "address_normalizer":
            return self.library.standardize_address(text, mode="usps")
        return postal_text(self.parser.parse(text).to_usps())

    def parse(self, request):
        result = prediction(request, native=None)
        if self.task == "classify":
            if self.library_name == "address_normalizer":
                raw = self.library.get_address_type(request.text)
            else:
                raw = self.parser.parse(request.text).address_type()
            result["result"] = {"standard": "street", "rural_route": "rural"}.get(raw, raw)
            result["native"] = {"classification": raw}
        elif self.task == "match":
            if self.library_name == "address_normalizer":
                keys = [self.library.standardize_for_comparison(t) for t in (request.text, request.other_text)]
            else:
                keys = [self.parser.parse(t).key(unit=True) for t in (request.text, request.other_text)]
            if not all(isinstance(key, str) and key for key in keys):
                return prediction(request, status="refused", message="native API returned no comparison key", native={"keys": keys})
            result["keys"], result["native"] = keys, {"keys": keys}
        elif self.task == "normalize":
            if self.library_name == "address_normalizer":
                native_record = self.library.normalize_record(request.text, options=self.library.AnalyzeOptions(format_mode="usps"))
                native = asdict(native_record.components)
                audit = asdict(native_record)
            else:
                native_record = self.parser.parse(request.text)
                native = native_record.to_dict()
                audit = native
            projected = component_record(native, self.library_name)
            result["normalized"] = [canonical(projected).decode("utf-8")]
            result["native"] = dict(record=audit, projected=projected)
        else:
            texts = request.payload["texts"]
            scalar = [self.scalar(text) for text in texts]
            if self.library_name == "address_normalizer":
                batch = self.library.normalize_batch(texts, mode="usps")
            else:
                batch = [postal_text(item.to_usps()) if item is not None else None for item in self.parser.parse_many(texts)]
            observed = dict(scalar=scalar, repeat=[self.scalar(text) for text in texts], batch=batch)
            twice, errors = [], []
            for index,value in enumerate(scalar):
                try:twice.append(self.scalar(value))
                except Exception as exc:
                    twice.append(dict(error=type(exc).__name__))
                    errors.append(dict(index=index,operation='renormalize',error=type(exc).__name__))
            observed['normalized_twice']=twice
            if self.library_name == "address_normalizer":
                observed["stream"] = list(self.library.normalize_stream(iter(texts), mode="usps"))
                observed["chunked"] = [value for chunk in self.library.normalize_chunked(iter(texts), chunk_size=37, mode="usps") for value in chunk]
            if errors:
                return prediction(request,status='error',message=f'{len(errors)} native re-normalization calls failed',native=dict(observations=observed,errors=errors))
            result["result"], result["native"] = observed, observed
        return result
