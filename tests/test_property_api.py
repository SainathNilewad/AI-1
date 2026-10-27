"""Automated test suite for real estate property API adapters and clients."""

from unittest.mock import MagicMock, patch

import httpx

from src.property_api.factory import get_property_client
from src.property_api.local_client import LocalPropertyClient
from src.property_api.models import PropertySearchParams
from src.property_api.rest_client import RestPropertyClient
from src.schema import SearchFilter
from src.search import filter_to_params, search_properties_api

# =====================================================================
# 1. LocalPropertyClient Tests
# =====================================================================

def test_local_client_strict_search():
    client = LocalPropertyClient()
    params = PropertySearchParams(city="Noida", bedrooms=2, transaction="rent", budget_max=35000)
    resp = client.search(params)

    assert not resp.is_live_api
    assert not resp.is_fallback
    assert resp.error_message is None
    assert len(resp.properties) > 0
    for p in resp.properties:
        assert p.city.lower() == "noida"
        assert p.bedrooms == 2
        assert p.transaction == "rent"
        assert p.price <= 35000
        assert p.source == "local_catalog"


def test_local_client_pagination():
    client = LocalPropertyClient()
    params_p1 = PropertySearchParams(city="Noida", page=1, page_size=3)
    resp_p1 = client.search(params_p1)

    assert resp_p1.page == 1
    assert resp_p1.page_size == 3
    assert len(resp_p1.properties) == 3
    assert resp_p1.has_next_page is True

    params_p2 = PropertySearchParams(city="Noida", page=2, page_size=3)
    resp_p2 = client.search(params_p2)
    assert resp_p2.page == 2
    assert len(resp_p2.properties) == 3

    # IDs between page 1 and page 2 must be distinct
    p1_ids = {p.id for p in resp_p1.properties}
    p2_ids = {p.id for p in resp_p2.properties}
    assert p1_ids.isdisjoint(p2_ids)


def test_local_client_relaxed_fallback():
    client = LocalPropertyClient()
    # Extremely low budget for 3BHK in Mumbai triggers fallback
    params = PropertySearchParams(city="Mumbai", bedrooms=3, transaction="rent", budget_max=10000)
    resp = client.search(params)

    assert resp.is_fallback is True
    assert len(resp.properties) > 0
    assert any(p.city.lower() == "mumbai" for p in resp.properties)


# =====================================================================
# 2. RestPropertyClient Tests (Mocked Live External API)
# =====================================================================

def test_rest_client_missing_key():
    client = RestPropertyClient(api_key="")
    params = PropertySearchParams(city="Austin", page=1, page_size=5)
    resp = client.search(params)

    assert resp.is_live_api is True
    assert resp.error_message is not None
    assert "API key missing" in resp.error_message
    assert len(resp.properties) == 0


