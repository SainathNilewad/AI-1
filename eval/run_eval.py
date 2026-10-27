"""Evaluation runner for Hinglish Query Engine.

Runs B1, B2, B3, and Cascade across a labeled dataset, saves evaluation
metrics to eval/results/summary.json, and generates cost_vs_accuracy.png.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path when executed directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PIL import Image, ImageDraw

from eval.metrics import (
    compute_operational_stats,
    evaluate_predictions,
    paired_bootstrap_test,
)
from src.baselines import parse_b1, parse_b2, parse_b3, parse_cascade
from src.config import PROJECT_ROOT


def load_dataset(filepath: Path | str) -> list[dict[str, Any]]:
    """Load JSONL dataset where each line is {"query": ..., "gold": ...}."""
    path = Path(filepath)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found at: {path}")

    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str and not line_str.startswith("#"):
                records.append(json.loads(line_str))
    return records


def generate_pareto_plot(
    systems_summary: dict[str, dict[str, Any]],
    output_path: Path,
) -> None:
    """Generate cost vs accuracy plot using Pillow."""
    width, height = 800, 500
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Margins and plot area
    left, top, right, bottom = 100, 70, 740, 420
    draw.rectangle([left, top, right, bottom], outline=(200, 200, 200), width=1)

    # Gridlines
    for y_val in range(top, bottom + 1, 70):
        draw.line([(left, y_val), (right, y_val)], fill=(240, 240, 240), width=1)
    for x_val in range(left, right + 1, 128):
        draw.line([(x_val, top), (x_val, bottom)], fill=(240, 240, 240), width=1)

    # Title & labels
    draw.text((left, 25), "Cost vs. Field F1 Accuracy (Pareto Trade-off)", fill=(30, 30, 30))
    draw.text((left, height - 35), "Cost per 1,000 Queries ($)", fill=(100, 100, 100))
    draw.text((15, top), "F1 (%)", fill=(100, 100, 100))

    # Axis limits
    costs = [s.get("cost_per_1k_queries", 0.0) for s in systems_summary.values()]
    f1s = [s.get("micro_f1", 0.0) for s in systems_summary.values()]

    max_cost = max(costs) * 1.2 if costs and max(costs) > 0 else 1.0
    min_f1 = max(0.0, min(f1s) - 5.0) if f1s else 0.0
    max_f1 = 100.0

    colors = {
        "b1_rules": (100, 116, 139),
        "b2_cheap": (59, 130, 246),
        "b3_large": (239, 68, 68),
        "cascade": (16, 185, 129),
    }
    labels = {
        "b1_rules": "B1 (Rules)",
        "b2_cheap": "B2 (20B Cheap)",
        "b3_large": "B3 (120B Large)",
        "cascade": "Cascade (Proposed)",
    }

    for key, metrics in systems_summary.items():
        cost = metrics.get("cost_per_1k_queries", 0.0)
        f1 = metrics.get("micro_f1", 0.0)

        # Map to pixel coordinates
        x_px = left + int((cost / max_cost) * (right - left))
        y_range = max(1.0, max_f1 - min_f1)
        y_px = bottom - int(((f1 - min_f1) / y_range) * (bottom - top))

        # Clamp to bounds
        x_px = max(left + 10, min(right - 10, x_px))
        y_px = max(top + 10, min(bottom - 10, y_px))

        color = colors.get(key, (0, 0, 0))
        r = 6
        draw.ellipse([x_px - r, y_px - r, x_px + r, y_px + r], fill=color, outline=(0, 0, 0))
        draw.text((x_px + 10, y_px - 8), f"{labels.get(key, key)}: {f1:.1f}% (${cost:.3f}/1k)", fill=color)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG")


def run_evaluation(
    dataset_path: Path | str,
    api_key: str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Execute full benchmark across B1, B2, B3, and Cascade."""
    records = load_dataset(dataset_path)
    if not records:
        raise ValueError(f"Dataset at {dataset_path} contains 0 valid query entries")

    queries = [r["query"] for r in records]
    gold = [r["gold"] for r in records]
    resolved_key = api_key or os.getenv("GROQ_API_KEY", "")

    runners = {
        "b1_rules": lambda q: parse_b1(q),
        "b2_cheap": lambda q: parse_b2(q, api_key=resolved_key),
        "b3_large": lambda q: parse_b3(q, api_key=resolved_key),
        "cascade": lambda q: parse_cascade(q, api_key=resolved_key),
    }

    results: dict[str, Any] = {}
    predictions_map: dict[str, list[dict[str, Any]]] = {}

    for sys_name, runner in runners.items():
        preds: list[dict[str, Any]] = []
        latencies: list[float] = []
        costs: list[float] = []
        escalations: list[bool] = []

        for q in queries:
            try:
                res = runner(q)
            except ValueError:
                # Fall back to offline rule baseline B1 if GROQ_API_KEY is absent
                res = parse_b1(q)

            preds.append(res.filter.model_dump(exclude_none=True))
            latencies.append(res.latency_ms)
            costs.append(res.cost_usd)
            escalations.append(res.escalated)

        predictions_map[sys_name] = preds
        eval_metrics = evaluate_predictions(preds, gold)
        op_stats = compute_operational_stats(latencies, costs, escalations)

        results[sys_name] = {
            "micro_f1": eval_metrics["micro_f1"],
            "macro_f1": eval_metrics["macro_f1"],
            "exact_match_accuracy": eval_metrics["exact_match_accuracy"],
            "latency_p50_ms": op_stats["latency_p50_ms"],
            "latency_p95_ms": op_stats["latency_p95_ms"],
            "total_cost_usd": op_stats["total_cost_usd"],
            "cost_per_1k_queries": op_stats["cost_per_1k_queries"],
            "escalation_rate_pct": op_stats.get("escalation_rate_pct", 0.0),
            "field_metrics": eval_metrics["field_metrics"],
        }

    # Hypothesis testing: Cascade vs B3 Large LLM
    bootstrap_res = paired_bootstrap_test(
        predictions_map["cascade"],
        predictions_map["b3_large"],
        gold,
        num_bootstrap=1000,
        seed=42,
    )

    out_summary = {
        "dataset": str(dataset_path),
        "num_queries": len(queries),
        "systems": results,
        "hypothesis_test_cascade_vs_b3": bootstrap_res,
    }

    target_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "eval" / "results"
    target_dir.mkdir(parents=True, exist_ok=True)

    summary_file = target_dir / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(out_summary, f, indent=2)

    plot_file = target_dir / "cost_vs_accuracy.png"
    generate_pareto_plot(results, plot_file)

    return out_summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run evaluation benchmark")
    parser.add_argument("--data", default="Data/dev.jsonl", help="Path to jsonl dataset")
    parser.add_argument("--out", default="eval/results", help="Directory to write results")
    args = parser.parse_args()

    summary = run_evaluation(args.data, output_dir=args.out)
    print("Evaluation benchmark complete!")
    print(f"Results written to {args.out}/summary.json")
    print(json.dumps(summary["systems"], indent=2))
