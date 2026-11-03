"""One aggregate scorecard, rendered consistently for terminals and exports."""
from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path
import statistics
import unicodedata

from .io import identity, read_json, require, sha256, within

METRICS = ('strict', 'delimiter', 'complete', 'fine-f1', 'exact', 'throughput', 'streetline', 'streetline-v2')
FORMATS = ('console', 'markdown', 'csv', 'json', 'html')
LABELS = {'rust-learned': 'Rust learned', 'rust-default': 'Rust default',
          'boundaryboys': 'BoundaryBoys', 'doorplate': 'Doorplate',
          'libpostal-default': 'libpostal default', 'libpostal-senzing': 'libpostal Senzing'}
PANEL_LABELS = {'geosearch-dev': 'GeoSearch dev', 'geosearch-test': 'GeoSearch test (publisher split)',
                'doorplate-v1': 'Doorplate suite', 'expanded-usa': 'Expanded USA'}
VIEW_LABELS = {'natural': 'normal', 'hand': 'handwritten'}
METRIC_LABELS = {'strict': 'Strict supplied-field agreement', 'delimiter': 'Edge-delimiter supplied-field agreement',
                 'complete': 'Strict complete-address agreement', 'fine-f1': 'Fine token F1',
                 'exact': 'Exact task agreement', 'throughput': 'Exploratory throughput · addresses/s',
                 'streetline': 'strict-streetline/v1 profile agreement',
                 'streetline-v2': 'strict-streetline/v2 source-order profile agreement'}


def clean(value):
    """Keep labels from introducing terminal controls, newlines or bidi overrides."""
    return ''.join(' ' if c.isspace() else c for c in str(value) if not unicodedata.category(c).startswith('C') or c.isspace())


def width(value):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in value)


def fit(value, size, *, right=False, ascii=False):
    value = clean(value)
    if width(value) > size:
        ending = '~' if ascii else '…'
        result = ''
        for c in value:
            if width(result + c) > size - 1:
                break
            result += c
        value = result + ending
    padding = ' ' * max(0, size - width(value))
    return padding + value if right else value + padding


def _sum(populations, metric):
    rows = sum(p['rows'] for p in populations)
    statuses = {}
    for p in populations:
        for name, n in p.get('statuses', {}).items():
            statuses[name] = statuses.get(name, 0) + n
    result = dict(status='unmeasured', score=None, correct=None, denominator=0, rows=rows,
                  errors=statuses.get('error', 0), refusals=statuses.get('refused', 0))
    if metric in ('streetline', 'streetline-v2'):
        profile = 'strict-streetline/v2' if metric == 'streetline-v2' else 'strict-streetline/v1'
        parts = [p.get('profiles', {}).get(profile) for p in populations]
        if parts and all(parts):
            result.update(correct=sum(p['correct'] for p in parts), denominator=sum(p['denominator'] for p in parts),
                          inferred_state_rows=sum(p['inferred_state_rows'] for p in parts))
            if result['denominator']:
                result['score'] = result['correct'] / result['denominator']
    elif metric == 'fine-f1':
        parts = [p['tokens']['complete']['metrics'] for p in populations if p['tokens']['complete']['metrics'] is not None]
        if parts:
            totals = {k: sum(p[k] for p in parts) for k in ('tp', 'fp', 'fn')}
            n = 2 * totals['tp'] + totals['fp'] + totals['fn']
            result.update(**totals, denominator=totals['tp'] + totals['fn'], score=2 * totals['tp'] / n if n else None)
    else:
        key = {'strict': 'supplied_fields', 'delimiter': 'delimiter_fields', 'complete': 'complete_address', 'exact': 'agreement'}[metric]
        parts = [p[key] for p in populations]
        result.update(correct=sum(p['correct'] for p in parts), denominator=sum(p['denominator'] for p in parts))
        if result['denominator']:
            result['score'] = result['correct'] / result['denominator']
    eligibility_key = 'tokens' if metric == 'fine-f1' else {'strict': 'supplied_fields', 'delimiter': 'delimiter_fields', 'complete': 'complete_address'}.get(metric)
    if eligibility_key and all('eligibility' in p for p in populations):
        result['_eligibility'] = tuple(p['eligibility'][eligibility_key] for p in populations)
    if result['score'] is not None:
        result['status'] = 'measured'
    return result



