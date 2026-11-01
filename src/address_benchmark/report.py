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
