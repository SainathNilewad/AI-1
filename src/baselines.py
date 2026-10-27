"""Baselines (B1, B2, B3) and cost-aware cascade for Hinglish query parsing."""

import time
from typing import Any

from pydantic import BaseModel, ValidationError

from src.llm import extract_with_llm
from src.normalizer import extract_regex_candidates, normalize_query
from src.schema import SearchFilter

CHEAP_MODEL = "openai/gpt-oss-20b"
LARGE_MODEL = "openai/gpt-oss-120b"


class ExtractionResult(BaseModel):
    """Unified container for query extraction output and operational metrics."""

    filter: SearchFilter
    tier: str
    confidence: float
    latency_ms: float
    cost_usd: float
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False
    escalated: bool = False


def _dict_to_filter(data: dict[str, Any]) -> SearchFilter:
    """Safely cast raw dictionary to SearchFilter with canonical value mappings."""
    clean_data = dict(data)
    ptype = clean_data.get("property_type")
    if isinstance(ptype, str):
        ptype_clean = ptype.lower().strip()
        if ptype_clean in ["apartment", "apt", "builder floor", "flat"]:
            clean_data["property_type"] = "flat"
        elif ptype_clean in ["independent house", "kothi", "house"]:
            clean_data["property_type"] = "house"
        elif ptype_clean in ["paying guest", "hostel", "pg"]:
            clean_data["property_type"] = "pg"
        elif ptype_clean in ["land", "plot"]:
            clean_data["property_type"] = "plot"
        elif ptype_clean in ["villa"]:
            clean_data["property_type"] = "villa"
        else:
            clean_data["property_type"] = None

    valid_fields = {
        k: clean_data[k]
        for k in ["bhk", "budget_min", "budget_max", "city", "locality", "property_type"]
        if k in clean_data and clean_data[k] is not None
    }
    return SearchFilter(**valid_fields)


def parse_b1(query: str) -> ExtractionResult:
    """Baseline B1: Pure rule-based / regex normalization."""
    t0 = time.perf_counter()
    normalized = normalize_query(query)
    extracted = extract_regex_candidates(normalized)
    filter_obj = _dict_to_filter(extracted)
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    has_core = bool(filter_obj.bhk or filter_obj.city)
    confidence = 0.85 if has_core else 0.40

    return ExtractionResult(
        filter=filter_obj,
        tier="b1_rules",
        confidence=confidence,
        latency_ms=latency_ms,
        cost_usd=0.0,
        input_tokens=0,
        output_tokens=0,
        cached=False,
        escalated=False,
    )


def parse_b2(query: str, api_key: str | None = None, use_cache: bool = True) -> ExtractionResult:
    """Baseline B2: Cheap LLM only (openai/gpt-oss-20b)."""
    raw_dict, stats = extract_with_llm(query, model_name=CHEAP_MODEL, api_key=api_key, use_cache=use_cache)
    try:
        filter_obj = _dict_to_filter(raw_dict)
        confidence = 0.85
    except (ValidationError, TypeError, ValueError):
        filter_obj = SearchFilter()
        confidence = 0.0

    return ExtractionResult(
        filter=filter_obj,
        tier="b2_cheap",
        confidence=confidence,
        latency_ms=stats.get("latency_ms", 0.0),
        cost_usd=stats.get("cost_usd", 0.0),
        input_tokens=stats.get("input_tokens", 0),
        output_tokens=stats.get("output_tokens", 0),
        cached=stats.get("cached", False),
        escalated=False,
    )


def parse_b3(query: str, api_key: str | None = None, use_cache: bool = True) -> ExtractionResult:
    """Baseline B3: Large LLM only (openai/gpt-oss-120b)."""
    raw_dict, stats = extract_with_llm(query, model_name=LARGE_MODEL, api_key=api_key, use_cache=use_cache)
    try:
        filter_obj = _dict_to_filter(raw_dict)
        confidence = 0.95
    except (ValidationError, TypeError, ValueError):
        filter_obj = SearchFilter()
        confidence = 0.0

    return ExtractionResult(
        filter=filter_obj,
        tier="b3_large",
        confidence=confidence,
        latency_ms=stats.get("latency_ms", 0.0),
        cost_usd=stats.get("cost_usd", 0.0),
        input_tokens=stats.get("input_tokens", 0),
        output_tokens=stats.get("output_tokens", 0),
        cached=stats.get("cached", False),
        escalated=False,
    )


