"""Synthetic native-artifact controls; no external or private corpus access."""
from contextlib import redirect_stderr, redirect_stdout
from collections import Counter
from copy import deepcopy
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from address_benchmark.adapters import DemoParser
from address_benchmark.io import identity, read_json, read_jsonl, sha256, write_json, write_jsonl
from address_benchmark.protocol import Request, request_hash
from address_benchmark.runner import run, source_pins
from tools import changed_review_queue as review


class ChangedReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.patch = patch.object(review, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def rows(self, count=4, source="PRIVATE_SOURCE"):
        return [dict(id=f"PRIVATE_ID_{i}", text=f"{i + 1} Maple St, Example, NY 00000", source=source,
                     family=f"PRIVATE_FAMILY_{i}", origin="authored", split="conformance", reference={})
                for i in range(count)]

    def fixture(self, name, rows=None, *, mutate=None, order=False):
        rows = deepcopy(self.rows() if rows is None else rows)
        directory = self.root / name
        directory.mkdir()
        (directory / "engine-accuracy").mkdir()
        adapter = DemoParser({})
        requests = [Request(row["id"], row["text"], request_hash(row["text"]), "US", "en-US") for row in rows]
        predictions = [adapter.parse(request) for request in requests]
        if mutate:
            mutate(predictions)
        write_jsonl(directory / "inputs.jsonl", [r.to_dict() for r in reversed(requests)] if order else [r.to_dict() for r in requests])
        write_jsonl(directory / "references.jsonl", rows[1:] + rows[:1] if order else rows)
        write_jsonl(directory / "engine-accuracy/predictions.jsonl", predictions)
        manifest = dict(id="PRIVATE_CORPUS", country="US", locale="en-US", task="parse", ontology=adapter.metadata["ontology"])
        write_json(directory / "corpus.json", manifest)
        runtime = dict(adapter=adapter.metadata)
        entry = dict(status="ok", identity=runtime, identity_sha256=identity(runtime))
        write_json(directory / "engine-accuracy/identity.json", runtime)
        write_json(directory / "engine-accuracy/execution.json", entry)
        report = dict(schema="address-benchmark.run/v1", status="complete", corpus=dict(id=manifest["id"]), task="parse",
                      input_sha256=sha256(directory / "inputs.jsonl"), source_pins={"retained.py": "0" * 64}, accuracy=dict(engine=entry))
        self.seal(directory, report)
        return directory

    def seal(self, directory, report=None):
        report = report or read_json(directory / "run.json")
        report["artifacts"] = {str(path.relative_to(directory)): sha256(path) for path in directory.rglob("*")
                               if path.is_file() and path.name != "run.json"}
        report["input_sha256"] = sha256(directory / "inputs.jsonl")
        report.pop("content_id", None)
        report["content_id"] = identity(report)
        (directory / "run.json").write_text(json.dumps(report), encoding="utf-8")

    def build(self, left, right, name="queue", **kwargs):
        return review.build_queue(left, right, baseline="engine", candidate="engine",
                                  output=self.root / "work" / name, **kwargs)

    def replace_jsonl(self, directory, name, rows):
        (directory / name).unlink()
        write_jsonl(directory / name, rows)
        self.seal(directory)

    def test_stable_id_join_accepts_independently_reordered_streams(self):
        left = self.fixture("before")
        right = self.fixture("after", order=True, mutate=lambda rows: rows[2].update(native={"changed": True}))
        result = self.build(left, right)
        self.assertEqual((result["shared_rows"], result["changed_rows"], result["unchanged_rows"]), (4, 1, 3))
        card, = read_jsonl(self.root / "work/queue/queue.jsonl")
        self.assertEqual(card["id"], "PRIVATE_ID_2")
        self.assertNotIn("reference", card)
        self.assertEqual(card["before"]["id"], card["after"]["id"])
        receipt = read_json(self.root / "work/queue/review.json")
        self.assertEqual(receipt["before"]["source_pins"], {"retained.py": "0" * 64})

    def test_missing_between_runs_is_explicit_and_sampled(self):
        left = self.fixture("before", self.rows()[:3])
        right = self.fixture("after", self.rows()[1:])
        result = self.build(left, right)
        self.assertEqual(result, dict(before_rows=3, after_rows=3, shared_rows=2, before_only=1,
                                     after_only=1, unchanged_rows=2, changed_rows=2, selected_rows=2))
        cards = list(read_jsonl(self.root / "work/queue/queue.jsonl"))
        self.assertEqual({tuple(card["changes"]) for card in cards}, {("missing_before",), ("missing_after",)})
        self.assertTrue(all((card["before"] is None) != (card["after"] is None) for card in cards))

    def test_duplicate_and_missing_stream_rows_are_rejected(self):
        for stream in ("inputs.jsonl", "references.jsonl", "engine-accuracy/predictions.jsonl"):
            for mode in ("duplicate", "missing"):
                with self.subTest(stream=stream, mode=mode):
                    suffix = stream.replace("/", "-") + mode
                    left = self.fixture("left" + suffix)
                    right = self.fixture("right" + suffix)
                    rows = list(read_jsonl(right / stream))
                    self.replace_jsonl(right, stream, rows + rows[:1] if mode == "duplicate" else rows[:-1])
                    with self.assertRaises(ValueError):
                        self.build(left, right, suffix)
                    self.assertFalse((self.root / "work" / suffix).exists())

    def test_same_id_with_changed_input_rejected_even_with_valid_new_hash(self):
        left = self.fixture("before")
        rows = self.rows()
        rows[0]["text"] = "99 Maple St, Example, NY 00000"
        right = self.fixture("after", rows)
        with self.assertRaisesRegex(ValueError, "shared input identity"):
            self.build(left, right)

    def test_prediction_hash_and_ownership_mismatch_rejected(self):
        left = self.fixture("before")
        right = self.fixture("bad-hash", mutate=lambda rows: rows[0].update(input_sha256="0" * 64))
        with self.assertRaises(ValueError):
            self.build(left, right)
        rows = self.rows(); rows[0]["source"] = "different"
        right = self.fixture("bad-source", rows)
        with self.assertRaisesRegex(ValueError, "ownership"):
            self.build(left, right)

    def test_combined_fields_errors_refusals_and_extension_fields_survive(self):
        left = self.fixture("before")
        def mutate(rows):
            rows[0].update(native={"new": True}, inferred=[{"new": True}], diagnostic="PRIVATE_NATIVE")
            for row, status in zip(rows[1:3], ("error", "refused")):
                row.update(status=status, evidence=[], tokens=[], native={"detail": "PRIVATE_NATIVE"}, message="PRIVATE_MESSAGE")
        right = self.fixture("after", mutate=mutate)
        self.build(left, right)
        cards = {card["id"]: card for card in read_jsonl(self.root / "work/queue/queue.jsonl")}
        self.assertEqual(cards["PRIVATE_ID_0"]["changes"], ["inferred", "native", "other"])
        self.assertEqual(cards["PRIVATE_ID_0"]["changed_fields"], ["diagnostic", "inferred", "native"])
        self.assertEqual({cards[f"PRIVATE_ID_{i}"]["after"]["status"] for i in (1, 2)}, {"error", "refused"})
        self.assertIn("status", cards["PRIVATE_ID_1"]["changes"])

    def test_prediction_comparison_preserves_json_types_and_absent_fields(self):
        before = dict(id="x", schema="s", input_sha256="h", native=True, result=None)
        after = dict(id="x", schema="s", input_sha256="h", native=1)
        self.assertEqual(review.changes(before, after), (["result", "native"], ["native", "result"]))
        self.assertEqual(review.changes(dict(native=False), dict(native=0))[0], ["native"])

    def test_deterministic_source_and_complete_change_combination_balancing(self):
        cards = []
        for source, kinds in (("large", (["native"], ["evidence"], ["tokens"])), ("small", (["native", "status"],))):
            for changes in kinds:
                for index in range(5):
                    cards.append(dict(corpus_id="c", id=f"{source}-{changes}-{index}", ownership=dict(source=source), changes=changes))
        selected = review.draw(cards, 8, 17)
        self.assertEqual(selected, review.draw(list(reversed(cards)), 8, 17))
        self.assertEqual(Counter(card["ownership"]["source"] for card in selected), {"large": 4, "small": 4})
        self.assertEqual({tuple(card["changes"]) for card in selected}, {("native",), ("evidence",), ("tokens",), ("native", "status")})
        self.assertNotEqual(selected, review.draw(cards, 8, 18))

    def test_cli_stdout_is_counts_only_and_errors_never_quote_private_content(self):
        left = self.fixture("before")
        right = self.fixture("after", mutate=lambda rows: rows[0].update(native="PRIVATE_NATIVE"))
        args = [str(left), str(right), "--baseline", "engine", "--candidate", "engine", "--out", str(self.root / "work/queue")]
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(review.main(args), 0)
        self.assertEqual(json.loads(stdout.getvalue())["changed_rows"], 1)
        self.assertNotIn("PRIVATE", stdout.getvalue() + stderr.getvalue())
        (right / "engine-accuracy/predictions.jsonl").write_text('{"PRIVATE_SECRET":invalid}\n')
        self.seal(right)
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(review.main(args[:-1] + [str(self.root / "work/bad")]), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "changed-review: invalid-input-or-output\n")
        self.assertFalse((self.root / "work/bad").exists())

    def test_artifact_and_envelope_tampering_rejected(self):
        left, right = self.fixture("before"), self.fixture("after")
        (right / "inputs.jsonl").write_text("PRIVATE_BAD_DATA")
        with self.assertRaisesRegex(ValueError, "artifact hash"):
            self.build(left, right)
        right = self.fixture("bad-envelope")
        report = read_json(right / "run.json"); report["status"] = "gated"
        (right / "run.json").write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "content identity"):
            self.build(left, right)

    def test_output_is_local_fresh_private_and_never_overlaps_sources(self):
        left, right = self.fixture("before"), self.fixture("after")
        with patch.object(review, "ROOT", Path(review.__file__).resolve().parents[1]):
            with self.assertRaises(ValueError): self.build(left, right)
        with self.assertRaises(ValueError):
            review.build_queue(left, right, baseline="engine", candidate="engine", output=self.root / "tracked")
        self.build(left, right)
        out = self.root / "work/queue"
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((out / "queue.jsonl").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((out / "review.json").stat().st_mode), 0o600)
        with self.assertRaises(ValueError): self.build(left, right)
        (self.root / "work/alias").symlink_to(left, target_is_directory=True)
        with self.assertRaises(ValueError): self.build(left, right, "alias/child")
        with self.assertRaises(ValueError): self.build(left, right, "../escape")
        local_source = self.root / "work/source"
        left.rename(local_source)
        with self.assertRaises(ValueError): self.build(local_source, right, "source/child")
        with self.assertRaises(ValueError): self.build(local_source, right, ".")
        self.assertFalse((local_source / "child").exists())

    def test_bounds_fail_before_output_and_zero_changes_is_valid(self):
        left, right = self.fixture("before"), self.fixture("after")
        for n in (0, -1, 1001):
            with self.assertRaises(ValueError): self.build(left, right, n=n)
        with patch.object(review, "MAX_ROWS", 7):
            with self.assertRaisesRegex(ValueError, "row limit"): self.build(left, right)
        with patch.object(review, "MAX_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "byte limit"): self.build(left, right)
        self.assertFalse((self.root / "work").exists())
        result = self.build(left, right)
        self.assertEqual(result["selected_rows"], 0)
        self.assertEqual((self.root / "work/queue/queue.jsonl").read_bytes(), b"")

    def test_actual_authored_run_to_queue_without_model_or_label_calls(self):
        repository = Path(review.__file__).resolve().parents[1]
        pins = source_pins()
        directory = self.root / "native-run"
        result = run(repository / "examples/corpora/us-core/manifest.json", repository / "examples/adapters/engines.json", directory)
        self.assertEqual(result["status"], "complete")
        engines = list(result["accuracy"])
        population = review.build_queue(directory, directory, baseline=engines[0], candidate=engines[-1],
                                       output=self.root / "work/native-review", n=3)
        self.assertGreater(population["selected_rows"], 0)
        self.assertLessEqual(population["selected_rows"], 3)
        self.assertEqual(result, read_json(directory / "run.json"))
        self.assertEqual(pins, source_pins())


if __name__ == "__main__":
    unittest.main()
