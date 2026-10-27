# Architecture & Experiment Decisions Log

This document records all architectural, statistical, and modeling decisions for the Hinglish Query Understanding Engine. Every entry includes the rationale and context for interview clarity.

---

## 1. Pre-Registered Success Target & Statistical Evaluation Criteria

* **Date:** Project Inception (Phase 0)
* **Pre-Registered Target:**
  > "The cascade's field-level F1 is within 3 points of the large-LLM baseline (B3), judged by a paired bootstrap on the F1 difference where the lower bound of the 95% CI is above -3, at under 25% of B3's cost per 1k queries."
* **Decision Rules:**
  * **No Target Shifting:** The success target will NOT be adjusted after observing results. If the cascade fails to meet the target, or if the cheap model alone matches the large LLM and renders the cascade redundant, that outcome is reported as an honest scientific finding.
  * **Paired Bootstrap on Differences:** Point estimates can be deceptive due to sample variance. We compute the difference $\Delta F_1 = F_{1,\text{cascade}} - F_{1,\text{B3}}$ across paired resamples (1,000+ iterations). The lower bound of the 95% percentile bootstrap confidence interval must be $> -3.0$.
  * **Comprehensive Cost Accounting:** Cost per 1,000 queries includes all token usage (prompt + completion), all retries, all self-consistency sample calls, and escalation calls to Tier 2.

---

## 2. Dataset Discipline & Split Integrity

* **Dev Set (~60 queries):** Used exclusively for prompt iteration, few-shot demonstration selection, threshold sweep, and confidence calibration.
* **Test Set (~140 queries):** Strictly locked. Scored only at final evaluation milestones. Never used to pick thresholds, select few-shots, or guide prompt changes.
* **Author-Crafted Real Data:** All dev and test queries must be hand-written and labeled based on real-world Indian search patterns (e.g., 99acres, MagicBricks). No auto-generation or synthetic contamination in dev or test splits.
* **Synthetic Data Isolation:** Any synthetic or augmented queries must be stored separately (e.g., `data/synthetic_train.jsonl`) and clearly tagged.

---

## 3. Directory Layout & Configuration Agnosticism

* **Decision:** Keep domain specifications (schema, aliases, units, prompts) out of Python code.
* **Why:** The engine must be domain-agnostic. Adding a new domain (e.g., jobs) should require only a new YAML config file without altering normalizer, cascade, or validation code.
* **Relative Path Handling:** All file operations in `src/config.py` resolve relative to `PROJECT_ROOT` to prevent path-resolution failures when executing commands from different working directories or CI environments.

---

## 4. Dated Model Pricing & Cost Accounting

* **Decision:** Model prices are maintained in a version-controlled, dated YAML file (`configs/prices.yaml`, effective 2024-10-01).
* **Why:** LLM pricing fluctuates across providers. Pinning prices with an effective date ensures deterministic and reproducible cost calculations in `eval/metrics.py`.

---

## 5. Model Determinism & Inference Protocol

* **Decision:** All evaluation runs will use `temperature = 0` (or the minimum supported deterministic setting) and pinned model IDs (e.g., `gpt-4o-mini-2024-07-18` / `gpt-4o-2024-08-06`).
* **Why:** Reproducibility. Raw model responses for each run will be saved in `eval/results/` to enable post-hoc audits and prevent unverified metric claims.

---

## 6. Deployment Interface: Streamlit

* **Decision:** Deploy via a single `app.py` on Streamlit Community Cloud rather than FastAPI + Docker.
* **Why:** Streamlit provides a direct interactive interface for live user queries, side-by-side model comparison, and visualization of evaluation metrics. API secrets are handled safely via `st.secrets` (falling back to local environment variables), with rate-limits (10 queries per session, 200 characters max) to prevent API credit exhaustion.
