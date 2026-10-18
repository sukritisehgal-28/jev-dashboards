"""Turn cached predictions into results.csv, summary.md and figures."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from . import metrics as M
from .labels import COLUMN_TYPES
from .types import Example, Prediction

LABELS = list(COLUMN_TYPES)
N_BINS = 10
TARGET_RISK = 0.05


def _arrays(examples: list[Example], preds: dict[str, Prediction]):
    """Align predictions to examples; only examples with a prediction are kept."""
    kept = [e for e in examples if e.id in preds]
    y = [e.label for e in kept]
    yhat = [preds[e.id].label for e in kept]
    P = np.array([[preds[e.id].probs.get(k, 0.0) for k in LABELS] for e in kept])
    true_idx = np.array([LABELS.index(e.label) for e in kept])
    conf = P.max(axis=1) if len(kept) else np.array([])
    correct = (np.array(yhat, dtype=object) == np.array(y, dtype=object)).astype(int)
    return kept, y, yhat, P, true_idx, conf, correct


def score(examples: list[Example], preds: dict[str, Prediction], cost_error: float, cost_defer: float) -> dict:
    kept, y, yhat, P, true_idx, conf, correct = _arrays(examples, preds)
    if not kept:
        return {}
    groups = [e.source for e in kept]
    acc_lo, acc_hi = M.grouped_bootstrap_ci(lambda idx: correct[idx].mean(), groups)
    cov, thr = M.coverage_at_risk(conf, correct, TARGET_RISK)
    policy = M.best_deferral_policy(conf, correct, cost_error, cost_defer)
    p_list = [preds[e.id] for e in kept]
    latencies = np.array([p.latency_ms for p in p_list])
    return {
        "n": len(kept),
        "accuracy": float(correct.mean()),
        "acc_ci_lo": acc_lo,
        "acc_ci_hi": acc_hi,
        "macro_f1": M.macro_f1(y, yhat),
        "ece": M.ece(conf, correct, N_BINS),
        "brier": M.brier(P, true_idx),
        "log_loss": M.log_loss(P[np.arange(len(kept)), true_idx]),
        "aurc": M.aurc(conf, correct),
        f"coverage_at_{int(TARGET_RISK * 100)}pct_error": cov,
        "threshold_at_target": thr,
        "policy_threshold": policy.threshold,
        "policy_coverage": policy.coverage,
        "policy_cost_per_item": policy.cost_per_item,
        "latency_p50_ms": float(np.percentile(latencies, 50)),
        "latency_p95_ms": float(np.percentile(latencies, 95)),
        "usd_per_1k": float(np.mean([p.cost_usd for p in p_list]) * 1000),
    }


def write_report(
    examples: list[Example], predictions: list[Prediction], run_dir: Path,
    cost_error: float = 1.0, cost_defer: float = 0.1,
) -> pd.DataFrame:
    by_cond: dict[tuple[str, str], dict[str, Prediction]] = defaultdict(dict)
    for p in predictions:
        by_cond[(p.predictor, p.variant)][p.example_id] = p

    rows = []
    for (predictor, variant), preds in sorted(by_cond.items()):
        s = score(examples, preds, cost_error, cost_defer)
        if not s:
            continue
        base = by_cond.get((predictor, "base"))
        if base and variant != "base":
            shared = [e.id for e in examples if e.id in preds and e.id in base]
            s["flip_rate_vs_base"] = M.flip_rate([base[i].label for i in shared], [preds[i].label for i in shared])
        rows.append({"predictor": predictor, "variant": variant, **s})
    df = pd.DataFrame(rows)
    df.to_csv(run_dir / "results.csv", index=False)

    md = [
        "# Evaluation summary",
        "",
        f"Columns scored per condition are in `n`. Accuracy CIs are 95% bootstrap intervals that resample "
        f"whole source tables. ECE uses {N_BINS} equal-width bins. Deferral policy: wrong automatic "
        f"decision costs {cost_error}, deferring to a person costs {cost_defer}.",
        "",
    ]
    if not df.empty:
        md += ["## All conditions", "", _table(df), ""]
        md += _paired_section(examples, by_cond)
        md += _per_label_section(examples, by_cond)
        md += _per_tag_section(examples, by_cond)
    (run_dir / "summary.md").write_text("\n".join(md))
    _figures(examples, by_cond, run_dir)
    return df


def _table(df: pd.DataFrame) -> str:
    cols = ["predictor", "variant", "n", "accuracy", "acc_ci_lo", "acc_ci_hi", "macro_f1", "ece",
            "brier", "aurc", f"coverage_at_{int(TARGET_RISK * 100)}pct_error", "flip_rate_vs_base",
            "latency_p50_ms", "usd_per_1k"]
    cols = [c for c in cols if c in df.columns]
    return df[cols].to_markdown(index=False, floatfmt=".3f")


def _paired_section(examples, by_cond) -> list[str]:
    """McNemar of every predictor against Jev on the base condition, same columns only."""
    jev = by_cond.get(("jev", "base"))
    if not jev:
        return []
    out = ["## Paired comparison against Jev (base condition, exact McNemar)", "",
           "| predictor | Jev right, other wrong | other right, Jev wrong | p-value |", "| --- | --- | --- | --- |"]
    for (predictor, variant), preds in sorted(by_cond.items()):
        if variant != "base" or predictor == "jev":
            continue
        shared = [e for e in examples if e.id in preds and e.id in jev]
        a = np.array([int(jev[e.id].label == e.label) for e in shared])
        b = np.array([int(preds[e.id].label == e.label) for e in shared])
        r = M.mcnemar(a, b)
        out.append(f"| {predictor} | {r.a_only} | {r.b_only} | {r.p_value:.3g} |")
    return out + [""]


def _per_label_section(examples, by_cond) -> list[str]:
    """Accuracy by true column type, base condition: where does each tier lose?"""
    base = {p: preds for (p, v), preds in by_cond.items() if v == "base"}
    if not base:
        return []
    header = "| true type | n | " + " | ".join(sorted(base)) + " |"
    out = ["## Accuracy by true column type (base condition)", "", header,
           "| --- | --- | " + " | ".join("---" for _ in base) + " |"]
    for label in LABELS:
        exs = [e for e in examples if e.label == label]
        if not exs:
            continue
        cells = []
        for p in sorted(base):
            got = [base[p][e.id].label == label for e in exs if e.id in base[p]]
            cells.append(f"{np.mean(got):.2f}" if got else "-")
        out.append(f"| {label} | {len(exs)} | " + " | ".join(cells) + " |")
    return out + [""]


def _per_tag_section(examples, by_cond) -> list[str]:
    """Accuracy on each hard-case tag, base condition, plus all columns not tagged ambiguous."""
    base = {p: preds for (p, v), preds in by_cond.items() if v == "base"}
    tags = sorted({t for e in examples for t in e.tags})
    if not base or not tags:
        return []
    slices = [(t, [e for e in examples if t in e.tags]) for t in tags]
    slices.append(("(all except ambiguous)", [e for e in examples if "ambiguous" not in e.tags]))
    out = ["## Accuracy by hard-case tag (base condition)", "",
           "| tag | n | " + " | ".join(sorted(base)) + " |",
           "| --- | --- | " + " | ".join("---" for _ in base) + " |"]
    for tag, exs in slices:
        cells = []
        for p in sorted(base):
            got = [base[p][e.id].label == e.label for e in exs if e.id in base[p]]
            cells.append(f"{np.mean(got):.2f}" if got else "-")
        out.append(f"| {tag} | {len(exs)} | " + " | ".join(cells) + " |")
    return out + [""]


def _figures(examples, by_cond, run_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base = {p: preds for (p, v), preds in by_cond.items() if v == "base"}
    if not base:
        return
    fig_dir = run_dir / "figures"
    fig_dir.mkdir(exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", linewidth=1, label="perfect calibration")
    for p, preds in sorted(base.items()):
        _, _, _, _, _, conf, correct = _arrays(examples, preds)
        bins = [b for b in M.reliability_bins(conf, correct, N_BINS) if b.count]
        ax.plot([b.mean_conf for b in bins], [b.accuracy for b in bins], marker="o", label=p)
    ax.set_xlabel("stated confidence (top-1 probability)")
    ax.set_ylabel("observed accuracy")
    ax.set_title("Reliability diagram, base condition")
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "reliability.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    for p, preds in sorted(base.items()):
        _, _, _, _, _, conf, correct = _arrays(examples, preds)
        rc = M.risk_coverage(conf, correct)
        ax.plot(rc.coverage, rc.risk, label=f"{p} (AURC {M.aurc(conf, correct):.3f})")
    ax.axhline(TARGET_RISK, linestyle="--", color="grey", linewidth=1, label=f"{TARGET_RISK:.0%} error target")
    ax.set_xlabel("coverage (share of decisions automated)")
    ax.set_ylabel("error rate among automated decisions")
    ax.set_title("Risk-coverage, base condition")
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "risk_coverage.png", dpi=150)
    plt.close(fig)