def test_rest_client_successful_response():
    client = RestPropertyClient(api_key="test_live_key_123")
    mock_payload = [
        {
            "id": "LIVE-101",
            "formattedAddress": "123 South Congress Ave, Austin, TX",
            "price": 2400,
            "propertyType": "Apartment",
            "bedrooms": 2,
            "bathrooms": 2.0,
            "squareFootage": 1150,
            "photos": ["https://example.com/photos/101.jpg"],
            "listingUrl": "https://example.com/listings/101",
            "city": "Austin",
            "county": "Travis County",
        },
        {
            "id": "LIVE-102",
            "formattedAddress": "456 Lamar Blvd, Austin, TX",
            "price": 3100,
            "propertyType": "Condo",
            "bedrooms": 2,
            "bathrooms": 2.5,
            "squareFootage": 1300,
            "photos": [{"url": "https://example.com/photos/102.jpg"}],
            "listingUrl": "https://example.com/listings/102",
            "city": "Austin",
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.Client.get", return_value=mock_resp):
        params = PropertySearchParams(city="Austin", bedrooms=2, transaction="rent", page_size=2)
        resp = client.search(params)

        assert resp.is_live_api is True
        assert resp.error_message is None
        assert len(resp.properties) == 2

        first = resp.properties[0]
        assert first.id == "LIVE-101"
        assert first.title == "123 South Congress Ave, Austin, TX"
        assert first.price == 2400
        assert first.bedrooms == 2
        assert first.bathrooms == 2.0
        assert first.photo_url == "https://example.com/photos/101.jpg"
        assert first.listing_url == "https://example.com/listings/101"
        assert first.source == "live_api"

        second = resp.properties[1]
        assert second.photo_url == "https://example.com/photos/102.jpg"
        assert second.listing_url == "https://example.com/listings/102"


def test_rest_client_empty_results():
    client = RestPropertyClient(api_key="valid_key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []

    with patch("httpx.Client.get", return_value=mock_resp):
        params = PropertySearchParams(city="NowhereVille", bedrooms=5)
        resp = client.search(params)

        assert resp.is_live_api is True
        assert resp.error_message is None
        assert len(resp.properties) == 0
        assert resp.has_next_page is False


def test_rest_client_missing_fields_graceful():
    client = RestPropertyClient(api_key="valid_key")
    # Missing photos, bathrooms, squareFootage, listingUrl
    sparse_payload = [
        {
            "id": "SPARSE-1",
            "formattedAddress": "789 Barebones Rd",
            "price": 1800,
            "city": "Austin",
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sparse_payload

    with patch("httpx.Client.get", return_value=mock_resp):
        params = PropertySearchParams(city="Austin")
        resp = client.search(params)

        assert len(resp.properties) == 1
        item = resp.properties[0]
        assert item.id == "SPARSE-1"
        assert item.photo_url is None
        assert item.bathrooms is None
        assert item.listing_url is None
        assert item.price == 1800


def test_rest_client_unauthorized_401():
    client = RestPropertyClient(api_key="invalid_token")
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"error": "Unauthorized"}'

    with patch("httpx.Client.get", return_value=mock_resp):
        resp = client.search(PropertySearchParams(city="Austin"))
        assert resp.error_message is not None
        assert "401" in resp.error_message
        assert len(resp.properties) == 0


def test_rest_client_rate_limited_429():
    client = RestPropertyClient(api_key="rate_limited_token")
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Too Many Requests"

    with patch("httpx.Client.get", return_value=mock_resp):
        resp = client.search(PropertySearchParams(city="Austin"))
        assert resp.error_message is not None
        assert "Rate limit" in resp.error_message or "429" in resp.error_message
        assert len(resp.properties) == 0


def test_rest_client_timeout():
    client = RestPropertyClient(api_key="valid_key", timeout_seconds=0.1)

    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Read timeout")):
        resp = client.search(PropertySearchParams(city="Austin"))
        assert resp.error_message is not None
        assert "timed out" in resp.error_message
        assert len(resp.properties) == 0


# =====================================================================
# 3. Factory & Search Adapter Tests
# =====================================================================

def test_factory_local_selection():
    client = get_property_client(provider_override="local")
    assert isinstance(client, LocalPropertyClient)
    assert not client.is_live


def test_factory_live_selection():
    client = get_property_client(provider_override="live", api_key_override="test_key")
    assert isinstance(client, RestPropertyClient)
    assert client.is_live


def test_filter_to_params_conversion():
    filter_obj = SearchFilter(
        city="noida",
        locality="Sector 62",
        bhk=3,
        transaction="buy",
        budget_min=10000000,
        budget_max=20000000,
        property_type="flat",
    )
    params = filter_to_params(filter_obj, page=2, page_size=6)

    assert params.city == "noida"
    assert params.locality == "Sector 62"
    assert params.bedrooms == 3
    assert params.transaction == "buy"
    assert params.budget_min == 10000000
    assert params.budget_max == 20000000
    assert params.property_type == "flat"
    assert params.page == 2
    assert params.page_size == 6


def test_search_properties_api_integration():
    mock_client = MagicMock(spec=LocalPropertyClient)
    mock_client.search.return_value = MagicMock(total_count=5)

    filter_obj = SearchFilter(city="noida", bhk=2)
    resp = search_properties_api(filter_obj, client=mock_client, page=1, page_size=9)

    assert mock_client.search.called
    assert resp.total_count == 5
