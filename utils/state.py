"""Session-state helpers (the working dataset shared by all pages)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from analytics.data_cleaning import ensure_schema
from database.db_manager import DatabaseError, DatabaseManager


@st.cache_resource(show_spinner=False)
def get_db() -> DatabaseManager:
    """One DatabaseManager per server process."""
    return DatabaseManager()


def safe_db() -> DatabaseManager | None:
    """DB handle or ``None`` (after showing a friendly message) if storage is unavailable."""
    try:
        return get_db()
    except DatabaseError as exc:
        st.error(str(exc))
        return None


def set_dataset(df: pd.DataFrame, session_id: str | None = None, label: str = "") -> None:
    st.session_state["dataset"] = ensure_schema(df)
    st.session_state["session_id"] = session_id
    st.session_state["dataset_label"] = label
    st.session_state.pop("filtered_df", None)
    st.session_state.pop("ai_results", None)


def get_dataset() -> pd.DataFrame | None:
    df = st.session_state.get("dataset")
    return df if isinstance(df, pd.DataFrame) and not df.empty else None


def require_dataset() -> pd.DataFrame:
    """Return the working dataset or show a guidance message and stop the page."""
    df = get_dataset()
    if df is None:
        st.info("No dataset loaded yet. Run a scrape in **Web Scraper** or reload a saved session in **Scraping History**.", icon="ℹ️")
        st.stop()
    return df


def dataset_caption() -> str:
    df = get_dataset()
    label = st.session_state.get("dataset_label", "")
    return f"Working dataset: {len(df)} records" + (f" · {label}" if label else "") if df is not None else ""
