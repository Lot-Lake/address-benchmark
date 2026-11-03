"""Paired analysis of existing verified runs/plans; never execute adapters."""
from pathlib import Path
import shutil

from .io import identity, read_json, read_jsonl, require, sha256, within, write_json, write_jsonl
from .runner import verify, source_pins
from .scoring import GATE_METRICS, comparison
from .report import public_rate

SCHEMA = 'address-benchmark.comparison/v1'


def locations(source):
    path = Path(source).resolve()
    verify(path)
    if path.is_dir():
        path = path / ('plan-results.json' if (path / 'plan-results.json').exists() else 'run.json')
    value = read_json(path)
    if value['schema'] == 'address-benchmark.plan/v1':
        path = path.parent / 'plan-results.json'; value = read_json(path)
    if value['schema'] == 'address-benchmark.plan-results/v1':
        return {t['id']: within(path.parent, t['output']) for t in value['tracks'] if t['status'] != 'not-executed'}
    return {value['corpus']['id']: path.parent}


def compare_sources(left, right, output, *, baseline, candidate, metric='strict', track=None):
    require(metric in GATE_METRICS, 'unsupported comparison metric')
    a, b = locations(left), locations(right)
    keys = [track] if track is not None else list(a)
    require(set(keys) <= set(a) & set(b) and (track is not None or set(a) == set(b)), 'comparison requires matching executed tracks')
    out = Path(output).resolve()
    require(not out.exists(), 'fresh comparison output required')
    require(all(not out.is_relative_to(p) and not p.is_relative_to(out) for p in [*a.values(), *b.values()]), 'comparison output cannot nest with source runs')
    out.mkdir(parents=True, mode=0o700)
    result = dict(schema=SCHEMA, policy='address-benchmark.paired-comparison/v1', metric=metric, source_pins=source_pins(), tracks=[])
    for index, key in enumerate(keys):
        left_run, right_run = read_json(a[key] / 'run.json'), read_json(b[key] / 'run.json')
        require((left_run['task'], left_run['scorer'], left_run['normalization'], left_run.get('secondary_normalization'), left_run['source_pins']) ==
                (right_run['task'], right_run['scorer'], right_run['normalization'], right_run.get('secondary_normalization'), right_run['source_pins']), 'comparison policy differs')
        require(left_run['input_sha256'] == right_run['input_sha256'] and
                sha256(a[key] / 'references.jsonl') == sha256(b[key] / 'references.jsonl'), 'comparison input/reference panel differs')
        for directory in (a[key], b[key]):
            require(not metric.startswith('strict-streetline/') or metric in read_json(directory / 'corpus.json').get('scoring_profiles', []), 'comparison profile not declared')
        require(left_run['accuracy'].get(baseline, {}).get('status') == right_run['accuracy'].get(candidate, {}).get('status') == 'ok', 'comparison accuracy unavailable')
        prefix = f'track-{index + 1}'
        directory = out / prefix; directory.mkdir()
        for side, source, engine in [('left', a[key], baseline), ('right', b[key], candidate)]:
            shutil.copyfile(source / 'run.json', directory / (side + '-run.json'))
            shutil.copyfile(source / (engine + '-accuracy') / 'cases.jsonl', directory / (side + '-cases.jsonl'))
        left_cases = list(read_jsonl(directory / 'left-cases.jsonl'))
        right_cases = list(read_jsonl(directory / 'right-cases.jsonl'))
        cohorts = left_run.get('cohorts', [])
        require(not any(isinstance(c['basis'], dict) and c['basis'].get('kind') == 'baseline-correct' for c in cohorts)
                or left_run['settings']['baseline'] == baseline, 'comparison cohort baseline differs')
        records, counts = comparison(left_cases, right_cases, cohorts, metric=metric)
        write_jsonl(directory / 'paired.jsonl', records)
        result['tracks'].append(dict(id=key, directory=prefix, baseline=baseline, candidate=candidate,
            left_content_id=left_run['content_id'], right_content_id=right_run['content_id'], cohorts=cohorts, summary=counts))
    result['artifacts'] = {str(p.relative_to(out)): sha256(p) for p in sorted(out.rglob('*')) if p.is_file()}
    result['content_id'] = identity(result)
    write_json(out / 'comparison.json', result)
    return result


def verify_comparison(output):
    out = Path(output).resolve()
    if out.is_file(): out = out.parent
    result = read_json(out / 'comparison.json')
    require(result['schema'] == SCHEMA and result['source_pins'] == source_pins(), 'comparison framework/policy differs')
    require(result['content_id'] == identity({k: v for k, v in result.items() if k != 'content_id'}), 'comparison identity differs')
    for name, digest in result['artifacts'].items():
        require(sha256(within(out, name)) == digest, 'comparison artifact differs')
    for track in result['tracks']:
        directory = within(out, track['directory'])
        for side, engine in [('left', track['baseline']), ('right', track['candidate'])]:
            report = read_json(directory / (side + '-run.json'))
            require(report['content_id'] == track[side + '_content_id'] == identity({k: v for k, v in report.items() if k != 'content_id'}), 'comparison source identity differs')
            require(sha256(directory / (side + '-cases.jsonl')) == report['artifacts'][engine + '-accuracy/cases.jsonl'], 'comparison source cases differ')
        records, counts = comparison(list(read_jsonl(directory / 'left-cases.jsonl')), list(read_jsonl(directory / 'right-cases.jsonl')), track['cohorts'], metric=result['metric'])
        require(records == list(read_jsonl(directory / 'paired.jsonl')) and counts == track['summary'], 'comparison paired judgments differ')
    return dict(status='verified', scope='retained source case identities and paired judgments; original native rescoring requires the source runs')


def public_comparison(result, minimum=20):
    require(type(minimum) is int and minimum >= 1, 'positive publication minimum denominator required')
    return dict(schema=SCHEMA, policy=result['policy'], metric=result['metric'],
        publication_policy=dict(schema='address-benchmark.publication/v2', min_denominator=minimum),
        tracks=[dict(id=f'panel-{i + 1}', **public_rate(t['summary'], ('judged_pairs', 'left_only', 'right_only', 'unmatched_judgments'),
                    t['summary']['judged_pairs'], minimum)) for i, t in enumerate(result['tracks'])])
