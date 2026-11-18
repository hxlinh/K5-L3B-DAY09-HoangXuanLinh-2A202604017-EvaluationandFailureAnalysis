"""Regression test from docs/trace_case.md: seeded_regression C-014@11 (FM-05, double deduction)."""
import pytest

pytestmark = pytest.mark.student


def run_case(shape):
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9.graders import RefundAmountCorrect
    from lab9.trace_case import investigate

    case = investigate(shape, "C-014", 11)
    ctx = EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=case["label"], output=case["trial"],
                           duration=0.0, _span_tree=None, attributes={}, metrics={})
    proposals = [e["payload"]["amount_vnd"] for e in case["trial"]["events"] if e.get("kind") == "proposal"]
    return RefundAmountCorrect().evaluate(ctx).value, proposals


def test_double_deduction_is_caught():
    correct, proposals = run_case("seeded_regression")
    assert correct is False
    assert proposals == [120000]


def test_fixed_shape_keeps_the_quote():
    correct, proposals = run_case("fixed")
    assert correct is True
    assert proposals == []
