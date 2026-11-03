"""Human-readable comparison with annotation and timing scope in the table."""
from __future__ import annotations


def agreement(value):
    if value["rate"] is None:
        return "unmeasured"
    return f"{value['correct']}/{value['denominator']} ({100 * value['rate']:.1f}%)"


def render(report):
    if report["task"] != "parse":
        return render_task(report)
    lines = ["# Address benchmark", "", f"Corpus: `{report['corpus']['id']}` · status: **{report['status']}**",
             "", "Original/native evidence only. Supplied-field agreement on partial references is not whole-address accuracy.",
             "Views overlap and must not be summed. Authored, natural, generated, and source-field-supervised inputs are separate populations.",
             "", "| Engine | Population/view | Rows / families | Supplied fields | Complete address |",
             "| --- | --- | ---: | ---: | ---: |"]
    for name, entry in report["accuracy"].items():
        if entry["status"] != "ok":
            lines.append(f"| {name} | {entry['status']} (exit {entry['exit_code']}) | — | unmeasured | unmeasured |")
        for population, m in entry.get("populations", {}).items():
            lines.append(f"| {name} | {population} | {m['rows']} / {m['source_families']} | {agreement(m['supplied_fields'])} | {agreement(m['complete_address'])} |")
    lines += ["", "Fine token/span precision, recall, F1, role counts, errors/refusals, unsupported roles and per-case deltas are in `run.json` and the hashed case artifacts.",
              "Partial fine annotations support positive-label recall only: precision and F1 remain unmeasured.", ""]
    if report["trials"]:
        lines += ["## Exploratory paired throughput", "", "Independent processes; paired engine order reversed on alternating trials. Every engine uses the same shuffled input-only panel.",
                  "Allocation/public API included; output destruction, validation, JSON artifacts, startup and model load excluded. A command bridge includes its pipe/JSON work.",
                  "", "| Ratio (>1 favors numerator) | Complete pairs | Median | Conditional bootstrap 95% interval | Status |",
                  "| --- | ---: | ---: | --- | --- |"]
        for label, m in report["paired"].items():
            value = f"{m['median_ratio']:.4f}" if m["median_ratio"] else "unmeasured"
            interval = "unmeasured" if m["bootstrap_95_interval"] is None else "–".join(f"{x:.4f}" for x in m["bootstrap_95_interval"])
            lines.append(f"| {label} | {m['pairs']}/{m['expected_pairs']} | {value} | {interval} | {m['status']} |")
        noisy = [f"trial {trial['trial']} {name}" for trial in report["trials"] for name, cell in trial["engines"].items() if cell.get("noisy_over_10_percent")]
        if noisy:
            lines += ["", "Sample spread >10%: " + ", ".join(noisy) + "."]
        lines += ["", "Keep raw per-process samples and exits. The interval assumes independent pairs; shared-host load and thermal effects can violate this. Missing/failing trials invalidate a full-cohort ratio."]
    lines += ["", "## Limits", ""] + ["- " + item for item in report["limitations"]]
    return "\n".join(lines) + "\n"


def render_task(report):
    task = report["task"]
    lines = [f"# Address {task} benchmark", "", f"Corpus: `{report['corpus']['id']}` · status: **{report['status']}**", "",
             "Each named profile is a separate task. Authored conformance evidence is not population accuracy or an unseen evaluation.", "",
             "| Engine | Population/view | Rows / families | Exact agreement | Distinct-entity collisions |",
             "| --- | --- | ---: | ---: | ---: |"]
    for name, entry in report["accuracy"].items():
        if entry["status"] != "ok":
            lines.append(f"| {name} | {entry['status']} (exit {entry['exit_code']}) | — | unmeasured | — |")
        for label, m in entry.get("populations", {}).items():
            lines.append(f"| {name} | {label} | {m['rows']} / {m['source_families']} | {agreement(m['agreement'])} | {m.get('distinct_entity_collisions', 'n/a')} |")
    lines += ["", "Normalization compares ordered output strings exactly under the corpus's named profile. Identity uses independently authored pair labels and native key equality; missing/error outputs remain in the agreement denominator.",
              "Pair precision/recall/F1, same-entity stability, collision counts, coverage, statuses and per-case deltas are retained in `run.json` and the case artifacts.", ""]
    if report["trials"]:
        lines += ["Paired exploratory timing, every raw sample, reversed run orders and actual process exits are retained in `run.json`.", ""]
    lines += ["## Limits", ""] + ["- " + item for item in report["limitations"]]
    return "\n".join(lines) + "\n"


# Publication is an allowlist projection, not recursive key deletion. In
# particular, corpus/engine/source/subset/cohort names are arbitrary private data.
STATUSES = {"ok", "complete", "incomplete", "gated", "measured", "unmeasured", "unavailable", "failed", "invalid", "timeout", "refused", "error", "passed", "not-requested", "not-executed", "executed", "blocked-by-accuracy-gate"}


def public_status(value):
    return value if value in STATUSES else "unavailable"


def public_numbers(value, keys):
    import math
    return {key: value[key] for key in keys if key in value and
            (value[key] is None or type(value[key]) in (bool, int, float) and
             (type(value[key]) is not float or math.isfinite(value[key])))}



def public_interval(value):
    if isinstance(value, list) and len(value) == 2 and len(public_numbers(dict(enumerate(value)), (0, 1))) == 2:
        return value if all(type(x) in (int, float) for x in value) else None
    return None

