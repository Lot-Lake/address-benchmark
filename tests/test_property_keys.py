from pathlib import Path
import unittest

from address_benchmark.corpus import check_reference, load_corpus
from address_benchmark.tasks import score_task, summarize_task

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "examples/corpora/us-identity-property/manifest.json"
META = dict(tasks=["match"])
BASIS = "authored"


def pair(a, b, *, level="property"):
    reference = dict(coverage="complete", same_entity=a == b, entity_level=level, label_basis=BASIS)
    if level == "property":
        reference["entities"] = [a, b]
    return dict(id=f"{a}|{b}", family="f", split="s", origin="authored", subsets=[], reference=reference)


def keyed(left, right, status="ok"):
    return dict(status=status, keys=[left, right] if status == "ok" else [])


class PropertyKeyReportTests(unittest.TestCase):
    def test_property_pairs_need_entities_that_agree_with_the_label(self):
        check_reference(pair("p1", "p1")["reference"], "x", task="match")
        bad = pair("p1", "p2")["reference"]
        bad["same_entity"] = True
        with self.assertRaisesRegex(ValueError, "contradict"):
            check_reference(bad, "x", task="match")
        missing = pair("p1", "p1")["reference"]
        del missing["entities"]
        with self.assertRaisesRegex(ValueError, "name both entities"):
            check_reference(missing, "x", task="match")
        with self.assertRaisesRegex(ValueError, "identity level"):
            check_reference(dict(pair("p1", "p1")["reference"], entity_level="parcel"), "x", task="match")

    def test_keys_per_property_and_false_merges(self):
        cases = [score_task(pair("p1", "p1"), keyed("K1", "K1"), META),
                 score_task(pair("p1", "p1"), keyed("K1", "K1B"), META),      # p1 fragments into two keys
                 score_task(pair("p1", "p2"), keyed("K1", "K1"), META),       # distinct pair merged
                 score_task(pair("p3", "p4"), keyed("K3", "K4"), META),
                 score_task(pair("p4", "p5"), keyed("K4X", "K1B"), META),     # p5 collides with p1 across pairs
                 score_task(pair("p6", "p6"), keyed(None, None, "error"), META)]
        report = summarize_task(cases)["property_keys"]
        self.assertEqual(report["properties"], 5)
        self.assertEqual(report["keys_per_property"], {1: 3, 2: 2})
        self.assertEqual(report["fragmented_properties"], 2)
        self.assertEqual((report["same_property_pairs"], report["distinct_property_pairs"]), (3, 3))
        self.assertEqual(report["false_merge_pairs"], 1)
        self.assertEqual(report["colliding_keys"], 2)
        self.assertEqual(report["properties_in_collisions"], 3)
        self.assertEqual(report["missing_key_sides"], 2)
        self.assertIn("property level", summarize_task(cases)["scope"])

    def test_delivery_unit_results_are_unchanged(self):
        case = score_task(pair("a", "a", level="delivery-unit"), keyed("K", "K"), META)
        self.assertNotIn("keys", case)
        summary = summarize_task([case])
        self.assertNotIn("property_keys", summary)
        self.assertIn("delivery-unit level", summary["scope"])

    def test_authored_property_corpus_loads(self):
        manifest, rows, _ = load_corpus(CORPUS)
        self.assertEqual(manifest["profile"], "address-benchmark.property-key-equality/v1")
        self.assertEqual({r["reference"]["entity_level"] for r in rows}, {"property"})
        self.assertEqual(sum(r["reference"]["same_entity"] for r in rows), 4)


if __name__ == "__main__":
    unittest.main()
