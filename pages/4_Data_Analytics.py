"""Analytics dashboard computed from the working dataset."""
import pandas as pd
import streamlit as st

from analytics import statistics as stats
from analytics import visualizations as viz
from analytics.keyword_analysis import top_keywords
from utils.state import dataset_caption, require_dataset
from utils.ui import metric_row, page_header

page_header("Data Analytics", "Interactive statistics computed from your scraped data.", "📊")
df = require_dataset()
st.caption(dataset_caption())

s = stats.compute_summary(df)
metric_row([
    ("Total records", f"{s['total_records']:,}", ""),
    ("Unique domains", f"{s['unique_domains']:,}", ""),
    ("Avg content length", f"{s['avg_content_length']:,.0f}", "characters"),
    ("Total links", f"{s['total_links']:,}", ""),
    ("Records with dates", f"{s['records_with_dates']:,}", f"of {s['total_records']:,}"),
])
st.write("")


def show(fig, empty_msg: str) -> None:
    if fig is None:
        st.info(empty_msg, icon="ℹ️")
    else:
        st.plotly_chart(fig, width="stretch")


c1, c2 = st.columns(2)
with c1:
    show(viz.content_length_histogram(df), "No content length data available.")
with c2:
    show(viz.records_per_domain_bar(stats.records_per_domain(df)), "No domain data available.")

c3, c4 = st.columns(2)
with c3:
    freq = st.radio("Activity granularity", ["Daily", "Hourly"], horizontal=True, label_visibility="collapsed")
    show(viz.activity_line(stats.activity_over_time(df, "H" if freq == "Hourly" else "D")), "No timestamps available.")
with c4:
    show(viz.publication_bar(stats.publication_distribution(df)),
         "No publication dates were found in these records, so this chart is unavailable.")

c5, c6 = st.columns(2)
with c5:
    show(viz.top_domains_bar(stats.top_domains_by_content(df)), "No domain data available.")
with c6:
    n = st.slider("Number of keywords", 5, 40, 15)
    mode = st.radio("Keyword type", ["Single words", "Two-word phrases"], horizontal=True)
    text = df["title"].astype(str) + " " + df["content"].astype(str)
    kw = top_keywords(text, n, bigrams=mode == "Two-word phrases")
    show(viz.keywords_bar(kw), "Not enough text to extract keywords.")

with st.expander("Keyword table"):
    st.dataframe(kw, hide_index=True, width="stretch")
