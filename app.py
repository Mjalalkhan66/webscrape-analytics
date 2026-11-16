"""WebScrape Analytics — Streamlit entry point.

Run locally:   streamlit run app.py
Cloud entry:   app.py
"""
from pathlib import Path

import streamlit as st

import config

st.set_page_config(
    page_title=config.APP_NAME,
    page_icon=str(config.BASE_DIR / "assets" / "logo.png") if (config.BASE_DIR / "assets" / "logo.png").exists() else config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("pages/1_Home.py", title="Home", icon="🏠", default=True),
    st.Page("pages/2_Web_Scraper.py", title="Web Scraper", icon="🕷️"),
    st.Page("pages/3_Scraped_Data.py", title="Scraped Data", icon="🗂️"),
    st.Page("pages/4_Data_Analytics.py", title="Data Analytics", icon="📊"),
    st.Page("pages/5_AI_Insights.py", title="AI Insights", icon="🤖"),
    st.Page("pages/6_Scraping_History.py", title="Scraping History", icon="🕘"),
    st.Page("pages/7_Export_Data.py", title="Export Data", icon="📥"),
]
navigation = st.navigation(pages)

logo = Path(config.BASE_DIR / "assets" / "logo.png")
if logo.exists():
    st.logo(str(logo), size="large")

with st.sidebar:
    st.caption(f"{config.APP_NAME} · v{config.APP_VERSION}")
    df = st.session_state.get("dataset")
    if df is not None and len(df):
        st.success(f"{len(df)} records loaded", icon="✅")
    else:
        st.info("No dataset loaded", icon="ℹ️")

navigation.run()
