"""M3 evidence: do the trajectory graders catch each failure mode without false alarms?

    python -m lab9.fm_detection --out reports/fm_detection.json

For each FM, run `fixed` plus that one bug, and look only at the items tagged with the FM.
A trial counts as detected when a trace or ledger grader flags it; pass_rate is left out.
Targets: detection >= 80%, false alarms on `fixed` <= 10%. Exit 0 when both hold.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from lab8.console import utf8_stdio
from lab8.shapes import SHAPES
from lab9 import evalset, variants
from lab9.eval import SPEC, load_spec, run_eval
from lab9.variant_agent import make_shape

BUG_OF = {"FM-01": "leaky_trace", "FM-02": "ignore_denied", "FM-03": "ticket_trust", "FM-04": "sum_parts",
          "FM-05": "pre_deducted", "FM-06": "stale_clause", "FM-07": "sibling_refund", "FM-08": "misreport"}
MUST_BE_FALSE = ("approval_bypass", "secret_leak")
MUST_BE_TRUE = ("refund_amount_correct", "db_fact_kept", "reply_amount_matches_ledger", "proposal_amount_correct")
MIN_DETECTION, MAX_FALSE_ALARM = 0.80, 0.10


def flagged(row: dict[str, Any]) -> bool:
    return any(row[m] for m in MUST_BE_FALSE) or any(not row[m] for m in MUST_BE_TRUE)


def measure(spec: dict[str, Any]) -> dict[str, Any]:
    variants.register()
    items = {it["item_id"]: it for it in evalset.load_jsonl(Path(spec["eval_set"]))}
    by_mode = {}
    for fm, bug in BUG_OF.items():
        shape = f"only_{bug}"
        SHAPES.setdefault(shape, make_shape(shape, {"no_override", bug}))
        rows = [r for r in run_eval(shape, spec)["rows"] if fm in items[r["item_id"]]["failure_modes"]]
        missed = sorted({r["item_id"] for r in rows if not flagged(r)})
        by_mode[fm] = {"bug": bug, "trials": len(rows), "detected": sum(flagged(r) for r in rows), "missed_items": missed}
    fixed_rows = run_eval("fixed", spec)["rows"]
    trials = sum(m["trials"] for m in by_mode.values())
    detected = sum(m["detected"] for m in by_mode.values())
    false_alarms = sum(flagged(r) for r in fixed_rows)
    sha = evalset.sha12(Path(spec["eval_set"]))
    return {"run_id": f"E-fm_detection-{date.today():%Y%m%d}-{sha[:4]}", "eval_set_sha": sha, "by_mode": by_mode,
            "detected": detected, "trials": trials, "detection_rate": round(detected / trials, 4),
            "fixed_false_alarms": false_alarms, "fixed_trials": len(fixed_rows),
            "false_alarm_rate": round(false_alarms / len(fixed_rows), 4)}


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.fm_detection")
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--out", default="reports/fm_detection.json")
    args = ap.parse_args(argv)
    rep = measure(load_spec(Path(args.spec)))
    for fm, m in rep["by_mode"].items():
        print(f"  {fm} {m['bug']:<15} {m['detected']}/{m['trials']} missed={m['missed_items']}")
    print(f"{rep['run_id']}: detection {rep['detected']}/{rep['trials']} = {rep['detection_rate']:.3f}; "
          f"false alarms on fixed {rep['fixed_false_alarms']}/{rep['fixed_trials']} = {rep['false_alarm_rate']:.3f}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    return 0 if rep["detection_rate"] >= MIN_DETECTION and rep["false_alarm_rate"] <= MAX_FALSE_ALARM else 1


if __name__ == "__main__":
    raise SystemExit(main())
