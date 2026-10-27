"""Factory for instantiating the appropriate property provider client."""

import os
from typing import Literal

from src.property_api.base import BasePropertyClient
from src.property_api.local_client import LocalPropertyClient
from src.property_api.rest_client import RestPropertyClient


def get_property_client(
    provider_override: Literal["local", "live", "auto"] | None = None,
    api_key_override: str | None = None,
    base_url_override: str | None = None,
) -> BasePropertyClient:
    """Resolve and return active property client according to environment or overrides.

    Resolution logic:
    1. If provider_override is 'local', return LocalPropertyClient.
    2. If provider_override is 'live', return RestPropertyClient (using key).
    3. If 'auto' or not specified:
       - Checks REAL_ESTATE_API_PROVIDER and REAL_ESTATE_API_KEY in environment.
       - If REAL_ESTATE_API_KEY is present and provider is 'live' or 'rentcast', returns RestPropertyClient.
       - Otherwise, returns LocalPropertyClient with verified offline inventory.
    """
    env_provider = os.getenv("REAL_ESTATE_API_PROVIDER", "auto").lower()
    env_key = os.getenv("REAL_ESTATE_API_KEY", "")
    env_url = os.getenv("REAL_ESTATE_API_BASE_URL", "")

    effective_provider = provider_override or env_provider
    api_key = api_key_override if api_key_override is not None else env_key
    base_url = base_url_override if base_url_override is not None else (env_url or None)

    if effective_provider in ("live", "rentcast") or (effective_provider == "auto" and api_key):
        return RestPropertyClient(api_key=api_key, base_url=base_url)

    return LocalPropertyClient()
