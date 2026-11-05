"""Map frozen-scorer Doorplate denominators onto the legacy token-aligned population.

The legacy fine and unit-token reports judged only rows whose gold token values equal
the input's whitespace tokens. This prints aggregate counts for all rows, for the
excluded rows, and for the kept rows, plus the SHA-256 of the sorted excluded IDs.
It never prints row text or IDs.

    python -E -s tools/doorplate_alignment_map.py COMPARE.jsonl.gz RUN/e429-accuracy/cases.jsonl
"""
import gzip
import hashlib
import json
import sys


def fine_exact(case):
    tokens = case["tokens"]
    return (case["status"] == "ok" and tokens["status"] == "measured" and tokens["coverage"] == "complete"
            and not tokens["metrics"]["fp"] and not tokens["metrics"]["fn"] and not tokens.get("missing_span_items"))


def aggregate(cases):
    units = [c["unit_ownership"] for c in cases]
    return dict(rows=len(cases), fine_exact=sum(map(fine_exact, cases)),
                unit_positive_rows=sum(u["gold_unit"] is True for u in units),
                unit_positive_correct=sum(u["gold_unit"] is True and u["span_agrees"] is True for u in units),
                unit_negative_rows=sum(u["gold_unit"] is False and u["span_agrees"] is not None for u in units),
                false_unit_rows=sum(u["gold_unit"] is False and u["span_agrees"] is False for u in units),
                negative_tokens=sum(u["negative_tokens"] or 0 for u in units),
                false_positive_tokens=sum(u["false_positive_tokens"] or 0 for u in units),
                delimiter_correct=sum(c["delimiter_fields_agree"] is True for c in cases),
                strict_correct=sum(c["primary_agrees"] is True for c in cases))


def main(compare, cases_path):
    with gzip.open(compare, "rt", encoding="utf-8") as handle:
        excluded = {str(r["id"]) for r in map(json.loads, handle) if [v for v, _ in r["tokens"]] != r["input"].split()}
    cases = [json.loads(line) for line in open(cases_path, encoding="utf-8")]
    native = lambda case: case["id"].split(":", 1)[1]
    out = dict(rule="gold token values != input.split()",
               excluded_ids_sha256=hashlib.sha256(("\n".join(sorted(excluded)) + "\n").encode()).hexdigest(),
               all=aggregate(cases), excluded=aggregate([c for c in cases if native(c) in excluded]),
               kept=aggregate([c for c in cases if native(c) not in excluded]))
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(*sys.argv[1:3])
