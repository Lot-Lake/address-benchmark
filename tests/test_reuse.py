from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from address_benchmark.cli import main
from address_benchmark.io import identity, read_json, sha256, write_json
from address_benchmark.plan import run_plan
from address_benchmark.runner import run, verify
from address_benchmark.tables import FORMATS, load_scorecard, render

ROOT = Path(__file__).resolve().parents[1]


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.counter = self.root / 'counter'
        self.engine = dict(name='incumbent', adapter='tests.support:Counting', config=dict(counter=str(self.counter)))

    def plan(self, directory, engines, *, corpus='us-core', timing=False):
        directory.mkdir()
        shutil.copytree(ROOT / ('examples/corpora/' + corpus), directory / 'corpus')
        write_json(directory / 'engines.json', engines)
        write_json(directory / 'plan.json', dict(schema='address-benchmark.plan/v1', name='reuse integration', engines='engines.json',
            tracks=[dict(id='core', corpus='corpus/manifest.json', output='run')],
            execution=dict(timing=timing, trials=2, samples=2, min_seconds=.001, timeout=30)))
        return directory / 'plan.json'

    def execute(self, plan, *, reuse=None):
        with redirect_stderr(io.StringIO()):
            receipt = run_plan(plan, reuse=reuse)
        return receipt, read_json(plan.parent / 'run/run.json')

    def count(self, path=None):
        path = path or self.counter
        return len(path.read_text().splitlines()) if path.exists() else 0

    def prior(self, *, engine=None):
        plan = self.plan(self.root / 'prior', [engine or self.engine])
        receipt, report = self.execute(plan)
        return plan, receipt, report

    def source(self, plan, report):
        return dict(directory=plan.parent / 'run', content_id=report['content_id'])

    def test_adding_engine_reuses_verified_cell_without_inference_and_marks_all_exports(self):
        prior, _, original = self.prior()
        self.assertEqual(self.count(), 8)
        new_counter = self.root / 'new-counter'
        added = deepcopy(self.engine); added['name'] = 'new'; added['config']['counter'] = str(new_counter)
        plan = self.plan(self.root / 'next', [self.engine, added])
        receipt, report = self.execute(plan, reuse=prior)
        self.assertEqual(report['reuse']['incumbent']['status'], 'reused')
        self.assertEqual(report['reuse']['new']['status'], 'fresh')
        self.assertEqual((self.count(), self.count(new_counter)), (8, 8))
        self.assertEqual(receipt['tracks'][0]['engines'], {'incumbent': 'reused', 'new': 'fresh'})
        cell = report['accuracy']['incumbent']
        self.assertIsNone(cell['exit_code'])
        self.assertEqual(cell['origin']['source_exit_code'], 0)
        self.assertEqual(cell['populations'], original['accuracy']['incumbent']['populations'])
        self.assertEqual(verify(plan.parent / 'run')['status'], 'verified')
        for fmt in FORMATS:
            text = render(load_scorecard(plan), fmt, counts=True)
            self.assertIn('reused' if fmt != 'json' else '"reused": true', text)
        # Independent copies keep the new audit valid after the original goes away.
        shutil.rmtree(prior.parent)
        self.assertEqual(verify(plan.parent / 'run')['status'], 'verified')

    def test_fresh_is_default(self):
        prior, _, _ = self.prior()
        _, report = self.execute(self.plan(self.root / 'next', [self.engine]))
        self.assertEqual(self.count(), 16)
        self.assertEqual(report['reuse']['incumbent']['status'], 'fresh')

    def test_config_change_runs_fresh(self):
        prior, _, _ = self.prior()
        changed = deepcopy(self.engine); changed['config']['counter'] = str(self.root / 'other-counter')
        _, report = self.execute(self.plan(self.root / 'next', [changed]), reuse=prior)
        self.assertEqual(report['reuse']['incumbent']['reason'], 'engine-config-changed-or-added')
        self.assertEqual(self.count(self.root / 'other-counter'), 8)

    def test_corpus_change_runs_fresh(self):
        prior, _, _ = self.prior()
        _, report = self.execute(self.plan(self.root / 'next', [self.engine], corpus='us-challenge'), reuse=prior)
        self.assertEqual(report['reuse']['incumbent']['reason'], 'corpus-manifest-changed')
        self.assertGreater(self.count(), 8)

    def test_model_change_and_environment_change_run_fresh(self):
        model = self.root / 'model'; model.write_bytes(b'frozen model')
        self.engine['config']['model'] = str(model)
        prior, _, _ = self.prior()
        model.write_bytes(b'changed completed model')
        _, report = self.execute(self.plan(self.root / 'model-next', [self.engine]), reuse=prior)
        self.assertEqual(report['reuse']['incumbent']['reason'], 'runtime-probe-mismatch')
        self.assertEqual(self.count(), 16)
        # Changed environment cannot quietly reuse an otherwise matching cell.
        old = os.environ.get('BENCHMARK_REUSE_TEST_ENV')
        os.environ['BENCHMARK_REUSE_TEST_ENV'] = 'new-runtime-setting'
        try:
            _, report = self.execute(self.plan(self.root / 'env-next', [self.engine]), reuse=self.root / 'model-next')
        finally:
            if old is None:
                os.environ.pop('BENCHMARK_REUSE_TEST_ENV')
            else:
                os.environ['BENCHMARK_REUSE_TEST_ENV'] = old
        self.assertEqual(report['reuse']['incumbent']['reason'], 'runtime-probe-mismatch')
        self.assertEqual(self.count(), 24)

    def test_tampered_prior_artifact_is_never_reused(self):
        prior, _, _ = self.prior()
        with (prior.parent / 'run/incumbent-accuracy/predictions.jsonl').open('a') as stream:
            stream.write('{}\n')
        _, report = self.execute(self.plan(self.root / 'next', [self.engine]), reuse=prior)
        self.assertEqual(report['reuse']['incumbent']['reason'], 'source-verification-failed')
        self.assertEqual(self.count(), 16)
        self.assertEqual(verify(self.root / 'next/run')['status'], 'verified')

    def test_missing_track_runs_fresh_and_source_plan_mutation_is_rejected(self):
        prior, _, _ = self.prior()
        plan = self.plan(self.root / 'next', [self.engine])
        value = read_json(plan); value['tracks'][0]['id'] = 'new-track'; plan.write_text(json.dumps(value))
        _, report = self.execute(plan, reuse=prior.parent)
        self.assertEqual(report['reuse']['incumbent']['reason'], 'no-prior-track')
        prior.write_text(prior.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'reuse plan changed'):
            self.execute(self.plan(self.root / 'mutated', [self.engine]), reuse=prior)
        self.assertFalse((self.root / 'mutated/run').exists())

    def test_unavailable_prior_cell_runs_fresh(self):
        missing = dict(name='missing', adapter='not_a_real_benchmark_plugin')
        prior, _, _ = self.prior(engine=missing)
        _, report = self.execute(self.plan(self.root / 'next', [missing]), reuse=prior)
        self.assertEqual(report['reuse']['missing']['reason'], 'prior-cell-unsuccessful')
        self.assertEqual(report['accuracy']['missing']['status'], 'unavailable')

    def test_lazy_runtime_difference_falls_back_without_parsing_in_probe(self):
        self.engine['adapter'] = 'tests.support:LazyCounting'
        prior, _, _ = self.prior()
        _, report = self.execute(self.plan(self.root / 'next', [self.engine]), reuse=prior)
        self.assertEqual(report['reuse']['incumbent']['reason'], 'runtime-probe-mismatch')
        self.assertEqual(self.count(), 16)

    def test_timing_is_fresh_even_when_accuracy_is_reused(self):
        prior, _, _ = self.prior()
        plan = self.plan(self.root / 'next', [self.engine, dict(name='peer', adapter='demo')], timing=True)
        _, report = self.execute(plan, reuse=prior)
        self.assertEqual(report['reuse']['incumbent']['status'], 'reused')
        self.assertEqual(len(report['trials']), 2)
        self.assertEqual(report['trials'][0]['order'], list(reversed(report['trials'][1]['order'])))
        self.assertEqual(report['paired']['incumbent/peer']['pairs'], 2)
        self.assertFalse(load_scorecard(plan, metric='throughput')['rows'][0]['cells']['incumbent']['reused'])
        self.assertIn('[reused accuracy]', (plan.parent / 'run/report.md').read_text())
        self.assertGreater(self.count(), 8)
        self.assertEqual(verify(plan.parent / 'run')['status'], 'verified')

    def test_reused_artifacts_are_copies_and_provenance_is_revalidated(self):
        prior, _, _ = self.prior()
        plan = self.plan(self.root / 'next', [self.engine])
        _, report = self.execute(plan, reuse=prior)
        old = prior.parent / 'run/incumbent-accuracy/predictions.jsonl'
        new = plan.parent / 'run/incumbent-accuracy/predictions.jsonl'
        self.assertNotEqual(old.stat().st_ino, new.stat().st_ino)
        target = plan.parent / 'run/reuse/incumbent/source-run.json'
        value = read_json(target); value['accuracy']['incumbent']['exit_code'] = 17
        target.write_text(json.dumps(value))
        report['artifacts'][str(target.relative_to(plan.parent / 'run'))] = sha256(target)
        report['content_id'] = identity({k: v for k, v in report.items() if k != 'content_id'})
        (plan.parent / 'run/run.json').write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'reuse source content identity'):
            verify(plan.parent / 'run')

    def test_reuse_source_and_output_cannot_nest(self):
        prior, _, report = self.prior()
        with self.assertRaisesRegex(ValueError, 'cannot nest'):
            run(prior.parent / 'corpus/manifest.json', prior.parent / 'engines.json', prior.parent / 'run/child', reuse=self.source(prior, report))

    def test_copy_race_is_rejected_and_falls_back_to_fresh_accuracy(self):
        from address_benchmark import reuse as implementation
        prior, _, _ = self.prior()
        plan = self.plan(self.root / 'next', [self.engine])
        original_copy = implementation._copy
        def corrupt_copy(source, target):
            original_copy(source, target)
            if target.name == 'predictions.jsonl':
                target.write_text('{}\n')
        with patch.object(implementation, '_copy', side_effect=corrupt_copy):
            _, report = self.execute(plan, reuse=prior)
        self.assertEqual(report['reuse']['incumbent']['reason'], 'source-changed-during-copy')
        self.assertEqual(self.count(), 16)
        self.assertEqual(verify(plan.parent / 'run')['status'], 'verified')

    def test_input_identity_mismatch_is_not_reused(self):
        prior, receipt, report = self.prior()
        report['input_sha256'] = '0' * 64
        report['content_id'] = identity({k: v for k, v in report.items() if k != 'content_id'})
        (prior.parent / 'run/run.json').write_text(json.dumps(report))
        receipt['tracks'][0]['content_id'] = report['content_id']
        (prior.parent / 'plan-results.json').write_text(json.dumps(receipt))
        _, result = self.execute(self.plan(self.root / 'next', [self.engine]), reuse=prior)
        self.assertEqual(result['reuse']['incumbent']['reason'], 'source-verification-failed')
        self.assertEqual(self.count(), 16)

    def test_legacy_runtime_without_environment_pin_is_not_reused(self):
        prior, receipt, report = self.prior()
        entry = report['accuracy']['incumbent']
        entry['identity'].pop('environment_sha256')
        entry['identity_sha256'] = identity(entry['identity'])
        identity_file = prior.parent / 'run/incumbent-accuracy/identity.json'
        identity_file.write_text(json.dumps(entry['identity']))
        report['artifacts']['incumbent-accuracy/identity.json'] = sha256(identity_file)
        path = prior.parent / 'run/incumbent-accuracy/execution.json'
        path.write_text(json.dumps(entry))
        report['artifacts']['incumbent-accuracy/execution.json'] = sha256(path)
        report['content_id'] = identity({k: v for k, v in report.items() if k != 'content_id'})
        (prior.parent / 'run/run.json').write_text(json.dumps(report))
        receipt['tracks'][0]['content_id'] = report['content_id']
        (prior.parent / 'plan-results.json').write_text(json.dumps(receipt))
        _, result = self.execute(self.plan(self.root / 'next', [self.engine]), reuse=prior)
        self.assertEqual(result['reuse']['incumbent']['reason'], 'legacy-runtime-contract')
        self.assertEqual(self.count(), 16)

    def test_private_reuse_failure_diagnostic_does_not_leak_source_filename(self):
        secret = self.root / 'PRIVATE_SOURCE_817.json'
        secret.write_text('[]')
        plan = self.plan(self.root / 'next', [self.engine])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(['run-plan', str(plan), '--reuse', str(secret)]), 1)
        self.assertNotIn(str(self.root), err.getvalue())
        self.assertNotIn('PRIVATE_SOURCE_817', err.getvalue())
        self.assertFalse((plan.parent / 'run').exists())

    def test_reuse_chain_remains_auditable_after_originals_are_removed(self):
        prior, _, _ = self.prior()
        next_plan = self.plan(self.root / 'second', [self.engine])
        self.execute(next_plan, reuse=prior)
        final_plan = self.plan(self.root / 'third', [self.engine])
        _, report = self.execute(final_plan, reuse=next_plan)
        self.assertEqual(report['reuse']['incumbent']['status'], 'reused')
        self.assertEqual(self.count(), 8)
        shutil.rmtree(prior.parent)
        shutil.rmtree(next_plan.parent)
        self.assertEqual(verify(final_plan.parent / 'run')['status'], 'verified')

    def test_probe_panel_metadata_is_revalidated_even_if_artifact_is_reindexed(self):
        prior, _, _ = self.prior()
        plan = self.plan(self.root / 'next', [self.engine])
        _, report = self.execute(plan, reuse=prior)
        path = plan.parent / 'run/reuse-probe-incumbent/identity-probe.json'
        value = read_json(path); value['input_sha256'] = '0' * 64
        path.write_text(json.dumps(value))
        report['artifacts'][str(path.relative_to(plan.parent / 'run'))] = sha256(path)
        report['content_id'] = identity({k: v for k, v in report.items() if k != 'content_id'})
        (plan.parent / 'run/run.json').write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'reuse probe panel differs'):
            verify(plan.parent / 'run')

    def test_reused_scoped_accuracy_still_fails_gate_before_speed_or_public_track(self):
        from address_benchmark.plan import freeze_plan
        from tools.prepare_scoped_example import prepare
        prior = prepare(self.root / 'scoped-prior')
        freeze_plan(prior)
        with redirect_stderr(io.StringIO()):
            run_plan(prior)
        plan = prepare(self.root / 'scoped-next')
        value = read_json(plan)
        value['execution'].update(timing=True, gate=dict(candidate='candidate', max_losses=0, min_correct=1, min_preservation=1))
        value['tracks'].append(dict(id='public-followup', corpus='manifest.json', output='public-followup'))
        plan.write_text(json.dumps(value))
        freeze_plan(plan)
        with redirect_stderr(io.StringIO()):
            receipt = run_plan(plan, reuse=prior)
        report = read_json(plan.parent / 'execution/run.json')
        self.assertTrue(all(v['status'] == 'reused' for v in report['reuse'].values()))
        self.assertEqual(report['status'], 'gated')
        self.assertEqual(report['measurements']['timing'], 'blocked-by-accuracy-gate')
        self.assertEqual(receipt['tracks'][1]['status'], 'not-executed')
        self.assertFalse((plan.parent / 'public-followup').exists())
        self.assertEqual(verify(plan.parent / 'execution')['status'], 'verified')

    def test_existing_normalization_task_uses_the_same_reuse_contract(self):
        engines = [dict(name='normalize', adapter='demo-normalize')]
        prior = self.plan(self.root / 'prior-normalize', engines, corpus='us-normalization')
        self.execute(prior)
        plan = self.plan(self.root / 'next-normalize', engines, corpus='us-normalization')
        _, report = self.execute(plan, reuse=prior)
        self.assertEqual(report['reuse']['normalize']['status'], 'reused')
        self.assertEqual(verify(plan.parent / 'run')['status'], 'verified')

    def test_reused_publisher_cells_preserve_noncomparability_and_both_public_markers(self):
        from tests.test_reference_comparability import ReferenceComparabilityTests
        fixture = ReferenceComparabilityTests()
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        manifest_path = fixture.root / 'manifest.json'
        manifest = read_json(manifest_path)
        manifest['license']['redistribution'] = 'local-only'
        manifest['id'] = 'PRIVATE_REUSED_PUBLISHER_671'
        manifest_path.write_text(json.dumps(manifest))
        prior = fixture.execute()
        result = run(manifest_path, fixture.root / 'engines.json', fixture.root / 'expanded',
                     reuse=dict(directory=fixture.root / 'run', content_id=prior['content_id']))
        self.assertEqual(result['reuse']['clean-components']['status'], 'reused')
        self.assertEqual(verify(fixture.root / 'expanded')['status'], 'verified')
        card = load_scorecard(fixture.root / 'expanded', publishable=True)
        cell = card['rows'][0]['cells']['engine-1']
        self.assertTrue(cell['reused'])
        self.assertFalse(cell['comparable'])
        self.assertEqual(cell['status'], 'suppressed')
        self.assertEqual(cell['noncomparable_reasons'], ['reference-edge-delimiters'])
        for fmt in FORMATS:
            text = render(card, fmt, counts=True)
            self.assertNotIn('PRIVATE_REUSED_PUBLISHER_671', text)
            self.assertNotIn(str(fixture.root), text)
            self.assertIn('"reused": true' if fmt == 'json' else '[reused]', text)
            self.assertIn('non-comparable' if fmt != 'json' else '"comparable": false', text)
        detailed = load_scorecard(fixture.root / 'expanded', publishable=True, min_denominator=1)
        source = detailed['aggregates'][0]['engines']['engine-1']['sources'][0]
        for metric in ('supplied_fields', 'complete_address'):
            self.assertFalse(source[metric]['comparable'])
            self.assertEqual(source[metric]['recommended_metric'], 'delimiter')

    def test_inconsistent_runtime_envelope_cannot_reuse_another_models_predictions(self):
        prior, receipt, report = self.prior()
        entry = report['accuracy']['incumbent']
        entry['identity']['adapter']['model'] = 'inconsistent-runtime-description'
        entry['identity_sha256'] = identity(entry['identity'])
        path = prior.parent / 'run/incumbent-accuracy/execution.json'
        path.write_text(json.dumps(entry))
        report['artifacts']['incumbent-accuracy/execution.json'] = sha256(path)
        report['content_id'] = identity({k: v for k, v in report.items() if k != 'content_id'})
        (prior.parent / 'run/run.json').write_text(json.dumps(report))
        receipt['tracks'][0]['content_id'] = report['content_id']
        (prior.parent / 'plan-results.json').write_text(json.dumps(receipt))
        _, result = self.execute(self.plan(self.root / 'next', [self.engine]), reuse=prior)
        self.assertEqual(result['reuse']['incumbent']['reason'], 'source-verification-failed')
        self.assertEqual(self.count(), 16)

    def test_engine_snapshot_preserves_exact_compact_config_bytes(self):
        plan = self.plan(self.root / 'compact', [self.engine])
        path = plan.parent / 'engines.json'
        encoded = json.dumps([self.engine], separators=(',', ':')).encode()
        path.write_bytes(encoded)
        _, report = self.execute(plan)
        self.assertEqual((plan.parent / 'run/engines.json').read_bytes(), encoded)
        self.assertEqual(report['engine_config_sha256'], sha256(plan.parent / 'run/engines.json'))
        self.assertEqual(verify(plan.parent / 'run')['status'], 'verified')

    def test_cli_reuse_and_publishable_private_exports_exclude_source_paths_and_ids(self):
        from address_benchmark.plan import freeze_plan
        secret = 'PRIVATE_REUSE_76191'
        self.engine['name'] = secret
        prior = self.plan(self.root / 'private-prior', [self.engine])
        manifest = read_json(prior.parent / 'corpus/manifest.json')
        manifest['license']['redistribution'] = 'local-only'
        (prior.parent / 'corpus/manifest.json').write_text(json.dumps(manifest))
        freeze_plan(prior)
        self.execute(prior)
        plan = self.plan(self.root / 'private-next', [self.engine])
        (plan.parent / 'corpus/manifest.json').write_text(json.dumps(manifest))
        freeze_plan(plan)
        with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(main(['run-plan', str(plan), '--reuse', str(prior)]), 0)
        self.assertIn('[reused]', stdout.getvalue())
        self.assertNotIn(secret, stdout.getvalue() + stderr.getvalue())
        for fmt in FORMATS:
            output = render(load_scorecard(plan, publishable=True), fmt, counts=True)
            self.assertNotIn(secret, output)
            self.assertNotIn(str(self.root), output)
            self.assertIn('reused', output)


if __name__ == '__main__':
    unittest.main()