def reference_warning(report, view, metric, *, source=None, population=None):
    if report["task"] != "parse" or metric not in ("strict", "complete"):
        return None
    audit = report.get("reference_comparability")
    def warning(rows):
        return dict(comparable=False, reference_edge_rows=rows, recommended_metric="delimiter",
                    noncomparable_reasons=["reference-edge-delimiters"])
    if not audit:
        # Old envelopes can still identify a publisher format when their full
        # private reference artifact was not supplied to this reporting process.
        if any(r.get("format") == "doorplate-compare" for r in report.get("corpus", {}).get("resources", [])):
            return warning(None)
        return None
    count = "complete_rows" if metric == "complete" else "rows"
    if source is not None:
        if "sources" not in audit:
            # A legacy panel audit cannot establish which individual source was
            # affected. Keep its strict rates diagnostic until gold is supplied.
            return warning(None) if any(v[count] for v in audit["populations"].values()) else None
        affected = audit["sources"].get(source, {}).get(count, 0)
    elif population is not None:
        affected = audit["populations"].get(population, {}).get(count, 0)
    else:
        suffix = "/all" if view == "all" else "/subset:" + view
        affected = sum(value[count] for key, value in audit["populations"].items() if key.endswith(suffix))
    if affected:
        return warning(affected)
    return None


def scorecard(runs, *, metric='strict', subsets=(), title='Address benchmark', engines=None, publishable=False, min_denominator=20):
    """Build from recorded aggregates, never raw addresses or native output."""
    require(metric in METRICS, 'unknown report metric')
    require(type(min_denominator) is int and min_denominator >= 1, 'positive publication minimum denominator required')
    require(runs, 'at least one recorded run is required')
    require(len(set(subsets)) == len(subsets) and 'all' not in subsets, 'subset names must be unique; all is already included')
    require(metric != 'throughput' or not subsets, 'timing is recorded for whole panels; subset throughput is unavailable')
    names = list(engines or [])
    rows, sources = [], []
    for label, report in runs:
        require(report['task'] == 'parse' or metric in ('strict', 'exact', 'throughput'), 'this metric requires a parsing run')
        for name in report['accuracy']:
            if name not in names:
                names.append(name)
        sources.append(dict(id=label, content_id=report.get('content_id'), status=report['status'],
                            created_at=report.get('created_at'),
                            task=report['task'], scorer=report['scorer'], normalization=report['normalization'],
                            secondary_normalization=report.get('secondary_normalization')))
        effective = metric if report['task'] == 'parse' or metric == 'throughput' else 'exact'
        require(effective != 'exact' or report['task'] != 'parse', 'exact task agreement requires a non-parsing run')
        for view in ('all', *subsets):
            cells = {}
            for name, entry in report['accuracy'].items():
                cell = dict(status=entry['status'], score=None, correct=None, denominator=None,
                            exit_code=entry.get('exit_code'), rows=None, errors=None, refusals=None)
                if entry['status'] == 'ok':
                    populations = [p for key, p in entry['populations'].items() if key.endswith('/all' if view == 'all' else '/subset:' + view)]
                    if effective == 'throughput':
                        if view != 'all':
                            continue  # Whole-panel timing must never be attributed to a subset.
                        trials = [t['engines'].get(name, {}) for t in report['trials']]
                        if len(trials) >= 2 and all(t.get('status') == 'ok' and t.get('median_ns_per_address', 0) > 0 for t in trials):
                            cell.update(status='measured', score=1e9 / statistics.median(t['median_ns_per_address'] for t in trials),
                                        trials=len(trials), noisy=any(t.get('noisy_over_10_percent') for t in trials))
                        else:
                            cell['status'] = 'incomplete' if trials else 'unmeasured'
                    elif populations:
                        cell.update(_sum(populations, effective))
                    else:
                        cell['status'] = 'unmeasured'
                cell["reused"] = effective != "throughput" and entry.get("origin", {}).get("kind") == "reused"
                cell["source_exit_code"] = entry.get("origin", {}).get("source_exit_code")

                if entry['status'] == 'ok':
                    cell['_publication_rows'] = (sum(p['tokens']['complete'].get('eligible_rows', 0) for p in populations) if effective == 'fine-f1'
                        else sum(p['rows'] for p in populations) if effective == 'throughput' else cell.get('denominator'))
                cells[name] = cell
            if view != 'all' and not any(c.get('rows') for c in cells.values()):
                continue
            measured = [c for c in cells.values() if c.get('score') is not None]
            matched = len({c.get('_eligibility') for c in measured}) <= 1
            for cell in cells.values():
                cell['comparable'] = matched
                if not matched and cell.get('score') is not None:
                    cell['noncomparable_reasons'] = ['eligibility-mismatch']
                cell.pop('_eligibility', None)
            display_label = PANEL_LABELS.get(label, label)
            warning = reference_warning(report, view, effective)
            if warning:
                for cell in cells.values():
                    if cell.get("score") is not None:
                        reasons = cell.get('noncomparable_reasons', []) + warning['noncomparable_reasons']
                        cell.update(warning)
                        cell['noncomparable_reasons'] = reasons
            rows.append(dict(id=f'{label}/{view}', label=display_label if view == 'all' else f'{display_label} / {VIEW_LABELS.get(view, view)}',
                             panel=label, view=view, task=report['task'], metric=effective,
                             rows=next((c['rows'] for c in cells.values() if c.get('rows') is not None), None), cells=cells))
    require(names, 'at least one engine is required')
    require(all(any(r['view'] == name for r in rows) for name in subsets), 'requested subset is not present in these runs')
    if all(r['metric'] == 'exact' for r in rows):
        metric = 'exact'
    card = dict(schema='address-benchmark.scorecard/v1', title=title, metric=metric, engines=names, rows=rows, sources=sources,
                notes=[
                    'Counts and failures use the recorded scoring denominators. Partial references judge supplied labels; they are not whole-address accuracy.',
                    'Subset rows overlap the parent dataset. Public/development-exposed fixtures do not establish unseen accuracy.',
                    'Bold marks rounded row leaders only when measured denominators match. Missing/unsupported scores are unmeasured, never zero.',
                    'Strict preserves punctuation. Edge-delimiter ignores component-edge comma/semicolon/colon only, plus case and whitespace.',
                    'Timing appears only when recorded: exploratory process medians, not accuracy-run wall time. † marks sample spread above 10%; ! marks native errors/refusals.',
                    'The report command checks recorded run identities. Exports do not rescore predictions or rehash every artifact.'
                ])
    if publishable or any(report.get('privacy') == 'local-only' for _, report in runs):
        from .report import public_scorecard, publishable_aggregates, publication_aliases
        aliases = publication_aliases(card, runs)
        card = public_scorecard(card, aliases=aliases, min_denominator=min_denominator)
        card['aggregates'] = publishable_aggregates(runs, engines=names, aliases=aliases, min_denominator=min_denominator)
    for row in card['rows']:
        for cell in row['cells'].values():
            cell.pop('_publication_rows', None)
    from .report import public_status
    notes = [f"{aliases['panels'][label] if publishable or any(r.get('privacy') == 'local-only' for _, r in runs) else label}: gate " +
        public_status(report.get('gate', {}).get('status', 'not-executed')) for label, report in runs
        if report.get('gate', {}).get('status') in ('passed', 'failed') or report['status'] == 'not-executed']
    if notes:
        card['gate_notes'] = notes
    return card


