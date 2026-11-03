"""Authored controls and an optional public-API usaddress wrapper; no gold access."""
from __future__ import annotations

import importlib
import importlib.metadata
import platform
import re
import shutil
import subprocess
from pathlib import Path

from .protocol import FINE_TO_COARSE, ONTOLOGY, PROTOCOL, NORMALIZE_ONTOLOGY, MATCH_ONTOLOGY, TASK_ONTOLOGIES, check_metadata, prediction
from .io import canonical, loads, require


class Unavailable(RuntimeError):
    pass


class AdapterProtocolError(ValueError):
    pass


def metadata(name, mapping, *, version="1", spans=False, tokens=False, model="none", dependencies=None):
    return dict(protocol=PROTOCOL, name=name, version=version, ontology=ONTOLOGY,
                mapping_version=name + "/v1", role_map=mapping,
                supported_roles=sorted({r for r in mapping.values() if r is not None}),
                runtime=platform.python_version(), model=model, dependency_versions=dependencies or {},
                threading="one caller; dependency helper threads not controlled",
                ownership="fresh Python dictionaries/lists/strings; results consumed and released",
                tasks=["parse"], span_support=spans, token_support=tokens)


class DemoParser:
    """Intentionally limited comma-delimited US syntax, NOT a production parser."""

    def __init__(self, config):
        if config:
            raise ValueError("demo adapter takes no configuration")
        mapping = {r: r for r in ("house_number", "road_name", "road_type", "city", "state", "postcode")}
        self.metadata = metadata("authored-demo", mapping, spans=True, tokens=True)

    def parse(self, request):
        match = re.fullmatch(r"(?P<house_number>\d+) (?P<road>[^,]+), (?P<city>[^,]+), (?P<state>[A-Z]{2}) (?P<postcode>\d{5}(?:-\d{4})?)", request.text)
        if not match:
            return prediction(request, status="refused", message="outside authored demonstration grammar", native={"match": False})
        evidence = []
        for group in ("house_number", "road", "city", "state", "postcode"):
            start, _ = match.span(group)
            value = match.group(group)
            for token in re.finditer(r"\S+", value):
                role = group
                if role == "road":
                    role = "road_type" if token.group().casefold() in {"st", "st.", "rd", "rd.", "ave", "ave."} else "road_name"
                a, b = start + token.start(), start + token.end()
                evidence.append(dict(native_role=role, value=token.group(),
                                     spans=[[len(request.text[:a].encode("utf-8")), len(request.text[:b].encode("utf-8"))]]))
        return prediction(request, evidence, tokens=evidence, native={"groups": match.groupdict()})


class RefusalParser:
    def __init__(self, config):
        if config:
            raise ValueError("refusal adapter takes no configuration")
        self.metadata = metadata("refusal-control", {})

    def parse(self, request):
        return prediction(request, status="refused", message="intentional conformance control", native={"refused": True})


class DemoNormalizer:
    """Named authored profile: uppercase plus whitespace collapse, no inference."""
    PROFILE = "address-benchmark.uppercase-whitespace/v1"

    def __init__(self, config):
        require(not config, "demo normalizer takes no config")
        self.metadata = metadata("uppercase-whitespace-demo", {})
        self.metadata.update(ontology=NORMALIZE_ONTOLOGY, tasks=["normalize"], profiles=[self.PROFILE])

    def parse(self, request):
        require(request.profile == self.PROFILE, "unsupported normalization profile")
        value = " ".join(request.text.upper().split())
        result = prediction(request, native={"text": value})
        result["normalized"] = [value]
        return result


