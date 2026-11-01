from collections import Counter
from pathlib import Path
import unittest

from address_benchmark.corpus import audit_corpora, load_corpus

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "examples/corpora/us-units-adversarial/manifest.json"


class UnitsAdversarialCorpusTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.rows, self.audit = load_corpus(CORPUS)

    def test_manifest_pins_an_authored_mit_corpus(self):
        self.assertEqual(self.manifest["license"], {**self.manifest["license"], "spdx": "MIT", "redistribution": "allowed"})
        self.assertEqual({r["origin"] for r in self.rows}, {"authored"})
        self.assertEqual(len(self.rows), 104)
        self.assertEqual(len({r["family"] for r in self.rows}), len(self.rows))

    def test_reference_values_are_literal_source_segments(self):
        for row in self.rows:
            for values in row["reference"]["fields"].values():
                for value in values:
                    self.assertIn(value, row["text"], row["id"])

    def test_every_group_is_a_subset_and_only_the_route_bare_value_case_is_partial(self):
        groups = Counter(s for r in self.rows for s in r["subsets"])
        self.assertEqual(groups["highway"], 18)
        self.assertEqual(groups["lot"], 6)
        self.assertEqual(groups["basement"], 4)
        partial = [r for r in self.rows if r["reference"]["coverage"] == "partial"]
        self.assertEqual([r["id"] for r in partial], ["units-106"])
        self.assertNotIn("unit", partial[0]["reference"]["fields"])

    def test_no_exact_overlap_with_the_other_authored_parsing_corpora(self):
        corpora = [(name, load_corpus(ROOT / f"examples/corpora/{name}/manifest.json")[1])
                   for name in ("us-units-adversarial", "us-core", "us-challenge", "us-rendered")]
        report = audit_corpora(corpora)
        self.assertEqual(report["exact_duplicates"], [])


if __name__ == "__main__":
    unittest.main()
