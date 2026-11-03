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
        display_name = name + (" [reused accuracy]" if entry.get("origin", {}).get("kind") == "reused" else "")
        if entry["status"] != "ok":
            lines.append(f"| {display_name} | {entry['status']} (exit {entry['exit_code']}) | — | unmeasured | unmeasured |")
        for population, m in entry.get("populations", {}).items():
            audit = report.get("reference_comparability") or {}
            affected = audit.get("populations", {}).get(population, {}).get("rows", 0)
            marker = " [non-comparable; use edge-delimiter]" if affected else ""
            lines.append(f"| {display_name} | {population} | {m['rows']} / {m['source_families']} | {agreement(m['supplied_fields'])}{marker} | {agreement(m['complete_address'])}{marker if audit.get('populations', {}).get(population, {}).get('complete_rows', 0) else ''} |")
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
        display_name = name + (" [reused accuracy]" if entry.get("origin", {}).get("kind") == "reused" else "")
        if entry["status"] != "ok":
            lines.append(f"| {display_name} | {entry['status']} (exit {entry['exit_code']}) | — | unmeasured | — |")
        for label, m in entry.get("populations", {}).items():
            lines.append(f"| {display_name} | {label} | {m['rows']} / {m['source_families']} | {agreement(m['agreement'])} | {m.get('distinct_entity_collisions', 'n/a')} |")
    lines += ["", "Normalization compares ordered output strings exactly under the corpus's named profile. Identity uses independently authored pair labels and native key equality; missing/error outputs remain in the agreement denominator.",
              "Pair precision/recall/F1, same-entity stability, collision counts, coverage, statuses and per-case deltas are retained in `run.json` and the case artifacts.", ""]
    if report["trials"]:
        lines += ["Paired exploratory timing, every raw sample, reversed run orders and actual process exits are retained in `run.json`.", ""]
    lines += ["## Limits", ""] + ["- " + item for item in report["limitations"]]
    return "\n".join(lines) + "\n"


# Publication is an allowlist projection, not recursive key deletion. In
# particular, corpus/engine/source/subset/cohort names are arbitrary private data.
STATUSES = {"ok", "complete", "incomplete", "gated", "measured", "unmeasured", "unavailable", "failed", "invalid", "timeout", "refused", "error", "passed", "not-requested", "not-executed", "executed", "blocked-by-accuracy-gate", "suppressed"}


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


DEFAULT_MIN_DENOMINATOR = 20


def publication_aliases(card, runs):
    panels = {label: f"panel-{i + 1}" for i, (label, _) in enumerate(runs)}
    views, sources, cohorts = {}, {}, {}
    for label, report in runs:
        panel = panels[label]
        selected = [r['view'] for r in card['rows'] if r['panel'] == label and r['view'] != 'all']
        views[label] = {'all': panel + '/all', **{v: f"{panel}/view-{i + 1}" for i, v in enumerate(selected)}}
        order = list(report.get('source_order', []))
        for entry in report['accuracy'].values():
            available = entry.get('sources', {k: v for k, v in entry.get('populations', {}).items() if k.endswith('/all')})
            order.extend(k for k in available if k not in order)
        sources[label] = {key: f"{panel}/source-{i + 1}" for i, key in enumerate(order)}
        order = [c['id'] for c in report.get('cohorts', [])]
        for delta in report.get('deltas', {}).values():
            order.extend(k for k in delta.get('preservation', {}) if k not in order)
        cohorts[label] = {key: f"{panel}/cohort-{i + 1}" for i, key in enumerate(order)}
    return dict(panels=panels, views=views, sources=sources, cohorts=cohorts)


