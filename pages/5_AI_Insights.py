"""Optional AI insights with full non-AI fallbacks."""
import pandas as pd
import streamlit as st

from ai.categorizer import categorize_text
from ai.client import AIError, load_config
from ai.summarizer import keywords_for, summarize_dataset, summarize_text
from analytics import visualizations as viz
from analytics.keyword_analysis import top_keywords
from utils.state import dataset_caption, require_dataset
from utils.ui import page_header

MAX_RECORDS = 10

page_header("AI Insights", "Summaries, topics and keywords — AI-powered when a key is configured.", "🤖")
df = require_dataset()
st.caption(dataset_caption())

try:
    secrets = st.secrets
    secrets.get("AI_API_KEY")  # probe: raises if no secrets file exists
except Exception:
    secrets = None
config = load_config(secrets)

if config:
    st.success(f"AI provider configured: **{config.label}**. Selected text is sent to this provider.", icon="🔑")
else:
    st.info(
        "No AI API key configured, so the **basic mode** is active: frequency-based keywords, rule-based "
        "categories and extractive summaries. Set `AI_API_KEY` (env var or Streamlit secrets) to enable AI.",
        icon="ℹ️",
    )

labels = {i: f"{(r.title or r.url)[:70]} — {r.domain}" for i, r in df.iterrows()}
scope = st.radio("Records to analyse", ["Selected records", f"First {MAX_RECORDS} records", "Entire dataset (overview only)"], horizontal=True)
selected: list[int] = []
if scope == "Selected records":
    selected = st.multiselect(f"Choose up to {MAX_RECORDS} records", list(labels), format_func=labels.get,
                              default=list(labels)[:3], max_selections=MAX_RECORDS)
elif scope.startswith("First"):
    selected = list(df.index[:MAX_RECORDS])

tasks = st.multiselect("Tasks", ["Summaries", "Categories", "Keywords", "Dataset overview"],
                       default=["Summaries", "Categories", "Keywords", "Dataset overview"])

if st.button("Run analysis", type="primary"):
    subset = df.loc[selected] if selected else df
    results: dict = {"rows": [], "overview": None, "errors": []}
    with st.spinner("Analysing…"):
        per_record = subset.iterrows() if selected else iter(())
        for idx, rec in per_record:
            text = rec["content"] or rec["paragraphs"] or rec["meta_description"]
            row = {"Record": labels.get(idx, rec["url"])}
            try:
                if "Summaries" in tasks and selected:
                    row["Summary"], row["Summary method"] = summarize_text(text, config)
                if "Categories" in tasks:
                    row["Category"], row["Topics"], row["Category method"] = categorize_text(text, config)
                    row["Topics"] = ", ".join(row["Topics"])
            except AIError as exc:
                results["errors"].append(str(exc))
                config_fallback = None
                if "Summaries" in tasks and "Summary" not in row:
                    row["Summary"], row["Summary method"] = summarize_text(text, config_fallback)
                if "Categories" in tasks and "Category" not in row:
                    row["Category"], _, row["Category method"] = categorize_text(text, config_fallback)
                    row["Topics"] = ""
            if "Keywords" in tasks:
                row["Keywords"] = ", ".join(keywords_for(text, config))
            results["rows"].append(row)
            if results["errors"] and config is not None and len(results["errors"]) >= 2:
                break  # stop hammering a failing provider
        if "Dataset overview" in tasks:
            try:
                results["overview"] = summarize_dataset(subset if selected else df, config)
            except AIError as exc:
                results["errors"].append(str(exc))
                results["overview"] = summarize_dataset(subset if selected else df, None)
    st.session_state["ai_results"] = results

res = st.session_state.get("ai_results")
if res:
    for err in dict.fromkeys(res["errors"]):
        st.warning(f"{err} Basic mode was used where the AI call failed.", icon="⚠️")
    if res["overview"]:
        text, method = res["overview"]
        with st.container(border=True):
            st.markdown("#### Dataset overview")
            st.write(text)
            st.caption(f"Method: {method}")
    rows = pd.DataFrame(res["rows"])
    if not rows.empty:
        st.markdown("#### Per-record results")
        st.dataframe(rows, hide_index=True, width="stretch")
        if "Category" in rows:
            counts = rows["Category"].value_counts().reset_index()
            counts.columns = ["category", "records"]
            fig = viz.category_donut(counts)
            if fig:
                st.plotly_chart(fig, width="stretch")
    st.markdown("#### Frequently discussed subjects")
    subset_text = df["title"].astype(str) + " " + df["content"].astype(str)
    st.plotly_chart(viz.keywords_bar(top_keywords(subset_text, 15), "Top subjects (keyword frequency)"), width="stretch") if len(subset_text) else None
