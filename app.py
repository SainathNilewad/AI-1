"""Hinglish Query Understanding Engine - Streamlit Interactive App."""

import os
import time

import streamlit as st

from src.config import PROJECT_ROOT
from src.normalizer import extract_regex_candidates, normalize_query
from src.schema import SearchFilter

# 1. Page Configuration & Header
st.set_page_config(page_title="Hinglish Query Parser", layout="wide")
st.title("Hinglish Real Estate Query Parser")
st.caption("Converts colloquial Hinglish search queries into validated structured JSON filters.")

# 2. Safety & Session State
if "query_count" not in st.session_state:
    st.session_state.query_count = 0
if "current_query" not in st.session_state:
    st.session_state.current_query = "noida me 2bhk sasta near metro"

api_key = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))

# 3. Clickable Example Queries
EXAMPLES = [
    "noida me 2bhk sasta near metro",
    "gurgaon sec 54 3bhk under 1.5cr",
    "bandra flat 2 bhk rent under 60k",
    "south delhi 4bhk luxury apartment",
    "whitefield bangalore 1bhk 25k",
]
st.write("**Click an example query:**")
cols = st.columns(len(EXAMPLES))
for idx, ex in enumerate(EXAMPLES):
    if cols[idx].button(ex, key=f"btn_{idx}"):
        st.session_state.current_query = ex

# 4. Input & Controls
query = st.text_input(
    "Search Query (max 200 chars):",
    value=st.session_state.current_query,
    max_chars=200,
)
col_btn, col_chk = st.columns([1, 4])
parse_btn = col_btn.button("Parse Query", type="primary")
compare_mode = col_chk.checkbox("Compare cheap vs large model output", value=False)

# 5. Parse Query Execution
if parse_btn:
    if not query.strip():
        st.warning("Please enter a non-empty search query.")
    elif st.session_state.query_count >= 10:
        st.error("Session limit reached (10 queries maximum). Please reload the page to start a new session.")
    else:
        st.session_state.query_count += 1
        t0 = time.perf_counter()
        try:
            normalized = normalize_query(query)
            extracted = extract_regex_candidates(normalized)
            result = SearchFilter(
                bhk=extracted.get("bhk"),
                budget_min=extracted.get("budget_min"),
                budget_max=extracted.get("budget_max"),
                city=extracted.get("city"),
                locality=extracted.get("locality"),
                property_type=extracted.get("property_type"),
            )
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            st.success(f"Parsed successfully (Session query {st.session_state.query_count}/10)")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tier Used", "Tier 0 (Rule Baseline)")
            m2.metric("Confidence", "High" if result.bhk and result.city else "Medium")
            m3.metric("Latency", f"{latency_ms} ms")
            m4.metric("Cost", "$0.000000")

            st.subheader("Structured Search Filter")
            st.json(result.model_dump(exclude_none=True))

            if compare_mode:
                st.info("Side-by-side LLM model comparison activates upon Groq API key configuration and cascade activation.")
        except Exception as e:  # noqa: BLE001
            st.error(f"Failed to parse query: {e}")

# 6. Evaluation Results Section
st.divider()
st.subheader("Benchmark & Evaluation Results")
eval_dir = PROJECT_ROOT / "eval" / "results"
summary_file = eval_dir / "summary.json"
plot_file = eval_dir / "cost_vs_accuracy.png"

if summary_file.exists() and plot_file.exists():
    st.image(str(plot_file), caption="Cost vs Accuracy Pareto Curve")
    st.json(summary_file.read_text(encoding="utf-8"))
else:
    st.info("Offline evaluation results will display here once the evaluation suite runs.")
