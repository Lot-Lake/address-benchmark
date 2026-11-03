"""Versioned, identical policies for every adapter. No prediction repair."""
from __future__ import annotations

from collections import Counter, defaultdict
import re

from .protocol import FINE_TO_COARSE

SCORER = "address-benchmark.scorer/v1"
SCOPED_SCORER = "address-benchmark.scorer/v2"
NORMALIZATION = "casefold-whitespace/v1"
EFFECT_ROLES = {"unit": ("unit",), "building": ("building",), "recipient": ("recipient",), "road_city": ("road", "city")}
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


def score_case(row, prediction, metadata, profiles=(), *, scorer=SCORER):
    if scorer == SCOPED_SCORER:
        return score_scoped_case(row, prediction, metadata, profiles)
    if scorer != SCORER:
        raise ValueError("unsupported scorer policy")
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
    extra = {}
    if profiles:
        from .profiles import score_profile
        extra["profiles"] = {name: score_profile(name, row, prediction, metadata) for name in profiles}
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
                tokens=fine_score(reference, prediction, metadata, "tokens"), **extra)


def score_scoped_case(row, prediction, metadata, profiles=()):
    # Reuse the fixed v1 normalization/projection and fine positive-only policy.
    # An inactive role cannot earn a TP merely because a broad role_map has it.
    active = set(metadata.get("active_roles", metadata["supported_roles"]))
    metadata = {**metadata, "role_map": {key: value if value in active else None
                                        for key, value in metadata["role_map"].items()}}
    result = score_case(row, prediction, metadata)
    expected = row["reference"]["fields"]
    fields = project(prediction["evidence"], metadata["role_map"])
    supported = {FINE_TO_COARSE[r] for r in active}
    scope = set(expected) | (set(fields) if result["coverage"] == "complete" else set())
    role_agreement = {}
    for role in sorted(scope):
        # Unsupported positive assertions remain misses. Unsupported absence is
        # unjudged, and cannot inflate supplied-field or whole-address accuracy.
        role_agreement[role] = (None if not expected.get(role) and role not in supported else
                                prediction["status"] == "ok" and role in supported and
                                [normalize(v) for v in expected.get(role, [])] ==
                                [normalize(v) for v in fields.get(role, [])])
    judged = [v for v in role_agreement.values() if v is not None]
    passed = all(judged) if judged and len(judged) == len(role_agreement) else None
    result.update(source=row["source"], role_agreement=role_agreement,
                  primary_agrees=passed, supplied_fields_agree=passed,
                  complete_address_agrees=passed if result["coverage"] == "complete" and
                  all(v is not None for v in role_agreement.values()) else None)
    result["effects_agreement"] = {key: all(role_agreement[r] for r in roles)
        if all(role_agreement.get(r) is not None for r in roles) else None for key, roles in EFFECT_ROLES.items()}
    # Do not let the edge-delimiter view bypass the same eligibility contract.
    delimiter = [prediction["status"] == "ok" and role not in result["delimiter_mismatched_roles"]
                 and role in supported
                 for role, value in role_agreement.items() if value is not None]
    result["delimiter_fields_agree"] = all(delimiter) if delimiter and len(delimiter) == len(role_agreement) else None
    result["delimiter_complete_address_agrees"] = (result["delimiter_fields_agree"]
        if result["complete_address_agrees"] is not None else None)
    # Existing streetline profiles require their own complete source semantics;
    # partial source scopes cannot establish those derived whole-line claims.
    if profiles:
        from .profiles import COARSE_FIELD, score_profile
        result["profiles"] = {name: score_profile(name, row, prediction, metadata) for name in profiles}
        for profile in result["profiles"].values():
            if any(field in profile["scored_fields"] and role not in supported and not expected.get(role)
                   for role, field in COARSE_FIELD.items()):
                profile["agrees"] = None
    return result


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
            result[coverage] = dict(rows=len(chosen), eligible_rows=sum(bool(m["tp"] + (m["fp"] or 0) + m["fn"]) for m in metrics), metrics=total(metrics) if chosen else None,
                                    per_role_rows={role: sum(role in item["per_role"] for item in chosen) for role in roles},
                                    per_role={role: total([x["per_role"][role] for x in chosen if role in x["per_role"]]) for role in roles})
        result["unsupported_rows"] = sum(c[kind]["status"] == "unsupported" for c in cases)
        result["unannotated_rows"] = sum(c[kind]["status"] == "unannotated" for c in cases)
        return result
    extra = {}
    if cases and "role_agreement" in cases[0]:
        from .io import identity
        # Private aggregate membership pins prevent equal-sized but different
        # eligibility sets from being presented as a matched comparison.
        extra["eligibility"] = {key: identity(sorted(c["id"] for c in cases if c[field] is not None))
            for key, field in (("supplied_fields", "supplied_fields_agree"), ("complete_address", "complete_address_agrees"),
                               ("delimiter_fields", "delimiter_fields_agree"), ("delimiter_complete_address", "delimiter_complete_address_agrees"))}
        extra["eligibility"]["tokens"] = identity(sorted(c["id"] for c in cases
            if c["tokens"]["status"] == "measured" and c["tokens"]["coverage"] == "complete"))
        extra["effects"] = {key: rate([c["effects_agreement"][key] for c in cases]) for key in EFFECT_ROLES}
        extra["coverage"] = dict(Counter(c["coverage"] for c in cases))
        extra["roles"] = {role: rate([c["role_agreement"].get(role) for c in cases])
                          for role in sorted({r for c in cases for r in c["role_agreement"]})}
    if cases and "profiles" in cases[0]:
        from .profiles import summarize_profile
        extra["profiles"] = {name: summarize_profile([c["profiles"][name] for c in cases]) for name in cases[0]["profiles"]}
    return dict(rows=len(cases), source_families=len({c["family"] for c in cases}),
                statuses=dict(Counter(c["status"] for c in cases)),
                supplied_fields=rate([c["supplied_fields_agree"] for c in cases]),
                complete_address=rate([c["complete_address_agrees"] for c in cases]),
                delimiter_fields=rate([c["delimiter_fields_agree"] for c in cases]),
                delimiter_complete_address=rate([c["delimiter_complete_address_agrees"] for c in cases]),
                spans=fine("spans"), tokens=fine("tokens"),
                unadjudicated_rows=sum(bool(c["unadjudicated_roles"]) for c in cases), **extra)


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