class DemoKeys:
    PROFILE = "address-benchmark.delivery-unit-key-equality/v1"

    def __init__(self, config):
        require(not config, "demo keys takes no config")
        self.metadata = metadata("comparison-key-demo", {})
        self.metadata.update(ontology=MATCH_ONTOLOGY, tasks=["match"], profiles=[self.PROFILE],
                             key_policy="uppercase + whitespace + comma/period removal + four authored aliases; preserves all digits/units")

    @staticmethod
    def key(text):
        aliases = {"STREET": "ST", "AVENUE": "AVE", "ROAD": "RD", "APARTMENT": "APT"}
        return " ".join(aliases.get(token, token) for token in text.upper().replace(",", " ").replace(".", "").split())

    def parse(self, request):
        require(request.profile == self.PROFILE, "unsupported key comparison profile")
        keys = [self.key(request.text), self.key(request.other_text)]
        if not all(keys):
            return prediction(request, status="refused", message="empty comparison key", native={"keys": keys})
        result = prediction(request, native={"keys": keys})
        result["keys"] = keys
        return result


UTILITY_PROFILES = {task: f"address-benchmark.authored-{task}/v1" for task in ("format", "classify", "extract", "infer", "variants", "diagnostics", "stability")}


class DemoUtility:
    """Minimal authored controls for every utility track, not production logic."""

    def __init__(self, config):
        require(set(config) == {"task"} and config["task"] in UTILITY_PROFILES, "select one utility task")
        self.task = config["task"]
        self.metadata = metadata("authored-" + self.task + "-control", {})
        self.metadata.update(ontology=TASK_ONTOLOGIES[self.task], tasks=[self.task], profiles=[UTILITY_PROFILES[self.task]])

    def parse(self, request):
        require(request.profile == UTILITY_PROFILES[self.task], "unsupported profile")
        text = request.text
        result = prediction(request, native={"task": self.task})
        if self.task == "format":
            result["normalized"] = ["\n".join(field["value"] for field in request.payload["fields"])]
        elif self.task == "classify":
            result["result"] = "po_box" if text.upper().startswith("PO BOX ") else "intersection" if " & " in text else "street" if re.match(r"\d+ ", text) else "unknown"
        elif self.task == "extract":
            match = re.match(r"^(\d+[A-Za-z]?(?: \d+/\d+)?)(?:\s|$)", text)
            result["result"] = match.group(1) if match else None
        elif self.task == "infer":
            # Tiny documented control inventory; not a national ZIP database.
            result["result"] = {"state": {"10001": "NY", "90210": "CA"}.get(text)}
        elif self.task == "variants":
            result["result"] = list(dict.fromkeys([text, text.upper()]))
        elif self.task == "diagnostics":
            result["result"] = {"empty_input": not bool(text.strip()), "deliverability": "not_checked"}
        else:
            texts = request.payload["texts"]
            normalize = lambda value: " ".join(value.upper().split())
            scalar = [normalize(value) for value in texts]
            result["result"] = dict(scalar=scalar, repeat=[normalize(value) for value in texts],
                                    batch=list(map(normalize, texts)), normalized_twice=[normalize(value) for value in scalar],
                                    stream=[normalize(value) for value in iter(texts)],
                                    chunked=[normalize(value) for start in range(0, len(texts), 2) for value in texts[start:start + 2]])
        result["native"] = {"output": result.get("result", result["normalized"])}
        return result


