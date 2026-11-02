from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from address_benchmark.cli import main
from address_benchmark.io import identity
from address_benchmark.tables import export_scorecard, leaders, load_scorecard, render, scorecard, width


def population(rows=10, correct=8, complete=10, fine=True):
    return dict(rows=rows, source_families=rows, statuses={'ok': rows - 1, 'error': 1},
                supplied_fields=dict(correct=correct, denominator=rows, rate=correct / rows),
                delimiter_fields=dict(correct=correct + 1, denominator=rows, rate=(correct + 1) / rows),
                complete_address=dict(correct=min(correct, complete), denominator=complete, rate=min(correct, complete) / complete if complete else None),
                tokens={'complete': dict(rows=rows if fine else 0, metrics=dict(tp=8, fp=2, fn=4) if fine else None)})


def recorded():
    return dict(schema='address-benchmark.run/v1', task='parse', status='incomplete', corpus={'id': 'Test panel'},
                scorer='test-scorer/v1', normalization='casefold-whitespace/v1', secondary_normalization='edge/v1',
                artifacts={}, trials=[], accuracy={
                    'a': dict(status='ok', exit_code=0, populations={
                        'authored/test/all': population(), 'authored/test/subset:hard': population(2, 0),
                        'publisher/test/all': population(4, 1, complete=0),
                        'publisher/test/subset:hard': population(2, 1, complete=0)}),
                    'b': dict(status='ok', exit_code=0, populations={'authored/test/all': population(14, 0, complete=14, fine=False)}),
                    'missing': dict(status='unavailable', exit_code=69)})


