"""Property API integration module with pluggable adapters and local fallback."""

from src.property_api.base import BasePropertyClient
from src.property_api.factory import get_property_client
from src.property_api.local_client import LocalPropertyClient
from src.property_api.models import (
    PropertyItem,
    PropertySearchParams,
    PropertySearchResponse,
)
from src.property_api.rest_client import RestPropertyClient

__all__ = [
    "BasePropertyClient",
    "LocalPropertyClient",
    "PropertyItem",
    "PropertySearchParams",
    "PropertySearchResponse",
    "RestPropertyClient",
    "get_property_client",
]
