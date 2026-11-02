"""Render the nad-rendered parsing corpus from National Address Database (NAD) records.

    python3 tools/render_nad.py --nad NAD_TEXT.csv --out OUT [--per-state N] [--seed S]

NAD_TEXT.csv is a NAD r24 text extract with its header line (the full TXT/NAD_r24.txt member, or a sample of its
lines). The recipe (datasets/nad-rendered/recipe.json) pins the source, seed and strata. The data is not bundled:
this writes OUT/cases.jsonl and OUT/manifest.json locally, with the input file's SHA-256 and the NAD_Source
providers per state. Every row is GENERATED (origin "generated"): NAD structured fields rendered into one line.
They are not naturally entered addresses.

Record admission: a 1-6 digit Add_Number without prefix/suffix/post-modifier/building/floor; a 50-state code; a
five-digit ZIP; a usable city (Post_City, else Inc_Muni); a street name of plain characters (St_PreMod, St_PreTyp,
St_PreSep and St_Name joined); a street type, if present, that Publication 28 knows; Pub 28 directionals; a unit
that is empty, one short id, or a Pub 28 designator plus one id. A name whose last token is itself a street type
with no St_PosTyp is skipped (the "MAIN ST stored as the name" pattern). States with fewer than min_state usable
records are skipped; at most per_state records per state are kept with a seeded
reservoir, then shuffled per state. Memory is bounded by the retained sample.

Rendering, round-robin over a seeded shuffle (equal strata per state):
  clean     "123 N Main St Apt 5, Salt Lake City, UT 84101"   title case, commas, Pub 28 abbreviations
  nocomma   "123 N MAIN ST APT 5 SALT LAKE CITY UT 84101"     uppercase, no commas
  expanded  "123 NORTH MAIN STREET APARTMENT 5, SALT LAKE CITY, UT 84101"   uppercase, commas, spelled out
  noisy     lowercase (p .5), doubled spaces (p .5), comma placement noise, ZIP or state or both dropped
            (p .2 / .2 / .02), units typed APT/UNIT/# or bare rendered as "#5", "APT 5" or "UNIT 5"

References are COMPLETE and LITERAL: each coarse value is the exact rendered text of that segment (the street line
pre-directional + name + type + post-directional is one `road` value), with the line's case transform applied. A
field dropped from the line is absent from the reference.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import random
import re

ROOT = Path(__file__).resolve().parents[1]
RECIPE = json.loads((ROOT / "datasets/nad-rendered/recipe.json").read_text())
TABLES = json.loads((ROOT / "datasets/nad-rendered/pub28-forms.json").read_text())
STRATA = tuple(RECIPE["generator"]["strata"])
FIFTY = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
UNIT_ID = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,5}$")


def clean(value):
    text = str(value or "").upper().replace(".", "").replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9/#& ]", " ", text)).strip()


def forms(kind):
    return {re.sub(r"[^A-Z0-9 ]", " ", f.upper()).strip(): abbr for abbr, e in TABLES[kind].items() for f in e["forms"]}


SUFFIX, DIRS, UNITS = forms("suffix"), forms("directional"), forms("unit")
FULL = {kind: {abbr: e["name"] for abbr, e in TABLES[kind].items()} for kind in ("suffix", "directional", "unit")}


def fold(kind, value):
    text = clean(value)
    table = {"suffix": SUFFIX, "directional": DIRS}[kind]
    return table.get(text, table.get(text.replace(" ", ""), text)) if text else ""


def split_unit(raw):
    """-> (designator abbreviation or "", id), or None when unusable."""
    # Keep identifier hyphens; the general street cleaner treats them as spaces.
    text = str(raw or '').upper().replace('.', '').replace('#', ' ')
    tokens = text.split()
    if not tokens:
        return ("", "")
    if len(tokens) == 1 and UNIT_ID.match(tokens[0]):
        return ("", tokens[0])
    if len(tokens) == 2 and tokens[0] in UNITS and UNIT_ID.match(tokens[1]):
        return (UNITS[tokens[0]], tokens[1])
    return None


def admit(r):
    if r["State"] not in FIFTY or not re.fullmatch(r"\d{1,6}", r["Add_Number"] or "x"):
        return None
    if r["AddNum_Pre"] or r["AddNum_Suf"] or r["St_PosMod"] or r["Building"] or r["Floor"]:
        return None
    zip5 = (r["Zip_Code"] or "")[:5]
    city = r["Post_City"] if r["Post_City"] not in ("", "Not stated") else r["Inc_Muni"]
    if not re.fullmatch(r"\d{5}", zip5) or city in ("", "Not stated", "Unincorporated") or not re.fullmatch(r"[A-Za-z .'-]{2,40}", city):
        return None
    name = " ".join(x for x in (r["St_PreMod"], r["St_PreTyp"], r["St_PreSep"], r["St_Name"]) if x)
    if not r["St_Name"] or not re.fullmatch(r"[A-Za-z0-9 .'/-]{1,40}", name):
        return None
    tokens = clean(name).split()
    if not r["St_PosTyp"] and len(tokens) > 1 and tokens[-1] in SUFFIX:
        return None
    if r["St_PosTyp"] and fold("suffix", r["St_PosTyp"]) not in FULL["suffix"]:
        return None
    for field in ("St_PreDir", "St_PosDir"):
        if r[field] and fold("directional", r[field]) not in FULL["directional"]:
            return None
    unit = split_unit(r["Unit"])
    if unit is None:
        return None
    return {"number": r["Add_Number"], "predir": fold("directional", r["St_PreDir"]), "street": clean(name),
            "suffix": fold("suffix", r["St_PosTyp"]), "postdir": fold("directional", r["St_PosDir"]), "unit": unit,
            "city": clean(city), "state": r["State"], "zip": zip5}


def render(rec, stratum, rng):
    """-> (line, reference fields): every reference value is the literal rendered segment."""
    expanded = stratum == "expanded"
    spell = lambda kind, abbr: FULL[kind][abbr] if expanded and abbr else abbr
    road = " ".join(x for x in (spell("directional", rec["predir"]), rec["street"], spell("suffix", rec["suffix"]),
                                spell("directional", rec["postdir"])) if x)
    designator, uid = rec["unit"]
    style = None
    if stratum == "noisy" and uid and designator in ("", "APT", "UNIT"):
        style = rng.choice(("#", "APT", "UNIT"))
        designator = "" if style == "#" else style
    unit = "" if not uid else f"#{uid}" if style == "#" or not designator else f"{FULL['unit'].get(designator, designator) if expanded else designator} {uid}"
    state, zip5 = rec["state"], rec["zip"]
    if stratum == "noisy":
        drop = rng.random()
        if drop < 0.2:
            zip5 = ""
        elif drop < 0.4:
            state = ""
        elif drop < 0.42:
            zip5 = state = ""
    segments = [("house_number", rec["number"]), ("road", road), ("unit", unit), ("city", rec["city"]), ("state", state), ("postcode", zip5)]
    first = " ".join(v for _, v in segments[:3] if v)
    parts = [p for p in (first, rec["city"], " ".join(x for x in (state, zip5) if x)) if p]
    if stratum == "clean":
        case = lambda s, i: re.sub(r"(?<=\d)(St|Nd|Rd|Th)\b", lambda m: m.group(1).lower(), s.title()) if i < 2 else s
        sep = ", "
    elif stratum in ("nocomma", "expanded"):
        case = lambda s, i: s.upper()
        sep = " " if stratum == "nocomma" else ", "
    else:
        sep = ", " if rng.random() < 0.7 else " "
        lower = rng.random() < 0.5
        case = (lambda s, i: s.lower()) if lower else (lambda s, i: s)
    part_of = {"house_number": 0, "road": 0, "unit": 0, "city": 1, "state": 2, "postcode": 2}
    line = sep.join(case(p, i) for i, p in enumerate(parts))
    if stratum == "noisy" and rng.random() < 0.5:
        line = re.sub(r" ", lambda m: "  " if rng.random() < 0.25 else " ", line).replace(",", " ," if rng.random() < 0.3 else ",")
    fields = {role: [case(value, part_of[role])] for role, value in segments if value}
    return line.strip(), fields


def generate(handle, per_state, seed, min_state):
    if type(per_state) is not int or per_state <= 0 or type(min_state) is not int or min_state <= 0:
        raise ValueError('positive per-state and minimum-state counts required')
    reader = csv.reader(handle)
    columns = next(reader)
    records, providers = defaultdict(list), defaultdict(Counter)
    usable, sampling_rng = Counter(), {}
    for row in reader:
        if len(row) != len(columns):
            continue
        r = dict(zip(columns, row))
        rec = admit(r)
        if rec:
            state = rec['state']
            usable[state] += 1
            if state not in sampling_rng:
                sampling_rng[state] = random.Random(f'{seed}-{state}-reservoir-v1')
            rng = sampling_rng[state]
            retained = records[state]
            if len(retained) < per_state:
                retained.append(rec)
            else:
                index = rng.randrange(usable[state])
                if index < per_state:
                    retained[index] = rec
            providers[state][r.get("NAD_Source") or "(none)"] += 1
    rows, meta = [], {}
    for state in sorted(records):
        rng = random.Random(f"{seed}-{state}")
        recs = records[state]
        if usable[state] < min_state:
            continue
        rng.shuffle(recs)
        recs = recs[:per_state]
        meta[state] = {"usable": usable[state], "kept": len(recs), "providers": dict(providers[state].most_common(8))}
        for i, rec in enumerate(recs):
            stratum = STRATA[i % len(STRATA)]
            line, fields = render(rec, stratum, rng)
            digest = hashlib.sha256(line.encode()).hexdigest()
            rows.append({"family": "exact-input-proxy:" + digest, "id": f"nad-rendered:{state}-{i:05d}", "origin": RECIPE["origin"],
                         "reference": {"coverage": "complete", "fields": fields, "spans": [], "spans_coverage": "none",
                                       "tokens": [], "tokens_coverage": "none"},
                         "split": "generated", "subsets": [stratum, "state:" + state], "text": line})
    return rows, meta


def manifest(data, input_sha256, meta, settings):
    sha = hashlib.sha256(data).hexdigest()
    return {"schema": "address-benchmark.corpus/v1", "id": RECIPE["id"], "version": RECIPE["version"], "country": "US", "locale": "en-US",
            "task": "parse", "ontology": "address-benchmark.us-roles/v2",
            "provenance": {"source": RECIPE["source"]["catalog"], "upstream_revision": RECIPE["source"]["member"] + " sha256:" + input_sha256,
                           "file": RECIPE["source"]["file"], "generator": "tools/render_nad.py", "settings": settings, "states": meta},
            "license": {"spdx": RECIPE["license"]["spdx"], "redistribution": "local-only", "notice": RECIPE["license"]["notice"]},
            "construction": ["Rendered by tools/render_nad.py from NAD structured fields (see its docstring)",
                             "GENERATED one-line strings; not naturally entered; literal complete references"],
            "annotation_policy": "docs/spec/annotations.md#external-and-private-corpora",
            "exposure": {"status": "generated from public NAD records; parsers trained on OpenAddresses/NAD lineage may be exposed to the records",
                         "history": ["Generated locally from the pinned recipe"]},
            "family_policy": "Exact-input hash proxy; one rendering per NAD record.",
            "split_policy": "One generated split; strata and states are views.",
            "resources": [{"path": "cases.jsonl", "sha256": sha, "bytes": len(data)}]}


def main():
    g = RECIPE["generator"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--nad", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-state", type=int, default=g["per_state"])
    parser.add_argument("--seed", default=g["seed"])
    args = parser.parse_args()
    input_hash = hash_file(args.nad)
    with args.nad.open('r', encoding='utf-8-sig', errors='strict', newline='') as handle:
        rows, meta = generate(handle, args.per_state, args.seed, g['min_state'])
    if hash_file(args.nad) != input_hash:
        raise ValueError('NAD input changed during generation')
    if not rows:
        raise ValueError('NAD input produced no admissible sampled rows')
    args.out.mkdir(parents=True)
    data = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for r in rows).encode()
    (args.out / "cases.jsonl").write_bytes(data)
    settings = {"seed": args.seed, "per_state": args.per_state, "min_state": g["min_state"], 'sampler': 'per-state-reservoir/v1'}
    (args.out / "manifest.json").write_text(json.dumps(manifest(data, input_hash, meta, settings), indent=2, sort_keys=True) + "\n")
    print(json.dumps({"rows": len(rows), "states": sorted(meta)}))


def hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
