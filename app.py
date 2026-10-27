"""Hinglish Query Understanding Engine - Streamlit Interactive App."""

import os

import streamlit as st

from src.baselines import parse_b1, parse_b2, parse_b3, parse_cascade
from src.config import PROJECT_ROOT

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
    "noida me 2bhk sasta near metro", "gurgaon sec 54 3bhk under 1.5cr",
    "bandra flat 2 bhk rent under 60k", "south delhi 4bhk luxury apartment",
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
        try:
            if api_key:
                res = parse_cascade(query, api_key=api_key)
            else:
                res = parse_b1(query)
                st.info("Running local rule baseline B1. Set GROQ_API_KEY to activate Groq cascade.")

            st.success(f"Parsed successfully (Session query {st.session_state.query_count}/10)")
            m1, m2, m3, m4 = st.columns(4)
            tier_names = {"cascade_tier1": "Tier 1 (Cheap 20B)", "cascade_tier2": "Tier 2 (Large 120B)"}
            m1.metric("Tier Used", tier_names.get(res.tier, "Tier 0 (Rule Baseline)"))
            m2.metric("Confidence", f"{res.confidence * 100:.0f}%")
            m3.metric("Latency", f"{res.latency_ms:.1f} ms")
            m4.metric("Cost", f"${res.cost_usd:.6f}")

            st.subheader("Structured Search Filter")
            st.json(res.filter.model_dump(exclude_none=True))

            if compare_mode:
                st.divider()
                st.subheader("Model Comparison: Cheap (20B) vs Large (120B)")
                if api_key:
                    c1, c2 = st.columns(2)
                    b2_res = parse_b2(query, api_key=api_key)
                    b3_res = parse_b3(query, api_key=api_key)
                    with c1:
                        st.markdown(f"**Cheap (20B)** | Latency: {b2_res.latency_ms}ms | Cost: ${b2_res.cost_usd:.6f}")
                        st.json(b2_res.filter.model_dump(exclude_none=True))
                    with c2:
                        st.markdown(f"**Large (120B)** | Latency: {b3_res.latency_ms}ms | Cost: ${b3_res.cost_usd:.6f}")
                        st.json(b3_res.filter.model_dump(exclude_none=True))
                else:
                    st.warning("GROQ_API_KEY is required to compare live LLM model outputs.")
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
