"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb, isclose

import numpy as np
from scipy.stats import bootstrap

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for truth, verdict in zip(human, judge, strict=True):
        if verdict == POS:
            counts["tp" if truth == POS else "fp"] += 1
        else:
            counts["fn" if truth == POS else "tn"] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    """Precision: of the replies the judge failed, how many really fail.
    Recall: of the replies that really fail, how many the judge caught."""
    c = confusion(human, judge)
    flagged = c["tp"] + c["fp"]
    actual = c["tp"] + c["fn"]
    return (c["tp"] / flagged if flagged else 0.0, c["tp"] / actual if actual else 0.0)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    c = confusion(human, judge)
    n = sum(c.values())
    if n == 0:
        raise ValueError("kappa is undefined for empty input")
    p_o = (c["tp"] + c["tn"]) / n
    human_fail, judge_fail = (c["tp"] + c["fn"]) / n, (c["tp"] + c["fp"]) / n
    # Agreement expected by chance if human and judge labelled independently.
    p_e = human_fail * judge_fail + (1 - human_fail) * (1 - judge_fail)
    if isclose(p_e, 1.0):
        raise ValueError("kappa is undefined when chance agreement is 1")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1].
    Return NaN when sensitivity + specificity == 1: such a judge flags failures and good
    replies at the same rate, so its output says nothing about the true rate."""
    denominator = sensitivity + specificity - 1
    if isclose(denominator, 0.0, abs_tol=1e-12):
        return float("nan")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / denominator))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    first, second = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if first.shape != second.shape:
        raise ValueError("paired samples must have the same length")
    if np.array_equal(first, second):
        return 0.0, 0.0, 0.0

    def mean_difference(x: np.ndarray, y: np.ndarray, axis: int = -1) -> np.ndarray:
        return np.mean(x, axis=axis) - np.mean(y, axis=axis)

    # paired=True resamples whole items, so each item stays matched with itself in both versions.
    interval = bootstrap((first, second), mean_difference, paired=True, vectorized=True,
                         n_resamples=n_resamples, confidence_level=confidence,
                         method="percentile", rng=np.random.default_rng(rng)).confidence_interval
    return float(mean_difference(first, second)), float(interval.low), float(interval.high)


def _check_trials(n: int, c: int, k: int) -> None:
    """n trials, c of them passing, k drawn: require 0 <= c <= n and 1 <= k <= n."""
    if not 0 <= c <= n:
        raise ValueError(f"c must be between 0 and n, got n={n}, c={c}")
    if not 1 <= k <= n:
        raise ValueError(f"k must be between 1 and n, got n={n}, k={k}")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _check_trials(n, c, k)
    return 1 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _check_trials(n, c, k)
    return comb(c, k) / comb(n, k)
