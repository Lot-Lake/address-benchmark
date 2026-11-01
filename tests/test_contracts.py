from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from address_benchmark.adapters import DemoKeys, DemoNormalizer, DemoParser, DemoUtility, PythonCallable, RefusalParser
from address_benchmark.corpus import audit_corpora, check_reference, fetch, input_requests, load_corpus
from address_benchmark.io import canonical, loads, read_json, require, within
from address_benchmark.protocol import Request, check_prediction, check_spans, prediction, request_hash
from address_benchmark.scoring import normalize, project, score_case, summarize, summarize_views

ROOT = Path(__file__).resolve().parents[1]


def corpus(name="us-core"):
    manifest, rows, _ = load_corpus(ROOT / "examples" / "corpora" / name / "manifest.json")
    return manifest, rows, input_requests(manifest, rows)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.rows, self.requests = corpus()
        self.adapter = DemoParser({})
        self.request = self.requests[0]

    def test_input_request_cannot_contain_reference(self):
        data = self.request.to_dict()
        data["reference"] = {"fields": {"postcode": ["00123"]}}
        with self.assertRaisesRegex(ValueError, "keys differ"):
            Request.from_dict(data)

    def test_requests_roundtrip_without_annotation_metadata(self):
        data = self.request.to_dict()
        self.assertEqual(Request.from_dict(data), self.request)
        self.assertFalse({"reference", "family", "split", "subsets"} & set(data))

    def test_hash_mismatch_rejected(self):
        data = self.request.to_dict()
        data["text"] += "x"
        with self.assertRaisesRegex(ValueError, "hash differs"):
            Request.from_dict(data)

    def test_matching_hash_covers_second_input(self):
        self.assertNotEqual(request_hash("A", "B"), request_hash("A", "C"))
        self.assertNotEqual(request_hash("A", "B"), request_hash("B", "A"))

    def test_structured_hash_covers_literal_width_and_order(self):
        a = {"fields": [{"role": "unit", "value": "03"}, {"role": "postcode", "value": "00123"}]}
        b = {"fields": list(reversed(a["fields"]))}
        self.assertNotEqual(request_hash("", payload=a), request_hash("", payload=b))

    def test_utf8_spans_are_bytes(self):
        check_spans([[0, 2]], "éx")
        with self.assertRaises(UnicodeDecodeError):
            check_spans([[0, 1]], "éx")

    def test_invalid_repeated_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlapping"):
            check_spans([[1, 4], [3, 5]], "abcdef")

    def test_discontinuous_spans_preserved(self):
        check_spans([[0, 1], [4, 5]], "a b c")

    def test_wrong_output_identity_rejected(self):
        result = self.adapter.parse(self.request)
        result["input_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "identity"):
            check_prediction(result, self.request, self.adapter.metadata)

    def test_unknown_native_roles_not_silently_dropped(self):
        result = self.adapter.parse(self.request)
        result["evidence"][0]["native_role"] = "NEW_NATIVE_ROLE"
        with self.assertRaisesRegex(ValueError, "undeclared"):
            check_prediction(result, self.request, self.adapter.metadata)

    def test_explicit_unmapped_role_is_auditable(self):
        self.assertEqual(project([{"native_role": "query", "value": "near"}], {"query": None}), {"unsupported:query": ["near"]})

    def test_refusal_cannot_commit_evidence(self):
        result = self.adapter.parse(self.request)
        result.update(status="refused", message="no")
        with self.assertRaisesRegex(ValueError, "failed rows"):
            check_prediction(result, self.request, self.adapter.metadata)

    def test_native_values_may_differ_from_source_but_are_retained(self):
        result = self.adapter.parse(self.request)
        result["evidence"][1]["value"] = "ALDER"
        check_prediction(result, self.request, self.adapter.metadata)
        self.assertEqual(result["evidence"][1]["value"], "ALDER")


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.rows, self.requests = corpus()
        self.adapter = DemoParser({})

    def test_zip_width_and_punctuation_preserved(self):
        self.assertNotEqual(normalize("00123"), normalize("0123"))
        self.assertNotEqual(normalize("St."), normalize("St"))
        self.assertNotEqual(normalize("Café"), normalize("Cafe"))
        self.assertEqual(normalize(" Main  ST "), "main st")

    def test_nonadjacent_occurrences_remain_ordered(self):
        parts = [dict(native_role=r, value=v) for r, v in [("unit_type", "Apt"), ("unit_id", "2"), ("road_name", "Alder"), ("unit_type", "Apt"), ("unit_id", "7")]]
        self.assertEqual(project(parts, self.adapter.metadata["role_map"] | {"unit_type": "unit_type", "unit_id": "unit_id"}), {"unit": ["Apt 2", "Apt 7"], "road": ["Alder"]})

    def test_complete_reference_scores_extra_roles(self):
        row, request = self.rows[0], self.requests[0]
        pred = self.adapter.parse(request)
        metadata = deepcopy(self.adapter.metadata)
        metadata["role_map"]["country"] = "country"
        metadata["supported_roles"].append("country")
        pred["evidence"].append(dict(native_role="country", value="US", spans=None))
        result = score_case(row, pred, metadata)
        self.assertFalse(result["complete_address_agrees"])
        self.assertIn("country", result["mismatched_roles"])

    def test_partial_reference_does_not_judge_extra_roles(self):
        row = deepcopy(self.rows[0])
        row["reference"].update(coverage="partial", fields={"postcode": ["00123"]}, spans_coverage="partial", tokens_coverage="partial")
        result = score_case(row, self.adapter.parse(self.requests[0]), self.adapter.metadata)
        self.assertTrue(result["supplied_fields_agree"])
        self.assertIsNone(result["complete_address_agrees"])
        self.assertIn("road", result["unadjudicated_roles"])
        self.assertIsNone(result["spans"]["metrics"]["precision"])
        self.assertIsNone(result["spans"]["metrics"]["f1"])

    def test_coarse_success_does_not_imply_fine_success(self):
        # St. at the start of St. Elmo is a road-name token in gold.
        result = score_case(self.rows[4], self.adapter.parse(self.requests[4]), self.adapter.metadata)
        self.assertTrue(result["complete_address_agrees"])
        self.assertLess(result["tokens"]["metrics"]["f1"], 1)

    def test_absent_span_capability_is_unmeasured(self):
        metadata = deepcopy(self.adapter.metadata)
        metadata.update(span_support=False, token_support=False)
        result = score_case(self.rows[0], self.adapter.parse(self.requests[0]), metadata)
        self.assertEqual(result["spans"]["status"], "unsupported")
        self.assertIsNone(result["spans"]["metrics"])

    def test_duplicate_predictions_count_as_false_positives(self):
        pred = self.adapter.parse(self.requests[0])
        pred["tokens"].append(deepcopy(pred["tokens"][0]))
        result = score_case(self.rows[0], pred, self.adapter.metadata)
        self.assertEqual(result["tokens"]["metrics"]["fp"], 1)

    def test_errors_and_refusals_keep_denominator(self):
        control = RefusalParser({})
        cases = [score_case(row, control.parse(req), control.metadata) for row, req in zip(self.rows, self.requests)]
        result = summarize(cases)
        self.assertEqual(result["complete_address"], dict(correct=0, denominator=len(self.rows), rate=0))
        self.assertEqual(result["statuses"]["refused"], len(self.rows))

    def test_unlabeled_rows_have_no_accuracy(self):
        row = deepcopy(self.rows[0])
        row["reference"] = dict(coverage="none", fields={}, spans=[], tokens=[], spans_coverage="none", tokens_coverage="none")
        result = score_case(row, self.adapter.parse(self.requests[0]), self.adapter.metadata)
        self.assertIsNone(result["primary_agrees"])
        self.assertIsNone(summarize([result])["supplied_fields"]["rate"])

    def test_generated_views_are_not_independent_families(self):
        manifest, rows, requests = corpus("us-rendered")
        cases = [score_case(row, self.adapter.parse(req), self.adapter.metadata) for row, req in zip(rows, requests)]
        summary = summarize_views(cases)["source-field-supervised/conformance/all"]
        self.assertEqual((summary["rows"], summary["source_families"]), (24, 6))


class CorpusTests(unittest.TestCase):
    def test_all_authored_freezes_validate(self):
        for manifest in sorted((ROOT / "examples/corpora").glob("*/manifest.json")):
            with self.subTest(corpus=manifest.parent.name):
                load_corpus(manifest)

    def test_overlap_is_reported_not_summed(self):
        _, rows, _ = corpus()
        audit = audit_corpora([("core", rows)])
        self.assertTrue(audit["subset_overlaps"])
        self.assertEqual(audit["rows"], len(rows))

    def test_family_cross_split_audit(self):
        _, rows, _ = corpus()
        a, b = deepcopy(rows[0]), deepcopy(rows[1])
        b["family"], b["split"] = a["family"], "heldout"
        audit = audit_corpora([("example", [a, b])])
        self.assertEqual(len(audit["cross_split_families"]), 1)

    def test_exact_input_cross_split_audit(self):
        _, rows, _ = corpus()
        a, b = deepcopy(rows[0]), deepcopy(rows[0])
        b.update(id="other-id", split="heldout", family="another-family")
        self.assertEqual(len(audit_corpora([("example", [a, b])])["cross_split_exact"]), 1)

    def test_path_traversal_and_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "corpus"
            root.mkdir()
            (root / "escape").symlink_to(Path(tmp))
            for name in ("../outside", "/absolute", "escape/outside"):
                with self.assertRaises(ValueError):
                    within(root, name)

    def test_duplicate_keys_and_nonfinite_json_rejected(self):
        for value in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.assertRaises(ValueError):
                loads(value)

    def test_wrong_resource_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = read_json(ROOT / "examples/corpora/us-core/manifest.json")
            manifest["resources"][0]["sha256"] = "0" * 64
            Path(tmp, "cases.jsonl").write_bytes((ROOT / "examples/corpora/us-core/cases.jsonl").read_bytes())
            from address_benchmark.io import write_json
            write_json(Path(tmp, "manifest.json"), manifest)
            with self.assertRaisesRegex(ValueError, "hash differs"):
                load_corpus(Path(tmp, "manifest.json"))

    def fetch_fixture(self, directory):
        from address_benchmark.io import write_json
        manifest = read_json(ROOT / "examples/corpora/us-core/manifest.json")
        manifest["resources"][0]["url"] = "https://example.invalid/authored.jsonl"
        path = Path(directory) / "manifest.json"
        write_json(path, manifest)
        data = (ROOT / "examples/corpora/us-core/cases.jsonl").read_bytes()
        class Response(BytesIO):
            def geturl(self):
                return "https://example.invalid/authored.jsonl"
        return path, data, Response

    def test_fetch_verifies_hash_before_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, data, response = self.fetch_fixture(tmp)
            with patch("urllib.request.urlopen", return_value=response(data)):
                self.assertEqual(fetch(path), ["cases.jsonl"])
            self.assertEqual(Path(tmp, "cases.jsonl").read_bytes(), data)
            self.assertFalse(Path(tmp, "cases.jsonl.partial").exists())

    def test_fetch_tampered_and_oversize_download_not_installed(self):
        for mode in ("tampered", "oversize"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                path, data, response = self.fetch_fixture(tmp)
                with patch("urllib.request.urlopen", return_value=response(data + b"x" if mode == "tampered" else data)):
                    with self.assertRaises(ValueError):
                        fetch(path, max_bytes=1 if mode == "oversize" else len(data) + 10)
                self.assertFalse(Path(tmp, "cases.jsonl").exists())
                self.assertFalse(Path(tmp, "cases.jsonl.partial").exists())

    def test_fetch_preserves_another_invocations_partial_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, data, response = self.fetch_fixture(tmp)
            temporary = Path(tmp, "cases.jsonl.partial")
            temporary.write_bytes(b"another-owner")
            with patch("urllib.request.urlopen", return_value=response(data)):
                with self.assertRaises(FileExistsError):
                    fetch(path)
            self.assertEqual(temporary.read_bytes(), b"another-owner")


class UtilityTests(unittest.TestCase):
    def evaluate(self, name, adapter):
        manifest, rows, requests = corpus(name)
        return [score_case(row, check_prediction(adapter.parse(req), req, adapter.metadata), adapter.metadata) for row, req in zip(rows, requests)]

    def test_normalization_is_exact_not_casefolded_by_scorer(self):
        _, rows, requests = corpus("us-normalization")
        adapter = DemoNormalizer({})
        output = adapter.parse(requests[0])
        output["normalized"][0] = output["normalized"][0].lower()
        self.assertFalse(score_case(rows[0], output, adapter.metadata)["primary_agrees"])

    def test_independent_identity_pairs(self):
        cases = self.evaluate("us-identity", DemoKeys({}))
        result = summarize(cases)
        self.assertEqual(result["agreement"]["denominator"], 10)
        self.assertEqual(result["distinct_entity_collisions"], 0)
        self.assertEqual(result["same_entity"]["recall"], 1)

    def test_unit_erasing_keys_have_collision(self):
        _, rows, requests = corpus("us-identity")
        adapter = DemoKeys({})
        output = adapter.parse(requests[1])
        output["keys"] = ["12 ALDER ST", "12 ALDER ST"]
        result = summarize([score_case(rows[1], output, adapter.metadata)])
        self.assertEqual(result["distinct_entity_collisions"], 1)
        self.assertEqual(result["same_entity"]["precision"], 0)

    def test_refused_negative_pair_is_not_true_negative(self):
        _, rows, requests = corpus("us-identity")
        adapter = DemoKeys({})
        output = prediction(requests[1], status="refused", message="no key", native=None)
        result = summarize([score_case(rows[1], output, adapter.metadata)])
        self.assertEqual(result["true_distinct"], 0)
        self.assertEqual(result["undecided_distinct"], 1)
        self.assertEqual(result["agreement"]["rate"], 0)

    def test_all_utility_controls(self):
        for task in ("format", "classify", "extract", "infer", "variants", "diagnostics", "stability"):
            with self.subTest(task=task):
                cases = self.evaluate("us-" + task, DemoUtility({"task": task}))
                self.assertEqual(summarize(cases)["agreement"]["rate"], 1)

    def test_typed_false_is_not_numeric_zero(self):
        _, rows, requests = corpus("us-diagnostics")
        adapter = DemoUtility({"task": "diagnostics"})
        output = adapter.parse(requests[2])
        output["result"]["empty_input"] = 0
        self.assertFalse(score_case(rows[2], output, adapter.metadata)["primary_agrees"])

    def test_variant_unit_mutation_is_disallowed(self):
        _, rows, requests = corpus("us-variants")
        adapter = DemoUtility({"task": "variants"})
        output = adapter.parse(requests[0])
        output["result"].append("12 ALDER ST APT 4")
        result = score_case(rows[0], output, adapter.metadata)
        self.assertFalse(result["primary_agrees"])
        self.assertEqual(result["disallowed"], 1)

    def test_batch_reordering_fails_parity(self):
        _, rows, requests = corpus("us-stability")
        adapter = DemoUtility({"task": "stability"})
        output = adapter.parse(requests[0])
        output["result"]["batch"].reverse()
        result = score_case(rows[0], output, adapter.metadata)
        self.assertFalse(result["checks"]["scalar_batch"])
        self.assertTrue(result["checks"]["repeat"])

    def test_missing_batch_rows_invalidates_stability(self):
        _, rows, requests = corpus("us-stability")
        adapter = DemoUtility({"task": "stability"})
        output = adapter.parse(requests[0])
        output["result"]["batch"].pop()
        with self.assertRaisesRegex(ValueError, "length differs"):
            score_case(rows[0], output, adapter.metadata)

    def test_dropped_stream_tail_and_reordered_chunks_fail(self):
        _, rows, requests = corpus("us-stability")
        adapter = DemoUtility({"task": "stability"})
        output = adapter.parse(requests[0])
        output["result"]["chunked"].reverse()
        self.assertFalse(score_case(rows[0], output, adapter.metadata)["checks"]["scalar_chunked"])
        output["result"]["stream"].pop()
        with self.assertRaisesRegex(ValueError, "length differs"):
            score_case(rows[0], output, adapter.metadata)

    def test_public_callable_normalize_preserves_exact_output(self):
        adapter = PythonCallable(dict(callable="tests.support:canonical_text", task="normalize", profile=DemoNormalizer.PROFILE))
        self.assertEqual(summarize(self.evaluate("us-normalization", adapter))["agreement"]["rate"], 1)

    def test_public_callable_stream_and_chunk_observations(self):
        adapter = PythonCallable(dict(callable="tests.support:canonical_text", task="stability", profile="address-benchmark.authored-stability/v1",
                                      batch_callable="canonical_batch", stream_callable="canonical_stream", chunked_callable="canonical_chunked", chunk_size=2, kwargs={"mode": "upper"}))
        result = summarize(self.evaluate("us-stability", adapter))
        self.assertEqual(result["agreement"]["rate"], 1)
        self.assertEqual(set(result["checks"]), {"repeat", "scalar_batch", "idempotence", "scalar_stream", "scalar_chunked"})

    def test_public_callable_field_formatter(self):
        adapter = PythonCallable(dict(callable="tests.support:formatted_fields", task="format", profile="address-benchmark.authored-format/v1"))
        self.assertEqual(summarize(self.evaluate("us-format", adapter))["agreement"]["rate"], 1)

    def test_public_callable_inference_keeps_null(self):
        adapter = PythonCallable(dict(callable="tests.support:known_state", task="infer", profile="address-benchmark.authored-infer/v1", result_field="state"))
        self.assertEqual(summarize(self.evaluate("us-infer", adapter))["agreement"]["rate"], 1)


if __name__ == "__main__":
    unittest.main()
