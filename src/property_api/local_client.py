"""Local inventory adapter implementing BasePropertyClient using Data/properties.json."""

import json
from typing import Any

from src.config import PROJECT_ROOT
from src.property_api.base import BasePropertyClient
from src.property_api.models import (
    PropertyItem,
    PropertySearchParams,
    PropertySearchResponse,
)

PROPERTIES_FILE = PROJECT_ROOT / "Data" / "properties.json"


class LocalPropertyClient(BasePropertyClient):
    """Offline verified local property inventory provider."""

    name = "Local Verified Inventory"
    is_live = False

    def __init__(self, data_path: Any = PROPERTIES_FILE) -> None:
        self.data_path = data_path
        self._inventory: list[dict[str, Any]] | None = None

    def _load_inventory(self) -> list[dict[str, Any]]:
        if self._inventory is not None:
            return self._inventory
        if not self.data_path.exists():
            return []
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                self._inventory = json.load(f)
        except Exception:  # noqa: BLE001
            self._inventory = []
        return self._inventory or []

    def _to_item(self, p: dict[str, Any]) -> PropertyItem:
        return PropertyItem(
            id=str(p.get("id", "PROP-UNKNOWN")),
            title=p.get("title", "Property Listing"),
            price=int(p.get("price", 0)),
            transaction="rent" if str(p.get("tx", "")).lower() == "rent" else "buy",
            city=p.get("city", "Unknown"),
            locality=p.get("locality"),
            bedrooms=p.get("bhk"),
            bathrooms=p.get("bathrooms", float(p.get("bhk", 1)) if p.get("bhk") else None),
            property_type=p.get("type", "flat"),
            sqft=p.get("sqft"),
            furnishing=p.get("furn"),
            possession=p.get("poss"),
            near=p.get("near", []),
            photo_url=p.get("photo"),
            listing_url=p.get("listing_url", f"https://example.com/listings/{p.get('id', 'item')}"),
            source="local_catalog",
            raw_data=p,
        )

    def search(self, params: PropertySearchParams) -> PropertySearchResponse:
        """Search local inventory with strict filtering, fallback relaxation, and pagination."""
        inventory = self._load_inventory()
        if not inventory:
            return PropertySearchResponse(
                properties=[],
                total_count=0,
                page=params.page,
                page_size=params.page_size,
                has_next_page=False,
                is_fallback=False,
                provider_name=self.name,
                is_live_api=self.is_live,
            )

        # 1. Strict Search
        def matches_strict(p: dict[str, Any]) -> bool:
            if params.city and p.get("city") and p["city"].lower() != params.city.lower():
                return False
            if params.bedrooms is not None and p.get("bhk") is not None and p["bhk"] != params.bedrooms:
                return False
            if params.transaction and p.get("tx") and p["tx"].lower() != params.transaction.lower():
                return False
            if params.property_type and p.get("type") and p["type"].lower() != params.property_type.lower():
                return False
            price = p.get("price", 0)
            if params.budget_min is not None and price < params.budget_min:
                return False
            return not (params.budget_max is not None and price > params.budget_max)

        strict_matches = [p for p in inventory if matches_strict(p)]
        is_fallback = False
        candidates = strict_matches

        # 2. Relaxed Fallback
        if not candidates:
            is_fallback = True

            def matches_relaxed(p: dict[str, Any]) -> bool:
                if params.city and p.get("city") and p["city"].lower() != params.city.lower():
                    return False
                if params.bedrooms is not None and p.get("bhk") is not None and p["bhk"] != params.bedrooms:
                    return False
                if params.transaction and p.get("tx") and p["tx"].lower() != params.transaction.lower():
                    return False
                price = p.get("price", 0)
                return not (params.budget_max is not None and price > int(params.budget_max * 1.25))

            relaxed = [p for p in inventory if matches_relaxed(p)]
            if relaxed:
                candidates = relaxed
            elif params.city:
                city_matches = [p for p in inventory if p.get("city", "").lower() == params.city.lower()]
                candidates = city_matches or inventory
            else:
                candidates = inventory

        # Locality sorting boost
        def score(p: dict[str, Any]) -> int:
            sc = 100
            if params.locality and p.get("locality") and params.locality.lower() == p["locality"].lower():
                sc += 60
            return sc

        ranked = sorted(candidates, key=lambda p: (-score(p), p.get("price", 0)))

        # Pagination
        start = (params.page - 1) * params.page_size
        end = start + params.page_size
        paged_items = ranked[start:end]
        has_next = end < len(ranked)

        return PropertySearchResponse(
            properties=[self._to_item(p) for p in paged_items],
            total_count=len(ranked),
            page=params.page,
            page_size=params.page_size,
            has_next_page=has_next,
            is_fallback=is_fallback,
            provider_name=self.name,
            is_live_api=self.is_live,
        )
