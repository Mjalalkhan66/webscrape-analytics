"""Smoke tests: every page renders without exceptions, with and without data."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from analytics.data_cleaning import remove_duplicates

ROOT = Path(__file__).resolve().parent.parent
PAGES = [
    "pages/1_Home.py", "pages/2_Web_Scraper.py", "pages/3_Scraped_Data.py", "pages/4_Data_Analytics.py",
    "pages/5_AI_Insights.py", "pages/6_Scraping_History.py", "pages/7_Export_Data.py",
]


def _run(page, df=None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    if df is not None:
        at.session_state["dataset"] = df
    at.run()
    assert not at.exception, at.exception
    if page != "pages/1_Home.py":
        at.switch_page(page).run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_with_data(page, sample_df):
    at = _run(page, remove_duplicates(sample_df))
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_data(page):
    at = _run(page)
    assert not at.exception, [e.value for e in at.exception]


def test_scraper_rejects_private_url():
    at = _run("pages/2_Web_Scraper.py")
    at.text_input(key="scrape_url").set_value("http://127.0.0.1/admin").run()
    at.button[0].click().run()
    assert not at.exception
    assert any("not allowed" in e.value.lower() or "internal" in e.value.lower() for e in at.error)


def test_ai_page_runs_in_basic_mode(sample_df):
    at = _run("pages/5_AI_Insights.py", remove_duplicates(sample_df))
    assert any("basic mode" in i.value.lower() for i in at.info)
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.dataframe) >= 1
