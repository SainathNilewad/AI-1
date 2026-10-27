from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RealEstateQuery(BaseModel):
    """Structured search filters for real estate queries."""
    city: str | None = None
    locality: str | None = None
    bhk: int | None = None
    property_type: Literal["flat", "house", "plot", "villa", "pg"] | None = None
    transaction: Literal["buy", "rent"] | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    furnishing: Literal["furnished", "semi", "unfurnished"] | None = None
    possession: Literal["ready_to_move", "under_construction"] | None = None
    area_sqft_min: int | None = None
    area_sqft_max: int | None = None
    near: list[str] = Field(default_factory=list)
    price_preference: Literal["cheap", "premium", "none"] | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> "RealEstateQuery":
        """Verify minimum constraints do not exceed maximum constraints."""
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValueError(
                f"budget_min ({self.budget_min}) cannot exceed budget_max ({self.budget_max})"
            )
        if (
            self.area_sqft_min is not None
            and self.area_sqft_max is not None
            and self.area_sqft_min > self.area_sqft_max
        ):
            raise ValueError(
                f"area_sqft_min ({self.area_sqft_min}) cannot exceed area_sqft_max ({self.area_sqft_max})"
            )
        return self