def public_scorecard(card):
    """Only fixed labels, numeric cells and enumerated policy strings escape."""
    names = {name: f"engine-{i + 1}" for i, name in enumerate(card["engines"])}
    panels = {row["panel"]: f"source-{i + 1}" for i, row in enumerate(card["rows"]) if row["view"] == "all"}
    rows = []
    for i, row in enumerate(card["rows"]):
        panel = panels[row["panel"]]
        view = "all" if row["view"] == "all" else f"view-{i + 1}"
        cells = {}
        for name, cell in row["cells"].items():
            cells[names[name]] = dict(status=public_status(cell["status"]), **public_numbers(cell,
                ("score", "correct", "denominator", "rows", "errors", "refusals", "tp", "fp", "fn", "trials", "noisy", "exit_code", "comparable")))
        rows.append(dict(id=f"{panel}/{view}", label=panel if view == "all" else f"{panel} / {view}", panel=panel,
                         view=view, task=row["task"], metric=row["metric"], **public_numbers(row, ("rows",)), cells=cells))
    return dict(schema="address-benchmark.scorecard/v1", title="Aggregate address benchmark", metric=card["metric"],
                engines=list(names.values()), rows=rows, sources=[dict(id=f"source-{i + 1}", content_id=None,
                    status=public_status(s["status"])) for i, s in enumerate(card["sources"])],
                notes=["Aggregate-only export. Names are positional aliases; the private audit retains their mapping.",
                       "Partial references judge supplied labels only. Unjudged predictions are not correctness.",
                       "Development exposure and training exclusion do not establish blindness.",
                       "No raw inputs, local identities, paths, per-input hashes or failure examples are exported."])


def public_summary(value):
    from .protocol import FINE_TO_COARSE
    rate_keys = ("correct", "denominator", "rate")
    metric_keys = ("tp", "fp", "fn", "precision", "recall", "f1")
    result = public_numbers(value, ("rows", "source_families", "unadjudicated_rows"))
    result["statuses"] = public_numbers(value.get("statuses", {}), ("ok", "error", "refused"))
    result["coverage"] = public_numbers(value.get("coverage", {}), ("complete", "partial", "none"))
    for key in ("supplied_fields", "complete_address", "delimiter_fields", "delimiter_complete_address", "agreement"):
        if key in value:
            result[key] = public_numbers(value[key], rate_keys)
    result["roles"] = {role: public_numbers(value["roles"][role], rate_keys)
                       for role in sorted(set(value.get("roles", {})) & set(FINE_TO_COARSE.values()))}
    result["effects"] = {key: public_numbers(value.get("effects", {}).get(key, {}), rate_keys)
                         for key in ("unit", "building", "recipient", "road_city")}
    for kind in ("tokens", "spans"):
        if kind not in value:
            continue
        layer = value[kind]
        result[kind] = public_numbers(layer, ("unsupported_rows", "unannotated_rows"))
        for coverage in ("complete", "partial"):
            group = layer[coverage]
            result[kind][coverage] = dict(**public_numbers(group, ("rows",)), metrics=None if group["metrics"] is None else public_numbers(group["metrics"], metric_keys),
                per_role={role: public_numbers(group["per_role"][role], metric_keys)
                          for role in sorted(set(group["per_role"]) & set(FINE_TO_COARSE))})
    return result


def publishable_aggregates(runs, *, engines):
    """Per-source metrics, paired effects and supplied-cohort counts, no examples."""
    from .protocol import FINE_TO_COARSE
    exports = []
    names = {name: f"engine-{i + 1}" for i, name in enumerate(engines)}
    for index, (_, report) in enumerate(runs):
        engines = {}
        for name, entry in report["accuracy"].items():
            # Each resource/source remains separate. Older runs retain disjoint
            # origin/split populations, never overlapping subset sums.
            sources = entry.get("sources", {k: v for k, v in entry.get("populations", {}).items() if k.endswith("/all")})
            engines[names[name]] = dict(status=public_status(entry["status"]),
                sources=[dict(id=f"source-{i + 1}", **public_summary(value)) for i, (_, value) in enumerate(sorted(sources.items()))])
        deltas = []
        for label, value in report.get("deltas", {}).items():
            left, right = label.split("/")
            deltas.append(dict(left=names[left], right=names[right], **public_numbers(value, ("left_only", "right_only", "judged_pairs", "unmatched_judgments")),
                roles={role: public_numbers(counts, ("left_only", "right_only", "judged_pairs")) for role, counts in value.get("roles", {}).items() if role in set(FINE_TO_COARSE.values())},
                effects={key: public_numbers(value.get("effects", {}).get(key, {}), ("left_only", "right_only", "judged_pairs")) for key in ("unit", "building", "recipient", "road_city")},
                preservation=[dict(id=f"cohort-{i + 1}", **public_numbers(counts, ("denominator", "left_correct", "right_correct", "retained", "left_unjudged", "right_unjudged")))
                              for i, (_, counts) in enumerate(sorted(value.get("preservation", {}).items()))]))
        pairs = []
        for label, value in report.get("paired", {}).items():
            left, right = label.split("/")
            pairs.append(dict(left=names[left], right=names[right], status=public_status(value["status"]),
                **public_numbers(value, ("pairs", "expected_pairs", "median_ratio")),
                bootstrap_95_interval=public_interval(value["bootstrap_95_interval"])))
        exports.append(dict(id=f"track-{index + 1}", status=public_status(report["status"]), engines=engines, deltas=deltas, paired=pairs,
            scorer=report["scorer"] if report["scorer"] in ("address-benchmark.scorer/v1", "address-benchmark.scorer/v2") else "unavailable",
            gate=dict(status=public_status(report.get("gate", {}).get("status")), **public_numbers(report.get("gate", {}), ("losses", "correct", "judged_pairs", "preservation_passed"))),
            measurements={key: public_status(report.get("measurements", {}).get(key)) for key in ("timing", "public_evaluation", "memory", "latency")},
            blindness="not-established"))
    return exports
