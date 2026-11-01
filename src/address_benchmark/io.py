"""Strict JSON, physical-line JSONL, and portable content identities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def identity(value) -> str:
    return digest_bytes(canonical(value))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads(value):
    def invalid(value):
        raise ValueError(f"nonfinite JSON number: {value}")
    return json.loads(value, object_pairs_hook=_pairs, parse_constant=invalid)


def read_json(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    with Path(path).open("rb") as f:
        for line, raw in enumerate(f, 1):
            require(raw.strip() and len(raw) <= 4 * 1024 * 1024, f"invalid JSONL record {line}")
            value = loads(raw.decode("utf-8"))
            require(isinstance(value, dict), f"JSONL object required at {line}")
            yield value


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")


def write_jsonl(path, values):
    with Path(path).open("xb") as f:
        for value in values:
            f.write(canonical(value) + b"\n")


def within(root, relative):
    require(isinstance(relative, str) and not Path(relative).is_absolute(), "relative artifact path required")
    path = (Path(root) / relative).resolve()
    require(path.is_relative_to(Path(root).resolve()), "artifact escapes root")
    return path
