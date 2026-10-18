"""Metrics for accuracy, calibration, selective prediction and paired comparison.

Conventions: `conf` is the top-1 probability, `correct` is a 0/1 array,
`probs_true` is the probability assigned to the true label.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.stats import binomtest
from sklearn.metrics import f1_score

EPS = 1e-12


# ---------- accuracy and proper scoring rules ----------

def accuracy(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    return float(np.mean(np.asarray(y_true) == np.asarray(y_pred)))


def macro_f1(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    return float(f1_score(y_true, y_pred, average="macro", zero_division=0))


def brier(prob_matrix: np.ndarray, true_idx: np.ndarray) -> float:
    """Multiclass Brier score: mean over items of sum_k (p_k - 1[k = y])^2. Lower is better."""
    onehot = np.zeros_like(prob_matrix)
    onehot[np.arange(len(true_idx)), true_idx] = 1.0
    return float(np.mean(np.sum((prob_matrix - onehot) ** 2, axis=1)))


def log_loss(probs_true: np.ndarray) -> float:
    return float(-np.mean(np.log(np.clip(probs_true, EPS, 1.0))))


# ---------- calibration ----------

@dataclass
class ReliabilityBin:
    lo: float
    hi: float
    count: int
    mean_conf: float
    accuracy: float


def reliability_bins(conf: np.ndarray, correct: np.ndarray, n_bins: int = 10) -> list[ReliabilityBin]:
    """Equal-width bins over [0, 1]. Empty bins are kept with count 0."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(conf, edges[1:-1], right=True), 0, n_bins - 1)
    bins = []
    for b in range(n_bins):
        mask = idx == b
        n = int(mask.sum())
        bins.append(ReliabilityBin(
            lo=float(edges[b]), hi=float(edges[b + 1]), count=n,
            mean_conf=float(conf[mask].mean()) if n else float("nan"),
            accuracy=float(correct[mask].mean()) if n else float("nan"),
        ))
    return bins


def ece(conf: np.ndarray, correct: np.ndarray, n_bins: int = 10) -> float:
    """Expected calibration error, equal-width bins. Bin count is reported alongside: ECE depends on it."""
    total = len(conf)
    if total == 0:
        return float("nan")
    return float(sum(
        b.count / total * abs(b.mean_conf - b.accuracy)
        for b in reliability_bins(conf, correct, n_bins) if b.count
    ))


# ---------- selective prediction ----------

@dataclass
class RiskCoverage:
    coverage: np.ndarray  # fraction of items auto-handled, ascending
    risk: np.ndarray  # error rate among auto-handled items
    thresholds: np.ndarray  # confidence of the last item accepted at each coverage


def _sorted_risk(conf: np.ndarray, correct: np.ndarray):
    order = np.argsort(-conf, kind="stable")
    c = conf[order]
    n = np.arange(1, len(conf) + 1)
    risk = np.cumsum(1 - correct[order]) / n
    # A threshold cannot split items with equal confidence, so only the last
    # position of each tie group is an achievable operating point.
    group_end = np.r_[c[1:] != c[:-1], True]
    return c, n, risk, group_end


def risk_coverage(conf: np.ndarray, correct: np.ndarray) -> RiskCoverage:
    """Accept items from most to least confident; error rate at every achievable coverage."""
    c, n, risk, end = _sorted_risk(conf, correct)
    return RiskCoverage(coverage=n[end] / len(conf), risk=risk[end], thresholds=c[end])


def aurc(conf: np.ndarray, correct: np.ndarray) -> float:
    """Area under the risk-coverage curve. Lower is better; rewards ranking errors last.

    Each item contributes the risk at the end of its tie group, so tied
    confidences are not credited with an arbitrary within-tie order.
    """
    _, _, risk, end = _sorted_risk(conf, correct)
    group_risk = risk[end]
    group_id = np.r_[0, np.cumsum(end)[:-1]]
    return float(np.mean(group_risk[group_id]))


def coverage_at_risk(conf: np.ndarray, correct: np.ndarray, max_risk: float) -> tuple[float, float]:
    """Largest coverage whose selective error <= max_risk, and the confidence threshold that achieves it."""
    rc = risk_coverage(conf, correct)
    ok = np.where(rc.risk <= max_risk)[0]
    if len(ok) == 0:
        return 0.0, 1.0
    i = ok.max()
    return float(rc.coverage[i]), float(rc.thresholds[i])


@dataclass
class DeferralPolicy:
    threshold: float
    coverage: float
    selective_error: float
    cost_per_item: float


def best_deferral_policy(
    conf: np.ndarray, correct: np.ndarray, cost_error: float, cost_defer: float
) -> DeferralPolicy:
    """Choose the confidence threshold minimizing expected cost per item.

    Items at or above the threshold are auto-handled (cost_error when wrong);
    the rest are deferred to a person or a fallback model (cost_defer each).
    """
    n = len(conf)
    rc = risk_coverage(conf, correct)
    accepted = rc.coverage * n
    cost = (rc.risk * accepted * cost_error + (n - accepted) * cost_defer) / n
    defer_all = cost_defer
    i = int(np.argmin(cost))
    if defer_all <= cost[i]:
        return DeferralPolicy(threshold=1.01, coverage=0.0, selective_error=0.0, cost_per_item=defer_all)
    return DeferralPolicy(
        threshold=float(rc.thresholds[i]), coverage=float(rc.coverage[i]),
        selective_error=float(rc.risk[i]), cost_per_item=float(cost[i]),
    )


# ---------- uncertainty and paired tests ----------

def grouped_bootstrap_ci(
    statistic: Callable[[np.ndarray], float],
    groups: Sequence[str],
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile CI that resamples whole groups (source tables), not individual columns.

    `statistic` receives an index array into the original items.
    """
    groups = np.asarray(groups)
    uniq = np.unique(groups)
    members = {g: np.where(groups == g)[0] for g in uniq}
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(n_boot):
        picked = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([members[g] for g in picked])
        stats.append(statistic(idx))
    lo, hi = np.nanpercentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


@dataclass
class McNemar:
    a_only: int  # A right, B wrong
    b_only: int  # A wrong, B right
    p_value: float


def mcnemar(correct_a: np.ndarray, correct_b: np.ndarray) -> McNemar:
    """Exact McNemar test for two classifiers scored on the same items."""
    a_only = int(np.sum((correct_a == 1) & (correct_b == 0)))
    b_only = int(np.sum((correct_a == 0) & (correct_b == 1)))
    n = a_only + b_only
    p = 1.0 if n == 0 else float(binomtest(min(a_only, b_only), n, 0.5).pvalue)
    return McNemar(a_only, b_only, p)


def flip_rate(labels_a: Sequence[str | None], labels_b: Sequence[str | None]) -> float:
    """Share of items whose predicted label changes between two conditions."""
    a, b = np.asarray(labels_a, dtype=object), np.asarray(labels_b, dtype=object)
    return float(np.mean(a != b))
