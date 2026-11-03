"""Regression cases from Andrei-Dr's PR #13 review; fictional data only."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from address_benchmark.adapters import DemoParser
from address_benchmark.cli import main
from address_benchmark.gates import accuracy_gate, check_gate, resolve_cohorts
from address_benchmark.io import identity, read_json, sha256
from address_benchmark.plan import freeze_plan, run_plan
from address_benchmark.runner import run, verify
from address_benchmark.tables import FORMATS, load_scorecard, render, scorecard
from tools.prepare_scoped_example import prepare

ROOT = Path(__file__).resolve().parents[1]


def case(id, baseline=True, *, split='test', subsets=('floor',), delimiter=None, profile=None):
    return dict(id=id, family=id, coverage='partial', primary_agrees=baseline,
        delimiter_fields_agree=baseline if delimiter is None else delimiter,
        profiles={'strict-streetline/v1': {'agrees': profile}, 'strict-streetline/v2': {'agrees': profile}},
        split=split, subsets=list(subsets), role_agreement={}, effects_agreement={})


class ReviewContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, path, value):
        path.write_text(json.dumps(value))

    def test_command_file_inventory_pins_argv_and_metadata_models_before_workers(self):
        for target in ('bridge', 'model', 'declared'):
            with self.subTest(target=target):
                plan = prepare(self.root / target)
                bridge = plan.parent / 'bridge.py'
                bridge.write_bytes((ROOT / 'examples/adapters/jsonl_demo.py').read_bytes())
                model = plan.parent / 'model.bin'; model.write_bytes(b'completed synthetic model')
                declared = plan.parent / 'declared.bin'; declared.write_bytes(b'external declared asset')
                engines = read_json(plan.parent / 'engines.json')
                meta = DemoParser({}).metadata; meta['artifact_files'] = [str(declared)]
                engines[0] = dict(name='incumbent', adapter='command', config=dict(
                    command=[sys.executable, str(bridge), str(model)], metadata=meta))
                self.write(plan.parent / 'engines.json', engines)
                freeze_plan(plan)
                pins = read_json(plan)['pins']['runtime_assets']
                self.assertTrue(all(str(p.resolve()) in pins for p in (bridge, model, declared)))
                changed = {'bridge': bridge, 'model': model, 'declared': declared}[target]
                changed.write_bytes(changed.read_bytes() + b'!')
                with self.assertRaisesRegex(ValueError, 'frozen plan assets'):
                    run_plan(plan)
                self.assertFalse((plan.parent / 'execution').exists())

    def test_command_config_still_runs_without_unsupported_top_level_artifact_field(self):
        plan = prepare(self.root / 'command')
        engines = read_json(plan.parent / 'engines.json')
        engines[0] = dict(name='incumbent', adapter='command', config=dict(command=[sys.executable,
            str(ROOT / 'examples/adapters/jsonl_demo.py')], metadata=DemoParser({}).metadata))
        self.write(plan.parent / 'engines.json', engines)
        freeze_plan(plan)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(run_plan(plan)['status'], 'complete')
        self.assertEqual(verify(plan.parent / 'execution')['status'], 'verified')

    def test_gate_metric_uses_existing_case_judgments(self):
        cases = {'baseline': [case('a', True, profile=True)],
                 'candidate': [case('a', False, delimiter=True, profile=True)]}
        for metric in ('strict', 'delimiter', 'strict-streetline/v1', 'strict-streetline/v2'):
            gate = dict(candidate='candidate', metric=metric, max_losses=0, min_correct_rate=1)
            check_gate(gate, list(cases), 'baseline')
            result = accuracy_gate(cases, gate, 'baseline', [])
            self.assertEqual(result['status'], 'failed' if metric == 'strict' else 'passed')
            self.assertEqual(result['metric'], metric)
            self.assertEqual(result['policy'], 'address-benchmark.gate/v2')
        cases['candidate'][0]['profiles']['strict-streetline/v2']['agrees'] = None
        self.assertEqual(accuracy_gate(cases, dict(candidate='candidate', metric='strict-streetline/v2', min_correct_rate=1), 'baseline', [])['status'], 'failed')

    def test_real_comma_predictions_can_pass_delimiter_and_streetline_gates(self):
        from address_benchmark.io import read_jsonl, write_jsonl
        for metric in ('strict', 'delimiter', 'strict-streetline/v1', 'strict-streetline/v2'):
            with self.subTest(metric=metric):
                plan = prepare(self.root / metric.replace('/', '-'))
                manifest_path = plan.parent / 'manifest.json'
                manifest = read_json(manifest_path)
                manifest['scoring_profiles'] = ['strict-streetline/v1', 'strict-streetline/v2']
                data = plan.parent / 'partial.jsonl'
                rows = list(read_jsonl(data)); rows[0]['subsets'] = ['road-floor']
                data.unlink(); write_jsonl(data, rows)
                manifest['resources'][1]['sha256'] = sha256(data)
                self.write(manifest_path, manifest)
                engines = [dict(name='baseline', adapter='demo'), dict(name='candidate', adapter='tests.support:EdgeDemo')]
                self.write(plan.parent / 'engines.json', engines)
                result = run(manifest_path, plan.parent / 'engines.json', plan.parent / 'measured', baseline='baseline',
                    gate=dict(candidate='candidate', metric=metric, requirements=[dict(subset='road-floor', max_loss_rate=0, min_correct_rate=1)]))
                self.assertEqual(result['gate']['status'], 'failed' if metric == 'strict' else 'passed')
                self.assertEqual(verify(plan.parent / 'measured')['status'], 'verified')

    def test_gate_splits_and_count_rate_thresholds_per_subset_and_cohort(self):
        left = [case('a'), case('b'), case('c', split='excluded')]
        right = [case('a'), case('b', False), case('c', False, split='excluded')]
        cohorts = [dict(id='preserve', row_ids=['a'], basis='externally supplied')]
        gate = dict(candidate='candidate', metric='strict', splits=['test'], requirements=[
            dict(subset='floor', max_loss_rate=.5, min_correct=1),
            dict(cohort='preserve', min_correct_rate=1, min_preservation=1)])
        value = accuracy_gate({'baseline': left, 'candidate': right}, gate, 'baseline', cohorts)
        self.assertEqual(value['status'], 'passed')
        self.assertEqual(value['requirements'][0]['judged_pairs'], 2)
        self.assertEqual(value['requirements'][0]['loss_rate'], .5)
        gate['requirements'][0]['max_loss_rate'] = .49
        self.assertEqual(accuracy_gate({'baseline': left, 'candidate': right}, gate, 'baseline', cohorts)['status'], 'failed')
        gate['requirements'][0]['subset'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'unknown gate subset'):
            accuracy_gate({'baseline': left, 'candidate': right}, gate, 'baseline', cohorts)

    def test_baseline_only_cohort_recipe_is_candidate_independent_and_pin_bound(self):
        recipes = [dict(id='stable', basis=dict(kind='baseline-correct', subset='floor', splits=['test'], metric='delimiter'))]
        baseline = [case('a'), case('b', False), case('c', split='excluded')]
        accuracy = {'baseline': dict(status='ok', identity_sha256='a' * 64)}
        engines = [dict(name='baseline', adapter='demo')]
        contract = dict(framework={'scoring.py': '1' * 64}, corpus='2' * 64, scorer='fixed/v1')
        args = (recipes, {'baseline': baseline, 'candidate': [case('a', False)]}, 'baseline', accuracy, engines)
        cohorts = resolve_cohorts(*args, contract=contract)
        self.assertEqual(cohorts[0]['row_ids'], ['a'])
        pin = cohorts[0]['basis']['baseline_pin']
        self.assertEqual(len(pin), 64)
        args[1]['candidate'] = [case('b', True)]
        self.assertEqual(resolve_cohorts(*args, contract=contract), cohorts)
        supplied = [dict(id='external', row_ids=['a'], basis=dict(kind='external', baseline_pin=pin))]
        self.assertEqual(resolve_cohorts(supplied, args[1], 'baseline', accuracy, engines, contract=contract)[0]['row_ids'], ['a'])
        accuracy['baseline']['identity_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'baseline pin differs'):
            resolve_cohorts(supplied, args[1], 'baseline', accuracy, engines, contract=contract)

    def test_track_gate_override_and_plan_receipt_verification(self):
        plan = prepare(self.root / 'plan')
        value = read_json(plan)
        value['execution']['gate'] = dict(candidate='candidate', max_losses=0, min_correct=1, min_preservation=1)
        value['tracks'][0]['execution'] = dict(gate=dict(candidate='candidate', max_losses=1, min_correct=1, min_preservation=0))
        value['tracks'].append(dict(id='strict-followup', corpus='manifest.json', output='followup'))
        self.write(plan, value)
        freeze_plan(plan)
        with redirect_stderr(io.StringIO()):
            receipt = run_plan(plan)
        self.assertEqual([t['status'] for t in receipt['tracks']], ['complete', 'gated'])
        for path in (plan, plan.parent, plan.parent / 'plan-results.json'):
            self.assertEqual(verify(path)['status'], 'verified')
        (plan.parent / 'scores.csv').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'plan export artifact'):
            verify(plan.parent / 'plan-results.json')

    def test_publication_default_suppresses_every_small_numeric_channel(self):
        from tests.test_tables import recorded, population
        report = recorded()
        for entry in report['accuracy'].values():
            if entry['status'] == 'ok':
                entry['populations'] = {'authored/test/all': population(3, 2), 'authored/test/subset:PRIVATE_VIEW': population(3, 2)}
        report['privacy'] = 'local-only'
        report['gate'] = dict(status='failed', judged_pairs=3, correct=2, losses=1)
        report['deltas'] = {'a/b': dict(judged_pairs=3, left_only=2, right_only=1,
            preservation={'PRIVATE_COHORT': dict(denominator=3, left_correct=2, right_correct=1, retained=1)})}
        report['cohorts'] = [dict(id='PRIVATE_COHORT')]
        card = scorecard([('PRIVATE_PANEL', report)], subsets=['PRIVATE_VIEW'])
        self.assertEqual(card['publication_policy']['min_denominator'], 20)
        self.assertEqual(card['rows'][0]['cells']['engine-1']['status'], 'suppressed')
        self.assertNotIn('rows', card['rows'][0])
        group = card['aggregates'][0]
        self.assertEqual(group['deltas'][0]['preservation'][0], dict(id='panel-1/cohort-1', status='suppressed'))
        self.assertNotIn('correct', group['gate'])
        for fmt in FORMATS:
            text = render(card, fmt, counts=True)
            for secret in ('PRIVATE_PANEL', 'PRIVATE_VIEW', 'PRIVATE_COHORT', '66.67%', '2/3'):
                self.assertNotIn(secret, text, fmt)
            self.assertIn('suppressed', text)
        self.assertEqual(card['rows'][1]['id'], 'panel-1/view-1')
        self.assertEqual(card['sources'][0]['id'], group['id'])

    def test_large_export_retains_metrics_and_explicit_threshold_override_is_recorded(self):
        from tests.test_tables import recorded, population
        report = recorded(); report['privacy'] = 'local-only'
        for entry in report['accuracy'].values():
            if entry['status'] == 'ok': entry['populations'] = {'authored/test/all': population(30, 25)}
        card = scorecard([('private', report)])
        self.assertEqual(card['rows'][0]['cells']['engine-1']['correct'], 25)
        card = scorecard([('private', report)], min_denominator=40)
        self.assertEqual(card['rows'][0]['cells']['engine-1']['status'], 'suppressed')
        self.assertEqual(card['publication_policy']['min_denominator'], 40)

    def test_aliases_are_per_panel_and_do_not_depend_on_sorted_private_ids(self):
        from tests.test_tables import recorded, population
        report = recorded(); report['privacy'] = 'local-only'
        report['source_order'] = ['Z_PRIVATE_SOURCE', 'A_PRIVATE_SOURCE']
        report['cohorts'] = [dict(id='Z_PRIVATE_COHORT'), dict(id='A_PRIVATE_COHORT')]
        for entry in report['accuracy'].values():
            if entry['status'] == 'ok':
                entry['populations'] = {'authored/test/all': population(30, 25), 'authored/test/subset:floor': population(30, 25)}
                entry['sources'] = {'A_PRIVATE_SOURCE': population(15, 12), 'Z_PRIVATE_SOURCE': population(15, 13)}
        counts = dict(denominator=30, left_correct=25, right_correct=24, retained=24)
        report['deltas'] = {'a/b': dict(judged_pairs=30, left_only=1, right_only=0,
            preservation={'A_PRIVATE_COHORT': counts, 'Z_PRIVATE_COHORT': counts})}
        card = scorecard([('private-one', report), ('private-two', deepcopy(report))], subsets=['floor'], min_denominator=1)
        self.assertEqual([r['panel'] for r in card['rows']], ['panel-1', 'panel-1', 'panel-2', 'panel-2'])
        self.assertEqual([r['id'] for r in card['rows']], ['panel-1/all', 'panel-1/view-1', 'panel-2/all', 'panel-2/view-1'])
        sources = card['aggregates'][0]['engines']['engine-1']['sources']
        self.assertEqual([s['id'] for s in sources], ['panel-1/source-1', 'panel-1/source-2'])
        self.assertEqual(sources[0]['supplied_fields']['correct'], 13)
        self.assertEqual([c['id'] for c in card['aggregates'][0]['deltas'][0]['preservation']], ['panel-1/cohort-1', 'panel-1/cohort-2'])
        renamed = deepcopy(report)
        mapping = {'Z_PRIVATE_SOURCE': '0_RENAMED', 'A_PRIVATE_SOURCE': '9_RENAMED'}
        renamed['source_order'] = [mapping[x] for x in renamed['source_order']]
        for entry in renamed['accuracy'].values():
            if 'sources' in entry: entry['sources'] = {mapping[k]: v for k, v in entry['sources'].items()}
        after = scorecard([('new-one', renamed), ('new-two', deepcopy(renamed))], subsets=['floor'], min_denominator=1)
        self.assertEqual(render(card, 'json'), render(after, 'json'))

    def test_cross_plan_compare_uses_frozen_judgments_and_retains_private_pair_audit(self):
        from address_benchmark.comparison import compare_sources, public_comparison
        plans = [prepare(self.root / name) for name in ('left', 'right')]
        for plan in plans:
            freeze_plan(plan)
            with redirect_stderr(io.StringIO()): run_plan(plan)
        out = self.root / 'paired'
        result = compare_sources(plans[0], plans[1], out, baseline='incumbent', candidate='candidate')
        self.assertEqual(result['tracks'][0]['summary']['judged_pairs'], 4)
        self.assertEqual(result['tracks'][0]['summary']['left_only'], 1)
        self.assertEqual(result['tracks'][0]['summary']['right_only'], 1)
        self.assertEqual(verify(out)['status'], 'verified')
        self.assertEqual(public_comparison(result)['tracks'][0], dict(id='panel-1', status='suppressed'))
        self.assertNotIn(str(self.root), json.dumps(public_comparison(result)))
        (out / 'track-1/paired.jsonl').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'comparison artifact differs'):
            verify(out)

    def test_derived_cohort_membership_and_runtime_binding_are_in_private_audit(self):
        plan = prepare(self.root / 'derived')
        path = plan.parent / 'manifest.json'; value = read_json(path)
        value['preservation_cohorts'] = [dict(id='baseline-floor', basis=dict(kind='baseline-correct', subset='synthetic', metric='strict'))]
        self.write(path, value)
        freeze_plan(plan)
        with redirect_stderr(io.StringIO()): run_plan(plan)
        report = read_json(plan.parent / 'execution/run.json')
        cohort = report['cohorts'][0]
        self.assertEqual(cohort['row_ids'], ['synthetic-2', 'synthetic-3'])
        self.assertEqual(cohort['basis']['kind'], 'baseline-correct')
        self.assertEqual(len(cohort['basis']['baseline_pin']), 64)
        self.assertEqual(report['deltas']['incumbent/candidate']['preservation']['baseline-floor']['denominator'], 2)
        self.assertEqual(verify(plan.parent)['status'], 'verified')
        # Importing a saved membership must not create a self-referential hash:
        # the baseline binds input/reference panels, not its own pin field.
        imported = prepare(self.root / 'imported')
        manifest_path = imported.parent / 'manifest.json'
        manifest = read_json(manifest_path)
        manifest['preservation_cohorts'] = [dict(id='imported-floor', row_ids=cohort['row_ids'],
            basis=dict(kind='external', baseline_pin=cohort['basis']['baseline_pin']))]
        self.write(manifest_path, manifest)
        freeze_plan(imported)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(run_plan(imported)['status'], 'complete')
        self.assertEqual(verify(imported.parent)['status'], 'verified')

    def test_fine_token_volume_cannot_bypass_small_reference_or_role_groups(self):
        from address_benchmark.report import public_summary
        from tests.test_tables import population
        value = population(30, 25)
        metric = dict(tp=120, fp=0, fn=0, precision=1, recall=1, f1=1)
        value['tokens'] = dict(unsupported_rows=0, unannotated_rows=0,
            complete=dict(rows=30, eligible_rows=30, metrics=metric,
                per_role_rows={'road': 3, 'city': 30},
                per_role={'road': dict(metric, tp=90), 'city': dict(metric, tp=30)}),
            partial=dict(rows=0, eligible_rows=0, metrics=None, per_role={}))
        published = public_summary(value)
        self.assertEqual(published['tokens']['complete']['per_role']['road'], dict(status='suppressed'))
        self.assertEqual(published['tokens']['complete']['per_role']['city']['tp'], 30)
        value['tokens']['complete']['eligible_rows'] = 3
        self.assertEqual(public_summary(value)['tokens']['complete'], dict(status='suppressed'))

    def test_ungated_public_reports_do_not_gain_gate_notes(self):
        from tests.test_tables import recorded
        card = scorecard([('public', recorded())])
        self.assertNotIn('gate_notes', card)
        for fmt in FORMATS:
            self.assertNotIn('gate not-requested', render(card, fmt))

    def test_framework_mismatch_has_a_safe_reason_for_verify_and_compare(self):
        plan = prepare(self.root / 'PRIVATE_RETIRED_FRAMEWORK')
        freeze_plan(plan)
        with redirect_stderr(io.StringIO()):
            run_plan(plan)
        output = plan.parent / 'execution'
        self.assertEqual(verify(output)['status'], 'verified')
        report = read_json(output / 'run.json')
        # A valid envelope from a retired framework retains its own source pins.
        report['source_pins']['runner.py'] = '0' * 64
        report['content_id'] = identity({k: v for k, v in report.items() if k != 'content_id'})
        self.write(output / 'run.json', report)
        comparison = self.root / 'PRIVATE_COMPARISON'
        commands = [
            ['verify', str(output)],
            ['verify', str(output / 'run.json')],
            ['verify', str(plan.parent / 'plan-results.json')],
            ['compare', str(output), str(output), '--baseline', 'incumbent',
             '--candidate', 'candidate', '--out', str(comparison)],
        ]
        for command in commands:
            with self.subTest(command=command[0]), redirect_stderr(io.StringIO()) as err, redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(command), 1)
            self.assertEqual(err.getvalue(), 'address-benchmark: framework-differs\n')
            self.assertEqual(out.getvalue(), '')
        self.assertFalse(comparison.exists())
        # Artifact damage is still diagnosed before the framework mismatch.
        with (output / 'inputs.jsonl').open('a') as stream:
            stream.write('{}\n')
        with redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(['verify', str(output)]), 1)
        self.assertEqual(err.getvalue(), 'address-benchmark: artifact-integrity-failed\n')

    def test_errors_have_fixed_safe_reasons_including_verify_and_existing_output(self):
        private = self.root / 'PRIVATE_UNAVAILABLE_981'
        for command in (['verify', str(private)], ['report', str(private), '--publishable']):
            with redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(command), 1)
            self.assertNotIn(str(self.root), err.getvalue())
            self.assertNotIn('PRIVATE_UNAVAILABLE_981', err.getvalue())
            self.assertIn('asset-unavailable', err.getvalue())
        from tests.test_tables import recorded
        report = recorded(); report['content_id'] = identity(report)
        path = self.root / 'run.json'; self.write(path, report)
        output = self.root / 'exists.csv'; output.write_text('keep')
        with redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(['report', str(path), '--out', str(output)]), 1)
        self.assertIn('output-exists', err.getvalue())
        self.assertEqual(output.read_text(), 'keep')


if __name__ == '__main__': unittest.main()