class ScoreTableTests(unittest.TestCase):
    def saved_sources(self, root):
        paths=[]
        for name,views in [('deepparse-hf-us',['full','partial']),('nad-rendered',['clean','nocomma','expanded','noisy'])]:
            report=recorded();report['corpus']['id']=name
            for entry in report['accuracy'].values():
                if 'populations' in entry:
                    original=entry['populations']
                    entry['populations']={key:value for key,value in original.items() if '/subset:' not in key}
                    entry['populations'].update({key.replace('subset:hard','subset:'+view):value
                                                for key,value in original.items() if '/subset:' in key for view in views})
            report['content_id']=identity(report)
            path=root/(name+'.json');path.write_text(json.dumps(report));paths.append(path)
        return paths

    def test_multiple_sources_include_named_new_views_without_pooling(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=self.saved_sources(Path(tmp))
            card=load_scorecard(paths,subsets=['full','clean'])
            self.assertEqual([(r['panel'],r['view']) for r in card['rows']],
                             [('deepparse-hf-us','all'),('deepparse-hf-us','full'),('nad-rendered','all'),('nad-rendered','clean')])
            self.assertEqual(len(card['sources']),2)
            self.assertIn('multiple recorded',card['notes'][-1])

    def test_all_views_cli_and_duplicate_population_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=self.saved_sources(Path(tmp))
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(['report',*map(str,paths),'--all-views','--format','json']),0)
            self.assertEqual({r['view'] for r in json.loads(output.getvalue())['rows']},
                             {'all','full','partial','clean','nocomma','expanded','noisy'})
            with self.assertRaisesRegex(ValueError,'duplicate dataset'):
                load_scorecard([paths[0],paths[0]])
            with self.assertRaisesRegex(ValueError,'requested subset'):
                load_scorecard(paths,subsets=['missing-view'])

    def test_multiple_sources_cannot_mix_scoring_policies(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=self.saved_sources(Path(tmp))
            report=json.loads(paths[1].read_text());report.pop('content_id');report['normalization']='different-policy/v2';report['content_id']=identity(report)
            paths[1].write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'different scoring policies'):
                load_scorecard(paths)

    def test_weighted_disjoint_populations_and_explicit_subset(self):
        card = scorecard([('Example', recorded())], subsets=['hard'])
        a = card['rows'][0]['cells']['a']
        self.assertEqual((a['correct'], a['denominator'], a['rows']), (9, 14, 14))
        self.assertEqual(a['score'], 9 / 14)
        self.assertEqual(card['rows'][1]['cells']['a']['denominator'], 4)
        self.assertEqual(len(card['rows']), 2)  # Never sum a subset into its parent.

    def test_zero_missing_and_unsupported_stay_distinct(self):
        card = scorecard([('Example', recorded())])
        text = render(card, 'markdown')
        self.assertIn('0.00%', text)
        self.assertIn('unavailable', text)
        fine = scorecard([('Example', recorded())], metric='fine-f1')
        self.assertEqual(fine['rows'][0]['cells']['b']['status'], 'unmeasured')
        self.assertIsNone(fine['rows'][0]['cells']['b']['score'])
        self.assertIn('TP/FP/FN', render(fine, 'markdown', counts=True))

    def test_complete_denominator_ignores_partial_references(self):
        card = scorecard([('Example', recorded())], metric='complete')
        self.assertEqual(card['rows'][0]['cells']['a']['denominator'], 10)
        self.assertEqual(card['rows'][0]['cells']['a']['correct'], 8)
        self.assertEqual(leaders(card['rows'][0]), set())  # Different eligible populations.

    def test_delimiter_is_a_separate_metric_not_relabelled_strict(self):
        strict = scorecard([('Example', recorded())])
        delimiter = scorecard([('Example', recorded())], metric='delimiter')
        self.assertEqual(strict['rows'][0]['cells']['a']['correct'], 9)
        self.assertEqual(delimiter['rows'][0]['cells']['a']['correct'], 11)

    def test_console_groups_columns_with_no_controls_or_width_overflow(self):
        r = recorded()
        for i in range(7):
            r['accuracy'][f'library-{i}'] = deepcopy(r['accuracy']['a'])
        card = scorecard([('東京 benchmark\n\x1b[31m', r)])
        text = render(card, terminal_width=64, ascii=True, counts=True)
        self.assertNotIn('\x1b', text)
        self.assertIn('Columns 2/', text)
        self.assertTrue(all(width(line) <= 64 for line in text.splitlines()))
        colored = render(card, terminal_width=120, color=True)
        self.assertIn('\x1b[1;36m', colored)

    def test_html_and_markdown_escape_untrusted_labels(self):
        card = scorecard([('<script>alert(1)</script>|unsafe', recorded())], title='<img src=x onerror=alert(1)>')
        html = render(card, 'html')
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('scope="row"', html)
        self.assertIn('\\|unsafe', render(card, 'markdown'))

    def test_csv_quotes_labels_and_json_has_no_raw_runtime_or_address_data(self):
        r = recorded()
        r['host'] = {'private': '/Users/private/file'}
        r['accuracy']['a']['identity'] = {'private': 'sensitive address data'}
        card = scorecard([('Example, "quoted"', r)])
        rows = list(csv.reader(io.StringIO(render(card, 'csv'))))
        self.assertEqual(rows[1][0], 'Example, "quoted"')
        self.assertIn('9/14', rows[1][1])
        data = render(card, 'json')
        self.assertNotIn('/Users/private', data)
        self.assertNotIn('sensitive address', data)
        self.assertEqual(json.loads(data)['schema'], 'address-benchmark.scorecard/v1')

    def test_throughput_requires_all_process_trials_and_never_uses_wall_time(self):
        r = recorded()
        r['accuracy']['a']['process_wall_ns'] = 1
        card = scorecard([('Example', r)], metric='throughput')
        self.assertIsNone(card['rows'][0]['cells']['a']['score'])
        r['trials'] = [dict(engines={'a': dict(status='ok', median_ns_per_address=n, noisy_over_10_percent=True)}) for n in (100, 300)]
        with self.assertRaisesRegex(ValueError, 'whole panels'):
            scorecard([('Example', r)], metric='throughput', subsets=['hard'])
        card = scorecard([('Example', r)], metric='throughput')
        self.assertEqual(len(card['rows']), 1)
        self.assertEqual(card['rows'][0]['cells']['a']['score'], 5_000_000)
        self.assertIn('†', render(card))
        r['trials'][1]['engines']['a']['status'] = 'failed'
        card = scorecard([('Example', r)], metric='throughput')
        self.assertEqual(card['rows'][0]['cells']['a']['status'], 'incomplete')
        self.assertIsNone(card['rows'][0]['cells']['a']['score'])

    def test_utility_defaults_to_exact_profile_and_rejects_parse_only_metrics(self):
        r = recorded()
        r['task'] = 'normalize'
        for entry in r['accuracy'].values():
            for p in entry.get('populations', {}).values():
                p['agreement'] = p['supplied_fields']
        card = scorecard([('Normalize', r)])
        self.assertEqual(card['metric'], 'exact')
        with self.assertRaisesRegex(ValueError, 'parsing'):
            scorecard([('Normalize', r)], metric='fine-f1')

    def test_envelope_tampering_and_plan_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            r = recorded()
            r['content_id'] = identity(r)
            (root / 'run.json').write_text(json.dumps(r))
            self.assertEqual(len(load_scorecard(root)['rows']), 1)
            r['status'] = 'complete'
            (root / 'run.json').write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError, 'identity'):
                load_scorecard(root)
            (root / 'plan-results.json').write_text(json.dumps(dict(schema='address-benchmark.plan-results/v1', tracks=[dict(id='bad', output='../escape', content_id='bad')])))
            with self.assertRaisesRegex(ValueError, 'escapes'):
                load_scorecard(root)

    def test_cli_exports_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            r = recorded(); r['content_id'] = identity(r)
            (root / 'run.json').write_text(json.dumps(r))
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['report', str(root), '--format', 'console', '--width', '80']), 0)
            self.assertIn('Dataset / view', out.getvalue())
            self.assertNotIn('\x1b', out.getvalue())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['report', str(root), '--format', 'json', '--out', str(root/'result.json')]), 0)
            self.assertEqual(json.loads((root/'result.json').read_text())['schema'], 'address-benchmark.scorecard/v1')
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(['report', str(root), '--format', 'json', '--out', str(root/'result.json')]), 1)
            export_scorecard(load_scorecard(root), root)
            self.assertTrue(all((root / ('scores.' + suffix)).exists() for suffix in ('txt','md','csv','json','html')))
            with self.assertRaisesRegex(ValueError, 'fresh'):
                export_scorecard(load_scorecard(root), root)

    def test_missing_engine_in_second_dataset_does_not_shift_columns(self):
        a, b = recorded(), recorded()
        b['accuracy'] = {'b': b['accuracy']['b']}
        card = scorecard([('First', a), ('Second', b)], engines=['b', 'a', 'missing'])
        rows = list(csv.reader(io.StringIO(render(card, 'csv'))))
        self.assertEqual(rows[0], ['Dataset / view', 'b', 'a', 'missing'])
        self.assertIn('0.00%', rows[2][1])
        self.assertEqual(rows[2][2:], ['unmeasured', 'unmeasured'])

    def test_cli_json_plan_and_automatic_hashed_run_exports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(Path(__file__).resolve().parents[1] / 'examples/corpora/us-core', root / 'corpus')
            (root / 'engines.json').write_text(json.dumps([dict(name='demo', adapter='demo')]))
            (root / 'plan.json').write_text(json.dumps(dict(schema='address-benchmark.plan/v1', name='Console integration', engines='engines.json', tracks=[dict(id='core', corpus='corpus/manifest.json', output='results/core')])) )
            with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as progress:
                self.assertEqual(main(['run-plan', str(root / 'plan.json'), '--json']), 0)
            self.assertEqual(json.loads(out.getvalue())['status'], 'complete')
            self.assertIn('starting', progress.getvalue())
            run = json.loads((root / 'results/core/run.json').read_text())
            for suffix in ('txt', 'md', 'csv', 'json', 'html'):
                self.assertIn('scores.' + suffix, run['artifacts'])
                self.assertTrue((root / ('scores.' + suffix)).exists())


if __name__ == '__main__':
    unittest.main()
