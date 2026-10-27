"""Evaluation metrics: Field-level F1, Exact Match, and Paired Bootstrap CI."""

from typing import Any

import numpy as np

EVAL_FIELDS = [
    "city",
    "locality",
    "bhk",
    "property_type",
    "transaction",
    "budget_min",
    "budget_max",
    "furnishing",
    "possession",
    "price_preference",
]


def _normalize_val(val: Any) -> Any:
    """Normalize values for fair comparison (strip strings, handle floats/ints)."""
    if val is None:
        return None
    if isinstance(val, str):
        cleaned = val.strip().lower()
        return cleaned if cleaned else None
    if isinstance(val, (int, float)):
        return round(float(val))
    return val


def compute_field_confusion(
    predictions: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    field: str,
) -> dict[str, int]:
    """Calculate TP, FP, FN for a single field across all queries."""
    tp, fp, fn = 0, 0, 0
    for pred, gold in zip(predictions, ground_truth, strict=False):
        p_val = _normalize_val(pred.get(field))
        g_val = _normalize_val(gold.get(field))

        if p_val is not None and g_val is not None:
            if p_val == g_val:
                tp += 1
            else:
                fp += 1
                fn += 1
        elif p_val is not None and g_val is None:
            fp += 1
        elif p_val is None and g_val is not None:
            fn += 1

    return {"tp": tp, "fp": fp, "fn": fn}


def calculate_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Compute precision, recall, and F1 from confusion counts."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return round(precision * 100, 2), round(recall * 100, 2), round(f1 * 100, 2)


def evaluate_predictions(
    predictions: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Calculate Micro F1, Macro F1, Field-by-Field F1, and Exact Match Accuracy."""
    active_fields = fields or EVAL_FIELDS
    n = len(ground_truth)
    if n == 0 or len(predictions) != n:
        raise ValueError(f"Mismatched dataset lengths: {len(predictions)} predictions vs {n} gold")

    # 1. Exact Match
    exact_matches = 0
    for pred, gold in zip(predictions, ground_truth, strict=False):
        is_match = True
        for f in active_fields:
            if _normalize_val(pred.get(f)) != _normalize_val(gold.get(f)):
                is_match = False
                break
        if is_match:
            exact_matches += 1
    exact_match_acc = round((exact_matches / n) * 100, 2)

    # 2. Per-field and Micro totals
    total_tp, total_fp, total_fn = 0, 0, 0
    field_metrics: dict[str, dict[str, float]] = {}
    f1_list: list[float] = []

    for f in active_fields:
        counts = compute_field_confusion(predictions, ground_truth, f)
        p, r, f1 = calculate_f1(counts["tp"], counts["fp"], counts["fn"])
        field_metrics[f] = {"precision": p, "recall": r, "f1": f1}
        total_tp += counts["tp"]
        total_fp += counts["fp"]
        total_fn += counts["fn"]

        # Only include in Macro F1 if the field appeared in gold or prediction
        if counts["tp"] + counts["fp"] + counts["fn"] > 0:
            f1_list.append(f1)

    micro_p, micro_r, micro_f1 = calculate_f1(total_tp, total_fp, total_fn)
    macro_f1 = round(float(np.mean(f1_list)), 2) if f1_list else 0.0

    return {
        "num_queries": n,
        "exact_match_accuracy": exact_match_acc,
        "micro_precision": micro_p,
        "micro_recall": micro_r,
        "micro_f1": micro_f1,
        "macro_f1": macro_f1,
        "field_metrics": field_metrics,
    }


def paired_bootstrap_test(
    preds_a: list[dict[str, Any]],
    preds_b: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    num_bootstrap: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Compute paired bootstrap 95% confidence interval for (F1_a - F1_b).

    Used to test the pre-registered hypothesis:
    Cascade field-level F1 is within 3 points of B3 (lower bound of 95% CI > -3.0).
    """
    n = len(ground_truth)
    if not (len(preds_a) == len(preds_b) == n):
        raise ValueError("Lengths of preds_a, preds_b, and ground_truth must match")

    rng = np.random.default_rng(seed)
    diffs: list[float] = []

    for _ in range(num_bootstrap):
        sample_indices = rng.choice(n, size=n, replace=True)
        sub_gold = [ground_truth[i] for i in sample_indices]
        sub_a = [preds_a[i] for i in sample_indices]
        sub_b = [preds_b[i] for i in sample_indices]

        f1_a = evaluate_predictions(sub_a, sub_gold)["micro_f1"]
        f1_b = evaluate_predictions(sub_b, sub_gold)["micro_f1"]
        diffs.append(f1_a - f1_b)

    low_pct = (alpha / 2.0) * 100
    high_pct = (1.0 - alpha / 2.0) * 100
    ci_lower = round(float(np.percentile(diffs, low_pct)), 2)
    ci_upper = round(float(np.percentile(diffs, high_pct)), 2)
    mean_diff = round(float(np.mean(diffs)), 2)

    # Pre-registered check: CI lower bound must be > -3.0
    passes_preregistered = ci_lower > -3.0

    return {
        "num_bootstrap": num_bootstrap,
        "mean_diff": mean_diff,
        "ci_95_lower": ci_lower,
        "ci_95_upper": ci_upper,
        "passes_preregistered_margin": passes_preregistered,
    }


def compute_operational_stats(
    latencies_ms: list[float],
    costs_usd: list[float],
    escalations: list[bool] | None = None,
) -> dict[str, Any]:
    """Compute latency percentiles, average cost, and cost per 1k queries."""
    n = len(latencies_ms)
    if n == 0:
        return {}

    p50_latency = round(float(np.percentile(latencies_ms, 50)), 2)
    p95_latency = round(float(np.percentile(latencies_ms, 95)), 2)
    mean_latency = round(float(np.mean(latencies_ms)), 2)

    total_cost = sum(costs_usd)
    avg_cost = round(total_cost / n, 6)
    cost_per_1k = round(avg_cost * 1000.0, 4)

    stats: dict[str, Any] = {
        "latency_mean_ms": mean_latency,
        "latency_p50_ms": p50_latency,
        "latency_p95_ms": p95_latency,
        "total_cost_usd": round(total_cost, 6),
        "avg_cost_usd": avg_cost,
        "cost_per_1k_queries": cost_per_1k,
    }

    if escalations is not None and len(escalations) == n:
        escalation_rate = round((sum(1 for e in escalations if e) / n) * 100, 2)
        stats["escalation_rate_pct"] = escalation_rate

    return stats