def public_scorecard(card, *, aliases, min_denominator=DEFAULT_MIN_DENOMINATOR):
    names = {name: f"engine-{i + 1}" for i, name in enumerate(card['engines'])}
    rows = []
    for row in card['rows']:
        panel = aliases['panels'][row['panel']]
        view_id = aliases['views'][row['panel']][row['view']]
        cells = {}
        hidden = row.get('rows') is not None and row['rows'] < min_denominator
        for name, cell in row['cells'].items():
            denominator = cell.get('_publication_rows', cell.get('denominator'))
            suppressed = cell.get('score') is not None and (denominator is None or denominator < min_denominator)
            hidden |= suppressed
            if cell.get('score') is None:
                cells[names[name]] = dict(status=public_status(cell['status']), score=None,
                    **public_numbers(cell, ('comparable', 'reused')))
            elif suppressed:
                cells[names[name]] = dict(status='suppressed', score=None,
                    **public_numbers(cell, ('comparable', 'reused')))
            else:
                cells[names[name]] = dict(status=public_status(cell['status']), **public_numbers(cell,
                    ('score', 'correct', 'denominator', 'rows', 'errors', 'refusals', 'tp', 'fp', 'fn',
                     'trials', 'noisy', 'exit_code', 'comparable', 'reused', 'source_exit_code')))
        rows.append(dict(id=view_id, label=panel if row['view'] == 'all' else view_id,
                         panel=panel, view='all' if row['view'] == 'all' else view_id.rsplit('/', 1)[1],
                         task=row['task'], metric=row['metric'], cells=cells,
                         **({} if hidden else public_numbers(row, ('rows',)))))
    return dict(schema='address-benchmark.scorecard/v1', title='Aggregate address benchmark', metric=card['metric'],
        engines=list(names.values()), rows=rows,
        sources=[dict(id=aliases['panels'][s['id']], content_id=None, status=public_status(s['status'])) for s in card['sources']],
        publication_policy=dict(schema='address-benchmark.publication/v2', min_denominator=min_denominator,
            suppression='eligible-reference-rows', aliases='per-panel-declaration-order'),
        notes=['Aggregate-only export. Panel/source/view/cohort aliases share one namespace; mapping stays private.',
               'Small cells are suppressed under the recorded minimum denominator. This is not differential privacy or protection against arbitrary repeated queries.',
               'Partial references judge supplied labels only. Unjudged predictions are not correctness.',
               'Development exposure and training exclusion do not establish blindness.',
               'No raw inputs, local identities, paths, per-input hashes or failure examples are exported.',
               'Reused markers refer to verified prior accuracy only; timing trials execute fresh.'])


def public_rate(value, keys, denominator, minimum):
    if denominator < minimum:
        return dict(status='suppressed')
    return dict(status='measured', **public_numbers(value, keys))


def public_summary(value, minimum=DEFAULT_MIN_DENOMINATOR):
    from .protocol import FINE_TO_COARSE
    if value.get('rows', 0) < minimum:
        return dict(status='suppressed')
    rate_keys = ('correct', 'denominator', 'rate')
    metric_keys = ('tp', 'fp', 'fn', 'precision', 'recall', 'f1')
    result = dict(status='measured', **public_numbers(value, ('rows', 'source_families', 'unadjudicated_rows')))
    result['statuses'] = public_numbers(value.get('statuses', {}), ('ok', 'error', 'refused'))
    # Do not publish the sizes of small annotation strata through a side channel.
    coverage = value.get('coverage', {})
    result['coverage'] = ({'status': 'suppressed'} if any(0 < n < minimum for n in coverage.values())
                          else public_numbers(coverage, ('complete', 'partial', 'none')))
    for key in ('supplied_fields', 'complete_address', 'delimiter_fields', 'delimiter_complete_address', 'agreement'):
        if key in value:
            result[key] = public_rate(value[key], rate_keys, value[key]['denominator'], minimum)
    result['roles'] = {role: public_rate(counts, rate_keys, counts['denominator'], minimum)
        for role, counts in value.get('roles', {}).items() if role in set(FINE_TO_COARSE.values())}
    result['effects'] = {key: public_rate(counts, rate_keys, counts['denominator'], minimum)
        for key, counts in value.get('effects', {}).items() if key in ('unit', 'building', 'recipient', 'road_city')}
    for kind in ('tokens', 'spans'):
        if kind not in value:
            continue
        layer = value[kind]
        result[kind] = dict(capability='unsupported' if layer.get('unsupported_rows') == value['rows'] else
            'unannotated' if layer.get('unannotated_rows') == value['rows'] else 'available')
        for coverage in ('complete', 'partial'):
            group = layer.get(coverage, dict(rows=0, metrics=None, per_role={}))
            if group.get('eligible_rows', 0) < minimum:
                result[kind][coverage] = dict(status='suppressed')
            else:
                result[kind][coverage] = dict(status='measured', **public_numbers(group, ('rows',)),
                    metrics=None if group['metrics'] is None else public_numbers(group['metrics'], metric_keys),
                    per_role={role: public_rate(counts, metric_keys, group.get('per_role_rows', {}).get(role, 0), minimum)
                        for role, counts in group.get('per_role', {}).items() if role in FINE_TO_COARSE})
    return result


