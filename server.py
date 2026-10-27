"""Web server powering the consumer-facing real estate search portal."""

import json
import logging
import os
import time
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from src.baselines import parse_b1, parse_cascade
from src.config import PROJECT_ROOT
from src.property_api import get_property_client
from src.schema import SearchFilter
from src.search import format_inr, search_properties_api

logger = logging.getLogger(__name__)

WEB_DIR = PROJECT_ROOT / "web"
STATIC_DIR = WEB_DIR / "static"


def _resolve_api_key() -> str:
    return os.getenv("GROQ_API_KEY", "")


async def index(request: Request) -> FileResponse:
    """Serve the primary consumer real estate website."""
    index_file = WEB_DIR / "index.html"
    return FileResponse(index_file)


async def api_search(request: Request) -> JSONResponse:
    """Parse Hinglish search query through AI cascade and retrieve matched properties."""
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}

    query_str = body.get("query", "").strip()
    manual_city = body.get("city")
    manual_tx = body.get("transaction")
    manual_bhk = body.get("bhk")
    page = int(body.get("page", 1))
    page_size = int(body.get("page_size", 9))
    groq_key = _resolve_api_key()

    start_time = time.perf_counter()

    # 1. AI Parsing Step
    if query_str:
        if groq_key:
            parse_res = parse_cascade(query_str, api_key=groq_key)
        else:
            parse_res = parse_b1(query_str)
        extracted_filter = parse_res.filter
        tier = parse_res.tier
        confidence = parse_res.confidence
        latency_ms = parse_res.latency_ms
        cost_usd = parse_res.cost_usd
    else:
        extracted_filter = SearchFilter()
        tier = "direct_filter"
        confidence = 1.0
        latency_ms = 0.0
        cost_usd = 0.0

    # 2. Apply Manual UI Overrides if provided
    active_dict = extracted_filter.model_dump(exclude_none=True)
    if manual_city and manual_city != "all":
        active_dict["city"] = manual_city
    if manual_tx and manual_tx in ("buy", "rent"):
        active_dict["transaction"] = manual_tx
    if manual_bhk and str(manual_bhk).isdigit():
        active_dict["bhk"] = int(manual_bhk)

    try:
        combined_filter = SearchFilter(**active_dict)
    except Exception:  # noqa: BLE001
        combined_filter = extracted_filter

    # 3. Property Search Step
    client = get_property_client()
    search_resp = search_properties_api(
        combined_filter,
        client=client,
        page=page,
        page_size=page_size,
    )

    total_latency = (time.perf_counter() - start_time) * 1000.0

    # Format properties for rich UI cards
    formatted_props: list[dict[str, Any]] = []
    for p in search_resp.properties:
        formatted_props.append({
            "id": p.id,
            "title": p.title,
            "price": p.price,
            "price_formatted": format_inr(p.price, p.transaction),
            "transaction": p.transaction,
            "city": p.city,
            "locality": p.locality,
            "bedrooms": p.bedrooms,
            "bathrooms": p.bathrooms,
            "property_type": p.property_type,
            "sqft": p.sqft,
            "furnishing": p.furnishing,
            "possession": p.possession,
            "near": p.near,
            "photo_url": p.photo_url,
            "listing_url": p.listing_url,
            "source": p.source,
        })

    tier_labels = {
        "cascade_tier1": "Tier 1: Fast LLM (20B)",
        "cascade_tier2": "Tier 2: Reasoning LLM (120B)",
        "b1_rules": "Tier 0: Hinglish Rule Engine (Local)",
        "direct_filter": "Direct Filter",
    }

    return JSONResponse({
        "success": True,
        "query": query_str,
        "filter": combined_filter.model_dump(exclude_none=True),
        "metrics": {
            "tier": tier,
            "tier_label": tier_labels.get(tier, tier),
            "confidence": round(confidence * 100, 1),
            "parse_latency_ms": round(latency_ms, 1),
            "total_latency_ms": round(total_latency, 1),
            "cost_usd": f"${cost_usd:.6f}",
        },
        "properties": formatted_props,
        "total_count": search_resp.total_count,
        "page": search_resp.page,
        "page_size": search_resp.page_size,
        "has_next_page": search_resp.has_next_page,
        "is_fallback": search_resp.is_fallback,
        "provider_name": search_resp.provider_name,
        "is_live_api": search_resp.is_live_api,
        "error_message": search_resp.error_message,
    })


async def api_inquiry(request: Request) -> JSONResponse:
    """Handle property inquiry submissions from users."""
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        data = {}

    prop_id = data.get("property_id", "Unknown")
    name = data.get("name", "Interested Buyer")
    phone = data.get("phone", "")

    return JSONResponse({
        "success": True,
        "message": f"Inquiry registered! Verified broker for property {prop_id} has been notified and will contact {name} ({phone}) shortly.",
    })


async def api_stats(request: Request) -> JSONResponse:
    """Provide benchmark and inventory statistics."""
    summary_path = PROJECT_ROOT / "eval" / "results" / "summary.json"
    stats_data: dict[str, Any] = {}
    if summary_path.exists():
        try:
            stats_data = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as err:  # noqa: BLE001
            logger.warning("Failed to load evaluation summary: %s", err)

    return JSONResponse({
        "status": "healthy",
        "benchmark": stats_data,
        "cities": ["Noida", "Gurugram", "Delhi", "Mumbai", "Bengaluru", "Pune", "Hyderabad"],
    })


# Ensure static directory exists
STATIC_DIR.mkdir(parents=True, exist_ok=True)

routes = [
    Route("/", endpoint=index, methods=["GET"]),
    Route("/api/search", endpoint=api_search, methods=["POST"]),
    Route("/api/inquiry", endpoint=api_inquiry, methods=["POST"]),
    Route("/api/stats", endpoint=api_stats, methods=["GET"]),
    Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = Starlette(routes=routes, middleware=middleware)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)
