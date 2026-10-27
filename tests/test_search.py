"""Unit tests for the property search engine."""

from src.schema import SearchFilter
from src.search import format_inr, score_property, search_properties


def test_format_inr():
    assert format_inr(25000, "rent") == "₹25,000 / mo"
    assert format_inr(15000000, "buy") == "₹1.50 Cr"
    assert format_inr(20000000, "buy") == "₹2 Cr"
    assert format_inr(7500000, "buy") == "₹75 Lakh"
    assert format_inr(8550000, "buy") == "₹85.50 Lakh"
    assert format_inr(50000) == "₹50,000"


def test_score_property_boosts():
    prop = {
        "title": "2 BHK Apartment",
        "locality": "Sector 62",
        "city": "Noida",
        "near": ["metro", "park"],
        "furn": "furnished",
        "poss": "ready_to_move",
    }

    base_score = score_property(prop, SearchFilter())
    assert base_score == 100

    # Locality boost
    loc_filter = SearchFilter(locality="Sector 62")
    assert score_property(prop, loc_filter) == 160

    # Amenity boost
    amenity_filter = SearchFilter(near=["metro"])
    assert score_property(prop, amenity_filter) == 125

    # Multiple amenities + furnishing + possession
    full_filter = SearchFilter(
        locality="sector 62",
        near=["metro", "park"],
        furnishing="furnished",
        possession="ready_to_move",
    )
    # 100 + 60 (locality) + 25 (metro) + 25 (park) + 20 (furn) + 20 (poss) = 250
    assert score_property(prop, full_filter) == 250


def test_search_properties_strict():
    f = SearchFilter(
        city="noida",
        bhk=2,
        transaction="rent",
        budget_max=30000,
    )
    results, is_fallback = search_properties(f)
    assert not is_fallback
    assert len(results) > 0
    for p in results:
        assert p["city"].lower() == "noida"
        assert p["bhk"] == 2
        assert p["tx"] == "rent"
        assert p["price"] <= 30000


def test_search_properties_budget_filter():
    f = SearchFilter(
        city="gurugram",
        transaction="buy",
        budget_min=10000000,
        budget_max=25000000,
    )
    results, is_fallback = search_properties(f)
    assert not is_fallback
    assert len(results) > 0
    for p in results:
        assert p["city"].lower() == "gurugram"
        assert p["tx"] == "buy"
        assert 10000000 <= p["price"] <= 25000000


def test_search_properties_relaxed_fallback():
    # Intentionally tight budget to force relaxed fallback (e.g. 2bhk rent in Mumbai for 10k max)
    # If no strict match, relaxed matches with 25% buffer or city fallback
    f = SearchFilter(
        city="mumbai",
        bhk=3,
        transaction="rent",
        budget_max=15000,  # Unrealistic for Mumbai 3BHK rent
    )
    results, is_fallback = search_properties(f)
    assert is_fallback is True
    assert len(results) > 0
    # Should fall back to city matches
    assert any(p["city"].lower() == "mumbai" for p in results)


def test_search_properties_nonexistent_city():
    f = SearchFilter(city="Atlantis", bhk=5)
    results, is_fallback = search_properties(f)
    assert is_fallback is True
    # Should fall back to featured inventory
    assert len(results) > 0
