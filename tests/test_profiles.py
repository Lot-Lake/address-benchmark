import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from address_benchmark.corpus import check_manifest
from address_benchmark.io import read_json, write_json
from address_benchmark.ontologies import ONTOLOGY_V2, US_FINE
from address_benchmark.profiles import STREETLINE, canon, score_profile, summarize_profile
from address_benchmark.runner import run, verify
from address_benchmark.scoring import score_case, summarize
from address_benchmark.tables import scorecard

ROOT = Path(__file__).resolve().parents[1]
ROLE_MAP = {**US_FINE, "road": "road", "unit": "unit", "po_box": "po_box", "level": "level"}
META = dict(tasks=["parse"], role_map=ROLE_MAP, supported_roles=sorted({v for v in ROLE_MAP.values() if v}),
            span_support=False, token_support=False)


def row(text, fields, coverage="complete", spans=None):
    reference = dict(coverage=coverage, fields=fields, spans=spans or [], tokens=spans or [],
                     spans_coverage="complete" if spans else "none", tokens_coverage="complete" if spans else "none")
    return dict(id="r1", text=text, family="f", split="s", origin="authored", subsets=["all"], reference=reference)


def pred(*items, inferred=(), status="ok"):
    return dict(status=status, evidence=[dict(native_role=r, value=v, spans=None) for r, v in items],
                tokens=[], inferred=list(inferred), normalized=[], native=None)


def agrees(r, p):
    return score_profile(STREETLINE, r, p, META)


class StreetLineProfileTests(unittest.TestCase):
    def test_street_line_is_one_canonical_string_whatever_the_split(self):
        r = row("12 N Main St Exampleville NY 00123", dict(house_number=["12"], road=["N Main St"], city=["Exampleville"], state=["NY"], postcode=["00123"]))
        split = pred(("AddressNumber", "12"), ("StreetNamePreDirectional", "NORTH"), ("StreetName", "Main"), ("StreetNamePostType", "STREET"),
                     ("PlaceName", "Exampleville"), ("StateName", "NY"), ("ZipCode", "00123"))
        unsplit = pred(("AddressNumber", "12"), ("road", "N Main St"), ("PlaceName", "Exampleville"), ("StateName", "NY"), ("ZipCode", "00123"))
        missing_dir = pred(("AddressNumber", "12"), ("StreetName", "Main"), ("StreetNamePostType", "St"),
                           ("PlaceName", "Exampleville"), ("StateName", "NY"), ("ZipCode", "00123"))
        self.assertTrue(agrees(r, split)["agrees"])
        self.assertTrue(agrees(r, unsplit)["agrees"])
        self.assertEqual(agrees(r, missing_dir)["mismatched_fields"], ["streetline"])

    def test_street_line_order_is_predir_street_suffix_postdir(self):
        # The line is assembled by street-line part, not by token order, as the original kit does.
        r = row("5 Oak Ave E", dict(house_number=["5"], road=["Oak Ave E"]))
        p = pred(("AddressNumber", "5"), ("StreetNamePostDirectional", "E"), ("StreetName", "Oak"), ("StreetNamePostType", "Avenue"))
        self.assertTrue(agrees(r, p)["agrees"])

    def test_complete_reference_scores_every_field_and_absent_must_be_absent(self):
        r = row("12 Main St", dict(house_number=["12"], road=["Main St"]))
        invented = pred(("AddressNumber", "12"), ("StreetName", "Main"), ("StreetNamePostType", "St"), ("OccupancyIdentifier", "4"))
        result = agrees(r, invented)
        self.assertFalse(result["agrees"])
        self.assertEqual(result["mismatched_fields"], ["unit"])
        self.assertEqual(result["scored_fields"], ["number", "streetline", "unit", "city", "state", "zip"])

    def test_partial_reference_scores_only_supplied_fields(self):
        r = row("12 Main St Apt 4 Exampleville", dict(house_number=["12"], road=["Main St"], unit=[]), coverage="partial")
        extra_city = pred(("AddressNumber", "12"), ("StreetName", "Main"), ("StreetNamePostType", "St"), ("PlaceName", "Exampleville"))
        result = agrees(r, extra_city)
        self.assertTrue(result["agrees"])
        self.assertEqual(result["scored_fields"], ["number", "streetline", "unit"])
        with_unit = pred(("AddressNumber", "12"), ("StreetName", "Main"), ("StreetNamePostType", "St"), ("OccupancyType", "Apt"), ("OccupancyIdentifier", "4"))
        self.assertEqual(agrees(r, with_unit)["mismatched_fields"], ["unit"], "an empty supplied list asserts absence")

    def test_inferred_state_is_never_evidence_and_is_reported_separately(self):
        r = row("12 Main St 00123", dict(house_number=["12"], road=["Main St"], postcode=["00123"]))
        p = pred(("AddressNumber", "12"), ("StreetName", "Main"), ("StreetNamePostType", "St"), ("ZipCode", "00123"),
                 inferred=[dict(role="state", value="NY", basis="zip")])
        result = agrees(r, p)
        self.assertTrue(result["agrees"])
        self.assertEqual(result["inferred_roles"], ["state"])
        summary = summarize_profile([result, agrees(r, pred(("AddressNumber", "13")))])
        self.assertEqual((summary["correct"], summary["denominator"], summary["inferred_state_rows"]), (1, 2, 1))

    def test_failed_rows_fail_and_unlabeled_rows_are_not_scored(self):
        r = row("12 Main St", dict(house_number=["12"], road=["Main St"]))
        self.assertFalse(agrees(r, pred(status="error"))["agrees"])
        unlabeled = row("12 Main St", {}, coverage="none")
        self.assertIsNone(agrees(unlabeled, pred())["agrees"])

    def test_reference_spans_give_the_original_token_order(self):
        text = "PO Box 9 Apt 2"
        spans = [dict(role="us:USPSBoxType", span=[0, 6]), dict(role="us:USPSBoxID", span=[7, 8]),
                 dict(role="us:OccupancyType", span=[9, 12]), dict(role="us:OccupancyIdentifier", span=[13, 14])]
        r = row(text, dict(po_box=["PO Box 9"], unit=["Apt 2"]), spans=spans)
        p = pred(("USPSBoxType", "PO Box"), ("USPSBoxID", "9"), ("OccupancyType", "APARTMENT"), ("OccupancyIdentifier", "2"))
        self.assertTrue(agrees(r, p)["agrees"])
        swapped = pred(("OccupancyType", "Apt"), ("OccupancyIdentifier", "2"), ("USPSBoxType", "PO Box"), ("USPSBoxID", "9"))
        self.assertEqual(agrees(r, swapped)["mismatched_fields"], ["unit"])


