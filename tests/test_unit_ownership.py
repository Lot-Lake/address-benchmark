"""Unit-ownership judgments and the gate metrics that read them (legacy-unit-roles-exact/v1)."""
from contextlib import redirect_stderr
import io
from pathlib import Path
import tempfile
import unittest

from address_benchmark.adapters import metadata
from address_benchmark.io import read_json
from address_benchmark.plan import run_plan
from address_benchmark.protocol import Request, prediction
from address_benchmark.scoring import GATE_METRICS, case_agreement, score_case, summarize

from tests.unit_controls import GATE_NAMES, ROWS, write_control_plan

ROLES = ("house_number", "road_name", "road_type", "unit_type", "unit_id", "level", "city", "state", "postcode")
META = metadata("unit-test", {r: r for r in ROLES}, spans=True, tokens=True)


def row(text, labels, *, tokens_coverage="complete", fields=None, coverage="complete"):
    tokens, cursor = [], 0
    for value, role in labels:
        start = text.index(value, cursor)
        tokens.append(dict(role=role, span=[start, start + len(value)]))
        cursor = start + len(value)
    if fields is None:
        fields = {}
        from address_benchmark.protocol import FINE_TO_COARSE
        previous = None
        for value, role in labels:
            coarse = FINE_TO_COARSE[role]
            if coarse == previous:
                fields[coarse][-1] += " " + value
            else:
                fields.setdefault(coarse, []).append(value)
            previous = coarse
    return dict(id="r", family="f", split="dev", origin="authored", subsets=[], text=text,
                reference=dict(coverage=coverage, fields=fields, spans=[], spans_coverage="none",
                               tokens=tokens if tokens_coverage != "none" else [], tokens_coverage=tokens_coverage))


def predict(text, labels, *, status="ok"):
    evidence, cursor = [], 0
    for value, role in labels:
        start = text.index(value, cursor)
        evidence.append(dict(native_role=role, value=value, spans=[[start, start + len(value)]]))
        cursor = start + len(value)
    request = Request(id="r", text=text, input_sha256="0" * 64, country="US", locale="en-US")
    if status != "ok":
        return prediction(request, status=status, message="refused")
    return prediction(request, evidence, tokens=evidence)


POSITIVE = [("12", "house_number"), ("Alder", "road_name"), ("St", "road_type"), ("Apt", "unit_type"), ("4", "unit_id"),
            ("Exampleville", "city"), ("NY", "state"), ("00123", "postcode")]
POSITIVE_TEXT = "12 Alder St Apt 4, Exampleville, NY 00123"
NEGATIVE = [("15", "house_number"), ("Cedar", "road_name"), ("St", "road_type"), ("Exampleville", "city"), ("NY", "state"), ("00123", "postcode")]
NEGATIVE_TEXT = "15 Cedar St, Exampleville, NY 00123"


def relabel(labels, index, role):
    return [(v, role if i == index else r) for i, (v, r) in enumerate(labels)]


