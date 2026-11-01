"""Loss-aware readers for pinned publisher assets, without reference repair."""
from __future__ import annotations

import gzip
from pathlib import Path
import xml.etree.ElementTree as ET

from .io import digest_bytes, loads, read_jsonl, require
from .ontologies import COARSE_ALIASES, GEO_NATIVE, US_COARSE, US_FINE


def empty_reference():
    return dict(coverage="none", fields={}, spans=[], tokens=[], spans_coverage="none", tokens_coverage="none")


def fields_from_parts(parts):
    fields, previous = {}, None
    for value, label in parts:
        require(label in US_COARSE and isinstance(value, str), f"unsupported publisher label: {label}")
        role = US_COARSE[label]
        if role == previous:
            fields[role][-1] += " " + value
        else:
            fields.setdefault(role, []).append(value)
        previous = role
    return fields


def align_native(text, parts):
    """Exact sequential input-only alignment; never uses labels to search gold."""
    cursor, result = 0, []
    for value, label in parts:
        start = text.find(value, cursor) if value else -1
        if start < 0:
            result.append(None)
            continue
        stop = start + len(value)
        result.append([len(text[:start].encode("utf-8")), len(text[:stop].encode("utf-8"))])
        cursor = stop
    return result


def parse_reference(text, parts, spans=None):
    spans = align_native(text, parts) if spans is None else spans
    for (value, _), span in zip(parts, spans):
        if span is not None:
            require(text.encode("utf-8")[span[0]:span[1]].decode("utf-8") == value, "publisher source span/value differs")
    annotations = [dict(role=US_FINE[label], span=span) for (_, label), span in zip(parts, spans) if span is not None]
    complete_alignment = all(span is not None for span in spans)
    return dict(coverage="complete", fields=fields_from_parts(parts), spans=annotations, tokens=annotations,
                spans_coverage="complete" if complete_alignment else "partial",
                tokens_coverage="complete" if complete_alignment else "partial")


def row_record(manifest, resource, native_id, text, reference, *, subsets=(), native_provenance=None, origin=None):
    digest = digest_bytes(text.encode("utf-8"))
    return dict(id=manifest["id"] + ":" + str(native_id), text=text,
                family="exact-input-proxy:" + digest, family_basis="exact-text-only; upstream independent source families unavailable",
                split=resource.get("split", "publisher-evaluation"), origin=origin or resource.get("origin", "publisher-fixture"),
                subsets=list(subsets), reference=reference, upstream=native_provenance)


def records(path, resource, manifest):
    kind = resource["format"]
    if kind == "usaddress-xml":
        import re
        root = ET.parse(path).getroot()
        for index, element in enumerate(root.findall("AddressString")):
            text = "".join(element.itertext())
            parts = [("".join(child.itertext()), child.tag) for child in element]
            require(all(value for value, _ in parts), "empty publisher token")
            reference = parse_reference(text, parts)
            tokens = []
            for (value, label), span in zip(parts, align_native(text, parts)):
                if span is not None:
                    for token in re.finditer(r"\S+", value):
                        start = span[0] + len(value[:token.start()].encode("utf-8"))
                        stop = span[0] + len(value[:token.end()].encode("utf-8"))
                        tokens.append(dict(role=US_FINE[label], span=[start, stop]))
            reference["tokens"] = tokens
            yield row_record(manifest, resource, index, text, reference, native_provenance=dict(xml_record=index, tokenization="non-whitespace within publisher element/v1"))
        return
    if kind == "doorplate-compare":
        opener = gzip.open if Path(path).suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                row = loads(line)
                parts = [(value, label) for value, label in row["tokens"]]
                yield row_record(manifest, resource, row["id"], row["input"], parse_reference(row["input"], parts),
                                 subsets=["all", row["stratum"], "source:" + row["source"]],
                                 origin="publisher-fixture" if row["stratum"] == "hand" else "source-field-supervised",
                                 native_provenance={k: row[k] for k in ("source", "style", "mods", "tags")})
        return
    require(kind in ("geosearch-reference", "expanded-parser", "input-panel"), "unknown corpus reader")
    for index, row in enumerate(read_jsonl(path)):
        text = row.get("input", row.get("text"))
        require(isinstance(text, str), "publisher input string required")
        require(row.get("input_sha256", digest_bytes(text.encode())) == digest_bytes(text.encode()), "upstream input hash differs")
        if kind == "geosearch-reference":
            require(row["status"] == "valid" and not row["issues"] and len(row["tags"]) == len(row["tokens"]), "invalid publisher labels; no silent repair")
            parts = [(token["value"], GEO_NATIVE[tag.removeprefix("B-").removeprefix("I-")]) for tag, token in zip(row["tags"], row["tokens"])]
            spans = [[token["span"]["start"], token["span"]["end"]] for token in row["tokens"]]
            reference = parse_reference(text, parts, spans)
            provenance = row["provenance"]
            subsets = ["all", "constructed-token-input"]
        elif kind == "expanded-parser":
            reference = empty_reference()
            reference.update(coverage="complete" if row["expected_complete"] else "partial",
                             fields={COARSE_ALIASES.get(k, k): v for k, v in row["expected"].items()})
            provenance = row["source"]
            subsets = ["all", row["source"]["id"], "complete" if row["expected_complete"] else "partial"]
        else:
            reference, provenance, subsets = empty_reference(), {"input_panel_only": True}, ["workload-only"]
        yield row_record(manifest, resource, row.get("id", index), text, reference, subsets=subsets, native_provenance=provenance)
