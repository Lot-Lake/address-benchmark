"""Task-specific policies; no single composite address quality score."""
from collections import Counter

from .scoring import prf
from .io import canonical, require

NORMALIZE_SCORER = "address-benchmark.normalized-text-exact/v1"
MATCH_SCORER = "address-benchmark.identity-key-equality/v1"


def score_task(row, prediction, metadata):
    task = metadata["tasks"][0]
    ref = row["reference"]
    eligible = ref["coverage"] == "complete"
    result = dict(task=task, id=row["id"], family=row["family"], split=row["split"], origin=row["origin"],
                  subsets=row["subsets"], coverage=ref["coverage"], status=prediction["status"])
    if task in ("normalize", "format"):
        result["primary_agrees"] = prediction["status"] == "ok" and prediction["normalized"] == ref["values"] if eligible else None
        result["scorer"] = NORMALIZE_SCORER
    elif task == "match":
        decided = prediction["keys"][0] == prediction["keys"][1] if prediction["status"] == "ok" else None
        result.update(expected_same=ref["same_entity"], predicted_same=decided,
                      primary_agrees=decided == ref["same_entity"] if eligible and decided is not None else False if eligible else None,
                      scorer=MATCH_SCORER)
    elif task == "stability":
        value = prediction["result"]
        checks = {key: False for key in ref["checks"]}
        if prediction["status"] == "ok":
            targets = {"repeat": "repeat", "scalar_batch": "batch", "idempotence": "normalized_twice", "scalar_stream": "stream", "scalar_chunked": "chunked"}
            needed = {"scalar"} | {targets[key] for key in checks}
            require(isinstance(value, dict) and all(isinstance(value.get(k), list) for k in needed), "stability observations required")
            require(all(len(value[k]) == len(row["payload"]["texts"]) for k in needed), "stability stream length differs")
            checks = {key: canonical(value["scalar"]) == canonical(value[targets[key]]) for key in checks}
        result.update(checks=checks, primary_agrees=all(checks.values()) if eligible else None, scorer="address-benchmark.stability-observations/v1")
    elif task == "variants":
        values = prediction["result"] if prediction["status"] == "ok" else []
        require(isinstance(values, list) and all(isinstance(x, str) for x in values), "variant strings required")
        proposed, allowed, required = set(values), set(ref["allowed"]), set(ref["required"])
        result.update(primary_agrees=prediction["status"] == "ok" and required <= proposed <= allowed if eligible else None,
                      required_found=len(proposed & required), required_total=len(required),
                      disallowed=len(proposed - allowed), duplicate_outputs=len(values) - len(proposed), scorer="address-benchmark.variant-inventory/v1")
    else:
        result.update(primary_agrees=prediction["status"] == "ok" and canonical(prediction["result"]) == canonical(ref["expected"]) if eligible else None,
                      scorer="address-benchmark.typed-json-exact/v1")
    return result


def summarize_task(cases):
    task = cases[0]["task"]
    known = [c for c in cases if c["primary_agrees"] is not None]
    n = len(known)
    result = dict(task=task, rows=len(cases), source_families=len({c["family"] for c in cases}),
                  statuses=dict(Counter(c["status"] for c in cases)),
                  agreement=dict(correct=sum(c["primary_agrees"] for c in known), denominator=n,
                                 rate=sum(c["primary_agrees"] for c in known) / n if n else None))
    if task == "match":
        tp = sum(c["expected_same"] is True and c["predicted_same"] is True for c in known)
        fp = sum(c["expected_same"] is False and c["predicted_same"] is True for c in known)
        fn = sum(c["expected_same"] is True and c["predicted_same"] is not True for c in known)
        tn = sum(c["expected_same"] is False and c["predicted_same"] is False for c in known)
        missing_negative = sum(c["expected_same"] is False and c["predicted_same"] is None for c in known)
        result.update(same_entity=prf(tp, fp, fn), distinct_entity_collisions=fp, true_distinct=tn,
                      undecided_distinct=missing_negative, key_coverage=sum(c["predicted_same"] is not None for c in known) / n if n else None,
                      scope="authored pair decisions at delivery-unit level; no clustering/ranked-search or real-world prevalence claim")
    elif task == "stability":
        result["checks"] = {key: dict(passed=sum(c["checks"].get(key, False) for c in known if key in c["checks"]), denominator=sum(key in c["checks"] for c in known))
                            for key in sorted({k for c in known for k in c["checks"]})}
    elif task == "variants":
        result.update(required_found=sum(c["required_found"] for c in known), required_total=sum(c["required_total"] for c in known),
                      disallowed=sum(c["disallowed"] for c in known), duplicate_outputs=sum(c["duplicate_outputs"] for c in known))
    return result
