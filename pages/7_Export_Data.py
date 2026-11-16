"""Export datasets as CSV / Excel / plain text."""
import streamlit as st

from utils.exporters import (EXPORT_COLUMNS, ExportError, build_filename, record_to_text, to_csv_bytes,
                             to_excel_bytes)
from utils.state import dataset_caption, require_dataset
from utils.ui import page_header

page_header("Export Data", "Download your results as CSV, Excel or text.", "📥")
full = require_dataset()
st.caption(dataset_caption())


@st.cache_data(show_spinner=False, max_entries=8)
def _csv(df, cols):
    return to_csv_bytes(df, list(cols))


@st.cache_data(show_spinner=False, max_entries=8)
def _xlsx(df, cols):
    return to_excel_bytes(df, list(cols))


filtered = st.session_state.get("filtered_df")
has_filter = filtered is not None and 0 < len(filtered) < len(full)
choice = st.radio(
    "Dataset", ["Complete dataset", "Filtered dataset (from Scraped Data page)"] if has_filter else ["Complete dataset"],
    horizontal=True,
)
data = filtered if choice.startswith("Filtered") else full
kind = "filtered" if choice.startswith("Filtered") else "complete"
st.markdown(f"**{len(data):,}** records selected")

default_cols = [c for c in EXPORT_COLUMNS if c not in ("links", "images", "paragraphs", "h2", "h3")]
cols = st.multiselect("Columns", list(EXPORT_COLUMNS), default=default_cols, format_func=lambda c: EXPORT_COLUMNS[c])
if not cols:
    st.warning("Select at least one column.", icon="⚠️")
    st.stop()

domain = data["domain"].iloc[0] if data["domain"].nunique() == 1 else "multi-domain"
c1, c2 = st.columns(2)
with c1, st.container(border=True):
    st.markdown("#### CSV")
    st.download_button("Download CSV", _csv(data, tuple(cols)), build_filename(domain, kind, "csv"), "text/csv",
                       type="primary", width="stretch")
with c2, st.container(border=True):
    st.markdown("#### Excel (.xlsx)")
    try:
        st.download_button("Download Excel", _xlsx(data, tuple(cols)), build_filename(domain, kind, "xlsx"),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", width="stretch")
    except ExportError as exc:
        st.error(str(exc))

st.markdown("#### Individual record as text")
idx = st.selectbox("Record", list(data.index), format_func=lambda i: f"{(data.loc[i, 'title'] or data.loc[i, 'url'])[:80]}")
rec = data.loc[idx]
st.download_button("Download record (.txt)", record_to_text(rec).encode("utf-8"),
                   build_filename(rec["domain"] or "record", "record", "txt"), "text/plain")
