"""Central application configuration.

All values can be overridden with environment variables so the same code runs
locally and on Streamlit Community Cloud without modification.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "WebScrape Analytics"
APP_ICON = "🕸️"
APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("WEBSCRAPE_DATA_DIR", BASE_DIR / "data")).resolve()
SESSIONS_DIR = DATA_DIR / "sessions"
DB_PATH = DATA_DIR / "webscrape.db"

USER_AGENT = os.environ.get(
    "WEBSCRAPE_USER_AGENT",
    "WebScrapeAnalytics/1.0 (+https://github.com/your-username/webscrape-analytics; "
    "educational portfolio project; respects robots.txt)",
)

# --- Scraping limits -------------------------------------------------------
DEFAULT_TIMEOUT = 10          # seconds
MIN_DELAY = 1.0               # minimum seconds between requests to one host
DEFAULT_DELAY = 1.5
MAX_PAGES_LIMIT = 25          # hard cap, regardless of UI input
MAX_LINKS_PER_PAGE_LIMIT = 25
MAX_RESPONSE_BYTES = 2_000_000  # 2 MB per page
MAX_REDIRECTS = 5
MAX_CONTENT_CHARS = 100_000   # per record, keeps stored datasets small
ALLOWED_PORTS = frozenset({80, 443, 8080, 8443})
