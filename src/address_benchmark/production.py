"""Opt-in production adapters. All assets remain installed by their owners."""
from __future__ import annotations

import importlib
import importlib.metadata
import itertools
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .adapters import AdapterProtocolError, Unavailable, metadata
from .intake import align_native
from .io import read_jsonl, require, write_json, write_jsonl
from .ontologies import COARSE_ALIASES, NEUTRAL_ROLES, ONTOLOGY_V2, US_FINE
from .protocol import prediction


def role_map(namespace):
    if namespace == "usaddress":
        return {**US_FINE, "__unplaced__": None}
    require(namespace == "neutral", "explicit native namespace required")
    return {**{r: r for r in NEUTRAL_ROLES}, **COARSE_ALIASES, "__unplaced__": None}


def adapter_metadata(name, namespace, config):
    value = metadata(name, role_map(namespace), spans=namespace == "usaddress", tokens=namespace == "usaddress")
    value.update(ontology=ONTOLOGY_V2, mapping_version="address-benchmark.native-crosswalk/v2",
                 model=config.get("model_identity", "user-declared model; inspect file pins"),
                 artifact_files=config.get("artifact_files", []),
                 span_origin="adapter-derived exact sequential original-input alignment; unresolved pieces have no spans",
                 fine_scope="exact native usaddress-compatible roles" if namespace == "usaddress" else "coarse API; fine token/span-role scores unsupported",
                 provenance=config.get("provenance", {}), api_scope=config.get("api_scope", "native public API plus owned output conversion"))
    if "active_native_roles" in config:
        require(all(role in value["role_map"] for role in config["active_native_roles"]), "active native vocabulary absent from mapping")
        value["active_roles"] = sorted({value["role_map"][role] for role in config["active_native_roles"] if value["role_map"][role] is not None})
        value["role_inventory_basis"] = config.get("role_inventory_basis", "declared native model/API vocabulary; not empirical accuracy")
    return value


def convert(request, pairs, namespace, native, error=None):
    if error:
        return prediction(request, status="error", message=str(error), native=native)
    pairs = [(value, label if label is not None else "__unplaced__") for value, label in pairs]
    spans = align_native(request.text, pairs) if namespace == "usaddress" else [None] * len(pairs)
    evidence, tokens = [], []
    for (value, label), span in zip(pairs, spans):
        item = dict(native_role=label, value=value, spans=[span] if span is not None else None)
        evidence.append(item)
        if span is not None:
            tokens.append(dict(item))
    result = prediction(request, evidence, tokens=tokens, native=native)
    result["alignment"] = dict(origin="input-only exact sequential", unresolved=sum(x is None for x in spans))
    return result


class NativeBatch:
    """Generic argv/file bridge, useful for existing user-installed evaluators.

    command argv contains literal {inputs}/{outputs}; no shell or gold path.
    Native output: ordered id,input_sha256,labels[{value,label}],error JSONL.
    """
    def __init__(self, config):
        self.config = config
        self.namespace = config["namespace"]
        self.command = config["command"]
        require(isinstance(self.command, list) and self.command and all(isinstance(x, str) for x in self.command), "argv command required")
        require("{inputs}" in self.command and "{outputs}" in self.command, "exact input/output argv placeholders required")
        if not shutil.which(self.command[0]):
            raise Unavailable(f"native executable unavailable: {self.command[0]}")
        self.metadata = adapter_metadata(config["name"], self.namespace, config)
        self.metadata["execution"] = "native batch command; fresh process, input-only JSONL, actual exit and native output retained"

    def parse_many(self, requests, directory):
        source, output = directory / "native-inputs.jsonl", directory / "native-output.jsonl"
        write_jsonl(source, (dict(id=r.id, input=r.text) for r in requests))
        substitutions = {"{inputs}": str(source), "{outputs}": str(output), "{metadata}": str(directory / "native-metadata.json")}
        command = [substitutions.get(x, x) for x in self.command]
        with (directory / "native-stdout.log").open("xb") as stdout, (directory / "native-stderr.log").open("xb") as stderr:
            result = subprocess.run(command, stdout=stdout, stderr=stderr)
        write_json(directory / "native-execution.json", dict(command=command, exit_code=result.returncode))
        require(result.returncode == 0, f"native command exited {result.returncode}")
        require(output.is_file(), "native command produced no output")
        for request, row in itertools.zip_longest(requests, read_jsonl(output)):
            require(request is not None and row is not None, "native stream length differs")
            require(row.get("id") == request.id and row.get("input_sha256") == request.input_sha256, "native stream identity/order differs")
            require(row.get("namespace", self.namespace) == self.namespace, "native namespace differs")
            pairs = [(p["value"], p["label"]) for p in row["labels"]]
            yield convert(request, pairs, self.namespace, row, row.get("error"))

    def parse(self, request):
        raise AdapterProtocolError("native batch adapter requires whole-panel execution; no per-address startup timing substitution")


