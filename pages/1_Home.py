"""Home / dashboard."""
import pandas as pd
import streamlit as st

import config
from analytics.visualizations import sessions_activity_bar
from utils.helpers import format_duration
from utils.state import get_dataset, safe_db
from utils.ui import inject_css, metric_row

inject_css()
st.markdown(
    f'<div class="hero"><h1>🕸️ {config.APP_NAME}</h1>'
    "<p>Extract public web content responsibly, clean it, explore it with interactive analytics, "
    "and export the results — with optional AI-powered insights.</p></div>",
    unsafe_allow_html=True,
)

db = safe_db()
stats = db.get_stats() if db else {"sessions": 0, "urls_processed": 0, "records": 0}
metric_row([
    ("Scraping sessions", f"{stats['sessions']:,}", "All saved sessions"),
    ("URLs processed", f"{stats['urls_processed']:,}", "Pages fetched across sessions"),
    ("Extracted records", f"{stats['records']:,}", "Total records saved"),
    ("Working dataset", f"{len(get_dataset()) if get_dataset() is not None else 0:,}", "Records currently loaded"),
])

st.write("")
left, right = st.columns([3, 2], gap="large")

with left:
    sessions_df = db.sessions_dataframe() if db else pd.DataFrame()
    fig = sessions_activity_bar(sessions_df)
    if fig is not None:
        st.plotly_chart(fig, width="stretch")
    else:
        with st.container(border=True):
            st.markdown("#### 📈 Scraping activity")
            st.caption("Your activity chart appears here after your first scraping session.")

    st.markdown("#### Recent activity")
    recent = db.list_sessions(limit=5) if db else []
    if recent:
        table = pd.DataFrame([
            {"When (UTC)": s.created_at.replace("T", " ")[:16], "Domain": s.domain, "Records": s.records_count,
             "Status": s.status, "Duration": format_duration(s.duration_seconds)} for s in recent
        ])
        st.dataframe(table, hide_index=True, width="stretch")
    else:
        st.caption("No sessions yet.")

with right:
    with st.container(border=True):
        st.markdown("#### 🚀 Quick start")
        st.markdown(
            "1. Open **Web Scraper** and enter a public URL (or pick a template).\n"
            "2. Review results in **Scraped Data** — search, filter, clean.\n"
            "3. Explore **Data Analytics** and **AI Insights**.\n"
            "4. Download CSV / Excel in **Export Data**.\n"
            "5. Reload earlier runs from **Scraping History**."
        )
    st.write("")
    st.markdown("#### Quick navigation")
    n1, n2 = st.columns(2)
    n1.page_link("pages/2_Web_Scraper.py", label="Start scraping", icon="🕷️", width="stretch")
    n2.page_link("pages/3_Scraped_Data.py", label="Browse data", icon="🗂️", width="stretch")
    n1.page_link("pages/4_Data_Analytics.py", label="Analytics", icon="📊", width="stretch")
    n2.page_link("pages/6_Scraping_History.py", label="History", icon="🕘", width="stretch")
    st.caption("Responsible scraping: robots.txt is respected, requests are rate-limited, and CAPTCHAs / "
               "logins are never bypassed.")
