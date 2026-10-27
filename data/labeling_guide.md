# Real Estate Query Labeling Guide

This guide defines the annotation standard for labeling real estate queries in the Hinglish dataset. All annotations for dev and test splits must follow these exact rules.

---

## 1. Core Principle
* **Never Guess:** If a value is not explicitly stated or directly implied in the query, leave the field as `null`. Never impute defaults (e.g., do not default `transaction` to "buy" if unstated).

---

## 2. Field-by-Field Rules

### `city` & `locality`
* **Canonical City Names:** Map city names to canonical form (`gurgaon` -> "Gurugram", `bombay` -> "Mumbai", `bangalore` -> "Bengaluru").
* **Locality Separation:** If a query mentions "noida sector 62", label `city`: "Noida", `locality`: "Sector 62".
* **Locality Without City:** If query mentions only "indiranagar", label `city`: null, `locality`: "Indiranagar".

### `bhk` (integer)
* Standardize bedroom counts to an integer: "2bhk", "2 bhk", "2 bedroom", "2 bed" -> `2`.
* "1 rk" or "studio" -> `bhk`: 1.

### `property_type` ("flat" | "house" | "plot" | "villa" | "pg")
* "flat", "apartment", "apt", "builder floor" -> "flat"
* "house", "independent house", "kothi" -> "house"
* "villa" -> "villa"
* "plot", "land" -> "plot"
* "pg", "paying guest", "hostel" -> "pg"

### `transaction` ("buy" | "rent")
* "rent", "kiraya", "on rent" -> "rent"
* "buy", "purchase", "sale", "kharidna" -> "buy"
* If ambiguous (e.g., "noida 2bhk 50 lakh"), leave `transaction`: null unless the budget or phrasing clearly dictates it.

### `budget_min` & `budget_max` (INR integers)
* **Upper Bound / "tak" / "under":**
  * "1.5 cr tak", "under 50k", "max 80 lakh", "below 30k" -> set `budget_max` only. `budget_min` remains `null`.
* **Lower Bound / "above" / "starting":**
  * "starting 50 lakh", "above 25k", "min 1 cr" -> set `budget_min` only. `budget_max` remains `null`.
* **Range ("to", "-", "se"):**
  * "25k to 30k", "25-30k", "40 se 50 lakh" -> `budget_min`: 25000, `budget_max`: 30000.
* **Single Unqualified Budget Number:**
  * "budget 50 lakh", "50 lakh me flat" -> set `budget_max`: 5000000.

### `furnishing` ("furnished" | "semi" | "unfurnished")
* "furnished", "full furnished" -> "furnished"
* "semi furnished", "semi" -> "semi"
* "unfurnished", "empty", "khali" -> "unfurnished"

### `possession` ("ready_to_move" | "under_construction")
* "ready to move", "rtm", "ready" -> "ready_to_move"
* "under construction", "uc", "possession 2026" -> "under_construction"

### `near` (list of strings)
* Extract amenities following "near", "paas", "close to":
  * "near metro" -> `["metro"]`
  * "near metro station and market" -> `["metro", "market"]`
* Use canonical amenity tags: "metro", "school", "hospital", "mall", "market", "highway".

### `price_preference` ("cheap" | "premium" | "none")
* **Qualitative without numbers:**
  * "sasta 2bhk", "cheap flat", "low budget flat" -> `price_preference`: "cheap" (do not guess budget numbers).
  * "luxury 3bhk", "premium villa", "posh flat" -> `price_preference`: "premium".
* If budget numbers are provided without qualitative words, set `price_preference`: null.

---

## 3. Example Annotations

| Raw Query | Annotated JSON Filter |
|---|---|
| `noida me 2bhk sasta near metro` | `{"city": "Noida", "bhk": 2, "price_preference": "cheap", "near": ["metro"]}` |
| `gurgaon 3 bhk ready to move 1.5 cr tak` | `{"city": "Gurugram", "bhk": 3, "possession": "ready_to_move", "budget_max": 15000000}` |
| `furnished 1bhk rent dwarka 25k` | `{"locality": "Dwarka", "bhk": 1, "transaction": "rent", "furnishing": "furnished", "budget_max": 25000}` |
| `4bhk luxury villa buy in bangalore 5-8 cr` | `{"city": "Bengaluru", "bhk": 4, "property_type": "villa", "transaction": "buy", "price_preference": "premium", "budget_min": 50000000, "budget_max": 80000000}` |
