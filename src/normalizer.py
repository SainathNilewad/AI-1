import re
from typing import Any


def clean_text(text: str) -> str:
    """Normalize whitespace and lowercase the query string."""
    return " ".join(text.lower().strip().split())


def parse_currency_amount(amount: str | float, unit: str, units_map: dict[str, int]) -> int:
    """Convert a numeric amount and unit into an integer INR value."""
    multiplier = units_map.get(unit.lower().strip(), 1)
    val = float(amount) * multiplier
    return round(val)


def normalize_city(city_raw: str, aliases: dict[str, str]) -> str:
    """Map raw city text to its canonical name using alias dictionary."""
    clean = city_raw.lower().strip()
    return aliases.get(clean, city_raw.title().strip())


def extract_bhk(text: str) -> int | None:
    """Extract BHK bedroom count from query text."""
    match = re.search(r"\b(\d+)\s*(?:bhk|bedroom|bed|rk)\b", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_budget(text: str, units_map: dict[str, int]) -> tuple[int | None, int | None]:
    """
    Extract budget_min and budget_max from text based on keywords and unit multipliers.
    Returns (budget_min, budget_max).
    """
    unit_pattern = r"(?:cr|crore|crores|lakh|lakhs|lac|lacs|l|k|thousand|hazar)"

    # Range with two units: e.g. "40 lakh to 50 lakh" or "25k - 30k"
    range_match_full = re.search(
        rf"(\d+(?:\.\d+)?)\s*({unit_pattern})\s*(?:to|-|se)\s*(\d+(?:\.\d+)?)\s*({unit_pattern})",
        text,
        re.IGNORECASE,
    )
    if range_match_full:
        low_val, low_unit, high_val, high_unit = range_match_full.groups()
        b_min = parse_currency_amount(low_val, low_unit, units_map)
        b_max = parse_currency_amount(high_val, high_unit, units_map)
        return (min(b_min, b_max), max(b_min, b_max))

    # Shared unit range: e.g. "5-8 cr" or "25 to 30k"
    range_match_shared = re.search(
        rf"(\d+(?:\.\d+)?)\s*(?:to|-|se)\s*(\d+(?:\.\d+)?)\s*({unit_pattern})",
        text,
        re.IGNORECASE,
    )
    if range_match_shared:
        low_val, high_val, unit = range_match_shared.groups()
        b_min = parse_currency_amount(low_val, unit, units_map)
        b_max = parse_currency_amount(high_val, unit, units_map)
        return (min(b_min, b_max), max(b_min, b_max))

    # Upper bound: "1.5 cr tak", "under 25k", "max 50 lakh", "below 30k"
    upper_match = re.search(
        rf"(?:under|below|max|upto|up to)\s*(\d+(?:\.\d+)?)\s*({unit_pattern})|"
        rf"(\d+(?:\.\d+)?)\s*({unit_pattern})\s*(?:tak|max)",
        text,
        re.IGNORECASE,
    )
    if upper_match:
        val = upper_match.group(1) or upper_match.group(3)
        unit = upper_match.group(2) or upper_match.group(4)
        return (None, parse_currency_amount(val, unit, units_map))

    # Lower bound: "starting 50 lakh", "above 25k", "min 1 cr"
    lower_match = re.search(
        rf"(?:starting|above|min|minimum)\s*(\d+(?:\.\d+)?)\s*({unit_pattern})|"
        rf"(\d+(?:\.\d+)?)\s*({unit_pattern})\s*(?:plus|\+)",
        text,
        re.IGNORECASE,
    )
    if lower_match:
        val = lower_match.group(1) or lower_match.group(3)
        unit = lower_match.group(2) or lower_match.group(4)
        return (parse_currency_amount(val, unit, units_map), None)

    # Single unqualified amount: e.g. "budget 25k", "25k rent", "1.5 cr flat"
    single_match = re.search(
        rf"(?:budget\s*)?(\d+(?:\.\d+)?)\s*({unit_pattern})",
        text,
        re.IGNORECASE,
    )
    if single_match:
        val, unit = single_match.groups()
        return (None, parse_currency_amount(val, unit, units_map))

    return (None, None)


def normalize_query(text: str) -> str:
    """Lowercase and normalize whitespace in query."""
    return clean_text(text)


def extract_regex_candidates(text: str, domain: str = "real_estate") -> dict[str, Any]:
    """Extract candidate filter fields using deterministic regex and keyword matching."""
    from src.config import load_domain_config

    clean = clean_text(text)
    cfg = load_domain_config(domain)
    units_map = cfg.get("units", {})
    city_aliases = cfg.get("city_aliases", {})
    keywords = cfg.get("keywords", {})

    bhk = extract_bhk(clean)
    budget_min, budget_max = extract_budget(clean, units_map)

    matched_city = None
    for alias, canonical in sorted(city_aliases.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", clean):
            matched_city = canonical
            break

    matched_ptype = None
    prop_keywords = keywords.get("property_type", {})
    for kw, canonical in sorted(prop_keywords.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(kw)}\b", clean):
            matched_ptype = canonical
            break

    matched_tx = None
    tx_keywords = keywords.get("transaction", {})
    for kw, canonical in sorted(tx_keywords.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(kw)}\b", clean):
            matched_tx = canonical
            break

    matched_furnishing = None
    furn_keywords = keywords.get("furnishing", {})
    for kw, canonical in sorted(furn_keywords.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(kw)}\b", clean):
            matched_furnishing = canonical
            break

    matched_possession = None
    poss_keywords = keywords.get("possession", {})
    for kw, canonical in sorted(poss_keywords.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(kw)}\b", clean):
            matched_possession = canonical
            break

    matched_pref = None
    pref_keywords = keywords.get("price_preference", {})
    for kw, canonical in sorted(pref_keywords.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(kw)}\b", clean):
            matched_pref = canonical
            break

    matched_near: list[str] = []
    near_kws = keywords.get("near_amenities", {})
    for kw, canonical in sorted(near_kws.items(), key=lambda x: len(x[0]), reverse=True):
        if (
            re.search(rf"\b(?:near|paas|close to)\s+(?:the\s+)?{re.escape(kw)}\b", clean)
            or re.search(rf"\b{re.escape(kw)}\s+(?:ke\s+)?paas\b", clean)
            or (re.search(r"\b(?:near|paas)\b", clean) and re.search(rf"\b{re.escape(kw)}\b", clean))
        ) and canonical not in matched_near:
            matched_near.append(canonical)

    matched_locality = None
    sec_match = re.search(r"\b(?:sector|sec)\s*(\d+[a-zA-Z]?)\b", clean)
    if sec_match:
        matched_locality = f"Sector {sec_match.group(1).upper()}"
    else:
        localities_map = cfg.get("localities", {})
        for loc_alias, canonical_loc in sorted(localities_map.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(rf"\b{re.escape(loc_alias)}\b", clean):
                matched_locality = canonical_loc
                break


    return {
        "bhk": bhk,
        "budget_min": budget_min,
        "budget_max": budget_max,
        "city": matched_city,
        "locality": matched_locality,
        "property_type": matched_ptype,
        "transaction": matched_tx,
        "furnishing": matched_furnishing,
        "possession": matched_possession,
        "price_preference": matched_pref,
        "near": matched_near,
    }

