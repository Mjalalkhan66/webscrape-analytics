"""Interactive table with search, filters, sorting and record preview."""
import pandas as pd
import streamlit as st

from analytics.data_cleaning import remove_duplicates, remove_empty_records, with_parsed_dates
from utils.state import dataset_caption, require_dataset, set_dataset
from utils.ui import page_header

page_header("Scraped Data", "Search, filter and inspect the extracted records.", "🗂️")
df = require_dataset()
st.caption(dataset_caption())

FILTER_KEYS = ["f_search", "f_domains", "f_date_field", "f_dates", "f_sort", "f_order", "f_columns"]
DEFAULT_COLS = ["title", "domain", "publication_date", "word_count", "links_count", "url"]
ALL_COLS = ["title", "domain", "publication_date", "price", "word_count", "content_length", "links_count",
            "image_count", "record_type", "template", "scraped_at", "url", "meta_description"]


def reset_filters() -> None:
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


# --- cleaning actions -------------------------------------------------------
a1, a2, a3 = st.columns(3)
if a1.button("🧹 Remove duplicates", width="stretch"):
    before = len(df)
    new = remove_duplicates(df)
    set_dataset(new, st.session_state.get("session_id"), st.session_state.get("dataset_label", ""))
    st.toast(f"Removed {before - len(new)} duplicate record(s).")
    st.rerun()
if a2.button("🗑️ Remove empty records", width="stretch"):
    before = len(df)
    new = remove_empty_records(df)
    set_dataset(new, st.session_state.get("session_id"), st.session_state.get("dataset_label", ""))
    st.toast(f"Removed {before - len(new)} empty record(s).")
    st.rerun()
a3.button("↺ Reset filters", width="stretch", on_click=reset_filters)

# --- filters ----------------------------------------------------------------
dated = with_parsed_dates(df)
with st.container(border=True):
    f1, f2 = st.columns([2, 2])
    search = f1.text_input("Search", key="f_search", placeholder="Search title, description, content or URL")
    domains = f2.multiselect("Domain", sorted(d for d in df["domain"].unique() if d), key="f_domains")

    g1, g2, g3, g4 = st.columns([1.2, 1.6, 1.2, 1])
    date_field = g1.selectbox("Date field", ["Publication date", "Scraped date"], key="f_date_field")
    date_col = "pub_dt" if date_field == "Publication date" else "scraped_dt"
    valid = dated[date_col].dropna()
    date_range = ()
    if not valid.empty:
        lo, hi = valid.min().date(), valid.max().date()
        date_range = g2.date_input("Date range", value=(lo, hi), min_value=lo, max_value=hi, key="f_dates")
    else:
        g2.caption(f"No {date_field.lower()} values available.")
    sort_by = g3.selectbox("Sort by", ["title", "publication_date", "scraped_at", "word_count"], key="f_sort")
    ascending = g4.radio("Order", ["Ascending", "Descending"], key="f_order") == "Ascending"
    columns = st.multiselect("Columns to display", ALL_COLS, default=DEFAULT_COLS, key="f_columns")

mask = pd.Series(True, index=df.index)
if search.strip():
    needle = search.strip()
    hay = df["title"] + " " + df["meta_description"] + " " + df["content"] + " " + df["url"]
    mask &= hay.str.contains(needle, case=False, regex=False)
if domains:
    mask &= df["domain"].isin(domains)
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_ts = pd.Timestamp(date_range[0], tz="UTC")
    end_ts = pd.Timestamp(date_range[1], tz="UTC") + pd.Timedelta(days=1)
    in_range = (dated[date_col] >= start_ts) & (dated[date_col] < end_ts)
    full_range = tuple(date_range) == (lo, hi)
    mask &= in_range | (dated[date_col].isna() & full_range)
filtered = df[mask]
if sort_by == "title":
    filtered = filtered.sort_values("title", key=lambda s: s.str.lower(), ascending=ascending)
else:
    filtered = filtered.sort_values(sort_by, ascending=ascending, na_position="last")
filtered = filtered.reset_index(drop=True)
st.session_state["filtered_df"] = filtered

st.markdown(f"**{len(filtered):,}** of {len(df):,} records")
if filtered.empty:
    st.warning("No records match the current filters.", icon="🔍")
    st.stop()

view_cols = columns or DEFAULT_COLS
selection = st.dataframe(
    filtered[view_cols], hide_index=True, width="stretch", height=380, on_select="rerun",
    selection_mode="single-row", key="records_table",
    column_config={"url": st.column_config.LinkColumn("url"), "title": st.column_config.TextColumn("title", width="large")},
)

rows = selection.selection.rows if selection and selection.selection else []
st.markdown("#### Record preview")
if not rows:
    st.caption("Select a row in the table (checkbox on the left) to preview the full record.")
    idx = None
else:
    idx = rows[0]
if idx is not None and idx < len(filtered):
    rec = filtered.iloc[idx]
    with st.container(border=True):
        st.subheader(rec["title"] or "(untitled)")
        st.markdown(f"[{rec['url']}]({rec['url']})  ·  **{rec['domain']}**  ·  Published: {rec['publication_date'] or 'n/a'}")
        if rec["price"]:
            st.markdown(f"**Price:** {rec['price']}")
        if rec["meta_description"]:
            st.caption(rec["meta_description"])
        t1, t2, t3, t4 = st.tabs(["Content", "Headings", "Links", "Images"])
        with t1:
            st.text_area("Full extracted content", rec["content"] or rec["paragraphs"], height=300, disabled=True,
                         key=f"content_{idx}")
        with t2:
            for lvl in ("h1", "h2", "h3"):
                if rec[lvl]:
                    st.markdown(f"**{lvl.upper()}**")
                    st.write(rec[lvl])
            if not (rec["h1"] or rec["h2"] or rec["h3"]):
                st.caption("No headings extracted.")
        with t3:
            st.dataframe(pd.DataFrame({"link": rec["links"]}), hide_index=True, width="stretch",
                         column_config={"link": st.column_config.LinkColumn("link")}) if rec["links"] else st.caption("No links extracted.")
        with t4:
            st.dataframe(pd.DataFrame(rec["images"]), hide_index=True, width="stretch") if rec["images"] else st.caption("No images extracted.")
        if rec["extraction_notes"]:
            st.warning(rec["extraction_notes"], icon="⚠️")
