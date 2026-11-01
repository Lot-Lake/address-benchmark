"""Publish aggregate utility evidence; never export raw inputs or native values."""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from address_benchmark.io import read_json, read_jsonl
from address_benchmark.tasks import summarize_task

parser = argparse.ArgumentParser()
parser.add_argument('root', type=Path)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
tracks = {}
lines = ['# Production utility observations', '',
         'Separate task profiles; no combined score. Classification uses real publisher fixtures; normalization and matching are small exposed conformance panels. Stability compares actual native API observations on 1,024 real public input strings and does not establish accuracy.', '',
         '| Track | Engine | Agreements / evaluated rows | Status counts |',
         '| --- | --- | ---: | --- |']
details = []
for plan_path in sorted(args.root.glob('*/plan.json')):
    folder = plan_path.parent
    receipt = read_json(folder / 'plan-results.json')
    assert receipt['status'] == 'complete' and all(t['verification'] == 'verified' for t in receipt['tracks'])
    run = read_json(folder / 'results/run.json')
    assert run['status'] == 'complete'
    engines = {}
    for name, entry in run['accuracy'].items():
        assert entry['exit_code'] == 0 and entry['status'] == 'ok'
        directory = folder / 'results' / (name + '-accuracy')
        cases = list(read_jsonl(directory / 'cases.jsonl'))
        summary = summarize_task(cases)
        a = summary['agreement']
        lines.append(f"| {folder.name} | {name} | {a['correct']}/{a['denominator']} | {summary['statuses']} |")
        confusion, fields, checks = Counter(), Counter(), {}
        errors = Counter()
        for row, pred in itertools.zip_longest(read_jsonl(folder / 'results/references.jsonl'), read_jsonl(directory / 'predictions.jsonl')):
            assert row is not None and pred is not None and row['id'] == pred['id']
            if run['task'] == 'classify':
                actual = pred['result'] if pred['status'] == 'ok' else pred['status']
                if row['reference']['expected'] != actual:
                    confusion[(row['reference']['expected'], str(actual))] += 1
            elif run['task'] == 'normalize' and pred['status'] == 'ok':
                expected, actual = json.loads(row['reference']['values'][0]), json.loads(pred['normalized'][0])
                fields.update(key for key in expected if expected[key] != actual[key])
            elif run['task'] == 'stability':
                native = pred['native']
                observed = native.get('observations', native)
                scalar = observed.get('scalar', [])
                for check, target in dict(repeat='repeat', scalar_batch='batch', idempotence='normalized_twice', scalar_stream='stream', scalar_chunked='chunked').items():
                    if check not in row['reference']['checks']:
                        continue
                    actual = observed.get(target, [])
                    changed = sum(a != b for a, b in itertools.zip_longest(scalar, actual, fillvalue=object()))
                    texts = row['payload']['texts']
                    distinct_changed = len({texts[i] for i, (a,b) in enumerate(itertools.zip_longest(scalar, actual, fillvalue=object())) if a != b and i < len(texts)})
                    checks[check] = dict(changed_inputs=changed, distinct_changed_inputs=distinct_changed, input_count=len(texts), distinct_exact_inputs=len(set(texts)), output_count=len(actual))
                errors.update(item['error'] for item in native.get('errors', []))
        summary.update(classification_confusions=[dict(expected=a, predicted=b, rows=n) for (a,b),n in confusion.most_common()],
                       normalization_field_mismatches=dict(fields), stability_observations=checks, native_errors=dict(errors), identity_sha256=entry['identity_sha256'])
        engines[name] = summary
        details.append(f"### {folder.name} / {name}\n")
        if confusion:
            details.append('Class disagreements: ' + '; '.join(f'{a} → {b}: {n:,}' for (a,b),n in confusion.most_common()) + '.\n')
        if fields:
            details.append('Normalized component mismatches (overlapping): ' + ', '.join(f'{key}: {n}' for key,n in fields.items()) + '.\n')
        if checks:
            details.extend(f"- {key}: {value['changed_inputs']:,}/{value['input_count']:,} changed input rows ({value['distinct_changed_inputs']:,} distinct exact inputs); {value['output_count']:,} outputs." for key,value in checks.items())
            details.append('')
        if errors:
            details.append('Native re-normalization exceptions retained: ' + str(dict(errors)) + '. A row with native errors remains a failed stability row; independently observed parity is diagnostic only.\n')
        if run['task'] == 'match':
            details.append(f"Distinct-pair collisions: {summary['distinct_entity_collisions']}; key coverage: {summary['key_coverage']}. Ten fictional independent pair controls do not estimate real matching accuracy.\n")
        if not (confusion or fields or checks or run['task'] == 'match'):
            details.append('No disagreement in this narrowly scoped panel.\n')
    tracks[folder.name] = dict(task=run['task'], run_content_id=run['content_id'], source_pins=run['source_pins'], engines=engines)
lines += ['', 'Doorplate native `street` includes highway forms, whereas the publisher type fixture distinguishes `highway`; taxonomy disagreement needs review before attributing these rows to parser errors. The normalization profile is a uniform five-component projection, not native full-string postal formatting. Matching is delivery-unit key equality, not ranked matching, clustering or geocoding.', '', *details,
          '## Coverage limits', '',
          'The real parsing cohort and these utility panels do not cover every production API. Formatting from structured components, field-level helpers, source-accounting hierarchy, extraction, ZIP/state inference, diagnostics and variants have executable framework/example contracts, but still need dedicated production adapters and independently reviewed task-matched references. No production accuracy claim is made for those unmeasured surfaces. Streaming backpressure, memory, cold start and calibrated throughput also remain separate work.', '',
          'Classification inputs overlap the parsing panel. Stability inputs also come from the existing public comparison workload. Do not add these counts as independent source families. Full references, predictions, native observations, exceptions and per-row decisions stay in local verified run artifacts.']
(args.out / 'utilities.md').write_text('\n'.join(lines) + '\n')
(args.out / 'utilities.json').write_text(json.dumps(dict(schema='address-benchmark.utility-comparison/v1', tracks=tracks, normalization_intake=read_json(args.root / 'normalization-intake.json')), indent=2) + '\n')
print(json.dumps(dict(tracks=len(tracks), output=str(args.out))))