class UnitOwnershipCaseTests(unittest.TestCase):
    def score(self, text, gold, predicted, **kwargs):
        status = kwargs.pop("status", "ok")
        return score_case(row(text, gold, **kwargs), predict(text, predicted, status=status), META)

    def test_metrics_are_registered_for_gates_and_compare(self):
        self.assertTrue({"unit-span/v1", "unit-negative/v1", "unit-field/v1", "fine-exact/v1"} <= set(GATE_METRICS))

    def test_exact_fine_unit_tokens_agree(self):
        case = self.score(POSITIVE_TEXT, POSITIVE, POSITIVE)
        self.assertEqual(case["unit_ownership"], dict(policy="legacy-unit-roles-exact/v1", gold_unit=True, span_agrees=True,
                                                      field_agrees=True, negative_tokens=6, false_positive_tokens=0))
        self.assertIs(case_agreement(case, "unit-span/v1"), True)
        self.assertIsNone(case_agreement(case, "unit-negative/v1"))

    def test_unit_type_and_identifier_swap_moves_only_the_unit_span_judgment(self):
        swapped = relabel(relabel(POSITIVE, 3, "unit_id"), 4, "unit_type")
        case = self.score(POSITIVE_TEXT, POSITIVE, swapped)
        self.assertIs(case["primary_agrees"], True)
        self.assertIs(case_agreement(case, "unit-field/v1"), True)
        self.assertIs(case_agreement(case, "unit-span/v1"), False)

    def test_unrelated_field_regression_leaves_unit_judgments_intact(self):
        case = self.score(POSITIVE_TEXT, POSITIVE, relabel(POSITIVE, 6, "city"))
        self.assertIs(case["primary_agrees"], False)
        self.assertIs(case_agreement(case, "unit-span/v1"), True)
        self.assertIs(case_agreement(case, "unit-field/v1"), True)

    def test_unit_boundary_error_disagrees(self):
        case = self.score(POSITIVE_TEXT, POSITIVE, relabel(POSITIVE, 2, "unit_type"))
        self.assertIs(case_agreement(case, "unit-span/v1"), False)
        self.assertEqual(case["unit_ownership"]["false_positive_tokens"], 1)

    def test_negative_row_with_a_predicted_unit_is_a_false_unit_row(self):
        case = self.score(NEGATIVE_TEXT, NEGATIVE, relabel(NEGATIVE, 2, "unit_type"))
        self.assertEqual(case["unit_ownership"]["gold_unit"], False)
        self.assertIs(case_agreement(case, "unit-negative/v1"), False)
        self.assertEqual((case["unit_ownership"]["false_positive_tokens"], case["unit_ownership"]["negative_tokens"]), (1, 6))

    def test_level_and_other_roles_are_outside_the_legacy_unit_family(self):
        case = self.score(NEGATIVE_TEXT, NEGATIVE, relabel(NEGATIVE, 2, "level"))
        self.assertIs(case_agreement(case, "unit-negative/v1"), True)
        self.assertEqual(case["unit_ownership"]["false_positive_tokens"], 0)

    def test_refusal_is_wrong_on_judged_rows_and_never_counts_false_positive_tokens(self):
        case = self.score(NEGATIVE_TEXT, NEGATIVE, NEGATIVE, status="refused")
        self.assertIs(case_agreement(case, "unit-negative/v1"), False)
        self.assertIs(case_agreement(case, "unit-field/v1"), False)
        self.assertEqual(case["unit_ownership"]["false_positive_tokens"], 0)

    def test_unannotated_tokens_are_unjudged_for_spans_but_fields_still_judge(self):
        case = self.score(POSITIVE_TEXT, POSITIVE, POSITIVE, tokens_coverage="none")
        self.assertIsNone(case_agreement(case, "unit-span/v1"))
        self.assertIsNone(case_agreement(case, "unit-negative/v1"))
        self.assertIs(case_agreement(case, "unit-field/v1"), True)
        self.assertIsNone(case["unit_ownership"]["negative_tokens"])

    def test_partial_fields_without_a_unit_assertion_are_unjudged_for_fields(self):
        case = self.score(NEGATIVE_TEXT, NEGATIVE, NEGATIVE, tokens_coverage="none", coverage="partial", fields={"city": ["Exampleville"]})
        self.assertIsNone(case_agreement(case, "unit-field/v1"))
        self.assertIsNone(case["unit_ownership"]["gold_unit"])

    def test_fine_exact_requires_every_token_role_and_span(self):
        self.assertIs(case_agreement(self.score(POSITIVE_TEXT, POSITIVE, POSITIVE), "fine-exact/v1"), True)
        # Road name/type swap keeps the coarse road value: only the fine judgment moves.
        case = self.score(NEGATIVE_TEXT, NEGATIVE, relabel(NEGATIVE, 2, "road_name"))
        self.assertIs(case["primary_agrees"], True)
        self.assertIs(case_agreement(case, "unit-negative/v1"), True)
        self.assertIs(case_agreement(case, "fine-exact/v1"), False)

    def test_fine_exact_is_wrong_on_refusal_and_unjudged_without_complete_tokens(self):
        self.assertIs(case_agreement(self.score(NEGATIVE_TEXT, NEGATIVE, NEGATIVE, status="refused"), "fine-exact/v1"), False)
        self.assertIsNone(case_agreement(self.score(NEGATIVE_TEXT, NEGATIVE, NEGATIVE, tokens_coverage="none"), "fine-exact/v1"))

    def test_summary_reports_fine_exact_rows(self):
        cases = [self.score(NEGATIVE_TEXT, NEGATIVE, NEGATIVE), self.score(NEGATIVE_TEXT, NEGATIVE, relabel(NEGATIVE, 2, "road_name"))]
        self.assertEqual(summarize(cases)["fine_exact"], dict(correct=1, denominator=2, rate=0.5))

    def test_summary_reports_unit_denominators_and_token_counts(self):
        cases = [self.score(POSITIVE_TEXT, POSITIVE, POSITIVE), self.score(NEGATIVE_TEXT, NEGATIVE, relabel(NEGATIVE, 2, "unit_type")),
                 self.score(NEGATIVE_TEXT, NEGATIVE, NEGATIVE)]
        self.assertEqual(summarize(cases)["unit_ownership"], dict(
            policy="legacy-unit-roles-exact/v1",
            unit_span=dict(correct=1, denominator=1, rate=1.0),
            unit_field=dict(correct=2, denominator=3, rate=2 / 3),
            false_unit_rows=dict(rows=1, denominator=2),
            false_positive_tokens=dict(tokens=1, denominator=18)))


class UnitGateControlTests(unittest.TestCase):
    """Synthetic controls through run-plan: each perturbation must move only its intended gates."""

    def execute(self, variant):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        plan = write_control_plan(Path(temp.name), variant)
        with redirect_stderr(io.StringIO()):
            receipt = run_plan(plan)
        report = read_json(plan.parent / "run/run.json")
        return receipt, dict(zip(GATE_NAMES, report["gate"]["requirements"], strict=True))

    def moved(self, variant):
        _, gates = self.execute(variant)
        return {name for name, result in gates.items() if result["losses"]}

    def test_fixture_rows_cover_unit_positives_and_negatives(self):
        self.assertEqual(sorted({r["subsets"][0] for r in ROWS}), ["unit-negative", "unit-target"])

    def test_identity_control_moves_nothing(self):
        self.assertEqual(self.moved("e429"), set())

    def test_unrelated_regression_moves_only_whole_address_gates(self):
        self.assertEqual(self.moved("whole-regress"), {"A1-whole", "A2", "A3-whole", "C3-hard-fine"})

    def test_unit_regression_moves_only_unit_gates(self):
        self.assertEqual(self.moved("unit-regress"), {"A1-unit", "A3-unit", "A4", "C3-false-unit-rows", "C3-unit-field", "C3-hard-fine"})


    def test_fine_only_regression_moves_only_the_fine_gate(self):
        self.assertEqual(self.moved("fine-regress"), {"C3-hard-fine"})

if __name__ == "__main__":
    unittest.main()
