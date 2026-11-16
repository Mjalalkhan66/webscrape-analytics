"""Scraping history stored in SQLite."""
import pandas as pd
import streamlit as st

from database.db_manager import DatabaseError
from utils.helpers import format_duration
from utils.state import safe_db, set_dataset
from utils.ui import page_header

page_header("Scraping History", "Previous sessions, stored locally in SQLite.", "🕘")
db = safe_db()
if db is None:
    st.stop()

try:
    sessions = db.list_sessions()
except DatabaseError as exc:
    st.error(str(exc))
    st.stop()

if not sessions:
    st.info("No scraping sessions yet. Run a scrape from the **Web Scraper** page.", icon="ℹ️")
    st.stop()

table = pd.DataFrame([{
    "Session ID": s.session_id, "URL": s.url, "Domain": s.domain, "Date (UTC)": s.created_at.replace("T", " ")[:19],
    "Records": s.records_count, "Status": s.status, "Duration": format_duration(s.duration_seconds),
    "Saved dataset": "yes" if s.dataset_file else "no",
} for s in sessions])
sel = st.dataframe(table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="hist_table")
rows = sel.selection.rows if sel and sel.selection else []

st.caption("Select a session to view details, reload its dataset or delete it. "
           "Note: on Streamlit Community Cloud, local files may be reset on restart or redeploy.")
if rows:
    s = sessions[rows[0]]
    with st.container(border=True):
        st.markdown(f"#### Session `{s.session_id}`")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Status", s.status)
        d2.metric("Records", s.records_count)
        d3.metric("Pages processed", s.pages_processed)
        d4.metric("Duration", format_duration(s.duration_seconds))
        st.write(f"**URL:** {s.url}  \n**Template:** {s.template}  \n**Started:** {s.created_at}")
        if s.message:
            st.warning(s.message, icon="⚠️")
        b1, b2 = st.columns(2)
        if b1.button("📂 Load dataset", disabled=not s.dataset_file, width="stretch"):
            try:
                loaded = db.load_dataset(s.session_id)
            except DatabaseError as exc:
                st.error(str(exc))
                loaded = None
            if loaded is None or loaded.empty:
                st.warning("The saved dataset is no longer available (it may have been cleared by a restart).", icon="⚠️")
            else:
                set_dataset(loaded, s.session_id, f"{s.domain} (session {s.session_id})")
                st.success(f"Loaded {len(loaded)} records.", icon="✅")
                st.page_link("pages/3_Scraped_Data.py", label="Open scraped data", icon="🗂️")
        if b2.button("🗑️ Delete session", width="stretch"):
            try:
                db.delete_session(s.session_id)
                st.toast("Session deleted.")
                st.rerun()
            except DatabaseError as exc:
                st.error(str(exc))

with st.expander("⚠️ Danger zone"):
    confirm = st.checkbox("I understand this permanently deletes all sessions and saved datasets.")
    if st.button("Clear all history", disabled=not confirm, type="primary"):
        try:
            n = db.clear_history()
            st.toast(f"Deleted {n} session(s).")
            st.rerun()
        except DatabaseError as exc:
            st.error(str(exc))
