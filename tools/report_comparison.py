"""Aggregate verified production runs without publishing raw address values."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import html
import itertools
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("plan", type=Path)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
root, output = args.plan.resolve().parent, args.out.resolve()
output.mkdir(parents=True, exist_ok=True)
plan = json.loads(args.plan.read_text())
receipt = json.loads((root / "plan-results.json").read_text())
assert receipt["status"] == "complete", "complete verified cohort required before comparative report"
assert all(t["verification"] == "verified" for t in receipt["tracks"])


def jsonl(path):
    with path.open() as f:
        for line in f:
            yield json.loads(line)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def rate(correct, total):
    return 100 * correct / total if total else None


def aggregate(path):
    counts = Counter()
    mismatches, strict_mismatches, unsupported = Counter(), Counter(), Counter()
    confusion = Counter()
    for case in jsonl(path):
        counts['rows'] += 1
        counts['eligible'] += case['primary_agrees'] is not None
        counts['complete'] += case['coverage'] == 'complete'
        counts['strict_correct'] += case['supplied_fields_agree'] is True
        counts['delimiter_correct'] += case['delimiter_fields_agree'] is True
        counts['complete_correct'] += case['delimiter_complete_address_agrees'] is True
        counts['errors'] += case['status'] == 'error'
        counts['refusals'] += case['status'] == 'refused'
        counts['unadjudicated_rows'] += bool(case['unadjudicated_roles'])
        mismatches.update(case['delimiter_mismatched_roles'])
        strict_mismatches.update(case['mismatched_roles'])
        unsupported.update(case['unsupported_reference_roles'])
        fine = case['tokens']
        if fine['status'] == 'measured' and fine['coverage'] == 'complete':
            counts['fine_rows'] += 1
            for name in ('tp','fp','fn'):
                counts[name] += fine['metrics'][name]
    values = dict(counts)
    values.update(strict_percent=rate(counts['strict_correct'], counts['eligible']),
                  delimiter_percent=rate(counts['delimiter_correct'], counts['eligible']),
                  complete_percent=rate(counts['complete_correct'], counts['complete']),
                  fine_token_f1=2*counts['tp']/(2*counts['tp']+counts['fp']+counts['fn']) if counts['fine_rows'] and 2*counts['tp']+counts['fp']+counts['fn'] else None,
                  mismatches=dict(mismatches.most_common()), strict_mismatches=dict(strict_mismatches.most_common()), unsupported_reference_roles=dict(unsupported.most_common()))
    return values


tables, summary, runtimes, baselines = [], {}, {}, ('rust-learned','rust-default')
exact_inputs = defaultdict(list)
for track in plan['tracks']:
    directory = root / track['output']
    report = json.loads((directory / 'run.json').read_text())
    assert report['status'] == 'complete'
    casepaths = {name: directory/(name+'-accuracy')/'cases.jsonl' for name in report['accuracy']}
    for row in jsonl(directory/'references.jsonl'):
        key=hashlib.sha256(row['text'].encode('utf-8')).hexdigest()
        exact_inputs[key].append(dict(corpus=track['id'],id=row['id'],split=row['split']))
    summary[track['id']] = dict(run_content_id=report['content_id'], source_pins=report['source_pins'], engines={}, baseline_comparisons={}, role_confusions={})
    for name, path in casepaths.items():
        values = aggregate(path)
        values['strata'] = {
            key: {metric: population[metric] for metric in ('rows', 'supplied_fields', 'delimiter_fields', 'statuses')}
            for key, population in report['accuracy'][name]['populations'].items()
        }
        summary[track['id']]['engines'][name] = values
        tables.append(dict(corpus=track['id'], engine=name, **{k:v for k,v in values.items() if not isinstance(v,dict)}))
        identity = report['accuracy'][name]['identity']
        adapter = identity['adapter']
        # Export an allowlist, never local artifact paths or installed-file inventories.
        public_identity = {k: adapter.get(k) for k in ('name', 'version', 'dependency_versions', 'model', 'runtime', 'threading', 'accuracy_workers')}
        public_identity['node_version'] = adapter.get('provenance', {}).get('node_version')
        public_identity['identity_sha256'] = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        runtimes.setdefault(name, {})[track['id']] = public_identity
    for baseline in baselines:
        base = {c['id']: (c['delimiter_fields_agree'], c['delimiter_mismatched_roles']) for c in jsonl(casepaths[baseline])}
        comparisons = {}
        for name, path in casepaths.items():
            if name == baseline:
                continue
            counts, repair_roles = Counter(), Counter()
            for case in jsonl(path):
                agree, roles = base[case['id']]
                if agree is False and case['delimiter_fields_agree'] is True:
                    counts['other_only_correct'] += 1
                    repair_roles.update(roles)
                elif agree is True and case['delimiter_fields_agree'] is False:
                    counts['baseline_only_correct'] += 1
            comparisons[name] = dict(other_only_correct=counts['other_only_correct'], baseline_only_correct=counts['baseline_only_correct'],
                                     net_other_advantage=counts['other_only_correct']-counts['baseline_only_correct'],
                                     baseline_mismatched_roles_on_other_only=dict(repair_roles.most_common()))
        summary[track['id']]['baseline_comparisons'][baseline] = comparisons
        # Complete publisher fine tokens only; no reference-based alignment.
        entry = report['accuracy'][baseline]
        if entry['identity']['adapter']['token_support']:
            mapping = entry['identity']['adapter']['role_map']
            pairs, totals = Counter(), Counter()
            for row, pred in itertools.zip_longest(jsonl(directory/'references.jsonl'), jsonl(directory/(baseline+'-accuracy')/'predictions.jsonl')):
                assert row is not None and pred is not None and row['id']==pred['id']
                if row['reference']['tokens_coverage']!='complete':
                    continue
                expected = {tuple(x['span']):x['role'] for x in row['reference']['tokens']}
                for token in pred['tokens']:
                    span=tuple(token['spans'][0]); role=mapping[token['native_role']]
                    if span in expected:
                        totals['exact_boundary_tokens'] += 1
                        if role != expected[span]:pairs[(expected[span],role or 'unmapped')] += 1
                    else:
                        totals['different_boundary_tokens'] += 1
            summary[track['id']]['role_confusions'][baseline] = dict(**totals, confusions=[dict(expected=a,predicted=b,tokens=n) for (a,b),n in pairs.most_common(30)])

fieldnames = sorted({k for row in tables for k in row})
with (output/'comparison.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fieldnames);writer.writeheader();writer.writerows(tables)
overlap=dict(source_rows=sum(len(x) for x in exact_inputs.values()),distinct_exact_inputs=len(exact_inputs),
             duplicate_groups=[dict(input_sha256=k,members=v) for k,v in exact_inputs.items() if len(v)>1],
             cross_split_groups=[dict(input_sha256=k,members=v) for k,v in exact_inputs.items() if len({m['split'] for m in v})>1],
             family_scope='Exact-text proxy only; independent source families and training overlap unknown')
(output/'overlap.json').write_text(json.dumps(overlap,indent=2)+'\n')
(output/'comparison.json').write_text(json.dumps(dict(schema='address-benchmark.comparison/v1', plan_sha256=sha(args.plan), tracks=summary, runtimes=runtimes, overlap=dict(source_rows=overlap['source_rows'],distinct_exact_inputs=overlap['distinct_exact_inputs'],cross_split_groups=len(overlap['cross_split_groups'])), provenance=dict(plan_receipt_sha256=sha(root/'plan-results.json'), generator_sha256=sha(Path(__file__)))),indent=2)+'\n')

lines=['# Fresh production parsing comparison','',
       f"Nine engine configurations; {overlap['source_rows']:,} source rows across four panels, {overlap['distinct_exact_inputs']:,} distinct exact UTF-8 inputs. Each engine ran fresh through the benchmark plan; predictions were rehashed and rescored. Source rows are not independent source families. Detailed exact cross-split/source overlap is retained locally in overlap.json; public exports include aggregate overlap counts only.",
       '', 'The retained learned Rust model and the default source parser are separate columns. These public/development-exposed fixtures do not establish unseen generalization. No private runtime, corpus or raw address is included in this report.',
       '', '| Corpus | Engine | Correct / eligible | Edge-delimiter agreement | Strict agreement | Fine token F1 | Errors / refusals |',
       '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
for row in tables:
    f1='unmeasured' if row['fine_token_f1'] is None else f"{100*row['fine_token_f1']:.2f}%"
    lines.append(f"| {row['corpus']} | {row['engine']} | {row.get('delimiter_correct',0):,}/{row['eligible']:,} | {row['delimiter_percent']:.2f}% | {row['strict_percent']:.2f}% | {f1} | {row.get('errors',0)} / {row.get('refusals',0)} |")
lines += ['', '## Runtime cohort', '', '| Engine | Installed package/model | Runtime |', '| --- | --- | --- |']
for name, tracks in runtimes.items():
    runtime = next(iter(tracks.values()))
    versions = ', '.join(f'{key} {value}' for key, value in (runtime['dependency_versions'] or {}).items())
    description = (versions + '; ' if versions else '') + runtime['model']
    interpreter = 'Python ' + runtime['runtime'] + (('; Node ' + runtime['node_version']) if runtime['node_version'] else '')
    lines.append(f'| {name} | {description} | {interpreter} |')
lines += ['', 'These are the installed versions actually executed, not claims about the latest upstream release. Fastaddress model v1 shares the usaddress CRF lineage. Mailwoman accuracy uses four independent CPU processes with one ONNX intra-op thread each. BoundaryBoys is a locally installed private executable; its source is not redistributed. Full runtime/file identities are retained locally; per-track identity hashes are exported in comparison.json.',
          '', 'Both field policies use the same untouched native predictions. The edge-delimiter diagnostic ignores only component-edge comma/semicolon/colon, case and whitespace; periods, abbreviations, accents, ZIP width and internal punctuation remain significant. Fine scores require publisher fine labels and declared native token support; coarse emitters are unmeasured, not zero.',
          '', 'Expanded USA contains 2,920 partial and 53 complete references. Its shared figure is supplied-field agreement; extra roles are unadjudicated. It is not whole-address accuracy. Doorplate has rendered and hand-authored origins; its strata are views, not additional rows. Native unplaced tokens are retained.',
          '', '## Where to investigate', '']
for baseline in baselines:
    lines += [f'### {baseline}', '']
    for corpus, data in summary.items():
        m=data['engines'][baseline]
        best=max(data['baseline_comparisons'][baseline].items(),key=lambda item:item[1]['net_other_advantage'])
        top=', '.join(f"{role}: {n:,}" for role,n in list(m['mismatches'].items())[:6])
        lines += [f"- **{corpus}:** {m.get('delimiter_correct',0):,}/{m['eligible']:,} supplied-field agreements. Frequent mismatch roles: {top or 'none'}. These role counts overlap.",
                  f"  Against {best[0]}, the other engine alone passes {best[1]['other_only_correct']:,} rows and this baseline alone passes {best[1]['baseline_only_correct']:,}; net difference {best[1]['net_other_advantage']:+,}. This is paired diagnostic evidence, not a deployable gold-selected selector."]
        conf=data['role_confusions'].get(baseline,{}).get('confusions',[])[:6]
        if conf:
            lines.append('  On exactly matching native/publisher token boundaries: '+ '; '.join(f"{x['expected']} → {x['predicted']}: {x['tokens']:,}" for x in conf)+'.')
        unsupported=m['unsupported_reference_roles']
        if unsupported:
            lines.append('  Reference-role requirements outside the declared active model/API inventory: '+', '.join(f'{role}: {n:,}' for role,n in unsupported.items())+'. These are capability/ontology gaps, not necessarily training-only errors.')
        lines.append('')
lines += ['## Improvement workflow','',
          '1. Review the leading role confusions and paired deficits in their original annotation/task profiles. Distinguish segmentation, native normalization, ontology mismatch and incorrect role decisions.',
          '2. Build independent positive/negative development and training families for those phenomena. Keep these public evaluation rows out of newly collected training material; log existing exposure explicitly.',
          '3. Fix and evaluate one declared candidate at a time, retaining gains and losses by source/stratum. Freeze a separately adjudicated heldout population before generalization claims.',
          '4. Measure performance on a fixed input-only panel in a separate contemporaneous paired experiment. Accuracy process wall times include model hashing/loading/I/O and are not parse throughput.',
          '', 'The files comparison.json and comparison.csv contain the aggregate evidence and per-baseline comparative counts. Full predictions, references, runtime identities, model hashes, exits/logs and case deltas remain in the local verified run folders. No raw address values are exported here.']
markdown='\n'.join(lines)+'\n'
(output/'comparison.md').write_text(markdown)
table_html=''.join('<tr>'+''.join('<td>'+html.escape(str(row.get(k,'')))+'</td>' for k in ('corpus','engine','delimiter_correct','eligible','delimiter_percent','strict_percent','fine_token_f1','errors','refusals'))+'</tr>' for row in tables)
page='<!doctype html><meta charset="utf-8"><title>Address utility comparison</title><style>body{font:15px system-ui;max-width:1500px;margin:40px auto;padding:0 24px;color:#18221f;background:#fafaf7}h1{font-size:34px}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{padding:10px;border-bottom:1px solid #dce3dd;text-align:right}td:first-child,td:nth-child(2){text-align:left}.scroll{overflow:auto}pre{white-space:pre-wrap;line-height:1.6;max-width:1100px}a{color:#22633d}</style><h1>Address utility comparison</h1><p>Fresh nine-engine parsing run. Public and development-exposed evidence; see scopes and limitations below.</p><div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in ('Corpus','Engine','Correct','Eligible','Delimiter %','Strict %','Fine token F1','Errors','Refusals'))+'</tr></thead><tbody>'+table_html+'</tbody></table></div><h2>Findings and methodology</h2><pre>'+html.escape(markdown)+'</pre>'
(output/'comparison.html').write_text(page)
print(json.dumps(dict(output=str(output), tracks=len(summary), engines=len(tables)//len(summary))))
