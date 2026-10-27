"""Unit tests for evaluation runner and plot generator."""

import json
from unittest.mock import patch

from PIL import Image

from eval.run_eval import generate_pareto_plot, load_dataset, run_evaluation
from src.baselines import ExtractionResult
from src.schema import SearchFilter


def test_load_dataset(tmp_path):
    data_file = tmp_path / "test_data.jsonl"
    data_file.write_text(
        '{"query": "noida 2bhk", "gold": {"city": "Noida", "bhk": 2}}\n'
        '# A comment line\n'
        '{"query": "delhi 1bhk", "gold": {"city": "Delhi", "bhk": 1}}\n',
        encoding="utf-8",
    )

    records = load_dataset(data_file)
    assert len(records) == 2
    assert records[0]["query"] == "noida 2bhk"
    assert records[0]["gold"]["city"] == "Noida"


def test_generate_pareto_plot(tmp_path):
    plot_file = tmp_path / "test_plot.png"
    systems_summary = {
        "b1_rules": {"micro_f1": 65.0, "cost_per_1k_queries": 0.0},
        "b2_cheap": {"micro_f1": 84.0, "cost_per_1k_queries": 0.08},
        "b3_large": {"micro_f1": 92.0, "cost_per_1k_queries": 0.22},
        "cascade": {"micro_f1": 90.5, "cost_per_1k_queries": 0.11},
    }

    generate_pareto_plot(systems_summary, plot_file)
    assert plot_file.exists()

    # Verify generated file is a valid PNG
    with Image.open(plot_file) as img:
        assert img.format == "PNG"
        assert img.size == (800, 500)


def test_run_evaluation_mocked(tmp_path):
    data_file = tmp_path / "dev_sample.jsonl"
    entries = [
        {"query": "noida 2bhk", "gold": {"city": "Noida", "bhk": 2}},
        {"query": "gurgaon 3bhk", "gold": {"city": "Gurugram", "bhk": 3}},
    ]
    with open(data_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(e) + "\n" for e in entries)

    fake_res = ExtractionResult(
        filter=SearchFilter(city="Noida", bhk=2),
        tier="cascade_tier1",
        confidence=0.9,
        latency_ms=100.0,
        cost_usd=0.0001,
        input_tokens=50,
        output_tokens=30,
        cached=True,
        escalated=False,
    )

    out_dir = tmp_path / "results"
    with (
        patch("eval.run_eval.parse_b1", return_value=fake_res),
        patch("eval.run_eval.parse_b2", return_value=fake_res),
        patch("eval.run_eval.parse_b3", return_value=fake_res),
        patch("eval.run_eval.parse_cascade", return_value=fake_res),
    ):
        summary = run_evaluation(data_file, output_dir=out_dir)

    assert "systems" in summary
    assert "b1_rules" in summary["systems"]
    assert "cascade" in summary["systems"]
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "cost_vs_accuracy.png").exists()