class PythonCallable:
    """Opt-in public Python API wrapper for existing utilities; never imports gold."""

    def __init__(self, config):
        allowed = {"callable", "task", "profile", "kwargs", "result_field", "constructor", "batch_callable", "stream_callable", "chunked_callable", "chunk_size", "artifact_files"}
        require(set(config) <= allowed and all(k in config for k in ("callable", "task", "profile")), "callable/task/profile configuration required")
        self.config = config
        self.task = config["task"]
        require(self.task in TASK_ONTOLOGIES and self.task != "parse", "use native evidence adapter for parsing")
        module, name = config["callable"].split(":", 1)
        try:
            self.module = importlib.import_module(module)
        except ImportError as exc:
            raise Unavailable(f"install {module} in the configured interpreter") from exc
        self.function = getattr(self.module, name)
        self.metadata = metadata(config["callable"], {})
        self.metadata.update(ontology=TASK_ONTOLOGIES[self.task], tasks=[self.task], profiles=[config["profile"]],
                             artifact_files=config.get("artifact_files", []), public_api=config["callable"], options=config.get("kwargs", {}))

    def call(self, value):
        from dataclasses import asdict, is_dataclass
        result = self.function(value, **self.config.get("kwargs", {}))
        return asdict(result) if is_dataclass(result) else result

    def parse(self, request):
        require(request.profile == self.config["profile"], "unsupported profile")
        result = prediction(request, native=None)
        if self.task == "match":
            values = [self.call(request.text), self.call(request.other_text)]
            if not all(isinstance(x, str) and x for x in values):
                return prediction(request, status="refused", message="public API returned no comparison key", native=values)
            result["keys"] = values
        elif self.task == "stability":
            texts = request.payload["texts"]
            batch = getattr(self.module, self.config["batch_callable"])
            scalar = [self.call(text) for text in texts]
            values = dict(scalar=scalar, repeat=[self.call(text) for text in texts],
                          batch=list(batch(texts, **self.config.get("kwargs", {}))), normalized_twice=[self.call(x) for x in scalar])
            if self.config.get("stream_callable"):
                stream = getattr(self.module, self.config["stream_callable"])
                values["stream"] = list(stream(iter(texts), **self.config.get("kwargs", {})))
            if self.config.get("chunked_callable"):
                chunked = getattr(self.module, self.config["chunked_callable"])
                size = self.config.get("chunk_size", 2)
                require(type(size) is int and size > 0, "positive chunk size required")
                values["chunked"] = [item for chunk in chunked(iter(texts), chunk_size=size, **self.config.get("kwargs", {})) for item in chunk]
            result["result"] = values
        else:
            argument = request.text
            if self.task == "format":
                fields = request.payload["fields"]
                require(len({f["role"] for f in fields}) == len(fields), "dict-formatting API cannot preserve repeated fields")
                argument = {field["role"]: field["value"] for field in fields}
                if self.config.get("constructor"):
                    argument = getattr(self.module, self.config["constructor"])(**argument)
            values = self.call(argument)
            if self.task in ("normalize", "format"):
                if values is None:
                    return prediction(request, status="refused", message="public API returned no formatted/normalized value", native=None)
                result["normalized"] = [values] if isinstance(values, str) else values
            else:
                result["result"] = {self.config["result_field"]: values} if self.config.get("result_field") else values
        result["native"] = values
        return result


# This mapping is an explicitly lossy interoperability policy, not a claim of
# identical annotation meaning. Unlisted roles must be added by a version bump.
USADDRESS_MAP = {
    "AddressNumber": "house_number", "AddressNumberPrefix": "house_number_prefix",
    "AddressNumberSuffix": "house_number_suffix", "StreetName": "road_name",
    "StreetNamePreDirectional": "road_direction", "StreetNamePostDirectional": "road_direction",
    "StreetNamePreType": "road_type", "StreetNamePostType": "road_type",
    "StreetNamePreModifier": "road_name", "StreetNamePostModifier": "road_name",
    "OccupancyType": "unit_type", "OccupancyIdentifier": "unit_id",
    "PlaceName": "city", "StateName": "state", "ZipCode": "postcode",
    "USPSBoxType": "po_box", "USPSBoxID": "po_box", "USPSBoxGroupType": "po_box", "USPSBoxGroupID": "po_box",
    "Recipient": "recipient", "BuildingName": "building", "LandmarkName": "building",
    "SubaddressType": "subaddress", "SubaddressIdentifier": "subaddress",
    "CountryName": "country", "CornerOf": "intersection", "IntersectionSeparator": "intersection",
    "NotAddress": "not_address",
}


