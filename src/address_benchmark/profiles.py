"""Named, versioned parsing scoring profiles, declared by a corpus manifest (`scoring_profiles`).

A profile is an additional score next to the shared scorer/v1 policy; it never replaces or changes it.
Corpora that declare no profile produce exactly the records they did before.

strict-streetline/v1 (docs/spec/profiles.md): six fields, number, streetline, unit, city, state and zip. The
street line (pre-directional, street name, street type and post-directional) is compared as ONE canonical string,
so where an engine splits the line does not matter. Values pass through one canonicalizer with USPS Publication 28
folds, applied identically to references and predictions. Complete references score all six fields, so an absent
reference field must be absent in the prediction; partial references score only the fields they supply (an empty
supplied list asserts absence). Only parsed evidence is scored: a ZIP-derived state belongs in `inferred`, is
never source evidence, and is counted separately.
"""
from __future__ import annotations

import re

from . import ontologies  # noqa: F401  registers the us-roles/v2 fine roles
from .io import require
from .protocol import FINE_TO_COARSE
from .pub28 import DIRECTIONALS, STATES, SUFFIXES, UNIT_DESIGNATORS

STREETLINE = "strict-streetline/v1"
PROFILES = (STREETLINE,)
FIELDS = ("number", "streetline", "unit", "city", "state", "zip")
COARSE_FIELD = {"house_number": "number", "road": "streetline", "unit": "unit", "subaddress": "unit", "level": "unit",
                "po_box": "unit", "city": "city", "state": "state", "postcode": "zip"}
# Reference coarse values without spans keep this unit-family order.
UNIT_ORDER = ("unit", "subaddress", "level", "po_box")
STREET_PART = {"us:StreetNamePreDirectional": "predir", "us:StreetNamePostType": "suffix", "us:StreetNamePostDirectional": "postdir"}
STREET_ORDER = ("predir", "street", "suffix", "postdir")
NAME_FOLD = {"SAINT": "ST", "FORT": "FT", "MOUNT": "MT"}


def clean(value):
    """Uppercase; drop periods and apostrophes; other characters outside [A-Z0-9/#&] become spaces."""
    text = str(value or "").upper().replace(".", "").replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9/#& ]", " ", text)).strip()


def canon(field, value):
    text = clean(value)
    if not text:
        return ""
    if field == "streetline":
        # Written forms of one route fold first, then token-wise C1 suffix, B directional and name folds.
        text = re.sub(r"\b(COUNTY|CNTY|CO) (RD|ROAD)\b", "CR", text)
        text = re.sub(r"\bUS (HWY|HIGHWAY|ROUTE|RTE)\b", "US", text)
        text = re.sub(r"\bSTATE (ROUTE|RTE|ROAD|RD)\b", "SR", text)
        text = re.sub(r"\b(STATE (HWY|HIGHWAY)|SH)\b", "SH", text)
        text = re.sub(r"\b(INTERSTATE|IH)\b", "I", text)
        return " ".join(DIRECTIONALS.get(t, SUFFIXES.get(t, t)) for t in (NAME_FOLD.get(t, t) for t in text.split()))
    if field == "city":
        return " ".join(DIRECTIONALS.get(t, t) for t in (NAME_FOLD.get(t, t) for t in text.split()))
    if field == "state":
        return STATES.get(text, text)
    if field == "zip":
        digits = re.sub(r"\D", "", text)
        return digits[:5] if len(digits) >= 5 else "0" + digits if len(digits) == 4 else digits
    if field == "unit":
        text = re.sub(r"\b(POST OFFICE|P O|PO) BOX\b", "PO BOX", text)
        text = re.sub(r"\bPOB\b", "PO BOX", text)
        text = re.sub(r"\b(RURAL ROUTE|RFD|R R)\b", "RR", text)
        text = re.sub(r"\b(HIGHWAY CONTRACT( ROUTE)?|STAR ROUTE|HCR)\b", "HC", text)
        return " ".join(UNIT_DESIGNATORS.get(t, t) for t in text.replace("#", " ").split())
    return text


