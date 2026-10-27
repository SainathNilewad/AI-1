"""Abstract base class for real estate property clients and adapters."""

from abc import ABC, abstractmethod

from src.property_api.models import PropertySearchParams, PropertySearchResponse


class BasePropertyClient(ABC):
    """Interface contract that all property providers must implement."""

    name: str = "BaseProvider"
    is_live: bool = False

    @abstractmethod
    def search(self, params: PropertySearchParams) -> PropertySearchResponse:
        """Execute property search and return standardized PropertySearchResponse."""