class UsaddressParser:
    def __init__(self, config):
        if config:
            raise ValueError("usaddress adapter takes no configuration")
        try:
            self.library = importlib.import_module("usaddress")
        except ImportError as exc:
            raise Unavailable("install the optional usaddress extra in your selected interpreter") from exc
        deps = {}
        for name in ("usaddress", "python-crfsuite", "probableparsing"):
            try:
                deps[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                deps[name] = "not-found"
        self.metadata = metadata("usaddress", USADDRESS_MAP, version=deps["usaddress"],
                                 model="bundled CRF; fingerprint installed package and dependency files", dependencies=deps)

    def parse(self, request):
        native = self.library.parse(request.text)
        # parse() retains repeated token labels; tag() would merge or reject them.
        return prediction(request, [dict(native_role=role, value=value, spans=None) for value, role in native], native=native)


def command_artifacts(command, declared=()):
    """One file inventory for freezing and the persistent command runtime."""
    require(isinstance(command, list) and command and all(isinstance(x, str) for x in command), "argv list required; no shell")
    executable = shutil.which(command[0])
    require(executable is not None, "command executable unavailable")
    require(isinstance(declared, (list, tuple)) and all(isinstance(x, str) for x in declared), "declared command artifact list required")
    return sorted({str(Path(executable).resolve()), *(str(Path(x).resolve()) for x in command[1:] if Path(x).is_file()),
                   *(str(Path(x).resolve()) for x in declared)})


class CommandAdapter:
    """Persistent JSONL bridge for user-installed Rust/Go/C/Node/etc. engines."""

    def __init__(self, config):
        require(set(config) == {"command", "metadata"}, "command adapter requires command and metadata")
        command = config["command"]
        require(isinstance(command, list) and command and all(isinstance(x, str) for x in command), "argv list required; no shell")
        executable = shutil.which(command[0])
        if executable is None:
            raise Unavailable(f"command unavailable: {command[0]}")
        self.metadata = dict(config["metadata"])
        check_metadata(self.metadata)
        self.metadata["bridge"] = "persistent JSONL; request/response serialization and pipe I/O included in API timing"
        self.metadata["artifact_files"] = command_artifacts(command, self.metadata.get("artifact_files", []))
        self.process = subprocess.Popen([executable, *command[1:]], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def parse(self, request):
        try:
            self.process.stdin.write(canonical(request.to_dict()) + b"\n")
            self.process.stdin.flush()
            raw = self.process.stdout.readline(4 * 1024 * 1024 + 1)
            require(raw.endswith(b"\n") and len(raw) <= 4 * 1024 * 1024, "invalid command response or process exited")
            return loads(raw.decode("utf-8"))
        except (ValueError, OSError) as exc:
            raise AdapterProtocolError(str(exc)) from exc

    def close(self):
        self.process.stdin.close()
        try:
            code = self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            raise ValueError("command ignored EOF; killed own command process")
        require(code == 0, f"command exit: {code}")


BUILTINS = {"demo": DemoParser, "refusal": RefusalParser, "usaddress": UsaddressParser, "command": CommandAdapter,
            "demo-normalize": DemoNormalizer, "demo-keys": DemoKeys}
BUILTINS.update({"demo-utility": DemoUtility, "python-callable": PythonCallable})


def load_adapter(spec, config):
    if spec in ("native-batch", "python-tokens", "libpostal", "address-normalizer-default"):
        from .production import NativeBatch, PythonTokens, DefaultNormalizer, Libpostal
        factory = {"native-batch": NativeBatch, "python-tokens": PythonTokens, "libpostal": Libpostal, "address-normalizer-default": DefaultNormalizer}[spec]
        adapter = factory(config)
        check_metadata(adapter.metadata)
        return adapter
    if spec in BUILTINS:
        factory = BUILTINS[spec]
    elif ":" in spec:
        module, name = spec.split(":", 1)
        try:
            factory = getattr(importlib.import_module(module), name)
        except (ImportError, AttributeError) as exc:
            raise Unavailable(f"adapter unavailable: {spec}: {exc}") from exc
    else:
        matches = list(importlib.metadata.entry_points(group="address_benchmark.adapters", name=spec))
        if len(matches) != 1:
            raise Unavailable(f"no unique adapter entry point: {spec}")
        factory = matches[0].load()
    adapter = factory(config)
    check_metadata(adapter.metadata)
    return adapter
