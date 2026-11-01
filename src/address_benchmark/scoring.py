"""Versioned, identical policies for every adapter. No prediction repair."""
from __future__ import annotations

from collections import Counter, defaultdict
import re

from .protocol import FINE_TO_COARSE

SCORER = "address-benchmark.scorer/v1"
NORMALIZATION = "casefold-whitespace/v1"
DELIMITER_POLICY = "casefold-whitespace-edge-delimiters/v1"


def normalize(value):
    # Intentionally preserves punctuation, accents, abbreviations and digit width.
    return re.sub(r"\s+", " ", value.casefold()).strip()


def normalize_delimiters(value):
    return normalize(value).strip(",;:").strip()


def project(evidence, mapping):
    fields, previous = defaultdict(list), None
    for item in evidence:
        fine = mapping[item["native_role"]]
        role = FINE_TO_COARSE[fine] if fine else "unsupported:" + item["native_role"]
        if role == previous:
            fields[role][-1] += " " + item["value"]
        else:
            fields[role].append(item["value"])
        previous = role
    return dict(fields)


def prf(tp, fp, fn, *, partial=False):
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    return dict(tp=tp, fp=None if partial else fp, fn=fn,
                precision=None if partial else precision, recall=recall, f1=None if partial else f1)


def fine_score(reference, prediction, metadata, kind):
    coverage = reference[kind + "_coverage"]
    supported = metadata["span_support" if kind == "spans" else "token_support"]
    if coverage == "none" or not supported:
        return dict(status="unannotated" if coverage == "none" else "unsupported", coverage=coverage,
                    metrics=None, per_role={}, unadjudicated=0)
    expected = Counter((x["role"], *x["span"]) for x in reference[kind])
    parts = prediction["evidence" if kind == "spans" else "tokens"]
    observed = Counter((metadata["role_map"][x["native_role"]] or "unsupported:" + x["native_role"], *span)
                       for x in parts for span in (x.get("spans") or []))
    matched, extra, missing = expected & observed, observed - expected, expected - observed
    tp, fp, fn = sum(matched.values()), sum(extra.values()), sum(missing.values())
    partial = coverage == "partial"
    per_role = {}
    role_counts = defaultdict(lambda: [0, 0, 0])
    for index, atoms in enumerate((matched, extra, missing)):
        for (role, _, _), count in atoms.items():
            role_counts[role][index] += count
    for role in sorted({x[0] for x in expected} | ({x[0] for x in observed} if not partial else set())):
        per_role[role] = prf(*role_counts[role], partial=partial)
    return dict(status="measured", coverage=coverage, metrics=prf(tp, fp, fn, partial=partial),
                per_role=per_role, unadjudicated=fp if partial else 0,
                missing_span_items=sum(not x.get("spans") for x in parts))


def score_case(row, prediction, metadata):
    if metadata["tasks"] != ["parse"]:
        from .tasks import score_task
        return score_task(row, prediction, metadata)
    reference = row["reference"]
    expected = reference["fields"]
    fields = project(prediction["evidence"], metadata["role_map"])
    complete = reference["coverage"] == "complete"
    scope = set(expected) | (set(fields) if complete else set())
    gold_values = {r: [normalize(v) for v in values] for r, values in expected.items()}
    predicted_values = {r: [normalize(v) for v in values] for r, values in fields.items()}
    mismatch = sorted(r for r in scope if gold_values.get(r, []) != predicted_values.get(r, []))
    delimiter_mismatch = sorted(r for r in scope if [v.strip(",;:").strip() for v in gold_values.get(r, [])] != [v.strip(",;:").strip() for v in predicted_values.get(r, [])])
    eligible = reference["coverage"] != "none"
    passed = prediction["status"] == "ok" and not mismatch
    return dict(task="parse", id=row["id"], family=row["family"], split=row["split"], origin=row["origin"], subsets=row["subsets"],
                coverage=reference["coverage"], status=prediction["status"],
                primary_agrees=passed if eligible else None,
                supplied_fields_agree=passed if eligible else None,
                complete_address_agrees=passed if complete else None, mismatched_roles=mismatch,
                delimiter_fields_agree=prediction["status"] == "ok" and not delimiter_mismatch if eligible else None,
                delimiter_complete_address_agrees=prediction["status"] == "ok" and not delimiter_mismatch if complete else None,
                delimiter_mismatched_roles=delimiter_mismatch, delimiter_policy=DELIMITER_POLICY,
                unadjudicated_roles=sorted(set(fields) - set(expected)) if not complete else [],
                unsupported_reference_roles=sorted(r for r in expected if r not in {FINE_TO_COARSE[v] for v in metadata.get("active_roles", metadata["supported_roles"])}),
                unsupported_fine_reference_roles=sorted({x["role"] for x in reference["tokens"]} - set(metadata.get("active_roles", metadata["supported_roles"]))),
                spans=fine_score(reference, prediction, metadata, "spans"),
                tokens=fine_score(reference, prediction, metadata, "tokens"))


def summarize(cases):
    if cases and cases[0]["task"] != "parse":
        from .tasks import summarize_task
        return summarize_task(cases)
    def rate(values):
        values = [v for v in values if v is not None]
        return dict(correct=sum(values), denominator=len(values), rate=sum(values) / len(values) if values else None)
    def fine(kind):
        # Partial positive-only recall is never pooled into full precision/F1.
        result = {}
        for coverage in ("complete", "partial"):
            chosen = [c[kind] for c in cases if c[kind]["status"] == "measured" and c[kind]["coverage"] == coverage]
            metrics = [x["metrics"] for x in chosen]
            roles = sorted({role for item in chosen for role in item["per_role"]})
            def total(items):
                return prf(sum(x["tp"] for x in items), sum(x["fp"] or 0 for x in items),
                           sum(x["fn"] for x in items), partial=coverage == "partial")
            result[coverage] = dict(rows=len(chosen), metrics=total(metrics) if chosen else None,
                                    per_role={role: total([x["per_role"][role] for x in chosen if role in x["per_role"]]) for role in roles})
        result["unsupported_rows"] = sum(c[kind]["status"] == "unsupported" for c in cases)
        result["unannotated_rows"] = sum(c[kind]["status"] == "unannotated" for c in cases)
        return result
    return dict(rows=len(cases), source_families=len({c["family"] for c in cases}),
                statuses=dict(Counter(c["status"] for c in cases)),
                supplied_fields=rate([c["supplied_fields_agree"] for c in cases]),
                complete_address=rate([c["complete_address_agrees"] for c in cases]),
                delimiter_fields=rate([c["delimiter_fields_agree"] for c in cases]),
                delimiter_complete_address=rate([c["delimiter_complete_address_agrees"] for c in cases]),
                spans=fine("spans"), tokens=fine("tokens"),
                unadjudicated_rows=sum(bool(c["unadjudicated_roles"]) for c in cases))


def summarize_views(cases):
    # Each origin/split is a separate population; views are never summed.
    populations = sorted({(c["origin"], c["split"]) for c in cases})
    result = {}
    for origin, split in populations:
        population = [c for c in cases if c["origin"] == origin and c["split"] == split]
        result[f"{origin}/{split}/all"] = summarize(population)
        for subset in sorted({s for c in population for s in c["subsets"]}):
            result[f"{origin}/{split}/subset:{subset}"] = summarize([c for c in population if subset in c["subsets"]])
    return result
