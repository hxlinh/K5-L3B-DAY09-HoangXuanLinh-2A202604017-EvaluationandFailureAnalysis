"""M7: report and spec tampering that integrity_check must refuse, beyond the public traps."""
import copy

import pytest

pytestmark = pytest.mark.student

ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["money_movement"] if i < 2 else []}
        for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2", "seeds": [1, 2],
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                     "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9,
                    "no_significant_drop": True, "blocking": True}]}


def report():
    return {"manifest": {"eval_set_sha": "x", "items": 4, "seeds": [1, 2]}, "rows": copy.deepcopy(ROWS),
            "metrics": {"pass_rate": 1.0}, "evaluator_failures": []}


def problems(pr, spec=SPEC, base_spec=None):
    from lab9.gate import integrity_check

    return integrity_check(pr, report(), spec, base_spec)


def test_clean_report_has_no_problem():
    assert problems(report()) == []
    assert problems(report(), SPEC, SPEC) == []


def test_duplicate_row_replacing_a_failure_is_refused():
    pr = report()
    pr["rows"][1] = copy.deepcopy(pr["rows"][0])
    assert any("duplicated" in p for p in problems(pr))


def test_evaluator_failure_on_a_green_run_is_refused():
    pr = report()
    pr["evaluator_failures"] = ["E-000@1:ApprovalBypass:boom"]
    assert any("evaluator failure" in p for p in problems(pr))


def test_crashed_grader_row_is_refused():
    pr = report()
    pr["rows"][0]["pass_rate"] = None
    assert any("no valid verdict" in p for p in problems(pr))


def test_edited_summary_metric_is_refused():
    pr = report()
    pr["rows"][0]["pass_rate"] = False
    assert any("its rows give" in p for p in problems(pr))


def test_item_moved_out_of_a_slice_is_refused():
    pr = report()
    for row in pr["rows"]:
        if row["item_id"] == "E-000":
            row["slices"] = []
    assert any("slice tags" in p for p in problems(pr))


@pytest.mark.parametrize("weaken", [
    lambda s: s["slices"].clear(),
    lambda s: s["slices"][0].update(min=0.5),
    lambda s: s["slices"][0].pop("no_significant_drop"),
    lambda s: s["slices"][0].update(blocking=False),
    lambda s: s["metrics"][0].update(blocking=False),
    lambda s: s["metrics"][0]["threshold"].pop("min"),
    lambda s: s["metrics"].clear(),
])
def test_weakened_spec_is_refused(weaken):
    loose = copy.deepcopy(SPEC)
    weaken(loose)
    assert problems(report(), loose, SPEC)


def test_stricter_spec_is_allowed():
    strict = copy.deepcopy(SPEC)
    strict["metrics"][0]["threshold"]["min"] = 0.9
    strict["slices"][0]["min"] = 0.95
    assert problems(report(), strict, SPEC) == []
