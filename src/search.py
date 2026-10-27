"""Property search and inventory matching engine."""

import json
from typing import Any

from src.config import PROJECT_ROOT
from src.property_api.base import BasePropertyClient
from src.property_api.factory import get_property_client
from src.property_api.models import PropertySearchParams, PropertySearchResponse
from src.schema import SearchFilter

PROPERTIES_FILE = PROJECT_ROOT / "Data" / "properties.json"


def load_properties() -> list[dict[str, Any]]:
    """Load property inventory from Data/properties.json."""
    if not PROPERTIES_FILE.exists():
        return []
    with open(PROPERTIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def format_inr(price: int, transaction: str | None = None) -> str:
    """Format numeric price into Indian currency notation."""
    if transaction == "rent":
        return f"₹{price:,} / mo"

    if price >= 10_000_000:
        cr_val = price / 10_000_000.0
        return f"₹{cr_val:.2f} Cr" if cr_val % 1 != 0 else f"₹{int(cr_val)} Cr"
    if price >= 100_000:
        lakh_val = price / 100_000.0
        return f"₹{lakh_val:.2f} Lakh" if lakh_val % 1 != 0 else f"₹{int(lakh_val)} Lakh"
    return f"₹{price:,}"


def score_property(prop: dict[str, Any], filter_obj: SearchFilter) -> int:
    """Calculate relevance match score for ranking."""
    score = 100

    # Locality boost
    if filter_obj.locality and prop.get("locality") and filter_obj.locality.lower() == prop["locality"].lower():
        score += 60

    # Amenity boosts
    if filter_obj.near and prop.get("near"):
        prop_near = [str(n).lower() for n in prop["near"]]
        for requested in filter_obj.near:
            if requested.lower() in prop_near:
                score += 25

    # Furnishing boost
    if filter_obj.furnishing and prop.get("furn") and filter_obj.furnishing.lower() == prop["furn"].lower():
        score += 20

    # Possession boost
    if filter_obj.possession and prop.get("poss") and filter_obj.possession.lower() == prop["poss"].lower():
        score += 20

    return score


def filter_to_params(
    filter_obj: SearchFilter,
    page: int = 1,
    page_size: int = 9,
) -> PropertySearchParams:
    """Convert parsed SearchFilter into PropertySearchParams for property clients."""
    return PropertySearchParams(
        city=filter_obj.city,
        locality=filter_obj.locality,
        transaction=filter_obj.transaction,
        bedrooms=filter_obj.bhk,
        property_type=filter_obj.property_type,
        budget_min=filter_obj.budget_min,
        budget_max=filter_obj.budget_max,
        page=page,
        page_size=page_size,
    )


def search_properties_api(
    filter_obj: SearchFilter,
    client: BasePropertyClient | None = None,
    page: int = 1,
    page_size: int = 9,
) -> PropertySearchResponse:
    """Execute unified property search against the active property provider client."""
    active_client = client or get_property_client()
    params = filter_to_params(filter_obj, page=page, page_size=page_size)
    return active_client.search(params)


def search_properties(
    filter_obj: SearchFilter,
    limit: int = 9,
) -> tuple[list[dict[str, Any]], bool]:
    """Search inventory using extracted SearchFilter.

    Returns (matched_properties, is_relaxed_fallback).
    """
    inventory = load_properties()
    if not inventory:
        return [], False

    def matches_strict(p: dict[str, Any]) -> bool:
        if filter_obj.city and p.get("city") and p["city"].lower() != filter_obj.city.lower():
            return False

        if filter_obj.bhk is not None and p.get("bhk") is not None and p["bhk"] != filter_obj.bhk:
            return False

        if filter_obj.transaction and p.get("tx") and p["tx"].lower() != filter_obj.transaction.lower():
            return False

        if filter_obj.property_type and p.get("type") and p["type"].lower() != filter_obj.property_type.lower():
            return False

        price = p.get("price", 0)
        if filter_obj.budget_min is not None and price < filter_obj.budget_min:
            return False
        return not (filter_obj.budget_max is not None and price > filter_obj.budget_max)

    # 1. Strict Search
    strict_matches = [p for p in inventory if matches_strict(p)]

    if strict_matches:
        ranked = sorted(strict_matches, key=lambda p: (-score_property(p, filter_obj), p.get("price", 0)))
        return ranked[:limit], False

    # 2. Relaxed Fallback Search (relax budget bounds by 25% or relax property type)
    def matches_relaxed(p: dict[str, Any]) -> bool:
        if filter_obj.city and p.get("city") and p["city"].lower() != filter_obj.city.lower():
            return False

        if filter_obj.bhk is not None and p.get("bhk") is not None and p["bhk"] != filter_obj.bhk:
            return False

        if filter_obj.transaction and p.get("tx") and p["tx"].lower() != filter_obj.transaction.lower():
            return False

        price = p.get("price", 0)
        return not (filter_obj.budget_max is not None and price > int(filter_obj.budget_max * 1.25))

    relaxed_matches = [p for p in inventory if matches_relaxed(p)]
    if relaxed_matches:
        ranked = sorted(relaxed_matches, key=lambda p: (-score_property(p, filter_obj), p.get("price", 0)))
        return ranked[:limit], True

    # 3. Broad Fallback by City
    if filter_obj.city:
        city_matches = [p for p in inventory if p.get("city", "").lower() == filter_obj.city.lower()]
        if city_matches:
            return city_matches[:limit], True

    # Fallback to top featured inventory
    return inventory[:limit], True
