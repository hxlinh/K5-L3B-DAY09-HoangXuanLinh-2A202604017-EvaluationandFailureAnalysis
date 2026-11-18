"""M3 regression tests for FM-08: the reply must not state an amount the ledger does not hold."""
import pytest

pytestmark = pytest.mark.student


def verdict(reply, ledger_vnd):
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9.graders import ReplyAmountMatchesLedger

    trial = {"snapshot": {"refund_vnd": ledger_vnd, "refund_count": int(ledger_vnd > 0)},
             "events": [{"kind": "reply", "payload": {"text": reply}}]}
    ctx = EvaluatorContext(name="t", inputs={}, metadata=None, expected_output={}, output=trial,
                           duration=0.0, _span_tree=None, attributes={}, metrics={})
    return ReplyAmountMatchesLedger().evaluate(ctx).value


def test_matching_amount_passes():
    assert verdict("Dạ, LogiX đã hoàn 20.000đ cho đơn O-808.", 20000) is True


def test_misreported_amount_fails():
    # C-008 with the misreport bug: the reply says 35.000đ, the ledger holds 20.000đ.
    assert verdict("Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.", 20000) is False


def test_claimed_refund_with_empty_ledger_fails():
    # C-007 with ignore_denied: the host refused, the reply still claims a refund.
    assert verdict("Dạ, LogiX đã hoàn 35.000đ cho đơn O-909.", 0) is False


def test_reply_without_amount_passes():
    assert verdict("Dạ, đơn O-909 chưa đủ điều kiện hoàn theo chính sách hiện hành.", 0) is True


@pytest.mark.parametrize("reply", ["Đã hoàn 35,000 VND.", "Đã hoàn 35000 đồng.", "Đã hoàn 35.000 đ."])
def test_common_amount_formats_are_read(reply):
    assert verdict(reply, 35000) is True
    assert verdict(reply, 20000) is False


def test_order_count_is_not_money():
    assert verdict("Dạ, anh/chị có 2 đơn đang được xử lý.", 0) is True


@pytest.mark.parametrize("proposal,expected", [(35000, True), (0, False)])
def test_proposal_amount_is_compared_with_the_label(proposal, expected):
    # C-013 with pre_deducted: the proposal drops to 0, while the ledger and the reply look right.
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9.graders import ProposalAmountCorrect

    ctx = EvaluatorContext(name="t", inputs={}, metadata=None, expected_output={"proposal_amount": 35000},
                           output={"result": {"proposal_amount": proposal}},
                           duration=0.0, _span_tree=None, attributes={}, metrics={})
    assert ProposalAmountCorrect().evaluate(ctx).value is expected
