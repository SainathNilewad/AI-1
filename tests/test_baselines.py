"""Unit tests for extraction baselines and cascade routing."""

from unittest.mock import patch

from src.baselines import (
    CHEAP_MODEL,
    LARGE_MODEL,
    _compute_confidence,
    parse_b1,
    parse_b2,
    parse_b3,
    parse_cascade,
)
from src.llm import compute_token_cost
from src.schema import SearchFilter


def test_compute_token_cost():
    # Tier 1: $0.075 / 1M in, $0.300 / 1M out
    # 1,000 in, 1,000 out => 0.000075 + 0.000300 = 0.000375
    cost_cheap = compute_token_cost(CHEAP_MODEL, input_tokens=1000, output_tokens=1000)
    assert cost_cheap == 0.000375

    # Tier 2: $0.150 / 1M in, $0.600 / 1M out
    # 1,000 in, 1,000 out => 0.000150 + 0.000600 = 0.000750
    cost_large = compute_token_cost(LARGE_MODEL, input_tokens=1000, output_tokens=1000)
    assert cost_large == 0.00075


def test_b1_rule_baseline():
    query = "noida sector 62 2bhk flat under 45k"
    res = parse_b1(query)
    assert res.tier == "b1_rules"
    assert res.filter.city == "Noida"
    assert res.filter.bhk == 2
    assert res.filter.budget_max == 45000
    assert res.cost_usd == 0.0
    assert res.confidence >= 0.70


def test_b2_cheap_baseline_success():
    fake_parsed = {
        "bhk": 3,
        "city": "Gurugram",
        "locality": "Sector 54",
        "budget_max": 15000000,
        "property_type": "apartment",
    }
    fake_stats = {"latency_ms": 120.0, "cost_usd": 0.00005, "input_tokens": 100, "output_tokens": 50, "cached": True}

    with patch("src.baselines.extract_with_llm", return_value=(fake_parsed, fake_stats)):
        res = parse_b2("gurgaon 3bhk sec 54 under 1.5cr", api_key="dummy")
        assert res.tier == "b2_cheap"
        assert res.filter.bhk == 3
        assert res.filter.city == "Gurugram"
        assert res.filter.budget_max == 15000000
        assert res.confidence == 0.85
        assert res.cost_usd == 0.00005


def test_b2_cheap_baseline_schema_failure():
    # Inverted budget (budget_min > budget_max) triggers Pydantic ValidationError
    fake_parsed = {"bhk": 2, "budget_min": 50000, "budget_max": 20000}
    fake_stats = {"latency_ms": 100.0, "cost_usd": 0.00004, "input_tokens": 100, "output_tokens": 50}

    with patch("src.baselines.extract_with_llm", return_value=(fake_parsed, fake_stats)):
        res = parse_b2("query with bad range", api_key="dummy")
        assert res.tier == "b2_cheap"
        assert res.filter.budget_min is None
        assert res.confidence == 0.0


def test_b3_large_baseline():
    fake_parsed = {"bhk": 4, "city": "Mumbai", "locality": "Bandra West", "property_type": "apartment"}
    fake_stats = {"latency_ms": 250.0, "cost_usd": 0.00015, "input_tokens": 120, "output_tokens": 80}

    with patch("src.baselines.extract_with_llm", return_value=(fake_parsed, fake_stats)):
        res = parse_b3("bandra west 4bhk luxury apartment", api_key="dummy")
        assert res.tier == "b3_large"
        assert res.filter.bhk == 4
        assert res.filter.city == "Mumbai"
        assert res.confidence == 0.95


def test_confidence_computation():
    filter_obj = SearchFilter(bhk=2, city="Noida", budget_max=50000)
    regex_candidates = {"bhk": 2, "city": "Noida", "budget_max": 50000}

    conf = _compute_confidence(filter_obj, regex_candidates)
    assert conf >= 0.85

    # If model disagrees with regex
    conf_mismatch = _compute_confidence(SearchFilter(bhk=3, city="Delhi"), regex_candidates)
    assert conf_mismatch < 0.50


def test_cascade_accepts_tier1_on_high_confidence():
    query = "noida 2bhk under 50k"
    fake_cheap_parsed = {"bhk": 2, "city": "Noida", "budget_max": 50000}
    fake_cheap_stats = {"latency_ms": 110.0, "cost_usd": 0.00004, "input_tokens": 80, "output_tokens": 40}

    with patch("src.baselines.extract_with_llm", return_value=(fake_cheap_parsed, fake_cheap_stats)) as mock_llm:
        res = parse_cascade(query, api_key="dummy", confidence_threshold=0.70)
        assert res.tier == "cascade_tier1"
        assert not res.escalated
        assert res.filter.bhk == 2
        assert res.filter.city == "Noida"
        assert mock_llm.call_count == 1  # Large model was never called!


def test_cascade_escalates_to_tier2_on_schema_failure():
    query = "noida 2bhk under 50k"
    # Cheap model returns invalid budget range
    fake_cheap_parsed = {"bhk": 2, "budget_min": 60000, "budget_max": 50000}
    fake_cheap_stats = {"latency_ms": 110.0, "cost_usd": 0.00004, "input_tokens": 80, "output_tokens": 40}

    # Large model returns corrected filter
    fake_large_parsed = {"bhk": 2, "city": "Noida", "budget_max": 50000}
    fake_large_stats = {"latency_ms": 280.0, "cost_usd": 0.00012, "input_tokens": 90, "output_tokens": 60}

    side_effects = [(fake_cheap_parsed, fake_cheap_stats), (fake_large_parsed, fake_large_stats)]

    with patch("src.baselines.extract_with_llm", side_effect=side_effects) as mock_llm:
        res = parse_cascade(query, api_key="dummy", confidence_threshold=0.70)
        assert res.tier == "cascade_tier2"
        assert res.escalated
        assert res.filter.bhk == 2
        assert res.filter.city == "Noida"
        assert res.cost_usd == 0.00016  # 0.00004 + 0.00012
        assert mock_llm.call_count == 2  # Both tiers were called