def _compute_confidence(filter_obj: SearchFilter, regex_candidates: dict[str, Any]) -> float:
    """Compute confidence score based on schema validity and rule agreement."""
    score = 0.50

    # Agreement on BHK if regex found one
    if regex_candidates.get("bhk") is not None:
        if filter_obj.bhk == regex_candidates.get("bhk"):
            score += 0.25
        else:
            score -= 0.35

    # Agreement on City if regex found one
    if regex_candidates.get("city") is not None:
        if filter_obj.city == regex_candidates.get("city"):
            score += 0.25
        else:
            score -= 0.35

    # Agreement on Budget Max if regex found one
    if regex_candidates.get("budget_max") is not None and filter_obj.budget_max is not None:
        ratio = filter_obj.budget_max / regex_candidates.get("budget_max")
        if 0.9 <= ratio <= 1.1:
            score += 0.15
        else:
            score -= 0.20

    return max(0.0, min(1.0, round(score, 2)))


def parse_cascade(
    query: str,
    api_key: str | None = None,
    use_cache: bool = True,
    confidence_threshold: float = 0.70,
) -> ExtractionResult:
    """Cost-aware model cascade.

    Routes query to cheap model (openai/gpt-oss-20b).
    If confidence < threshold or validation fails, escalates to large model (openai/gpt-oss-120b).
    Tracks total cost and cumulative latency across tiers.
    """
    normalized = normalize_query(query)
    regex_candidates = extract_regex_candidates(normalized)

    # Step 1: Run cheap model
    cheap_dict, cheap_stats = extract_with_llm(
        query, model_name=CHEAP_MODEL, api_key=api_key, use_cache=use_cache
    )

    is_valid_schema = True
    try:
        cheap_filter = _dict_to_filter(cheap_dict)
    except (ValidationError, TypeError, ValueError):
        cheap_filter = SearchFilter()
        is_valid_schema = False

    confidence = _compute_confidence(cheap_filter, regex_candidates) if is_valid_schema else 0.0

    # If confident and schema is valid, accept Tier 1
    if is_valid_schema and confidence >= confidence_threshold:
        return ExtractionResult(
            filter=cheap_filter,
            tier="cascade_tier1",
            confidence=confidence,
            latency_ms=cheap_stats.get("latency_ms", 0.0),
            cost_usd=cheap_stats.get("cost_usd", 0.0),
            input_tokens=cheap_stats.get("input_tokens", 0),
            output_tokens=cheap_stats.get("output_tokens", 0),
            cached=cheap_stats.get("cached", False),
            escalated=False,
        )

    # Step 2: Escalate to large model
    large_dict, large_stats = extract_with_llm(
        query, model_name=LARGE_MODEL, api_key=api_key, use_cache=use_cache
    )

    try:
        large_filter = _dict_to_filter(large_dict)
        final_confidence = 0.95
    except (ValidationError, TypeError, ValueError):
        # Fall back to regex extraction if even large model fails schema
        large_filter = _dict_to_filter(regex_candidates)
        final_confidence = 0.40

    total_latency = round(cheap_stats.get("latency_ms", 0.0) + large_stats.get("latency_ms", 0.0), 2)
    total_cost = round(cheap_stats.get("cost_usd", 0.0) + large_stats.get("cost_usd", 0.0), 6)
    total_in = cheap_stats.get("input_tokens", 0) + large_stats.get("input_tokens", 0)
    total_out = cheap_stats.get("output_tokens", 0) + large_stats.get("output_tokens", 0)

    return ExtractionResult(
        filter=large_filter,
        tier="cascade_tier2",
        confidence=final_confidence,
        latency_ms=total_latency,
        cost_usd=total_cost,
        input_tokens=total_in,
        output_tokens=total_out,
        cached=cheap_stats.get("cached", False) and large_stats.get("cached", False),
        escalated=True,
    )