def key(field, value):
    """Equality ignores spacing inside one field ("W 615" = "W615"); field boundaries still count."""
    return canon(field, value).replace(" ", "")


def _collect(items):
    """(fine role, value) pairs in source order -> profile field values."""
    parts = {}
    for fine, value in items:
        coarse = FINE_TO_COARSE.get(fine) if fine else None
        field = COARSE_FIELD.get(coarse)
        if field is None:
            continue
        slot = (field, STREET_PART.get(fine, "street")) if field == "streetline" else (field, None)
        # A predirectional after a name word is inside the name (Pub 28), e.g. OLD SOUTH PLANK ROAD.
        if slot == ("streetline", "predir") and ("streetline", "street") in parts:
            slot = ("streetline", "street")
        parts.setdefault(slot, []).append(value)
    out = {}
    for (field, part), values in parts.items():
        out.setdefault(field, {})[part] = " ".join(values)
    return {field: " ".join(p[x] for x in (STREET_ORDER if field == "streetline" else (None,)) if p.get(x))
            for field, p in out.items()}


def reference_fields(row):
    reference = row["reference"]
    if reference["spans_coverage"] == "complete":
        raw = row["text"].encode("utf-8")
        ordered = sorted(reference["spans"], key=lambda x: x["span"])
        return _collect((x["role"], raw[x["span"][0]:x["span"][1]].decode("utf-8")) for x in ordered)
    values = {}
    for coarse in sorted(reference["fields"], key=lambda r: UNIT_ORDER.index(r) if r in UNIT_ORDER else -1):
        field = COARSE_FIELD.get(coarse)
        if field and reference["fields"][coarse]:
            values[field] = " ".join(v for v in [values.get(field)] + reference["fields"][coarse] if v)
    return values


def supplied_fields(reference):
    if reference["coverage"] == "complete":
        return list(FIELDS)
    supplied = {COARSE_FIELD[r] for r in reference["fields"] if r in COARSE_FIELD}
    return [f for f in FIELDS if f in supplied]


def score_profile(name, row, prediction, metadata):
    require(name in PROFILES, "unknown scoring profile: " + str(name))
    reference = row["reference"]
    inferred = sorted({x.get("role") for x in prediction.get("inferred", []) if isinstance(x, dict) and x.get("role")})
    if reference["coverage"] == "none":
        return dict(agrees=None, scored_fields=[], mismatched_fields=[], inferred_roles=inferred)
    scored = supplied_fields(reference)
    if not scored:
        return dict(agrees=None, scored_fields=[], mismatched_fields=[], inferred_roles=inferred)
    gold = reference_fields(row)
    mapping = metadata["role_map"]
    predicted = _collect((mapping.get(x["native_role"]), x["value"]) for x in prediction["evidence"]) if prediction["status"] == "ok" else {}
    mismatched = [f for f in scored if key(f, gold.get(f)) != key(f, predicted.get(f))]
    return dict(agrees=prediction["status"] == "ok" and not mismatched, scored_fields=scored,
                mismatched_fields=mismatched, inferred_roles=inferred)


def summarize_profile(results):
    known = [r for r in results if r["agrees"] is not None]
    correct = sum(r["agrees"] for r in known)
    return dict(correct=correct, denominator=len(known), rate=correct / len(known) if known else None,
                inferred_state_rows=sum("state" in r["inferred_roles"] for r in results))


def check_profiles(manifest):
    names = manifest.get("scoring_profiles")
    if names is None:
        return
    require(isinstance(names, list) and names and len(names) == len(set(names)) and all(n in PROFILES for n in names),
            "unknown or duplicate scoring profile")
    require(manifest["task"] == "parse", "scoring profiles apply to parsing corpora")
