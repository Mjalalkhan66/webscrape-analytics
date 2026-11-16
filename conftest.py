"""Puts the project root on sys.path for pytest and provides shared fixtures."""
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

# Isolate runtime data (SQLite + datasets) from the real data/ folder during tests.
os.environ.setdefault("WEBSCRAPE_DATA_DIR", tempfile.mkdtemp(prefix="webscrape_test_"))
os.environ.pop("AI_API_KEY", None)

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


@pytest.fixture
def fixture_html():
    def _read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")
    return _read


@pytest.fixture
def sample_df():
    from analytics.data_cleaning import records_to_dataframe
    base = {"template": "generic", "record_type": "page", "status_code": 200}
    recs = [
        {**base, "url": "https://a.com/1", "domain": "a.com", "title": "Solar energy growth", "content": "Solar energy market growth continues. " * 20,
         "publication_date": "2024-03-15", "links": ["https://a.com/2", "https://x.com"], "images": [{"src": "https://a.com/i.png", "alt": "x"}], "scraped_at": "2024-04-01T10:00:00+00:00"},
        {**base, "url": "https://a.com/2", "domain": "a.com", "title": "Wind energy", "content": "Wind turbines generate energy for cities. " * 10,
         "publication_date": "2024-04-02", "links": ["https://a.com/1"], "scraped_at": "2024-04-02T10:00:00+00:00"},
        {**base, "url": "https://b.org/x", "domain": "b.org", "title": "Football season", "content": "The team won the league match with a late goal. " * 8,
         "publication_date": "", "links": [], "scraped_at": "2024-04-02T12:00:00+00:00"},
        {**base, "url": "https://a.com/1", "domain": "a.com", "title": "Solar energy growth", "content": "Solar energy market growth continues. " * 20,
         "publication_date": "2024-03-15", "links": [], "scraped_at": "2024-04-03T10:00:00+00:00"},
        {**base, "url": "https://c.net/empty", "domain": "c.net", "title": "", "content": "", "scraped_at": "2024-04-03T11:00:00+00:00"},
    ]
    return records_to_dataframe(recs)