def public_gate(gate, minimum):
    from .scoring import GATE_METRICS
    result = dict(status=public_status(gate.get('status')))
    if gate.get('metric') in GATE_METRICS:
        result['metric'] = gate['metric']
    if gate.get('policy') in ('address-benchmark.gate/v1', 'address-benchmark.gate/v2'):
        result['policy'] = gate['policy']
    if gate.get('judged_pairs', 0) >= minimum:
        result.update(public_numbers(gate, ('losses', 'correct', 'judged_pairs', 'preservation_passed')))
    if 'requirements' in gate:
        result['requirements'] = [dict(id=f"requirement-{i + 1}",
            **(dict(status='suppressed') if r['judged_pairs'] < minimum else
               dict(status=public_status(r['status']), **public_numbers(r, ('rows', 'judged_pairs', 'correct', 'losses', 'loss_rate', 'correct_rate')))))
            for i, r in enumerate(gate['requirements'])]
    return result


def publishable_aggregates(runs, *, engines, aliases, min_denominator=DEFAULT_MIN_DENOMINATOR):
    from .protocol import FINE_TO_COARSE
    exports = []
    names = {name: f"engine-{i + 1}" for i, name in enumerate(engines)}
    for label, report in runs:
        engine_results = {}
        for name, entry in report['accuracy'].items():
            sources = entry.get('sources', {k: v for k, v in entry.get('populations', {}).items() if k.endswith('/all')})
            engine_results[names[name]] = dict(reused=entry.get('origin', {}).get('kind') == 'reused', status=public_status(entry['status']),
                sources=[dict(id=alias, **public_summary(sources[key], min_denominator))
                    for key, alias in aliases['sources'][label].items() if key in sources])
        deltas = []
        for pair, value in report.get('deltas', {}).items():
            left, right = pair.split('/')
            denominator = value.get('judged_pairs', 0)
            delta = dict(left=names[left], right=names[right],
                **public_rate(value, ('left_only', 'right_only', 'judged_pairs', 'unmatched_judgments'), denominator, min_denominator))
            if denominator >= min_denominator:
                for key, inventory in [('roles', set(FINE_TO_COARSE.values())), ('effects', {'unit', 'building', 'recipient', 'road_city'})]:
                    delta[key] = {role: public_rate(counts, ('left_only', 'right_only', 'judged_pairs'), counts.get('judged_pairs', 0), min_denominator)
                        for role, counts in value.get(key, {}).items() if role in inventory}
            delta['preservation'] = [dict(id=alias, **public_rate(value['preservation'][key],
                ('denominator', 'left_correct', 'right_correct', 'retained', 'left_unjudged', 'right_unjudged'),
                value['preservation'][key]['denominator'], min_denominator))
                for key, alias in aliases['cohorts'][label].items() if key in value.get('preservation', {})]
            deltas.append(delta)
        pairs = []
        for pair, value in report.get('paired', {}).items():
            left, right = pair.split('/')
            rows = sum(p['rows'] for key, p in report['accuracy'][left].get('populations', {}).items() if key.endswith('/all'))
            published = (dict(status='suppressed') if rows < min_denominator else
                dict(status=public_status(value['status']), **public_numbers(value, ('pairs', 'expected_pairs', 'median_ratio')),
                     bootstrap_95_interval=public_interval(value['bootstrap_95_interval'])))
            pairs.append(dict(left=names[left], right=names[right], **published))
        exports.append(dict(id=aliases['panels'][label], status=public_status(report['status']), engines=engine_results,
            deltas=deltas, paired=pairs, gate=public_gate(report.get('gate', {}), min_denominator),
            scorer=report['scorer'] if report['scorer'] in ('address-benchmark.scorer/v1', 'address-benchmark.scorer/v2') else 'unavailable',
            measurements={key: public_status(report.get('measurements', {}).get(key)) for key in ('timing', 'public_evaluation', 'memory', 'latency')},
            blindness='not-established'))
    return exports