def _recorded_runs(source):
    path = Path(source).resolve()
    if path.is_dir():
        path = path / ('plan-results.json' if (path / 'plan-results.json').exists() else 'run.json')
    value = read_json(path)
    runs, engines, run_directories = [], [], {}
    if value.get('schema') == 'address-benchmark.plan/v1':
        receipt = read_json(path.parent / 'plan-results.json')
        require(receipt['plan_sha256'] == sha256(path), 'plan changed since execution')
        path, value = path.parent / 'plan-results.json', receipt
    if value.get('schema') == 'address-benchmark.plan-results/v1':
        for track in value['tracks']:
            if track.get('status') == 'not-executed':
                report = track['summary']
                require(report['content_id'] == track['content_id'], 'unexecuted track identity differs')
                runs.append((track['id'], report))
                continue
            run_path = within(path.parent, track['output']) / 'run.json'
            report = read_json(run_path)
            require(report.get('content_id') == track['content_id'], 'plan/run identity differs')
            runs.append((track['id'], report))
            run_directories[report['content_id']] = run_path.parent
            if not engines and (run_path.parent / 'engines.json').exists():
                require(sha256(run_path.parent / 'engines.json') == report['artifacts']['engines.json'], 'engine manifest changed')
                engines = [e['name'] for e in read_json(run_path.parent / 'engines.json')]
    else:
        require(value.get('schema') == 'address-benchmark.run/v1', 'report requires a run or executed plan')
        runs.append((value['corpus']['id'], value))
        run_directories[value['content_id']] = path.parent
        if (path.parent / 'engines.json').exists():
            require(sha256(path.parent / 'engines.json') == value['artifacts']['engines.json'], 'engine manifest changed')
            engines = [e['name'] for e in read_json(path.parent / 'engines.json')]
    for _, report in runs:
        require(report['content_id'] == identity({k: v for k, v in report.items() if k != 'content_id'}), 'run content identity differs')
        audit = report.get('reference_comparability') or {}
        if report['task'] == 'parse' and 'sources' not in audit and 'references.jsonl' in report.get('artifacts', {}):
            # Derive presentation metadata from hash-verified historical gold;
            # do not rewrite/rescore its envelope or its immutable exports.
            from .corpus import reference_comparability
            refs = run_directories[report['content_id']] / 'references.jsonl'
            if refs.exists():
                require(sha256(refs) == report['artifacts']['references.jsonl'], 'reference audit artifact changed')
                from .io import read_jsonl
                report['reference_comparability'] = reference_comparability(list(read_jsonl(refs)))
    return runs, engines


