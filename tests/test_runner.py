from copy import deepcopy
import os
from pathlib import Path
import statistics
import sys
import tempfile
import unittest

from address_benchmark.corpus import input_requests, load_corpus
from address_benchmark.io import read_json, read_jsonl, write_json
from address_benchmark.runner import paired_summary, run, validate_predictions, verify
from address_benchmark.adapters import DemoParser

ROOT = Path(__file__).resolve().parents[1]


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def execute(self, name="us-core", engines=None, timing=False):
        engines = engines or [{"name": "demo", "adapter": "demo"}, {"name": "refusal", "adapter": "refusal"}]
        spec = self.root / "engines.json"
        write_json(spec, engines)
        output = self.root / "run"
        result = run(ROOT / "examples/corpora" / name / "manifest.json", spec, output,
                     timing=timing, trials=2, samples=2, min_seconds=.003, timeout=30)
        return result, output

    def test_end_to_end_run_and_rescore(self):
        result, output = self.execute()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(verify(output)["status"], "verified")
        m = result["accuracy"]["refusal"]["populations"]["authored/conformance/all"]
        self.assertEqual(m["complete_address"]["denominator"], 8)
        self.assertEqual(m["complete_address"]["correct"], 0)
        self.assertTrue(list(output.glob("delta-*.jsonl")))
        self.assertTrue((output / "demo-accuracy/stderr.log").exists())

    def test_changed_prediction_is_detected(self):
        _, output = self.execute()
        with (output / "demo-accuracy/predictions.jsonl").open("ab") as f:
            f.write(b"{}\n")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            verify(output)

    def test_changed_report_is_detected(self):
        _, output = self.execute()
        result = read_json(output / "run.json")
        result["accuracy"]["demo"]["exit_code"] = 99
        (output / "run.json").unlink()
        write_json(output / "run.json", result)
        with self.assertRaisesRegex(ValueError, "content identity"):
            verify(output)

    def test_missing_adapter_is_unavailable_without_score(self):
        result, output = self.execute(engines=[dict(name="missing", adapter="no_such_benchmark_module_123:Factory")])
        entry = result["accuracy"]["missing"]
        self.assertEqual((result["status"], entry["status"], entry["exit_code"]), ("incomplete", "unavailable", 69))
        self.assertNotIn("populations", entry)
        self.assertEqual(verify(output)["status"], "verified")

    def test_wrong_identity_invalidates_cell(self):
        result, _ = self.execute(engines=[dict(name="wrong", adapter="tests.support:WrongIdentity")])
        self.assertEqual(result["accuracy"]["wrong"]["status"], "failed")
        self.assertNotIn("populations", result["accuracy"]["wrong"])

    def test_native_exception_stays_in_denominator(self):
        result, _ = self.execute(engines=[dict(name="broken", adapter="tests.support:Broken")])
        entry = result["accuracy"]["broken"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["populations"]["authored/conformance/all"]["statuses"], {"error": 8})
        self.assertEqual(entry["populations"]["authored/conformance/all"]["complete_address"]["denominator"], 8)

    def test_model_change_during_inference_invalidates_cell(self):
        model = self.root / "model.bin"
        model.write_bytes(b"original model fixture")
        result, _ = self.execute(engines=[dict(name="mutating", adapter="tests.support:MutatingArtifact", config={"model": str(model)})])
        self.assertEqual(result["accuracy"]["mutating"]["status"], "failed")
        self.assertNotIn("populations", result["accuracy"]["mutating"])

    def test_worker_timeout_records_actual_exit(self):
        spec = self.root / "engines.json"
        write_json(spec, [dict(name="slow", adapter="tests.support:Slow")])
        result = run(ROOT / "examples/corpora/us-core/manifest.json", spec, self.root / "run", timeout=.3)
        entry = result["accuracy"]["slow"]
        self.assertEqual(entry["status"], "timeout")
        self.assertIsInstance(entry["exit_code"], int)
        self.assertNotEqual(entry["exit_code"], 0)

    def test_pair_timing_reverses_order_uses_same_panel(self):
        result, output = self.execute(engines=[dict(name="a", adapter="demo"), dict(name="b", adapter="demo")], timing=True)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["trials"][0]["order"], list(reversed(result["trials"][1]["order"])))
        self.assertEqual(result["paired"]["a/b"]["pairs"], 2)
        self.assertIsNone(result["paired"]["a/b"]["bootstrap_95_interval"])
        for path in output.glob("trial-*/timing.json"):
            self.assertEqual(read_json(path)["panel_sha256"], read_json(next(output.glob("trial-*/timing.json")))["panel_sha256"])
        verify(output)

    def test_all_utility_tasks_run_in_subprocess(self):
        for task, adapter in [("normalization", "demo-normalize"), ("identity", "demo-keys"), *[(task, "demo-utility") for task in ("format", "classify", "extract", "infer", "variants", "diagnostics", "stability")]]:
            with self.subTest(task=task), tempfile.TemporaryDirectory(dir=self.root) as tmp:
                directory = Path(tmp)
                config = {"task": task} if adapter == "demo-utility" else {}
                write_json(directory / "engine.json", [dict(name="control", adapter=adapter, config=config)])
                result = run(ROOT / f"examples/corpora/us-{task}/manifest.json", directory / "engine.json", directory / "run")
                self.assertEqual(result["status"], "complete")
                self.assertEqual(verify(directory / "run")["status"], "verified")

    def test_stream_truncation_or_reordering_rejected(self):
        manifest, rows, _ = load_corpus(ROOT / "examples/corpora/us-core/manifest.json")
        requests = input_requests(manifest, rows)
        adapter = DemoParser({})
        outputs = [adapter.parse(request) for request in requests]
        for changed in (outputs[:-1], list(reversed(outputs)), outputs + [outputs[0]]):
            with self.assertRaises(ValueError):
                validate_predictions(rows, requests, changed, adapter.metadata)

    def test_fresh_output_directory_required(self):
        _, output = self.execute()
        with self.assertRaisesRegex(ValueError, "fresh output"):
            run(ROOT / "examples/corpora/us-core/manifest.json", self.root / "engines.json", output)

    def test_persistent_command_wire(self):
        adapter = DemoParser({})
        engine = dict(name="wire", adapter="command", config=dict(command=[sys.executable, str(ROOT / "examples/adapters/jsonl_demo.py")], metadata=adapter.metadata))
        result, output = self.execute(engines=[engine])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(verify(output)["status"], "verified")
        self.assertIn("bridge", result["accuracy"]["wire"]["identity"]["adapter"])

    def test_early_clean_command_exit_invalidates_stream(self):
        engine = dict(name="short", adapter="command", config=dict(command=[sys.executable, "-c", "pass"], metadata=DemoParser({}).metadata))
        result, _ = self.execute(engines=[engine])
        self.assertEqual(result["accuracy"]["short"]["status"], "failed")
        self.assertNotIn("populations", result["accuracy"]["short"])

    def test_incomplete_pairs_have_no_cherry_picked_estimate(self):
        trials = [dict(engines=dict(a=dict(status="ok", median_ns_per_address=1), b=dict(status="ok", median_ns_per_address=2))),
                  dict(engines=dict(a=dict(status="ok", median_ns_per_address=1), b=dict(status="failed")))]
        result = paired_summary(trials, ["a", "b"], seed=1)["a/b"]
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["median_ratio"])
        self.assertEqual(result["ratios"], [2])


if __name__ == "__main__":
    unittest.main()
