import pytest

from src.config import load_domain_config
from src.normalizer import (
    clean_text,
    extract_bhk,
    extract_budget,
    normalize_city,
    parse_currency_amount,
)
from src.schema import RealEstateQuery


@pytest.fixture
def re_config():
    return load_domain_config("real_estate")


def test_clean_text():
    raw = "  Noida  ME   2BHK  sasta "
    assert clean_text(raw) == "noida me 2bhk sasta"


def test_parse_currency_units(re_config):
    units = re_config["units"]
    assert parse_currency_amount("25", "k", units) == 25000
    assert parse_currency_amount("1.5", "cr", units) == 15000000
    assert parse_currency_amount("80", "lakh", units) == 8000000
    assert parse_currency_amount("80", "lac", units) == 8000000


def test_normalize_city_aliases(re_config):
    aliases = re_config["city_aliases"]
    assert normalize_city("gurgaon", aliases) == "Gurugram"
    assert normalize_city("bombay", aliases) == "Mumbai"
    assert normalize_city("bangalore", aliases) == "Bengaluru"
    assert normalize_city("noida", aliases) == "Noida"


def test_extract_bhk():
    assert extract_bhk("noida 2bhk flat") == 2
    assert extract_bhk("3 bhk ready to move") == 3
    assert extract_bhk("1 rk studio") == 1
    assert extract_bhk("independent house no bhk") is None


def test_extract_budget_ranges(re_config):
    units = re_config["units"]
    assert extract_budget("1.5 cr tak", units) == (None, 15000000)
    assert extract_budget("under 25k", units) == (None, 25000)
    assert extract_budget("starting 50 lakh", units) == (5000000, None)
    assert extract_budget("25k to 30k", units) == (25000, 30000)
    assert extract_budget("5-8 cr", units) == (50000000, 80000000)


def test_schema_valid_query():
    query = RealEstateQuery(
        city="Gurugram",
        bhk=3,
        possession="ready_to_move",
        budget_max=15000000,
    )
    assert query.city == "Gurugram"
    assert query.bhk == 3
    assert query.budget_max == 15000000


def test_schema_invalid_range_raises():
    with pytest.raises(ValueError, match="budget_min"):
        RealEstateQuery(budget_min=20000000, budget_max=10000000)


def test_extract_regex_candidates_full():
    from src.normalizer import extract_regex_candidates

    text = "noida sec 62 me 2bhk sasta furnished flat rent pe near metro 30k tak"
    extracted = extract_regex_candidates(text)
    assert extracted["city"] == "Noida"
    assert extracted["locality"] == "Sector 62"
    assert extracted["bhk"] == 2
    assert extracted["price_preference"] == "cheap"
    assert extracted["furnishing"] == "furnished"
    assert extracted["property_type"] == "flat"
    assert extracted["transaction"] == "rent"
    assert "metro" in extracted["near"]
    assert extracted["budget_max"] == 30000