def load_scorecard(source, *, all_views=False, **options):
    """Read one or more explicit completed run/plan sources without pooling rows."""
    inputs = list(source) if isinstance(source, (list, tuple)) else [source]
    require(inputs, 'at least one report source required')
    runs, engines = [], []
    for path in inputs:
        recorded, ordered = _recorded_runs(path)
        runs.extend(recorded)
        engines.extend(name for name in ordered if name not in engines)
    ids = [label for label, _ in runs]
    require(len(set(ids)) == len(ids), 'duplicate dataset IDs across report sources; select each population once')
    require(len({report['task'] for _, report in runs}) == 1, 'different tasks require separate score tables')
    require(len({(report['scorer'], report['normalization'], report.get('secondary_normalization')) for _, report in runs}) == 1,
            'different scoring policies require separate score tables')
    require(not all_views or not options.get('subsets'), 'select all views or named subsets, not both')
    if all_views:
        options['subsets'] = sorted({key.rsplit('/subset:', 1)[1] for _, report in runs
                                    for entry in report['accuracy'].values() for key in entry.get('populations', {})
                                    if '/subset:' in key and not key.endswith('/subset:all')})
    card = scorecard(runs, engines=engines, **options)
    if len(inputs) > 1:
        card['notes'].append('Combined from multiple recorded experiment sources; source run identities remain separate. This is not a new simultaneous run or a pooled overall score.')
    return card


def leaders(row):
    cells = row['cells']
    measured = {name: c for name, c in cells.items() if c.get('score') is not None}
    if len(measured) < 2 or any(c.get('comparable') is False for c in measured.values()) or len({c['denominator'] for c in measured.values()}) != 1:
        return set()
    scale = 1 if row['metric'] == 'throughput' else 100
    best = max(round(c['score'] * scale, 2) for c in measured.values())
    return {name for name, c in measured.items() if round(c['score'] * scale, 2) == best}


def cell_text(cell, metric, counts=False):
    if cell is None:
        return 'unmeasured'
    if cell.get('score') is None:
        return clean(cell['status']) + (' [non-comparable]' if 'reference-edge-delimiters' in cell.get('noncomparable_reasons', []) else '') + (' [reused]' if cell.get('reused') else '')
    if metric == 'throughput':
        return f"{cell['score']:,.0f}" + ('†' if cell.get('noisy') else '')
    text = f"{100 * cell['score']:.2f}%"
    if counts:
        text += (f" ({cell['tp']:,}/{cell['fp']:,}/{cell['fn']:,} TP/FP/FN)" if metric == 'fine-f1'
                 else f" ({cell['correct']:,}/{cell['denominator']:,})")
    if cell.get('errors') or cell.get('refusals'):
        text += ' !'
    if cell.get("reused"):
        text += " [reused]"
    if 'reference-edge-delimiters' in cell.get('noncomparable_reasons', []):
        text += ' [non-comparable]'
    return text



def reference_notes(card):
    if card['metric'] in ('strict', 'complete') and any('reference-edge-delimiters' in cell.get('noncomparable_reasons', [])
            for row in card['rows'] for cell in row['cells'].values()):
        return ['Cells marked non-comparable have publisher reference edge delimiters or an unavailable publisher reference audit. Use --metric delimiter; original references and diagnostic counts are unchanged.']
    return []


def display_notes(card):
    return [*card.get('gate_notes', []), *card['notes'], *reference_notes(card)]

