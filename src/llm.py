"""Groq API client with token accounting and offline replay caching."""

import hashlib
import json
import os
import re
import time
from typing import Any

import httpx

from src.config import PROJECT_ROOT, load_pricing_config

CACHE_DIR = PROJECT_ROOT / ".cache" / "groq_replay"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

EXTRACTION_SYSTEM_PROMPT = """You are a real estate search filter parser for colloquial Hinglish queries.
Extract the user's intent into a clean JSON object with these optional fields:
- "bhk": integer (e.g. 1, 2, 3, 4) or null
- "budget_min": integer in INR (e.g. 2000000) or null
- "budget_max": integer in INR (e.g. 15000000) or null
- "city": standardized title-case string (e.g. "Noida", "Gurugram", "Mumbai", "Delhi", "Bengaluru") or null
- "locality": string (e.g. "Sector 54", "Bandra West", "Whitefield") or null
- "property_type": lowercase string ("flat", "house", "plot", "villa", "pg") or null
- "transaction": lowercase string ("buy", "rent") or null
- "furnishing": lowercase string ("furnished", "semi", "unfurnished") or null
- "possession": lowercase string ("ready_to_move", "under_construction") or null
- "price_preference": lowercase string ("cheap", "premium", "none") or null
- "near": list of standardized strings (e.g. ["metro", "hospital", "school", "market", "mall", "highway"]) or []

Rules:
1. Always normalize city names: "gurgaon" -> "Gurugram", "bangalore" -> "Bengaluru", "bombay" -> "Mumbai".
2. Convert currency multipliers: "k" -> *1000, "lac"/"lakh" -> *100000, "cr"/"crore" -> *10000000.
3. If "under" or "below" or "tak", set budget_max. If "above" or "min", set budget_min. If a range like "1 to 1.5 cr", set both.
4. "rent"/"kiraya" -> transaction: "rent"; "buy"/"kharidna"/"purchase" -> transaction: "buy".
5. "sasta"/"cheap"/"affordable" -> price_preference: "cheap"; "luxury"/"premium"/"posh" -> price_preference: "premium".
6. If a field is not mentioned or cannot be inferred with certainty, set it to null (or [] for near).
7. Return ONLY a valid JSON object matching the keys above. Do not include markdown codeblocks or conversational text."""


def compute_token_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate query cost in USD based on configs/prices.yaml."""
    pricing = load_pricing_config().get("models", {}).get(model_name, {})
    if not pricing:
        return 0.0

    in_rate = pricing.get("input_cost_per_1m", 0.0)
    out_rate = pricing.get("output_cost_per_1m", 0.0)
    cost = (input_tokens / 1_000_000.0) * in_rate + (output_tokens / 1_000_000.0) * out_rate
    return round(cost, 6)


def _get_cache_path(model_name: str, messages: list[dict[str, str]]) -> Any:
    serialized = f"{model_name}:{json.dumps(messages, sort_keys=True)}"
    key = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key}.json"


def call_groq_api(
    messages: list[dict[str, str]],
    model_name: str,
    api_key: str | None = None,
    use_cache: bool = True,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Call Groq chat completions API with offline replay caching."""
    resolved_key = api_key or os.getenv("GROQ_API_KEY", "")
    cache_path = _get_cache_path(model_name, messages)

    if use_cache and cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["cached"] = True
            return data

    if not resolved_key:
        raise ValueError("GROQ_API_KEY is required to invoke Groq API (neither passed nor in env)")

    pricing_config = load_pricing_config().get("models", {}).get(model_name, {})
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
    }

    if "reasoning_effort" in pricing_config:
        payload["reasoning_effort"] = pricing_config["reasoning_effort"]

    headers = {
        "Authorization": f"Bearer {resolved_key}",
        "Content-Type": "application/json",
    }

    t0 = time.perf_counter()
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(GROQ_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        raw = resp.json()
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    choice = raw.get("choices", [{}])[0].get("message", {})
    content = choice.get("content", "{}")
    usage = raw.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    cost_usd = compute_token_cost(model_name, input_tokens, output_tokens)

    result = {
        "content": content,
        "model": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "cached": False,
    }

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    return result


def extract_with_llm(
    query: str,
    model_name: str,
    api_key: str | None = None,
    use_cache: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extract real estate search filters using a Groq LLM."""
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Extract search filter for: {query}"},
    ]

    res = call_groq_api(messages, model_name=model_name, api_key=api_key, use_cache=use_cache)
    content = res.get("content", "{}").strip()

    # Strip code block wrappers if returned
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    try:
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            parsed = {}
    except json.JSONDecodeError:
        parsed = {}

    stats = {
        "model": model_name,
        "input_tokens": res.get("input_tokens", 0),
        "output_tokens": res.get("output_tokens", 0),
        "cost_usd": res.get("cost_usd", 0.0),
        "latency_ms": res.get("latency_ms", 0.0),
        "cached": res.get("cached", False),
    }

    return parsed, stats