class CanonTests(unittest.TestCase):
    def test_pub28_folds(self):
        self.assertEqual(canon("streetline", "North Main Street"), canon("streetline", "N MAIN ST"))
        # CR then folds token-wise like every other token (to CIR, an observed CIRCLE spelling), on both sides alike.
        self.assertEqual(canon("streetline", "County Road 12"), canon("streetline", "CO RD 12"))
        self.assertEqual(canon("streetline", "US Highway 1"), "US 1")
        self.assertEqual(canon("streetline", "Saint Marks Pl"), "ST MARKS PL")
        self.assertEqual(canon("unit", "Apartment #4B"), "APT 4B")
        self.assertEqual(canon("unit", "P.O. Box 9"), "PO BOX 9")
        self.assertEqual(canon("unit", "Rural Route 2"), "RR 2")
        self.assertEqual(canon("city", "Saint Louis"), "ST LOUIS")
        self.assertEqual(canon("city", "North Las Vegas"), "N LAS VEGAS")
        self.assertEqual(canon("state", "New York"), "NY")
        self.assertEqual(canon("zip", "02134-1234"), "02134")
        self.assertEqual(canon("zip", "2134"), "02134")
        self.assertEqual(canon("number", "M.L. 12"), "ML 12")
        self.assertEqual(canon("city", "Coeur d'Alene"), "COEUR DALENE")

    def test_spacing_inside_a_field_is_ignored(self):
        r = row("W615 Main St Apt 4 B", dict(house_number=["W 615"], road=["Main St"], unit=["Apt 4 B"]))
        p = pred(("AddressNumber", "W615"), ("StreetName", "Main"), ("StreetNamePostType", "St"), ("OccupancyType", "Apt"), ("OccupancyIdentifier", "4B"))
        self.assertTrue(agrees(r, p)["agrees"])


class ProfileWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self, **extra):
        manifest = read_json(ROOT / "examples/corpora/us-core/manifest.json")
        manifest["resources"][0]["path"] = str((ROOT / "examples/corpora/us-core/cases.jsonl").resolve())
        manifest["resources"][0] = dict(external_path=manifest["resources"][0].pop("path"), **manifest["resources"][0])
        manifest["license"]["redistribution"] = "local-only"
        manifest.update(extra)
        return manifest

    def test_manifest_profile_names_are_checked(self):
        check_manifest(self.manifest(scoring_profiles=[STREETLINE]))
        with self.assertRaisesRegex(ValueError, "scoring profile"):
            check_manifest(self.manifest(scoring_profiles=["strict-streetline/v0"]))
        with self.assertRaisesRegex(ValueError, "scoring profile"):
            check_manifest(self.manifest(scoring_profiles=[STREETLINE, STREETLINE]))

    def test_cases_without_a_profile_are_unchanged(self):
        r = row("12 Main St", dict(house_number=["12"], road=["Main St"]))
        p = pred(("AddressNumber", "12"), ("StreetName", "Main"), ("StreetNamePostType", "St"))
        self.assertNotIn("profiles", score_case(r, p, META))
        self.assertNotIn("profiles", summarize([score_case(r, p, META)]))
        case = score_case(r, p, META, profiles=[STREETLINE])
        self.assertTrue(case["profiles"][STREETLINE]["agrees"])
        self.assertEqual(summarize([case])["profiles"][STREETLINE]["correct"], 1)

    def run_corpus(self, manifest):
        path = self.root / "corpus.json"
        write_json(path, manifest)
        engines = self.root / "engines.json"
        write_json(engines, [{"name": "demo", "adapter": "demo"}])
        output = self.root / "run"
        return run(path, engines, output, timeout=30), output

    def test_run_scores_declared_profile_verifies_and_reports(self):
        result, output = self.run_corpus(self.manifest(scoring_profiles=[STREETLINE]))
        population = result["accuracy"]["demo"]["populations"]["authored/conformance/all"]
        self.assertEqual(population["profiles"][STREETLINE]["denominator"], population["supplied_fields"]["denominator"])
        self.assertEqual(verify(output)["status"], "verified")
        card = scorecard([("core", result)], metric="streetline")
        cell = card["rows"][0]["cells"]["demo"]
        self.assertEqual((cell["status"], cell["correct"]), ("measured", population["profiles"][STREETLINE]["correct"]))

    def test_streetline_metric_is_unmeasured_without_the_profile(self):
        result, _ = self.run_corpus(self.manifest())
        self.assertNotIn("profiles", result["accuracy"]["demo"]["populations"]["authored/conformance/all"])
        cell = scorecard([("core", result)], metric="streetline")["rows"][0]["cells"]["demo"]
        self.assertEqual(cell["status"], "unmeasured")


if __name__ == "__main__":
    unittest.main()