def render_console(card, *, counts=False, terminal_width=120, color=False, ascii=False):
    require(terminal_width >= 40, 'console width must be at least 40')
    line, junction, bar = ('-', '+', '|') if ascii else ('─', '┼', '│')
    names = card['engines']
    label_width = min(max([width(clean(r['label'])) for r in card['rows']] + [14]), max(14, min(38, terminal_width // 3)))
    sizes = {n: max(width(LABELS.get(n, clean(n))), *(width(cell_text(r['cells'].get(n), r['metric'], counts)) for r in card['rows'])) for n in names}
    available = terminal_width - label_width - 3
    groups, group, used = [], [], 0
    for n in names:
        size = min(sizes[n], available)
        if group and used + 3 + size > available:
            groups.append(group); group, used = [], 0
        group.append(n); used += size + (3 if len(group) > 1 else 0)
    if group:
        groups.append(group)
    lines = [fit(card['title'], terminal_width, ascii=ascii).rstrip(), fit(METRIC_LABELS[card['metric']], terminal_width, ascii=ascii).rstrip(), '']
    for index, group in enumerate(groups):
        if len(groups) > 1:
            lines.append(f'Columns {index + 1}/{len(groups)}')
        columns = [label_width] + [min(sizes[n], available) for n in group]
        lines.append((' ' + bar + ' ').join([fit('Dataset / view', label_width, ascii=ascii)] + [fit(LABELS.get(n, n), columns[i+1], right=True, ascii=ascii) for i,n in enumerate(group)]))
        lines.append((line + junction + line).join(line * w for w in columns))
        for row in card['rows']:
            best = leaders(row)
            values = [fit(row['label'], label_width, ascii=ascii)]
            for i, n in enumerate(group):
                text = fit(cell_text(row['cells'].get(n), row['metric'], counts), columns[i+1], right=True, ascii=ascii)
                if ascii:
                    text = text.replace('†', '*')
                if color and n in best:
                    text = '\x1b[1;36m' + text + '\x1b[0m'
                values.append(text)
            lines.append((' ' + bar + ' ').join(values))
        lines.append('')
    import textwrap
    for note in display_notes(card):
        if ascii:
            note = note.replace('†', '*')
        lines.extend(textwrap.wrap(clean(note), terminal_width, subsequent_indent='  '))
    return '\n'.join(lines) + '\n'


def _markdown(value):
    return clean(value).replace('\\', '\\\\').replace('|', '\\|').replace('<', '&lt;').replace('>', '&gt;')


def render_markdown(card, *, counts=False):
    names = card['engines']
    lines = ['# ' + _markdown(card['title']), '', _markdown(METRIC_LABELS[card['metric']]), '',
             '| Dataset / view | ' + ' | '.join(_markdown(LABELS.get(n,n)) for n in names) + ' |',
             '| --- | ' + ' | '.join('---:' for _ in names) + ' |']
    for row in card['rows']:
        best = leaders(row)
        values = []
        for n in names:
            text = _markdown(cell_text(row['cells'].get(n), row['metric'], counts))
            values.append('**' + text + '**' if n in best else text)
        lines.append('| ' + _markdown(row['label']) + ' | ' + ' | '.join(values) + ' |')
    return '\n'.join(lines + ['', *(_markdown(note) for note in card.get('gate_notes', [])), '',
                             *('- ' + _markdown(note) for note in [*card['notes'], *reference_notes(card)])]) + '\n'


def render_csv(card):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    def safe(value):
        text = clean(value)
        return "'" + text if text.startswith(('=', '+', '-', '@')) else text
    writer.writerow(['Dataset / view', *(safe(n) for n in card['engines'])])
    for row in card['rows']:
        writer.writerow([safe(row['label']), *(cell_text(row['cells'].get(n), row['metric'], True) for n in card['engines'])])
    for note in [*card.get('gate_notes', []), *reference_notes(card)]:
        writer.writerow([safe(note)])
    return output.getvalue()


def render_html(card):
    esc = lambda value: html.escape(clean(value), quote=True)
    names = card['engines']
    head = ''.join('<th scope="col">' + esc(LABELS.get(n,n)) + '</th>' for n in names)
    body = []
    for row in card['rows']:
        best, cells = leaders(row), []
        for name in names:
            cell = row['cells'].get(name)
            score = cell_text(cell, row['metric'])
            detail = ''
            if cell and cell.get('score') is not None:
                if row['metric'] == 'fine-f1':
                    detail = f"TP {cell['tp']:,} · FP {cell['fp']:,} · FN {cell['fn']:,}"
                elif row['metric'] != 'throughput':
                    detail = f"{cell['correct']:,} / {cell['denominator']:,}"
                if cell.get('errors') or cell.get('refusals'):
                    detail += f" · {cell['errors']} errors · {cell['refusals']} refusals"
            cells.append('<td' + (' class="best"' if name in best else '') + '><span>' + esc(score) + '</span><small>' + esc(detail) + '</small></td>')
        body.append('<tr><th scope="row">' + esc(row['label']) + '</th>' + ''.join(cells) + '</tr>')
    sources = ''.join('<li>' + esc(s['id']) + ' · ' + esc(s['status']) + ' · <code>' + esc(s['content_id'] or 'see containing run.json') + '</code></li>' for s in card['sources'])
    notes = ''.join('<p>' + esc(note) + '</p>' for note in display_notes(card))
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + esc(card['title']) + '''</title><style>
:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;background:#151515;color:#eee}
*{box-sizing:border-box}body{margin:0;padding:40px 32px 56px}main{max-width:2100px;margin:auto}.eyebrow{font:600 11px ui-monospace,monospace;letter-spacing:.14em;color:#9baba3;text-transform:uppercase}h1{font-size:25px;letter-spacing:-.035em;margin:12px 0}header p{color:#bdbfbd;font-size:14px;line-height:1.6;margin:0 0 26px}.scroll{overflow:auto;border-top:1px solid #373937;border-bottom:1px solid #373937}table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px;font-variant-numeric:tabular-nums}th,td{padding:16px 18px;white-space:nowrap;text-align:right;border-bottom:1px solid #303230}thead th{font-size:12px;color:#bfc4bf;background:#1b1d1b}tbody th{font-weight:500;text-align:left;background:#151515}thead th:first-child{position:sticky;left:0;z-index:2;text-align:left}tbody th{position:sticky;left:0;z-index:1}tr:last-child>*{border-bottom:0}tbody tr:hover>*{background:#1c211e}td span{display:block;font-weight:500}td small{display:block;color:#999f99;font-size:11px;margin-top:5px}.best span{color:#b6e4c9;font-weight:750}.notes{max-width:1050px;color:#a7ada7;font-size:12px;line-height:1.7;margin-top:22px}.notes p{margin:8px 0}details{font-size:12px;color:#abb4ad;margin-top:24px}summary{cursor:pointer;padding:8px 0}code{overflow-wrap:anywhere}li{margin:8px 0}@media(max-width:640px){body{padding:26px 16px}h1{font-size:22px}th,td{padding:14px 12px}tbody th{max-width:190px;white-space:normal;min-width:160px}}@media print{:root{color-scheme:light;background:white;color:#111}body{padding:0}.scroll{overflow:visible}thead th,tbody th{position:static;background:white}.best span{color:#111}td small,.notes,details,header p{color:#444}table{font-size:10px}th,td{padding:8px}}
</style></head><body><main><header><div class="eyebrow">Address benchmark / scorecard</div><h1>''' + esc(card['title']) + '</h1><p>' + esc(METRIC_LABELS[card['metric']]) + ' · ' + str(len(card['sources'])) + ' datasets · ' + str(len(names)) + ''' configurations</p></header><div class="scroll" tabindex="0" role="region" aria-label="Benchmark comparison table"><table><thead><tr><th scope="col">Dataset / view</th>''' + head + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div><div class="notes">' + notes + '</div><details><summary>Recorded run identities</summary><ul>' + sources + '</ul></details></main></body></html>\n'


def render(card, format='console', **options):
    require(format in FORMATS, 'unknown report format')
    if format == 'console':
        return render_console(card, **options)
    if format == 'markdown':
        return render_markdown(card, counts=options.get('counts', False))
    if format == 'csv':
        return render_csv(card)
    if format == 'html':
        return render_html(card)
    return json.dumps({**card, 'notes': [*card['notes'], *reference_notes(card)]}, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def export_scorecard(card, directory, *, counts=False, overwrite=False):
    directory = Path(directory)
    require(not overwrite or not (directory / 'run.json').exists(), 'cannot overwrite score exports in an immutable run')
    if not overwrite:
        require(not any((directory / ('scores.' + suffix)).exists() for suffix in ('txt', 'md', 'csv', 'json', 'html')), 'fresh score export files required')
    for format, suffix in zip(FORMATS, ('txt', 'md', 'csv', 'json', 'html')):
        with (directory / ('scores.' + suffix)).open('w' if overwrite else 'x', encoding='utf-8', newline='') as stream:
            stream.write(render(card, format, counts=counts))