class PythonTokens:
    """usaddress, fastaddress, Doorplate public native token APIs."""
    def __init__(self, config):
        self.config = config
        name = config["library"]
        require(name in ("usaddress", "fastaddress", "doorplate"), "unsupported Python token library")
        try:
            self.library = importlib.import_module(name)
        except ImportError as exc:
            raise Unavailable(f"install {name} in the configured interpreter") from exc
        self.name = name
        self.metadata = adapter_metadata(name, "usaddress", config)
        self.metadata["dependency_versions"] = {name: importlib.metadata.version(name)}
        if name == "usaddress" and hasattr(self.library, "TAGGER"):
            native_roles = self.library.TAGGER.labels()
            self.metadata["active_roles"] = sorted({self.metadata["role_map"][role] for role in native_roles})
            self.metadata["role_inventory_basis"] = "actual loaded CRF tagger labels()"
        if name == "doorplate":
            self.parser = self.library.Parser()

    def parse(self, request):
        if self.name == "doorplate":
            parsed = self.parser.parse(request.text)
            native = parsed.to_usaddress_tags()
        elif self.name == "fastaddress":
            native = self.library.parse(request.text, model=self.config.get("model", "v1"))
        else:
            native = self.library.parse(request.text)
        return convert(request, native, "usaddress", {"tokens": native})


class Libpostal:
    """Independent wrapper of libpostal's documented C parser ABI."""
    def __init__(self, config):
        import ctypes as c
        class Options(c.Structure):
            _fields_ = [("language", c.c_char_p), ("country", c.c_char_p)]
        class Response(c.Structure):
            _fields_ = [("num_components", c.c_size_t), ("components", c.POINTER(c.c_char_p)), ("labels", c.POINTER(c.c_char_p))]
        library, data = Path(config["library"]), Path(config["data_dir"])
        # A parser-only model (e.g. Senzing) can live apart from the base data.
        parser_dir = Path(config.get("parser_dir", data))
        required = [data / name for name in ("transliteration", "address_expansions", "numex")] + [parser_dir / "address_parser"]
        missing = ([] if library.is_file() else [library]) + [path for path in required if not path.is_dir()]
        if missing:
            raise Unavailable("libpostal shared library/model paths missing: " + ", ".join(map(str, missing)))
        self.c, self.library = c, c.CDLL(str(library))
        signatures = {
            "libpostal_setup_datadir": ([c.c_char_p], c.c_bool), "libpostal_setup_parser_datadir": ([c.c_char_p], c.c_bool),
            "libpostal_get_address_parser_default_options": ([], Options),
            "libpostal_parse_address": ([c.c_char_p, Options], c.POINTER(Response)),
            "libpostal_address_parser_response_destroy": ([c.POINTER(Response)], None),
            "libpostal_teardown_parser": ([], None), "libpostal_teardown": ([], None),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.library, name)
            function.argtypes, function.restype = arguments, result
        self.base = self.parser = False
        try:
            self.base = bool(self.library.libpostal_setup_datadir(os.fsencode(data)))
            require(self.base, "libpostal base setup failed")
            self.parser = bool(self.library.libpostal_setup_parser_datadir(os.fsencode(parser_dir)))
            require(self.parser, "libpostal model setup failed")
            self.options = self.library.libpostal_get_address_parser_default_options()
        except BaseException:
            self.close()
            raise
        self.metadata = adapter_metadata(config.get("name", "libpostal"), "neutral", config)
        self.metadata["native_options"] = dict(language=None, country=None)

    def parse(self, request):
        require("\0" not in request.text, "embedded NUL cannot pass through C strings")
        text = self.c.create_string_buffer(request.text.encode("utf-8"))
        response = self.library.libpostal_parse_address(text, self.options)
        require(bool(response), "libpostal returned no response")
        try:
            value = response.contents
            parts = [(value.components[i].decode("utf-8"), value.labels[i].decode("utf-8")) for i in range(value.num_components)]
        finally:
            self.library.libpostal_address_parser_response_destroy(response)
        return convert(request, parts, "neutral", {"components": parts})

    def close(self):
        if self.parser:
            self.library.libpostal_teardown_parser()
            self.parser = False
        if self.base:
            self.library.libpostal_teardown()
            self.base = False


class DefaultNormalizer:
    """Source-preserving default public parser; never substitutes inferred fields."""
    def __init__(self, config):
        if config.get("module_path"):
            sys.path.insert(0, config["module_path"])
        try:
            self.library = importlib.import_module("address_normalizer")
        except ImportError as exc:
            raise Unavailable("install address_normalizer or provide a read-only module_path") from exc
        if not hasattr(self.library, "parse_record"):
            raise Unavailable("selected binding lacks public source evidence API")
        self.metadata = adapter_metadata("address-normalizer-default", "neutral", config)
        self.metadata["default_not_learned"] = True
        self.metadata["active_roles"] = ["house_number", "road", "po_box", "name", "unit", "level", "city", "state_district", "city_district", "suburb", "island", "state", "postcode", "country", "intersection_separator", "category", "near"]
        self.metadata["role_inventory_basis"] = "public source ParseField inventory; generic Name is not typed as a building or recipient"
        self.metadata["span_origin"] = "native source evidence; native coarse roles do not provide usaddress fine labels"
        self.metadata["artifact_files"] = sorted(set(config.get("artifact_files", []) + [self.library.__file__, self.library._native.__file__]))

    def parse(self, request):
        from dataclasses import asdict
        record = self.library.parse_record(request.text, country=request.country)
        evidence = record.evidence
        output = []
        for item in evidence["observed"]:
            role = item["field"]
            value = item.get("value", item.get("text"))
            spans = item.get("spans")
            if spans is None and item.get("span"):
                spans = [item["span"]]
            converted = [[s["start"], s["end"]] if isinstance(s, dict) else s for s in spans or []]
            output.append(dict(native_role=role, value=value, spans=converted or None))
        result = prediction(request, output, native=asdict(record))
        result["inferred"] = evidence.get("inferred", [])
        return result
