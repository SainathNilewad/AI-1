"""Unit tests for evaluation metrics, Exact Match, and Paired Bootstrap CI."""

import pytest

from eval.metrics import (
    calculate_f1,
    compute_field_confusion,
    compute_operational_stats,
    evaluate_predictions,
    paired_bootstrap_test,
)


def test_calculate_f1_basic():
    # TP=10, FP=0, FN=0 -> 100%
    p, r, f1 = calculate_f1(10, 0, 0)
    assert p == 100.0 and r == 100.0 and f1 == 100.0

    # TP=5, FP=5, FN=5 -> P=50%, R=50%, F1=50%
    p, r, f1 = calculate_f1(5, 5, 5)
    assert p == 50.0 and r == 50.0 and f1 == 50.0

    # TP=0, FP=5, FN=5 -> F1=0%
    p, r, f1 = calculate_f1(0, 5, 5)
    assert f1 == 0.0


def test_field_confusion_counting():
    gold = [
        {"city": "Noida", "bhk": 2},
        {"city": "Gurugram", "bhk": 3},
        {"city": None, "bhk": 1},
    ]
    preds = [
        {"city": "noida", "bhk": 2},  # city match (case-insensitive), bhk match
        {"city": "Delhi", "bhk": 3},  # city mismatch (FP+FN), bhk match
        {"city": "Mumbai", "bhk": None},  # city unexpected (FP), bhk missed (FN)
    ]

    city_counts = compute_field_confusion(preds, gold, "city")
    assert city_counts["tp"] == 1  # noida
    assert city_counts["fp"] == 2  # Delhi (mismatch) + Mumbai (unexpected)
    assert city_counts["fn"] == 1  # Gurugram missed

    bhk_counts = compute_field_confusion(preds, gold, "bhk")
    assert bhk_counts["tp"] == 2  # 2, 3
    assert bhk_counts["fp"] == 0
    assert bhk_counts["fn"] == 1  # 1 missed


def test_evaluate_predictions_perfect_match():
    gold = [
        {"city": "Noida", "bhk": 2, "budget_max": 50000},
        {"city": "Bengaluru", "bhk": 3, "property_type": "flat"},
    ]
    preds = [
        {"city": "Noida", "bhk": 2, "budget_max": 50000},
        {"city": "Bengaluru", "bhk": 3, "property_type": "flat"},
    ]

    res = evaluate_predictions(preds, gold)
    assert res["exact_match_accuracy"] == 100.0
    assert res["micro_f1"] == 100.0
    assert res["macro_f1"] == 100.0


def test_evaluate_predictions_mismatched_length_raises():
    with pytest.raises(ValueError, match="Mismatched dataset lengths"):
        evaluate_predictions([{"city": "Noida"}], [{"city": "Noida"}, {"city": "Delhi"}])


def test_paired_bootstrap_test():
    gold = [
        {"city": "Noida", "bhk": 2},
        {"city": "Gurugram", "bhk": 3},
        {"city": "Delhi", "bhk": 1},
        {"city": "Mumbai", "bhk": 4},
    ] * 10  # 40 items

    # Model A and Model B identical
    preds_a = list(gold)
    preds_b = list(gold)

    res = paired_bootstrap_test(preds_a, preds_b, gold, num_bootstrap=200, seed=42)
    assert res["mean_diff"] == 0.0
    assert res["ci_95_lower"] == 0.0
    assert res["ci_95_upper"] == 0.0
    assert res["passes_preregistered_margin"] is True


def test_compute_operational_stats():
    latencies = [100.0, 150.0, 200.0, 250.0, 300.0]
    costs = [0.0001, 0.0002, 0.0001, 0.0003, 0.0001]
    escalations = [False, False, True, False, False]

    stats = compute_operational_stats(latencies, costs, escalations)
    assert stats["latency_p50_ms"] == 200.0
    assert stats["latency_mean_ms"] == 200.0
    assert stats["latency_p95_ms"] == 290.0
    assert stats["total_cost_usd"] == 0.0008
    assert stats["cost_per_1k_queries"] == 0.16  # 0.00016 * 1000
    assert stats["escalation_rate_pct"] == 20.0  # 1 out of 5
