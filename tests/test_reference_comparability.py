from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from address_benchmark.corpus import load_corpus, reference_comparability
from address_benchmark.io import identity, read_json, read_jsonl, sha256, write_json, write_jsonl
from address_benchmark.runner import run, verify
from address_benchmark.tables import FORMATS, leaders, load_scorecard, render, scorecard

ROOT = Path(__file__).resolve().parents[1]


class ReferenceComparabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        manifest = read_json(ROOT / 'examples/corpora/us-core/manifest.json')
        manifest.update(id='fictional-publisher', ontology='address-benchmark.us-roles/v2')
        tokens = [('14', 'AddressNumber'), ('Maple', 'StreetName'), ('St,', 'StreetNamePostType'),
                  ('Example,', 'PlaceName'), ('NY', 'StateName'), ('00000', 'ZipCode')]
        raw = [dict(id='synthetic-a', input='14 Maple St, Example, NY 00000', tokens=tokens,
                    stratum='hand', source='synthetic', style='fictional', mods=[], tags=[]),
               dict(id='synthetic-b', input='15 Maple St, Example, NY 00000',
                    tokens=[('15', 'AddressNumber'), *[(v.rstrip(','), r) for v, r in tokens[1:]]],
                    stratum='clean', source='synthetic', style='fictional', mods=[], tags=[])]
        write_jsonl(self.root / 'publisher.jsonl', raw)
        manifest['resources'] = [dict(path='publisher.jsonl', sha256=sha256(self.root / 'publisher.jsonl'), format='doorplate-compare')]
        write_json(self.root / 'manifest.json', manifest)
        write_json(self.root / 'engines.json', [dict(name='clean-components', adapter='tests.support:DemoV2')])

    def execute(self):
        result = run(self.root / 'manifest.json', self.root / 'engines.json', self.root / 'run')
        self.assertEqual(result['status'], 'complete')
        return result

    def test_publisher_reference_values_and_utf8_spans_are_preserved(self):
        _, rows, _ = load_corpus(self.root / 'manifest.json')
        self.assertEqual(rows[0]['reference']['fields']['road'], ['Maple St,'])
        self.assertEqual(rows[0]['reference']['fields']['city'], ['Example,'])
        data = rows[0]['text'].encode()
        self.assertIn('St,', [data[x['span'][0]:x['span'][1]].decode() for x in rows[0]['reference']['tokens']])
        before = deepcopy(rows)
        policy = reference_comparability(rows)
        self.assertEqual(rows, before)
        self.assertEqual(policy['populations']['publisher-fixture/publisher-evaluation/all']['rows'], 1)

    def test_strict_counts_stay_exact_but_affected_views_are_not_comparable(self):
        result = self.execute()
        card = scorecard([('arbitrary-alias', result)], subsets=['hand', 'clean'])
        all_cell, hand_cell, clean_cell = [r['cells']['clean-components'] for r in card['rows']]
        self.assertEqual((all_cell['correct'], all_cell['denominator']), (1, 2))
        self.assertEqual((hand_cell['correct'], hand_cell['denominator']), (0, 1))
        self.assertFalse(all_cell['comparable'])
        self.assertEqual(all_cell['reference_edge_rows'], 1)
        self.assertEqual(all_cell['recommended_metric'], 'delimiter')
        self.assertEqual(all_cell['noncomparable_reasons'], ['reference-edge-delimiters'])
        self.assertTrue(clean_cell.get('comparable', True))
        for fmt in FORMATS:
            text = render(card, fmt, counts=True)
            self.assertIn('non-comparable' if fmt != 'json' else '"comparable": false', text, fmt)
        self.assertIn('non-comparable', (self.root / 'run/report.md').read_text())
        self.assertEqual(verify(self.root / 'run')['status'], 'verified')

    def test_delimiter_view_and_other_profiles_are_not_reinterpreted(self):
        result = self.execute()
        cell = scorecard([('example', result)], metric='delimiter')['rows'][0]['cells']['clean-components']
        self.assertEqual((cell['correct'], cell['denominator']), (2, 2))
        self.assertTrue(cell.get('comparable', True))
        fine = scorecard([('example', result)], metric='fine-f1')['rows'][0]['cells']['clean-components']
        self.assertTrue(fine.get('comparable', True))
        complete = scorecard([('example', result)], metric='complete')['rows'][0]['cells']['clean-components']
        self.assertFalse(complete['comparable'])

    def test_no_highlight_for_affected_reference_even_with_matching_denominators(self):
        result = self.execute()
        result['accuracy']['other'] = deepcopy(result['accuracy']['clean-components'])
        self.assertEqual(leaders(scorecard([('example', result)])['rows'][0]), set())
        self.assertEqual(leaders(scorecard([('example', result)], metric='delimiter')['rows'][0]), {'clean-components', 'other'})

    def test_historical_envelope_is_only_audited_after_its_references_are_hashed(self):
        result = self.execute()
        result.pop('reference_comparability')
        result['content_id'] = identity({k: v for k, v in result.items() if k != 'content_id'})
        run_path = self.root / 'run/run.json'
        run_path.write_text(json.dumps(result))
        before = run_path.read_bytes()
        card = load_scorecard(self.root / 'run')
        self.assertFalse(card['rows'][0]['cells']['clean-components']['comparable'])
        self.assertEqual(run_path.read_bytes(), before)
        with (self.root / 'run/references.jsonl').open('a') as stream:
            stream.write('{}\n')
        with self.assertRaisesRegex(ValueError, 'reference audit artifact changed'):
            load_scorecard(self.root / 'run')

    def test_missing_historical_reference_audit_does_not_establish_comparability(self):
        result = self.execute()
        result.pop('reference_comparability')
        result['artifacts'].pop('references.jsonl')
        result['content_id'] = identity({k: v for k, v in result.items() if k != 'content_id'})
        (self.root / 'run/run.json').write_text(json.dumps(result))
        card = load_scorecard(self.root / 'run')
        cell = card['rows'][0]['cells']['clean-components']
        self.assertFalse(cell['comparable'])
        self.assertIsNone(cell['reference_edge_rows'])

    def test_affected_partial_rows_do_not_taint_complete_address_denominator(self):
        _, rows, _ = load_corpus(self.root / 'manifest.json')
        rows[0]['reference']['coverage'] = 'partial'
        result = self.execute()
        result['reference_comparability'] = reference_comparability(rows)
        complete = scorecard([('example', result)], metric='complete')['rows'][0]['cells']['clean-components']
        self.assertTrue(complete.get('comparable', True))
        self.assertFalse(scorecard([('example', result)])['rows'][0]['cells']['clean-components']['comparable'])
        summary = scorecard([('example', result)], publishable=True, min_denominator=1)['aggregates'][0]['engines']['engine-1']['sources'][0]
        self.assertFalse(summary['supplied_fields']['comparable'])
        self.assertNotIn('comparable', summary['complete_address'])

    def test_private_aggregate_exports_keep_comparability_warning_without_identifiers(self):
        manifest_path = self.root / 'manifest.json'
        value = read_json(manifest_path)
        value['license']['redistribution'] = 'local-only'
        value['id'] = 'PRIVATE_PUBLISHER_514'
        manifest_path.write_text(json.dumps(value))
        self.execute()
        for fmt in FORMATS:
            text = render(load_scorecard(self.root / 'run', publishable=True), fmt, counts=True)
            self.assertNotIn('PRIVATE_PUBLISHER_514', text)
            self.assertNotIn(str(self.root), text)
            self.assertIn('non-comparable' if fmt != 'json' else '"comparable": false', text)
            self.assertIn('--metric delimiter', text)
            self.assertNotIn('reference_edge_rows', text)
        card = load_scorecard(self.root / 'run', publishable=True, min_denominator=1)
        summary = card['aggregates'][0]['engines']['engine-1']['sources'][0]
        for metric in ('supplied_fields', 'complete_address'):
            self.assertFalse(summary[metric]['comparable'])
            self.assertEqual(summary[metric]['recommended_metric'], 'delimiter')
        cell = card['rows'][0]['cells']['engine-1']
        self.assertEqual(cell['recommended_metric'], 'delimiter')
        self.assertEqual(cell['noncomparable_reasons'], ['reference-edge-delimiters'])

    def test_per_source_public_rates_flag_one_affected_row_without_flagging_clean_source(self):
        from address_benchmark.protocol import FINE_TO_COARSE
        manifest_path = self.root / 'manifest.json'
        manifest = read_json(manifest_path)
        manifest.update(scorer='address-benchmark.scorer/v2', resources=[])
        manifest['license']['redistribution'] = 'local-only'
        scope = {kind: dict(coverage='complete', absence=True,
                           roles=sorted(set(FINE_TO_COARSE.values()) if kind == 'fields' else FINE_TO_COARSE))
                 for kind in ('fields', 'tokens', 'spans')}
        original = list(read_jsonl(self.root / 'publisher.jsonl'))
        for source in ('PRIVATE_AFFECTED', 'PRIVATE_CLEAN'):
            rows = []
            for index in range(20):
                row = deepcopy(original[0 if source == 'PRIVATE_AFFECTED' and index == 0 else 1])
                row['id'] = source + str(index)
                rows.append(row)
            data = self.root / (source + '.jsonl')
            write_jsonl(data, rows)
            manifest['resources'].append(dict(path=data.name, sha256=sha256(data), format='doorplate-compare',
                                              source=source, annotation_scope=scope))
        manifest_path.write_text(json.dumps(manifest))
        result = self.execute()
        self.assertEqual(result['reference_comparability']['sources'], {'PRIVATE_AFFECTED': dict(rows=1, complete_rows=1)})
        card = load_scorecard(self.root / 'run', publishable=True)
        sources = card['aggregates'][0]['engines']['engine-1']['sources']
        self.assertEqual([s['id'] for s in sources], ['panel-1/source-1', 'panel-1/source-2'])
        for metric in ('supplied_fields', 'complete_address'):
            self.assertEqual(sources[0][metric]['denominator'], 20)
            self.assertFalse(sources[0][metric]['comparable'])
            self.assertEqual(sources[0][metric]['noncomparable_reasons'], ['reference-edge-delimiters'])
            self.assertEqual(sources[0][metric]['recommended_metric'], 'delimiter')
            self.assertEqual(sources[1][metric]['rate'], 1)
            self.assertNotIn('comparable', sources[1][metric])
        self.assertNotIn('comparable', sources[0]['delimiter_fields'])
        text = render(card, 'json')
        for private in ('PRIVATE_AFFECTED', 'PRIVATE_CLEAN', 'reference_edge_rows', str(self.root)):
            self.assertNotIn(private, text)
        self.assertEqual(verify(self.root / 'run')['status'], 'verified')

        # Legacy panel-only audits are conservatively flagged until the source
        # dimension is reconstructed from the hash-verified references.
        result['reference_comparability'].pop('sources')
        conservative = scorecard([('private', result)], publishable=True)
        self.assertTrue(all(s['supplied_fields']['comparable'] is False
                            for s in conservative['aggregates'][0]['engines']['engine-1']['sources']))
        result['content_id'] = identity({k: v for k, v in result.items() if k != 'content_id'})
        path = self.root / 'run/run.json'
        path.write_text(json.dumps(result)); before = path.read_bytes()
        rebuilt = load_scorecard(self.root / 'run', publishable=True)
        self.assertEqual(rebuilt['aggregates'][0]['engines']['engine-1']['sources'], sources)
        self.assertEqual(path.read_bytes(), before)

    def test_eligibility_mismatch_has_its_own_reason_and_no_delimiter_remedy(self):
        from tests.test_tables import recorded
        report = recorded()
        report['accuracy'] = {'a': report['accuracy']['a'], 'b': deepcopy(report['accuracy']['a'])}
        for name, entry in report['accuracy'].items():
            for population in entry['populations'].values():
                population['eligibility'] = dict(supplied_fields=name, complete_address=name)
        for published in (False, True):
            card = scorecard([('Example', report)], publishable=published, min_denominator=1)
            self.assertEqual(leaders(card['rows'][0]), set())
            for cell in card['rows'][0]['cells'].values():
                self.assertFalse(cell['comparable'])
                self.assertEqual(cell['noncomparable_reasons'], ['eligibility-mismatch'])
                self.assertNotIn('recommended_metric', cell)
            for fmt in FORMATS:
                text = render(card, fmt)
                self.assertNotIn('--metric delimiter', text, fmt)
                self.assertNotIn('[non-comparable]', text, fmt)

    def test_reference_and_eligibility_reasons_both_survive_public_projection(self):
        result = self.execute()
        result['accuracy']['other'] = deepcopy(result['accuracy']['clean-components'])
        for name, entry in result['accuracy'].items():
            for population in entry['populations'].values():
                population['eligibility'] = dict(supplied_fields=name)
        card = scorecard([('example', result)], publishable=True, min_denominator=1)
        self.assertEqual(card['rows'][0]['cells']['engine-1']['noncomparable_reasons'],
                         ['eligibility-mismatch', 'reference-edge-delimiters'])

    def test_gate_notes_are_not_duplicated_and_unrelated_markdown_stays_plain(self):
        from tests.test_tables import recorded
        report = recorded(); report['gate'] = dict(status='passed')
        card = scorecard([('Example', report)])
        payload = json.loads(render(card, 'json'))
        self.assertEqual(payload['gate_notes'], ['Example: gate passed'])
        self.assertNotIn('Example: gate passed', payload['notes'])
        markdown = render(card, 'markdown')
        self.assertIn('\nExample: gate passed\n\n- Counts', markdown)
        self.assertNotIn('- Example: gate passed', markdown)
        csv = render(card, 'csv')
        self.assertEqual(csv.count('Example: gate passed'), 1)
        self.assertNotIn('--metric delimiter', csv)

    def test_inner_punctuation_periods_and_unlabeled_rows_are_not_flagged(self):
        _, rows, _ = load_corpus(self.root / 'manifest.json')
        row = rows[0]
        row['reference']['fields'] = {'road': ['St. Mary, North Rd.']}
        self.assertEqual(reference_comparability([row])['populations'], {})
        row['reference']['coverage'] = 'none'
        row['reference']['fields'] = {'road': ['ignore,']}
        self.assertEqual(reference_comparability([row])['populations'], {})


if __name__ == '__main__':
    unittest.main()
