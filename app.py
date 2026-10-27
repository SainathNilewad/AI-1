"""Hinglish Query Understanding Engine - Streamlit Interactive App."""

import json
import os

import streamlit as st

from src.baselines import parse_b1, parse_b2, parse_b3, parse_cascade
from src.config import PROJECT_ROOT
from src.property_api import get_property_client
from src.search import format_inr, search_properties_api

# 1. Page Configuration & Header
st.set_page_config(page_title="Hinglish Real Estate Query Parser", page_icon="🏠", layout="wide")
st.title("🏠 Hinglish Real Estate Query Parser")
st.caption("Converts colloquial Hinglish search queries into validated structured JSON filters using a cost-aware cascade.")

# 2. Safety & Session State
if "query_count" not in st.session_state:
    st.session_state.query_count = 0
if "current_query" not in st.session_state:
    st.session_state.current_query = "noida me 2bhk sasta near metro"

def _resolve_api_key() -> str:
    try:
        return str(st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", "")))
    except Exception:  # noqa: BLE001
        return os.getenv("GROQ_API_KEY", "")


def _resolve_property_api_config() -> tuple[str, str, str]:
    try:
        p_key = str(st.secrets.get("REAL_ESTATE_API_KEY", os.getenv("REAL_ESTATE_API_KEY", "")))
        p_provider = str(st.secrets.get("REAL_ESTATE_API_PROVIDER", os.getenv("REAL_ESTATE_API_PROVIDER", "auto")))
        p_url = str(st.secrets.get("REAL_ESTATE_API_BASE_URL", os.getenv("REAL_ESTATE_API_BASE_URL", "")))
        return p_key, p_provider, p_url
    except Exception:  # noqa: BLE001
        return (
            os.getenv("REAL_ESTATE_API_KEY", ""),
            os.getenv("REAL_ESTATE_API_PROVIDER", "auto"),
            os.getenv("REAL_ESTATE_API_BASE_URL", ""),
        )


api_key = _resolve_api_key()
env_prop_key, env_prop_provider, env_prop_url = _resolve_property_api_config()

# Sidebar: Property Provider Settings
with st.sidebar:
    st.header("⚙️ Data Settings")
    st.markdown("### Real Estate Property Provider")
    provider_choice = st.radio(
        "Listing Provider:",
        options=["Local Catalog (Verified Indian Listings)", "External REST API (RentCast Standard)"],
        index=0 if env_prop_provider == "local" or not env_prop_key else 1,
        help="Select between verified local Indian property database or external live REST API.",
    )
    is_live_selected = "External REST API" in provider_choice

    prop_api_key = st.text_input(
        "Property API Key (X-Api-Key):",
        value=env_prop_key,
        type="password",
        disabled=not is_live_selected,
        help="API key for authorized live real estate listings.",
    )
    prop_api_url = st.text_input(
        "Custom Endpoint (Optional):",
        value=env_prop_url,
        disabled=not is_live_selected,
        placeholder="https://api.rentcast.io/v1/listings/rental/long-term",
    )
    page_size_val = st.selectbox("Listings per page:", options=[6, 9, 12, 18], index=1)


# 3. Clickable Example Queries
EXAMPLES = [
    "noida me 2bhk sasta near metro",
    "gurgaon sec 54 3bhk ready to move 1.5cr tak",
    "furnished 1bhk rent dwarka 25k",
    "south delhi 4bhk luxury apartment buy 3 to 4 cr",
    "whitefield bangalore 2bhk semi furnished flat 30k rent",
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

            # Operational Metrics
            m1, m2, m3, m4 = st.columns(4)
            tier_names = {
                "cascade_tier1": "Tier 1 (Cheap 20B)",
                "cascade_tier2": "Tier 2 (Large 120B)",
                "b1_rules": "Tier 0 (Rule Baseline)",
            }
            m1.metric("Tier Used", tier_names.get(res.tier, res.tier))
            m2.metric("Confidence", f"{res.confidence * 100:.0f}%")
            m3.metric("Latency", f"{res.latency_ms:.1f} ms")
            m4.metric("Cost", f"${res.cost_usd:.6f}")

            # Structured Attributes Visual Cards
            st.subheader("Extracted Attributes")
            f = res.filter
            attr_cols = st.columns(4)

            city_loc = f"{f.city or '-'}" + (f" ({f.locality})" if f.locality else "")
            attr_cols[0].write(f"**📍 Location:** {city_loc}")
            attr_cols[1].write(f"**🛏️ BHK:** {f.bhk or '-'}")
            attr_cols[2].write(f"**🏢 Type:** {f.property_type or '-'}")
            attr_cols[3].write(f"**🤝 Transaction:** {f.transaction or '-'}")

            b_str = "-"
            if f.budget_min and f.budget_max:
                b_str = f"₹{f.budget_min:,} - ₹{f.budget_max:,}"
            elif f.budget_max:
                b_str = f"Up to ₹{f.budget_max:,}"
            elif f.budget_min:
                b_str = f"From ₹{f.budget_min:,}"

            attr_cols[0].write(f"**💰 Budget:** {b_str}")
            attr_cols[1].write(f"**🛋️ Furnishing:** {f.furnishing or '-'}")
            attr_cols[2].write(f"**🔑 Possession:** {f.possession or '-'}")
            near_str = ", ".join(f.near) if f.near else "-"
            attr_cols[3].write(f"**🚇 Near:** {near_str}")

            st.subheader("Validated JSON Filter (Search Engine Ready)")
            st.json(res.filter.model_dump(exclude_none=True))

            # Real Estate Search & Visual Property Listings
            st.divider()
            prop_client = get_property_client(
                provider_override="live" if is_live_selected else "local",
                api_key_override=prop_api_key if is_live_selected else "",
                base_url_override=prop_api_url if is_live_selected and prop_api_url else None,
            )

            with st.spinner("Searching property listings..."):
                search_resp = search_properties_api(
                    res.filter,
                    client=prop_client,
                    page=1,
                    page_size=page_size_val,
                )

            p_col1, p_col2 = st.columns([3, 1])
            with p_col1:
                st.subheader(f"🏢 Matching Properties ({len(search_resp.properties)} shown)")
            with p_col2:
                if search_resp.is_live_api:
                    st.success(f"🌐 {search_resp.provider_name}")
                else:
                    st.info(f"📦 {search_resp.provider_name}")

            if search_resp.error_message:
                st.error(f"⚠️ Provider Notice: {search_resp.error_message}")

            if search_resp.is_fallback:
                st.info("💡 Showing closest matching properties based on relaxed budget and location.")

            if not search_resp.properties and not search_resp.error_message:
                st.warning("No properties matching this criteria currently in database.")
            elif search_resp.properties:
                for i in range(0, len(search_resp.properties), 3):
                    chunk = search_resp.properties[i : i + 3]
                    p_cols = st.columns(3)
                    for c_idx, prop in enumerate(chunk):
                        with p_cols[c_idx], st.container(border=True):
                            if prop.photo_url:
                                st.image(prop.photo_url, use_container_width=True)
                            st.markdown(f"### {format_inr(prop.price, prop.transaction)}")
                            st.markdown(f"**{prop.title}**")
                            loc_str = f"📍 {prop.locality + ', ' if prop.locality else ''}{prop.city}"
                            st.caption(loc_str)

                            bhk_txt = f"{prop.bedrooms} BHK" if prop.bedrooms else "Studio/Unit"
                            sqft_txt = f"{prop.sqft:,} sq.ft" if prop.sqft else ""
                            st.write(f"🛏️ **{bhk_txt}** | 📐 {sqft_txt}")

                            furn_val = str(prop.furnishing or "-").title()
                            poss_val = str(prop.possession or "-").replace("_", " ").title()
                            st.write(f"🛋️ {furn_val} | 🔑 {poss_val}")

                            if prop.near:
                                amenities = " • ".join(prop.near)
                                st.caption(f"✨ Near: {amenities}")

                            st.caption(f"🏷️ Source: `{prop.source}`")

                            if prop.listing_url:
                                st.link_button("🔗 View Original Listing", prop.listing_url, use_container_width=True)

                            if st.button("Contact Agent", key=f"contact_{prop.id}_{i}_{c_idx}"):
                                st.success(f"Broker notified for {prop.id}! Reference inquiry sent.")

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
st.subheader("Benchmark & Offline Evaluation Results")
eval_dir = PROJECT_ROOT / "eval" / "results"
summary_file = eval_dir / "summary.json"
plot_file = eval_dir / "cost_vs_accuracy.png"

if summary_file.exists():
    try:
        summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
        num_q = summary_data.get("num_queries", 0)
        st.write(f"**Evaluated on {num_q} labeled queries** from `{summary_data.get('dataset', 'Data/dev.jsonl')}`")

        systems = summary_data.get("systems", {})
        if systems:
            table_rows = []
            for name, stats in systems.items():
                display_name = {
                    "b1_rules": "B1 (Rule Normalizer)",
                    "b2_cheap": "B2 (Cheap 20B LLM)",
                    "b3_large": "B3 (Large 120B LLM)",
                    "cascade": "Cascade (Proposed)",
                }.get(name, name)
                table_rows.append({
                    "System": display_name,
                    "Micro F1 (%)": f"{stats.get('micro_f1', 0.0):.2f}%",
                    "Macro F1 (%)": f"{stats.get('macro_f1', 0.0):.2f}%",
                    "Exact Match (%)": f"{stats.get('exact_match_accuracy', 0.0):.2f}%",
                    "Latency p50": f"{stats.get('latency_p50_ms', 0.0):.2f} ms",
                    "Cost / 1k Queries": f"${stats.get('cost_per_1k_queries', 0.0):.4f}",
                })
            st.dataframe(table_rows, hide_index=True)

        col_plot, col_ci = st.columns([3, 2])
        if plot_file.exists():
            with col_plot:
                st.image(str(plot_file), caption="Cost vs Accuracy Pareto Curve")

        with col_ci:
            hyp = summary_data.get("hypothesis_test_cascade_vs_b3", {})
            if hyp:
                st.markdown("### Paired Bootstrap Hypothesis Test")
                st.markdown(f"- **Mean F1 Difference (Cascade - B3):** {hyp.get('mean_diff', 0.0):.2f}%")
                st.markdown(f"- **95% CI Range:** `[{hyp.get('ci_95_lower', 0.0)}, {hyp.get('ci_95_upper', 0.0)}]`")
                if hyp.get("passes_preregistered_margin"):
                    st.success("✅ Pre-registered criterion satisfied: Lower 95% CI bound > -3.0%")
                else:
                    st.warning("⚠️ Pre-registered margin check not met")

        # Collapsible Raw Data
        with st.expander("View Full Summary JSON"):
            st.json(summary_data)
    except Exception as err:  # noqa: BLE001
        st.error(f"Error loading evaluation summary: {err}")
else:
    st.info("Offline evaluation results will display here once the evaluation suite runs.")
