import numpy as np
import pytest

from jeveval import metrics as M


def test_ece_zero_when_confidence_matches_accuracy():
    # 10 items at confidence 0.8, 8 correct -> perfectly calibrated.
    conf = np.full(10, 0.8)
    correct = np.array([1] * 8 + [0] * 2)
    assert M.ece(conf, correct) == pytest.approx(0.0)


def test_ece_detects_overconfidence():
    conf = np.full(10, 0.95)
    correct = np.array([1] * 5 + [0] * 5)
    assert M.ece(conf, correct) == pytest.approx(0.45)


def test_brier_and_log_loss_perfect_prediction():
    P = np.array([[1.0, 0.0], [0.0, 1.0]])
    assert M.brier(P, np.array([0, 1])) == pytest.approx(0.0)
    assert M.log_loss(np.array([1.0, 1.0])) == pytest.approx(0.0)


def test_risk_coverage_orders_by_confidence():
    conf = np.array([0.9, 0.8, 0.7, 0.6])
    correct = np.array([1, 1, 0, 0])
    rc = M.risk_coverage(conf, correct)
    np.testing.assert_allclose(rc.coverage, [0.25, 0.5, 0.75, 1.0])
    np.testing.assert_allclose(rc.risk, [0.0, 0.0, 1 / 3, 0.5])
    assert M.coverage_at_risk(conf, correct, 0.05) == (0.5, 0.8)


def test_ties_are_one_operating_point():
    # Same confidence for a right and a wrong item: input order must not matter.
    conf = np.array([0.9, 0.5, 0.5])
    a = M.risk_coverage(conf, np.array([1, 1, 0]))
    b = M.risk_coverage(conf, np.array([1, 0, 1]))
    np.testing.assert_allclose(a.coverage, [1 / 3, 1.0])
    np.testing.assert_allclose(a.risk, b.risk)
    assert M.aurc(conf, np.array([1, 1, 0])) == pytest.approx(M.aurc(conf, np.array([1, 0, 1])))


def test_aurc_rewards_putting_errors_last():
    correct = np.array([1, 1, 0, 0])
    good = M.aurc(np.array([0.9, 0.8, 0.2, 0.1]), correct)
    bad = M.aurc(np.array([0.1, 0.2, 0.8, 0.9]), correct)
    assert good < bad


def test_deferral_policy_defers_errors_when_cheap():
    conf = np.array([0.9, 0.8, 0.3, 0.2])
    correct = np.array([1, 1, 0, 0])
    policy = M.best_deferral_policy(conf, correct, cost_error=1.0, cost_defer=0.1)
    assert policy.coverage == 0.5
    assert policy.threshold == 0.8
    assert policy.cost_per_item == pytest.approx(0.05)


def test_mcnemar_counts_discordant_pairs():
    a = np.array([1, 1, 1, 1, 0, 1])
    b = np.array([0, 0, 0, 1, 0, 1])
    r = M.mcnemar(a, b)
    assert (r.a_only, r.b_only) == (3, 0)
    assert r.p_value == pytest.approx(0.25)


def test_grouped_bootstrap_ci_brackets_point_estimate():
    correct = np.array([1, 1, 0, 1, 0, 1, 1, 1])
    groups = ["a", "a", "b", "b", "c", "c", "d", "d"]
    lo, hi = M.grouped_bootstrap_ci(lambda idx: correct[idx].mean(), groups, n_boot=500)
    assert lo <= correct.mean() <= hi


def test_flip_rate():
    assert M.flip_rate(["a", "b", "c", "d"], ["a", "x", "c", "y"]) == 0.5
