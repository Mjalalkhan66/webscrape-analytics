"""Web scraper page: custom URL mode and predefined templates."""
import json

import pandas as pd
import streamlit as st

import config
from analytics.data_cleaning import clean_dataframe, records_to_dataframe, remove_duplicates
from database.db_manager import DatabaseError
from database.models import ScrapeSession
from scraper.crawler import CrawlOptions, crawl
from scraper.parser import ExtractOptions
from scraper.templates import TEMPLATES, get_template, template_config
from utils.helpers import format_duration, new_session_id, utc_now_iso
from utils.logger import get_logger
from utils.state import get_dataset, safe_db, set_dataset
from utils.ui import page_header
from utils.validators import URLValidationError, validate_url

logger = get_logger("page.scraper")
page_header("Web Scraper", "Extract publicly accessible information from a website.", "🕷️")

mode = st.radio("Scraping mode", ["Custom URL Scraper", "Predefined Template"], horizontal=True)

with st.container(border=True):
    if mode == "Predefined Template":
        key = st.selectbox(
            "Template", [k for k in TEMPLATES if k != "generic"],
            format_func=lambda k: TEMPLATES[k].name,
        )
        st.caption(TEMPLATES[key].description)
    else:
        key = "generic"

    url = st.text_input("Website URL", placeholder="https://example.com/blog", key="scrape_url",
                        help="Only public http(s) pages. Private/internal addresses are blocked.")

    c1, c2, c3, c4 = st.columns(4)
    max_pages = c1.slider("Max pages", 1, config.MAX_PAGES_LIMIT, 5)
    max_links = c2.slider("Links to follow per page", 0, config.MAX_LINKS_PER_PAGE_LIMIT, 5,
                          help="0 scrapes only the URL you entered.")
    timeout = c3.slider("Request timeout (s)", 3, 30, config.DEFAULT_TIMEOUT)
    delay = c4.slider("Delay between requests (s)", config.MIN_DELAY, 5.0, config.DEFAULT_DELAY, step=0.5)

    st.markdown("**Extraction options**")
    o = st.columns(6)
    opts = ExtractOptions(
        headings=o[0].checkbox("Headings", True), paragraphs=o[1].checkbox("Paragraphs", True),
        article=o[2].checkbox("Article text", True), links=o[3].checkbox("Links", True),
        images=o[4].checkbox("Images", True), date=o[5].checkbox("Dates", True),
    )
    append = st.checkbox("Append to the current working dataset", value=False)

    with st.expander("Preview extraction configuration"):
        st.json(template_config(get_template(key)), expanded=False)
        st.caption(json.dumps({"max_pages": max_pages, "links_per_page": max_links, "timeout": timeout,
                               "delay": delay, "robots_txt": "respected"}))

    start = st.button("Start scraping", type="primary", width="stretch")

st.info(
    "Limitations: pages that need JavaScript rendering, a login, or that use CAPTCHA / anti-bot protection "
    "are not supported and will be reported. Compatibility with every website is not guaranteed.",
    icon="⚠️",
)

if start:
    try:
        clean_url = validate_url(url)
    except URLValidationError as exc:
        st.error(str(exc), icon="🚫")
        st.stop()

    options = CrawlOptions(max_pages=max_pages, max_links_per_page=max_links, timeout=timeout, delay=delay,
                           template_key=key, follow_links=max_links > 0 and max_pages > 1, extract=opts)
    bar = st.progress(0.0, text="Starting…")
    with st.status(f"Scraping {clean_url}", expanded=True) as status:
        def on_progress(done: int, total: int, page_url: str, phase: str) -> None:
            bar.progress(min(done / total, 1.0), text=f"{phase.capitalize()}: {page_url[:80]}")
            if phase == "fetching":
                status.write(f"Fetching {page_url}")

        try:
            result = crawl(clean_url, options, progress=on_progress)
        except Exception:
            logger.exception("Unexpected crawl failure")
            status.update(label="Scraping failed", state="error")
            st.error("Something went wrong while scraping. Please check the URL and try again.", icon="🚫")
            st.stop()
        bar.progress(1.0, text="Done")
        status.update(label=f"Scraping {result.status}", state="error" if result.status == "failed" else "complete")

    df = clean_dataframe(records_to_dataframe(result.records)) if result.records else pd.DataFrame()
    session_id = new_session_id()
    db = safe_db()
    if db:
        try:
            db.save_session(ScrapeSession(
                session_id=session_id, url=result.start_url, domain=result.domain, created_at=utc_now_iso(),
                records_count=len(df), pages_processed=result.pages_succeeded, status=result.status,
                duration_seconds=round(result.duration, 2), template=key, message=result.error[:300],
            ), df if not df.empty else None)
        except DatabaseError as exc:
            st.warning(f"{exc} Your results are still available in this session.")

    if result.status == "failed" or df.empty:
        st.error(result.error or "No data could be extracted from this URL.", icon="🚫")
    else:
        if append and get_dataset() is not None:
            merged = remove_duplicates(pd.concat([get_dataset(), df], ignore_index=True))
            set_dataset(merged, session_id, f"{result.domain} (appended)")
        else:
            set_dataset(df, session_id, result.domain)
        st.success(f"Extracted {len(df)} record(s) from {result.pages_succeeded} page(s) in "
                   f"{format_duration(result.duration)}.", icon="✅")
        if result.status == "partial":
            st.warning("Some pages could not be fetched — see the page log below.", icon="⚠️")
        st.page_link("pages/3_Scraped_Data.py", label="Open the scraped data", icon="🗂️")

    for w in result.warnings[:10]:
        st.warning(w, icon="⚠️")
    if result.page_log:
        st.markdown("#### Page log")
        st.dataframe(pd.DataFrame(result.page_log), hide_index=True, width="stretch")
