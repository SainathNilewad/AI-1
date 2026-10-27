"""Standardized data models for property listings and API responses."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class PropertyItem(BaseModel):
    """Normalized property listing entity across all providers."""

    id: str
    title: str
    price: int
    transaction: Literal["buy", "rent"] = "rent"
    city: str
    locality: str | None = None
    bedrooms: int | None = None  # BHK
    bathrooms: float | None = None
    property_type: str | None = None  # flat, house, villa, condo, etc.
    sqft: int | None = None
    furnishing: str | None = None
    possession: str | None = None
    near: list[str] = Field(default_factory=list)
    photo_url: str | None = None
    listing_url: str | None = None  # Link to original external listing
    source: Literal["live_api", "local_catalog", "mock"] = "local_catalog"
    raw_data: dict[str, Any] = Field(default_factory=dict)

    @property
    def bhk(self) -> int | None:
        return self.bedrooms

    @property
    def tx(self) -> str:
        return self.transaction

    @property
    def photo(self) -> str | None:
        return self.photo_url

    @property
    def furn(self) -> str | None:
        return self.furnishing

    @property
    def poss(self) -> str | None:
        return self.possession


class PropertySearchParams(BaseModel):
    """Parameters passed to any property provider."""

    city: str | None = None
    locality: str | None = None
    transaction: Literal["buy", "rent"] | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    property_type: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    page: int = 1
    page_size: int = 9


class PropertySearchResponse(BaseModel):
    """Unified response returned by any property client."""

    properties: list[PropertyItem] = Field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 9
    has_next_page: bool = False
    is_fallback: bool = False
    provider_name: str = "Local Inventory"
    is_live_api: bool = False
    error_message: str | None = None
