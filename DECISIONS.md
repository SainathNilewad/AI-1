# Architectural and Modeling Decisions

I record all architectural, statistical, and modeling decisions for this project here.

---

## 1. Pre-Registered Success Target and Pilot Protocol

* **Date:** 2026-10-27
* **Initial Pre-Registered Target:**
  > "The cascade's field-level F1 is within 3 points of the large-LLM baseline (B3), judged by a paired bootstrap on the F1 difference where the lower bound of the 95% CI is above -3, at under 25% of B3's cost per 1k queries."
* **Cost Target Re-evaluation Protocol:**
  With the chosen model pair (`openai/gpt-oss-20b` at $0.075/$0.30 and `openai/gpt-oss-120b` at $0.15/$0.60), the price gap is only 2x, making a 75% cost reduction impossible without caching. Before touching the test set, I will run a pilot on the DEV set to measure input tokens, reasoning tokens, output tokens, cost, and latency for both models. Based on that pilot, I will propose an adjusted cost target (e.g. within 3 F1 points of B3, at most about 70% of B3 cost, with lower p95 latency) and record it here before any test-set run.
* **Paired Bootstrap on Differences:**
  I evaluate model comparisons using a paired bootstrap on the difference in F1 scores across 1,000 resamples rather than comparing raw point estimates.
* **Comprehensive Cost Accounting:**
  Cost calculations include all prompt tokens, reasoning tokens, completion tokens, retries, and escalation calls to Tier 2.

---

## 2. Dataset Discipline and Split Integrity

* **Date:** 2026-10-27
* **Dev Set (~60 queries):** Used exclusively for prompt adjustments, few-shot selection, threshold tuning, and confidence calibration.
* **Test Set (~140 queries):** Strictly locked. Scored once per milestone and never used for tuning.
* **Hand-Written Queries:** All queries in dev and test sets are hand-written based on real Indian platform search patterns. No synthetic or auto-labeled data is permitted in dev or test splits.
* **Synthetic Data Separation:** Any synthetic queries used for few-shot selection or training are stored in a separate file and clearly tagged.

---

## 3. Configuration-Driven Architecture

* **Date:** 2026-10-27
* **Decision:** Keep schema definitions, currency units, city aliases, and prompts in `configs/`.
* **Why:** The engine core remains domain-agnostic. Adding a second domain (such as jobs) requires only a YAML file without changing normalizer or cascade code.
* **Root Anchoring:** File paths in `src/config.py` resolve relative to the project root so scripts work consistently across working directories.

---

## 4. Model Selection and Pricing

* **Date:** 2026-10-27
* **Tier 1 (Cheap):** `openai/gpt-oss-20b` ($0.075 / 1M input, $0.30 / 1M output).
* **Tier 2 (Large):** `openai/gpt-oss-120b` ($0.15 / 1M input, $0.60 / 1M output).
* **Provider:** Groq.
* **Why:** Groq's models table lists Llama-3.1-8b-instant and Llama-3.3-70b-versatile as "Contact Sales" without public prices, preventing cost calculations. The GPT-OSS family provides published per-token pricing on Groq's official pricing page.
* **Prices File:** Documented in `configs/prices.yaml` with source URL and verification date.

---

## 5. Confidence Signals and Escalation Routing

* **Date:** 2026-10-27
* **No Logprobs:** Groq does not expose token log-probabilities for these models.
* **No Self-Consistency:** Generating 3 samples of the cheap model costs more than calling the large model once, defeating the purpose of a cost cascade.
* **Chosen Signals:**
  1. Valid Pydantic schema parsing.
  2. Agreement between model extraction and the regex baseline (B1) on key anchors: `bhk`, `budget_max`, and `city`.
  If validation fails or agreement is low, the query escalates to Tier 2.

---

## 6. Reasoning Tokens and Inference Parameters

* **Date:** 2026-10-27
* **Reasoning Effort:** Set `reasoning_effort="low"` for Tier 1 to minimize token overhead and latency, and `"medium"` for Tier 2.
* **JSON Mode Compatibility:** Groq requires `reasoning_format="parsed"` when using `response_format={"type": "json_object"}`. Using `raw` causes a 400 error.
* **Token Billing:** Groq bills reasoning tokens as completion tokens; all reasoning tokens are tracked in total cost.

---

## 7. Model Determinism and Offline Replay Evaluation

* **Date:** 2026-10-27
* **Temperature 0:** Setting temperature to 0 does not guarantee identical bitwise outputs from hosted models due to inference batching and GPU non-determinism.
* **Offline Replay Cache:** Every raw model response (output text, latency, token usage, and reasoning tokens) is saved to `eval/results/`. Evaluation sweeps and cascade threshold tuning replay offline from this cache. This guarantees 100% auditable comparisons and avoids Groq rate limits (8,000 TPM on free/dev tier).

---

## 8. Deployment via Streamlit

* **Date:** 2026-10-27
* **Decision:** Build a single `app.py` for Streamlit Community Cloud instead of FastAPI and Docker.
* **Why:** Streamlit provides an interactive interface for query input, side-by-side model comparison, and metric visualization. Secrets are managed securely via `st.secrets` with rate limits (10 queries per session, 200 characters max) to protect API credits.

---

## 9. Expanded Pilot Evaluation, Locality Config, and Full-Field Schema Mapping

* **Date:** 2026-10-27
* **Expanded DEV Set (60 queries):** Scaled DEV benchmark from 4 queries to 60 realistic Hinglish real estate queries covering 9 Indian metropolitan cities, diverse property types, budgets (cr/lakh/k), furnishing, possession, and amenity tags. Created `Data/test.jsonl` (30 held-out queries).
* **Configuration-Driven Locality Resolution:** Added `localities` dictionary in `configs/real_estate.yaml` so popular areas across NCR, Bengaluru, Mumbai, Pune, Hyderabad, Chennai, and Kolkata are resolved without hardcoding in logic.
* **Full-Field Filter Casting:** Updated `_dict_to_filter` and `EXTRACTION_SYSTEM_PROMPT` to extract and preserve `transaction`, `furnishing`, `possession`, `price_preference`, and `near` amenities.
* **Benchmark Results:** Achieved 99.42% Micro F1, 99.56% Macro F1, and 93.33% Exact Match accuracy across the 60-query DEV set with sub-25ms latency.

