"""
Unit tests for src/config_loader.py
"""

from pathlib import Path

import pytest

from src.config_loader import load_pricing_config, load_yaml


def test_load_pricing_config_success():
    """Verify that configs/prices.yaml loads correctly with required fields."""
    pricing = load_pricing_config()
    assert isinstance(pricing, dict)
    assert "effective_date" in pricing
    assert "currency" in pricing
    assert "models" in pricing
    assert "gpt-4o-mini" in pricing["models"]

    mini = pricing["models"]["gpt-4o-mini"]
    assert "input_cost_per_1m" in mini
    assert "output_cost_per_1m" in mini
    assert mini["input_cost_per_1m"] > 0
    assert mini["output_cost_per_1m"] > 0


def test_load_yaml_nonexistent_file():
    """Verify FileNotFoundError is raised when a config does not exist."""
    with pytest.raises(FileNotFoundError):
        load_yaml("configs/non_existent_config.yaml")


def test_load_yaml_empty_file(tmp_path: Path):
    """Verify ValueError is raised if a YAML file is completely empty."""
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        load_yaml(empty_file)


def test_load_yaml_non_dict_file(tmp_path: Path):
    """Verify ValueError is raised if root YAML element is a list instead of a dict."""
    list_file = tmp_path / "list.yaml"
    list_file.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping/dict"):
        load_yaml(list_file)
