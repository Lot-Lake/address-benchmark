"""Scope, frozen-plan, paired audit and publication boundary regressions."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from address_benchmark.adapters import DemoParser
from address_benchmark.cli import main
from address_benchmark.corpus import apply_scope, input_requests, load_corpus
from address_benchmark.io import identity, read_json, read_jsonl, sha256, write_json
from address_benchmark.plan import freeze_plan, run_plan
from address_benchmark.protocol import prediction
from address_benchmark.runner import paired_summary, verify
from address_benchmark.scoring import SCOPED_SCORER, SCORER, comparison, score_case, summarize
from address_benchmark.tables import FORMATS, load_scorecard, render
from tools.prepare_scoped_example import prepare


class PrivateEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = prepare(self.root / 'local')

    def replace(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def execute(self):
        freeze_plan(self.plan)
        with redirect_stderr(io.StringIO()):
            result = run_plan(self.plan)
        return result, read_json(self.plan.parent / 'execution/run.json')

    def test_source_scope_downgrades_all_layers_and_rejects_overclaims(self):
        manifest, rows, _ = load_corpus(self.plan.parent / 'manifest.json')
        ref = rows[2]['reference']
        self.assertEqual([ref[k] for k in ('coverage', 'tokens_coverage', 'spans_coverage')], ['partial'] * 3)
        scope = manifest['resources'][1]['annotation_scope']
        bad = deepcopy(ref); bad['fields']['unit'] = ['9']
        with self.assertRaisesRegex(ValueError, 'role scope'):
            apply_scope(bad, scope)
        bad = deepcopy(ref); bad['fields']['road'] = []
        with self.assertRaisesRegex(ValueError, 'absence'):
            apply_scope(bad, scope)
        manifest.pop('scorer')
        self.replace(self.plan.parent / 'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'scorer/v2'):
            load_corpus(self.plan.parent / 'manifest.json')

    def test_partial_predictions_are_unjudged_and_unsupported_absence_not_correct(self):
        manifest, rows, _ = load_corpus(self.plan.parent / 'manifest.json')
        adapter = DemoParser({})
        requests = input_requests(manifest, rows)
        result = score_case(rows[2], adapter.parse(requests[2]), adapter.metadata, scorer=SCOPED_SCORER)
        self.assertTrue(result['primary_agrees'])
        self.assertIsNone(result['complete_address_agrees'])
        self.assertIn('house_number', result['unadjudicated_roles'])
        self.assertEqual(result['tokens']['metrics']['tp'], 1)
        self.assertIsNone(result['tokens']['metrics']['fp'])
        self.assertIsNone(result['tokens']['metrics']['f1'])
        self.assertEqual(result['tokens']['unadjudicated'], 5)
        row = deepcopy(rows[2]); row['reference']['fields'] = {'unit': []}
        self.assertIsNone(score_case(row, adapter.parse(requests[2]), adapter.metadata, scorer=SCOPED_SCORER)['primary_agrees'])
        row['reference']['fields']['road'] = ['Maple St']
        self.assertIsNone(score_case(row, adapter.parse(requests[2]), adapter.metadata, scorer=SCOPED_SCORER)['primary_agrees'])
        # Legacy policy is explicit and retains its original interpretation.
        self.assertTrue(score_case(row, adapter.parse(requests[2]), adapter.metadata, scorer=SCORER)['primary_agrees'])

    def test_fine_annotations_remain_measured_without_coarse_labels(self):
        manifest_path = self.plan.parent / 'manifest.json'
        manifest = read_json(manifest_path)
        resource = manifest['resources'][1]
        resource['annotation_scope']['fields'] = dict(coverage='none', roles=[], absence=False)
        path = self.plan.parent / resource['path']
        rows = list(read_jsonl(path))
        for row in rows:
            row['reference']['fields'] = {}
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        resource['sha256'] = sha256(path)
        manifest['preservation_cohorts'][0]['row_ids'] = ['synthetic-2']
        self.replace(manifest_path, manifest)
        manifest, loaded, _ = load_corpus(manifest_path)
        row = loaded[2]
        self.assertEqual(row['reference']['coverage'], 'none')
        self.assertEqual(row['reference']['tokens_coverage'], 'partial')
        adapter = DemoParser({})
        request = input_requests(manifest, loaded)[2]
        case = score_case(row, adapter.parse(request), adapter.metadata, scorer=SCOPED_SCORER)
        self.assertIsNone(case['primary_agrees'])
        self.assertEqual(case['tokens']['metrics']['recall'], 1)
        self.assertEqual(summarize([case])['supplied_fields']['denominator'], 0)

    def test_inactive_fine_mapping_cannot_earn_true_positive(self):
        manifest, rows, _ = load_corpus(self.plan.parent / 'manifest.json')
        adapter = DemoParser({}); adapter.metadata['active_roles'] = ['city']
        request = input_requests(manifest, rows)[2]
        case = score_case(rows[2], adapter.parse(request), adapter.metadata, scorer=SCOPED_SCORER)
        self.assertFalse(case['primary_agrees'])
        self.assertEqual(case['tokens']['metrics']['tp'], 0)
        self.assertEqual(case['tokens']['metrics']['fn'], 1)

    def test_synthetic_plan_private_audit_gains_losses_refusals_and_sources(self):
        receipt, report = self.execute()
        self.assertEqual(receipt['status'], 'complete')
        self.assertEqual(verify(self.plan.parent / 'execution')['status'], 'verified')
        delta = report['deltas']['incumbent/candidate']
        self.assertEqual((delta['left_only'], delta['right_only'], delta['judged_pairs']), (1, 1, 4))
        self.assertEqual(delta['roles']['house_number']['judged_pairs'], 2)
        self.assertEqual(delta['preservation']['supplied-control'], dict(denominator=2, left_correct=2, right_correct=1, retained=1, left_unjudged=0, right_unjudged=0))
        cases = list(read_jsonl(self.plan.parent / 'execution/candidate-accuracy/cases.jsonl'))
        self.assertEqual(cases[-1]['status'], 'refused')
        sources = report['accuracy']['candidate']['sources']
        self.assertEqual(sources['complete.jsonl']['complete_address']['denominator'], 2)
        self.assertEqual(sources['partial.jsonl']['complete_address']['denominator'], 0)
        self.assertEqual(sources['partial.jsonl']['tokens']['partial']['rows'], 1)
        self.assertEqual(report['measurements']['timing'], 'not-requested')
        self.assertTrue((self.plan.parent / 'execution/candidate-accuracy/predictions.jsonl').exists())
        # Verification recomputes paired identities, not just their hashes.
        path = self.plan.parent / 'execution' / delta['artifact']
        path.write_text('{}\n')
        report['artifacts'][delta['artifact']] = sha256(path)
        report['content_id'] = identity({k: v for k, v in report.items() if k != 'content_id'})
        self.replace(self.plan.parent / 'execution/run.json', report)
        with self.assertRaisesRegex(ValueError, 'paired identities'):
            verify(self.plan.parent / 'execution')

    def test_accuracy_gate_stops_before_any_timing_process(self):
        plan = read_json(self.plan)
        public = read_json(self.plan.parent / 'manifest.json')
        public['license']['redistribution'] = 'allowed'
        self.replace(self.plan.parent / 'public-manifest.json', public)
        plan['tracks'].append(dict(id='public-followup', corpus='public-manifest.json', output='public-execution'))
        plan['execution'].update(timing=True, gate=dict(candidate='candidate', max_losses=0, min_correct=1, min_preservation=1))
        self.replace(self.plan, plan)
        receipt, report = self.execute()
        self.assertEqual(receipt['status'], 'incomplete')
        self.assertEqual(report['status'], 'gated')
        self.assertEqual(report['gate']['status'], 'failed')
        self.assertEqual(report['measurements']['timing'], 'blocked-by-accuracy-gate')
        self.assertEqual(receipt['tracks'][1]['status'], 'not-executed')
        self.assertFalse((self.plan.parent / 'public-execution').exists())
        self.assertEqual(load_scorecard(self.plan)['rows'][1]['cells']['engine-1']['status'], 'not-executed')
        self.assertEqual(report['trials'], [])
        self.assertFalse(list((self.plan.parent / 'execution').glob('trial-*')))
        self.assertEqual(verify(self.plan.parent / 'execution')['status'], 'verified')

    def test_frozen_plan_rejects_changed_engine_corpus_framework_and_runtime(self):
        engines = read_json(self.plan.parent / 'engines.json')
        asset = self.root / 'completed-model.bin'; asset.write_bytes(b'completed external fixture')
        engines[0]['config']['artifact_files'] = [str(asset)]
        self.replace(self.plan.parent / 'engines.json', engines)
        freeze_plan(self.plan)
        original = asset.read_bytes(); asset.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'frozen plan'):
            run_plan(self.plan)
        self.assertFalse((self.plan.parent / 'execution').exists())
        asset.write_bytes(original)
        frozen = read_json(self.plan)
        for key in ('framework', 'engines_sha256', 'corpora'):
            changed = deepcopy(frozen); changed['pins'][key] = {}
            self.replace(self.plan, changed)
            with self.assertRaisesRegex(ValueError, 'frozen plan'):
                run_plan(self.plan)
        self.replace(self.plan, frozen)
        with self.assertRaisesRegex(ValueError, 'already frozen'):
            freeze_plan(self.plan)

    def test_local_plan_requires_freeze_and_cohorts_must_be_supplied(self):
        with self.assertRaisesRegex(ValueError, 'must be frozen'):
            run_plan(self.plan)
        manifest = read_json(self.plan.parent / 'manifest.json')
        manifest['preservation_cohorts'][0]['row_ids'].append('candidate-derived-unknown-row')
        self.replace(self.plan.parent / 'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'cohort members'):
            freeze_plan(self.plan)

    def test_private_identifiers_and_paths_cannot_escape_files_or_public_console(self):
        manifest_path = self.plan.parent / 'manifest.json'
        manifest = read_json(manifest_path)
        secret = 'PRIVATE_SENTINEL_48179'
        manifest['id'] = secret + '-corpus'
        manifest['preservation_cohorts'][0]['id'] = secret + '-cohort'
        private_ids = []
        for resource in manifest['resources']:
            path = self.plan.parent / resource.pop('path')
            rows = list(read_jsonl(path))
            for row in rows:
                old = row['id']; row['id'] = secret + '-' + old
                row['family'] = secret + '-' + row['family']
                row['subsets'] = [secret + '-subset']
                private_ids.extend([row['id'], row['family']])
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            resource.update(external_path=str(path), sha256=sha256(path), source=secret + '-' + path.name)
        manifest['preservation_cohorts'][0]['row_ids'] = [secret + '-' + x for x in manifest['preservation_cohorts'][0]['row_ids']]
        manifest['exposure']['status'] = secret
        manifest['exposure']['history'] = [str(self.root)]
        self.replace(manifest_path, manifest)
        plan = read_json(self.plan); plan['name'] = secret; plan['tracks'][0]['id'] = secret
        engines = read_json(self.plan.parent / 'engines.json')
        engines.append(dict(name='echo', adapter='tests.support:PrivateEcho'))
        for e in engines:
            e['name'] = secret + '-' + e['name']
        plan['execution']['baseline'] = engines[0]['name']
        self.replace(self.plan.parent / 'engines.json', engines); self.replace(self.plan, plan)
        freeze_plan(self.plan)
        with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(main(['run-plan', str(self.plan), '--json']), 0)
        self.assertNotIn(secret, stdout.getvalue() + stderr.getvalue())
        self.assertNotIn(str(self.root), stdout.getvalue() + stderr.getvalue())
        report = read_json(self.plan.parent / 'execution/run.json')
        private_inputs = list(read_jsonl(self.plan.parent / 'execution/inputs.jsonl'))
        forbidden = [secret, str(self.root), *private_ids, *(x['text'] for x in private_inputs), *(x['input_sha256'] for x in private_inputs)]
        for base in (self.plan.parent, self.plan.parent / 'execution'):
            for path in base.glob('scores.*'):
                for value in forbidden:
                    self.assertNotIn(value, path.read_text(), path.name)
        for format in FORMATS:
            with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(['report', str(self.plan), '--publishable', '--all-views', '--title', secret, '--format', format]), 0)
            for value in forbidden:
                self.assertNotIn(value, out.getvalue() + err.getvalue(), format)
        data = load_scorecard(self.plan, publishable=True)['aggregates'][0]
        self.assertEqual(data['deltas'][0]['preservation'][0]['denominator'], 2)
        self.assertEqual(data['blindness'], 'not-established')
        self.assertEqual(data['engines']['engine-3']['sources'][0]['statuses']['error'], 2)
        self.assertEqual(load_scorecard(self.plan)['rows'][0]['cells']['engine-3']['errors'], 4)
        failures = list(read_jsonl(self.plan.parent / 'execution' / (engines[-1]['name'] + '-accuracy') / 'predictions.jsonl'))
        self.assertEqual(failures[0]['status'], 'error')
        self.assertIn(private_inputs[0]['text'], failures[0]['message'])
        self.assertIn(secret, json.dumps(report))  # audit remains complete and private
        # Failure text is also publication-safe, including filesystem exceptions.
        with redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(['report', str(self.root / secret), '--publishable']), 1)
        self.assertNotIn(secret, err.getvalue())
        self.assertNotIn(str(self.root), err.getvalue())

    def test_passed_gate_runs_balanced_four_pair_timing_with_uncertainty(self):
        manifest_path = self.plan.parent / 'manifest.json'
        manifest = read_json(manifest_path)
        path = self.plan.parent / 'partial.jsonl'
        path.write_text(path.read_text().splitlines()[0] + '\n')
        manifest['resources'][1]['sha256'] = sha256(path)
        self.replace(manifest_path, manifest)
        plan = read_json(self.plan)
        plan['execution'].update(timing=True, trials=4, samples=2, min_seconds=.001,
            gate=dict(candidate='candidate', max_losses=1, min_correct=2, min_preservation=.5))
        self.replace(self.plan, plan)
        _, report = self.execute()
        self.assertEqual(report['gate']['status'], 'passed')
        self.assertEqual(report['measurements']['timing'], 'executed')
        for i in (0, 2):
            self.assertEqual(report['trials'][i]['order'], list(reversed(report['trials'][i+1]['order'])))
        self.assertEqual(report['paired']['incumbent/candidate']['pairs'], 4)
        self.assertIsNotNone(report['paired']['incumbent/candidate']['bootstrap_95_interval'])
        self.assertEqual(verify(self.plan.parent / 'execution')['status'], 'verified')

    def test_effects_use_declared_field_denominators_and_independent_cohorts(self):
        from address_benchmark.adapters import metadata
        meta = metadata('field-controls', {r: r for r in ('unit', 'building', 'recipient', 'road', 'city')})
        row = dict(id='x', family='external-family', source='source', split='test', origin='authored', subsets=[],
                   reference=dict(coverage='partial', fields={r: [r] for r in meta['role_map']},
                                  tokens_coverage='none', spans_coverage='none', tokens=[], spans=[]))
        from address_benchmark.protocol import Request, request_hash
        req = Request('x', 'synthetic control', request_hash('synthetic control'), 'US', 'en-US')
        good = prediction(req, [dict(native_role=r, value=r) for r in meta['role_map']])
        bad = deepcopy(good)
        for item in bad['evidence']:
            item['value'] = 'changed'
        left = score_case(row, good, meta, scorer=SCOPED_SCORER)
        right = score_case(row, bad, meta, scorer=SCOPED_SCORER)
        metrics = summarize([left, right])
        for key in ('unit', 'building', 'recipient', 'road_city'):
            self.assertEqual(metrics['effects'][key], dict(correct=1, denominator=2, rate=.5))
        _, paired = comparison([left], [right], [dict(id='external', row_ids=['x'], basis='independent')])
        self.assertEqual(paired['effects']['road_city'], dict(left_only=1, right_only=0, judged_pairs=1))
        self.assertEqual(paired['preservation']['external']['denominator'], 1)

    def test_scoped_profile_cannot_promote_unsupported_absence(self):
        manifest, rows, _ = load_corpus(self.plan.parent / 'manifest.json')
        adapter = DemoParser({})
        req = input_requests(manifest, rows)[0]
        result = score_case(rows[0], adapter.parse(req), adapter.metadata,
                            profiles=['strict-streetline/v1', 'strict-streetline/v2'], scorer=SCOPED_SCORER)
        self.assertTrue(result['primary_agrees'])
        self.assertTrue(all(p['agrees'] is None for p in result['profiles'].values()))

    def test_equal_counts_with_different_eligibility_do_not_mark_leaders(self):
        from address_benchmark.tables import leaders, scorecard
        from tests.test_tables import recorded
        report = recorded()
        for name, entry in report['accuracy'].items():
            for pop in entry.get('populations', {}).values():
                pop['eligibility'] = {'supplied_fields': name}
        card = scorecard([('test', report)])
        self.assertEqual(leaders(card['rows'][0]), set())
        self.assertFalse(card['rows'][0]['cells']['a']['comparable'])

    def test_bootstrap_uses_all_complete_process_pairs(self):
        trials = [dict(engines=dict(a=dict(status='ok', median_ns_per_address=1), b=dict(status='ok', median_ns_per_address=n))) for n in (2, 3, 4, 5)]
        value = paired_summary(trials, ['a', 'b'], seed=1)['a/b']
        self.assertEqual(value['pairs'], 4)
        self.assertEqual(value['median_ratio'], 3.5)
        self.assertIsNotNone(value['bootstrap_95_interval'])
        self.assertEqual(value, paired_summary(trials, ['a', 'b'], seed=1)['a/b'])


if __name__ == '__main__':
    unittest.main()
