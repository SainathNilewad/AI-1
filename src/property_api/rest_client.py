"""REST API adapter for external authorized real estate property listing APIs."""

from typing import Any

import httpx

from src.property_api.base import BasePropertyClient
from src.property_api.models import (
    PropertyItem,
    PropertySearchParams,
    PropertySearchResponse,
)

DEFAULT_RENTAL_URL = "https://api.rentcast.io/v1/listings/rental/long-term"
DEFAULT_SALE_URL = "https://api.rentcast.io/v1/listings/sale"


class RestPropertyClient(BasePropertyClient):
    """Client adapter connecting to an authorized external Real Estate API (RentCast standard)."""

    name = "External Real Estate API (Live)"
    is_live = True

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def _map_item(self, item: dict[str, Any], transaction: str) -> PropertyItem:
        """Safely normalize diverse API response formats into standard PropertyItem."""
        # Address / Title extraction
        addr = item.get("formattedAddress") or item.get("addressLine1") or item.get("title") or "Property Listing"
        city = item.get("city") or "Unknown"

        # Price extraction
        price = item.get("price") or item.get("rent") or item.get("listPrice") or 0

        # Photos extraction
        photo = None
        photos = item.get("photos") or item.get("images") or []
        if isinstance(photos, list) and photos:
            photo = photos[0] if isinstance(photos[0], str) else photos[0].get("url")
        elif isinstance(photos, str):
            photo = photos

        # Listing link
        link = item.get("listingUrl") or item.get("url") or item.get("sourceUrl")

        return PropertyItem(
            id=str(item.get("id") or item.get("listingId") or hash(addr)),
            title=str(addr),
            price=int(price),
            transaction="rent" if transaction == "rent" else "buy",
            city=str(city),
            locality=item.get("county") or item.get("subdivision") or item.get("neighborhood"),
            bedrooms=item.get("bedrooms") or item.get("beds"),
            bathrooms=item.get("bathrooms") or item.get("baths"),
            property_type=item.get("propertyType"),
            sqft=item.get("squareFootage") or item.get("sqft"),
            furnishing=item.get("furnishing"),
            possession=item.get("status"),
            near=[],
            photo_url=photo,
            listing_url=link,
            source="live_api",
            raw_data=item,
        )

    def search(self, params: PropertySearchParams) -> PropertySearchResponse:
        """Fetch live listings from external REST API endpoint with full error and timeout handling."""
        if not self.api_key:
            return PropertySearchResponse(
                properties=[],
                total_count=0,
                page=params.page,
                page_size=params.page_size,
                has_next_page=False,
                is_fallback=False,
                provider_name=self.name,
                is_live_api=True,
                error_message="API key missing. Set REAL_ESTATE_API_KEY in your environment.",
            )

        # Determine target endpoint based on transaction type
        target_tx = params.transaction or "rent"
        endpoint = self.base_url
        if not endpoint:
            endpoint = DEFAULT_RENTAL_URL if target_tx == "rent" else DEFAULT_SALE_URL

        # Build query parameters according to standard REST property API specs
        offset = (params.page - 1) * params.page_size
        query_params: dict[str, Any] = {
            "limit": params.page_size,
            "offset": offset,
        }

        if params.city:
            query_params["city"] = params.city
        if params.bedrooms is not None:
            query_params["bedrooms"] = params.bedrooms
        if params.budget_min is not None:
            query_params["priceMin"] = params.budget_min
        if params.budget_max is not None:
            query_params["priceMax"] = params.budget_max
        if params.property_type:
            query_params["propertyType"] = params.property_type

        headers = {
            "Accept": "application/json",
            "X-Api-Key": self.api_key,
            "User-Agent": "HinglishPropertyQueryEngine/1.0",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.get(endpoint, params=query_params, headers=headers)

                if resp.status_code == 401:
                    return PropertySearchResponse(
                        properties=[],
                        total_count=0,
                        page=params.page,
                        page_size=params.page_size,
                        has_next_page=False,
                        is_fallback=False,
                        provider_name=self.name,
                        is_live_api=True,
                        error_message="Authentication failed (HTTP 401): Invalid REAL_ESTATE_API_KEY.",
                    )

                if resp.status_code == 429:
                    return PropertySearchResponse(
                        properties=[],
                        total_count=0,
                        page=params.page,
                        page_size=params.page_size,
                        has_next_page=False,
                        is_fallback=False,
                        provider_name=self.name,
                        is_live_api=True,
                        error_message="API Rate limit reached (HTTP 429). Please retry shortly.",
                    )

                if resp.status_code >= 400:
                    return PropertySearchResponse(
                        properties=[],
                        total_count=0,
                        page=params.page,
                        page_size=params.page_size,
                        has_next_page=False,
                        is_fallback=False,
                        provider_name=self.name,
                        is_live_api=True,
                        error_message=f"External API returned HTTP {resp.status_code}: {resp.text[:120]}",
                    )

                data = resp.json()
                raw_items = data if isinstance(data, list) else data.get("listings") or data.get("data") or []
                properties = [self._map_item(it, target_tx) for it in raw_items]

                # If returned list count == page_size, next page likely exists
                has_next = len(properties) == params.page_size

                return PropertySearchResponse(
                    properties=properties,
                    total_count=len(properties),
                    page=params.page,
                    page_size=params.page_size,
                    has_next_page=has_next,
                    is_fallback=False,
                    provider_name=self.name,
                    is_live_api=True,
                )

        except httpx.TimeoutException:
            return PropertySearchResponse(
                properties=[],
                total_count=0,
                page=params.page,
                page_size=params.page_size,
                has_next_page=False,
                is_fallback=False,
                provider_name=self.name,
                is_live_api=True,
                error_message=f"External API connection timed out after {self.timeout_seconds}s.",
            )
        except Exception as exc:  # noqa: BLE001
            return PropertySearchResponse(
                properties=[],
                total_count=0,
                page=params.page,
                page_size=params.page_size,
                has_next_page=False,
                is_fallback=False,
                provider_name=self.name,
                is_live_api=True,
                error_message=f"External API connection error: {exc}",
            )