GATE_METRICS = ("strict", "delimiter", "strict-streetline/v1", "strict-streetline/v2")


def case_agreement(case, metric="strict"):
    if metric == "strict":
        return case["primary_agrees"]
    if metric == "delimiter":
        return case.get("delimiter_fields_agree")
    if metric in GATE_METRICS:
        return case.get("profiles", {}).get(metric, {}).get("agrees")
    raise ValueError("unsupported gate metric")

def comparison(left, right, cohorts=(), *, metric="strict"):
    """Paired private identities and aggregate effects on identical judgments."""
    if len(left) != len(right) or any(a["id"] != b["id"] for a, b in zip(left, right)):
        raise ValueError("comparative case streams differ")
    records, counts = [], dict(left_only=0, right_only=0, judged_pairs=0, unmatched_judgments=0)
    roles = defaultdict(lambda: dict(left_only=0, right_only=0, judged_pairs=0))
    effects = {key: dict(left_only=0, right_only=0, judged_pairs=0) for key in EFFECT_ROLES}
    for a, b in zip(left, right):
        av, bv = case_agreement(a, metric), case_agreement(b, metric)
        counts["unmatched_judgments"] += (av is None) != (bv is None)
        counts["judged_pairs"] += av is not None and bv is not None
        counts["left_only"] += av is True and bv is False
        counts["right_only"] += bv is True and av is False
        for role in set(a.get("role_agreement", {})) | set(b.get("role_agreement", {})):
            x, y = a.get("role_agreement", {}).get(role), b.get("role_agreement", {}).get(role)
            roles[role]["judged_pairs"] += x is not None and y is not None
            roles[role]["left_only"] += x is True and y is False
            roles[role]["right_only"] += y is True and x is False
        for key in EFFECT_ROLES:
            x, y = a.get("effects_agreement", {}).get(key), b.get("effects_agreement", {}).get(key)
            effects[key]["judged_pairs"] += x is not None and y is not None
            effects[key]["left_only"] += x is True and y is False
            effects[key]["right_only"] += y is True and x is False
        records.append(dict(id=a["id"], family=a["family"], coverage=a["coverage"],
                            left_agrees=av, right_agrees=bv,
                            left_mismatched_roles=a.get("mismatched_roles"), right_mismatched_roles=b.get("mismatched_roles")))
    retention = {}
    for cohort in cohorts:
        members = set(cohort["row_ids"])
        chosen = [(a, b) for a, b in zip(left, right) if a["id"] in members]
        retention[cohort["id"]] = dict(denominator=len(members),
            left_correct=sum(case_agreement(a, metric) is True for a, _ in chosen),
            right_correct=sum(case_agreement(b, metric) is True for _, b in chosen),
            retained=sum(case_agreement(a, metric) is True and case_agreement(b, metric) is True for a, b in chosen),
            left_unjudged=sum(case_agreement(a, metric) is None for a, _ in chosen),
            right_unjudged=sum(case_agreement(b, metric) is None for _, b in chosen))
    return records, dict(**counts, roles=dict(roles), effects=effects, preservation=retention)
