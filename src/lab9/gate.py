"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = _structure_problems(pr, "PR") + _structure_problems(base, "baseline")
    problems += _row_value_problems(pr, spec)
    problems += _metric_mismatches(pr, spec)

    pr_tags, base_tags = _slice_tags(pr), _slice_tags(base)
    missing, extra = sorted(base_tags.keys() - pr_tags.keys()), sorted(pr_tags.keys() - base_tags.keys())
    if missing or extra:
        problems.append(f"(item, seed) set differs from baseline: {len(missing)} missing, {len(extra)} extra")
    relabelled = sorted({key[0] for key in pr_tags.keys() & base_tags.keys() if pr_tags[key] != base_tags[key]})
    if relabelled:
        problems.append(f"slice tags differ from baseline for {relabelled}")

    if base_spec is not None and base_spec.get("eval_set_version") == spec.get("eval_set_version"):
        problems += _ratchet_problems(spec, base_spec)
    return problems


def _structure_problems(report: dict, name: str) -> list[str]:
    """Checks that need no spec: bad metric values, crashed graders, wrong or repeated rows."""
    problems = [f"{name} metric {metric} is {value}" for metric, value in report["metrics"].items()
                if isinstance(value, float) and not math.isfinite(value)]
    if report.get("evaluator_failures"):
        problems.append(f"{name} has {len(report['evaluator_failures'])} evaluator failure(s)")
    manifest = report["manifest"]
    expected = manifest["items"] * len(manifest["seeds"])
    if len(report["rows"]) != expected:
        problems.append(f"{name} has {len(report['rows'])} rows, manifest requires {expected}")
    keys = [(row["item_id"], row["seed"]) for row in report["rows"]]
    if len(set(keys)) != len(keys):
        problems.append(f"{name} has {len(keys) - len(set(keys))} duplicated (item, seed) row(s)")
    return problems


def _graded_metrics(spec: dict) -> list[str]:
    return [metric["id"] for metric in spec["metrics"] if metric["id"] in GRADERS]


def _row_value_problems(report: dict, spec: dict) -> list[str]:
    """A grader verdict must be True or False. None or NaN would silently leave the mean."""
    bad: dict[str, int] = {}
    for row in report["rows"]:
        for metric in _graded_metrics(spec):
            if not isinstance(row.get(metric), bool):
                bad[metric] = bad.get(metric, 0) + 1
    return [f"{metric} has no valid verdict on {count} row(s)" for metric, count in bad.items()]


def _metric_mismatches(report: dict, spec: dict) -> list[str]:
    """The summary must equal what its own rows give, so editing a number alone is caught."""
    rows = report["rows"]
    metric_ids = [m for m in _graded_metrics(spec) if all(isinstance(row.get(m), bool) for row in rows)]
    has_cost = all("cost" in row for row in rows)
    recomputed = aggregate([{"cost": 0.0, **row} for row in rows], metric_ids, k_values=spec.get("pass_k", []))
    problems = []
    for metric, value in recomputed.items():
        stated = report["metrics"].get(metric)
        if metric == "cost_per_success" and not has_cost:
            continue
        if isinstance(stated, (int, float)) and value is not None and not math.isclose(stated, value, abs_tol=1e-9):
            problems.append(f"metric {metric} says {stated}, its rows give {value}")
    return problems


def _slice_tags(report: dict) -> dict[tuple[str, int], tuple[str, ...]]:
    return {(row["item_id"], row["seed"]): tuple(sorted(row.get("slices") or [])) for row in report["rows"]}


def _looser(name: str, new: dict, old: dict) -> list[str]:
    """How `new` weakens `old`. Works on a metric threshold and on a slice entry."""
    problems = []
    if "max" in old and new.get("max", math.inf) > old["max"]:
        problems.append(f"{name}: max loosened from {old['max']} to {new.get('max')}")
    if "min" in old and new.get("min", -math.inf) < old["min"]:
        problems.append(f"{name}: min loosened from {old['min']} to {new.get('min')}")
    if "max_increase" in old and new.get("max_increase", math.inf) > old["max_increase"]:
        problems.append(f"{name}: max_increase loosened from {old['max_increase']} to {new.get('max_increase')}")
    if old.get("no_significant_drop") and not new.get("no_significant_drop"):
        problems.append(f"{name}: no_significant_drop removed")
    return problems


def _ratchet_problems(spec: dict, base_spec: dict) -> list[str]:
    """On one eval-set version, a spec may get stricter but never weaker."""
    problems = [f"spec field {field} changed on the same eval-set version"
                for field in ("eval_set", "labels", "seeds", "bootstrap") if spec.get(field) != base_spec.get(field)]
    new_metrics = {metric["id"]: metric for metric in spec["metrics"]}
    for old in base_spec["metrics"]:
        new = new_metrics.get(old["id"])
        if new is None:
            problems.append(f"metric {old['id']} removed")
            continue
        if old.get("blocking") and not new.get("blocking"):
            problems.append(f"metric {old['id']} is no longer blocking")
        problems += _looser(f"metric {old['id']}", new.get("threshold") or {}, old.get("threshold") or {})
    new_slices = {(entry["name"], entry["metric"]): entry for entry in spec.get("slices") or []}
    for old in base_spec.get("slices") or []:
        name = f"slice {old['name']}/{old['metric']}"
        new = new_slices.get((old["name"], old["metric"]))
        if new is None:
            problems.append(f"{name} removed")
            continue
        if old.get("blocking") and not new.get("blocking"):
            problems.append(f"{name} is no longer blocking")
        problems += _looser(name, new, old)
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for entry in spec.get("slices") or []:
        name, metric = entry["name"], entry["metric"]
        slice_id = f"slice:{name}/{metric}"
        pr_items = per_item(pr, metric, slice_name=name)
        base_items = per_item(base, metric, slice_name=name)
        note = ""
        if not pr_items:
            # An empty slice proves nothing, so it must not count as a pass.
            value, failed = None, True
            note = "no rows in this slice"
        else:
            value = sum(pr_items.values()) / len(pr_items)
            failed = "min" in entry and value < entry["min"]
            keys = sorted(set(pr_items) & set(base_items))
            if entry.get("no_significant_drop") and keys:
                d, lo, hi = stats.paired_bootstrap([pr_items[k] for k in keys], [base_items[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                failed = failed or hi < 0
        if failed and entry.get("blocking"):
            blocked.append(slice_id)
        label = "ok" if not failed else "BLOCK" if entry.get("blocking") else "warn"
        shown = "None" if value is None else f"{value:.4f}"
        lines.append(f"  {slice_id:<36} {shown:<8} n={len(pr_items):<3} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
