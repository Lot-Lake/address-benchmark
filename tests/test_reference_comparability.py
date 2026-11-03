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
        self.assertNotIn('comparable', clean_cell)
        for fmt in FORMATS:
            text = render(card, fmt, counts=True)
            self.assertIn('non-comparable' if fmt != 'json' else '"comparable": false', text, fmt)
        self.assertIn('non-comparable', (self.root / 'run/report.md').read_text())
        self.assertEqual(verify(self.root / 'run')['status'], 'verified')

    def test_delimiter_view_and_other_profiles_are_not_reinterpreted(self):
        result = self.execute()
        cell = scorecard([('example', result)], metric='delimiter')['rows'][0]['cells']['clean-components']
        self.assertEqual((cell['correct'], cell['denominator']), (2, 2))
        self.assertNotIn('comparable', cell)
        fine = scorecard([('example', result)], metric='fine-f1')['rows'][0]['cells']['clean-components']
        self.assertNotIn('comparable', fine)
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
        self.assertNotIn('comparable', complete)
        self.assertFalse(scorecard([('example', result)])['rows'][0]['cells']['clean-components']['comparable'])

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
