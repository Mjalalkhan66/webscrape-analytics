# 🕸️ WebScrape Analytics

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-FF4B4B)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/tests-pytest-green)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](#)

## Project overview
WebScrape Analytics is an interactive Streamlit application that extracts **publicly accessible** web content,
cleans it, analyses it with interactive Plotly charts, optionally enriches it with LLM-powered insights, and
exports the results. Scraping is built to be *responsible*: robots.txt is respected, requests are rate-limited,
and the app is hardened against SSRF.

## Key features
- **Custom URL scraper** and **templates** (news, blog, general site, product listings) with configurable CSS-selector strategies.
- Same-domain crawler with page / link limits, timeout, delay, progress and per-page log.
- Extracts title, meta description, H1–H3, paragraphs, main article text (Trafilatura), links, images + alt text, publication date, domain, timestamp.
- **Scraped Data**: search, domain/date filters, sorting, column selection, record preview, de-duplication, empty-record removal.
- **Analytics**: KPIs, keyword frequency, content-length histogram, records per domain, activity over time, publication distribution, top domains.
- **AI Insights** (optional): summaries, categories, keywords, dataset overview — with rule-based/extractive fallbacks when no API key is set.
- **History** in SQLite with reloadable datasets, per-session delete and confirmed clear-all.
- **Export** to CSV / Excel (complete or filtered) and single records as text.

## Technology stack
Python · Streamlit · Requests · BeautifulSoup4 + lxml · Trafilatura · Pandas · NumPy · Plotly · SQLite · OpenPyXL · pytest

## Architecture
```
Streamlit pages (UI only)  ──►  scraper/   fetcher → robots → crawler → parser (+ templates)
        │                       analytics/ cleaning → statistics → keywords → visualizations
        │                       ai/        client (provider-agnostic) → summarizer / categorizer
        │                       database/ SQLite metadata + JSON dataset files
        └──────────────────►    utils/     validators (SSRF), exporters, helpers, logger, state, ui
```
UI and scraping logic are separate: pages only call into the packages. `app.py` uses `st.navigation`,
so it is the single entry point.

## Folder structure
```
webscrape-analytics/
├── app.py  config.py  requirements.txt  requirements-dev.txt  pytest.ini  conftest.py
├── .streamlit/ (config.toml, secrets.toml.example)   .env.example   .gitignore
├── pages/      1_Home … 7_Export_Data
├── scraper/    fetcher.py parser.py crawler.py templates.py robots_handler.py
├── analytics/  data_cleaning.py statistics.py keyword_analysis.py visualizations.py
├── ai/         client.py summarizer.py categorizer.py
├── database/   db_manager.py models.py
├── utils/      validators.py exporters.py helpers.py logger.py state.py ui.py
├── assets/logo.png   data/.gitkeep   tests/ (+ fixtures/)
```

## Installation & local execution
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Configuration
Everything is optional; the app is fully functional without an AI key.

| Variable | Purpose |
|---|---|
| `AI_PROVIDER` | `anthropic` (default) or `openai` (any OpenAI-compatible API) |
| `AI_API_KEY` | API key (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` also accepted) |
| `AI_MODEL`, `AI_BASE_URL` | Optional overrides |
| `WEBSCRAPE_DATA_DIR`, `WEBSCRAPE_USER_AGENT`, `WEBSCRAPE_LOG_LEVEL` | App settings |

Locally: export variables (see `.env.example`) or copy `.streamlit/secrets.toml.example` to
`.streamlit/secrets.toml`. **Never commit keys.** Set a real contact URL in `WEBSCRAPE_USER_AGENT`.

## Deployment (GitHub + Streamlit Community Cloud)
```bash
git init && git add . && git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/webscrape-analytics.git
git push -u origin main
```
1. Go to <https://share.streamlit.io> → **Create app** → pick the repo, branch `main`, main file **`app.py`**.
2. Advanced settings → choose Python 3.11+ and paste secrets (TOML) if you want AI:
   ```toml
   AI_PROVIDER = "anthropic"
   AI_API_KEY = "..."
   ```
3. Deploy.

**Persistence caveat:** SQLite and `data/sessions/*.json` live on the container's local disk and are *not*
guaranteed to survive restarts or redeploys. Storage is isolated behind `database/db_manager.py`, so swapping in
a hosted database / object storage later only touches that module. The app also tolerates missing saved files.

## Testing
```bash
pip install -r requirements-dev.txt
pytest -q
```
Tests use local HTML fixtures and a throwaway local HTTP server — no live websites. They cover URL validation /
SSRF, parsing, metadata, crawling, robots.txt, fetch errors, cleaning, de-duplication, keywords, analytics,
exports (CSV + Excel round-trip), the database layer, and smoke-render every Streamlit page (`streamlit.testing`).

## Responsible scraping policy
- robots.txt is honoured (unreachable robots.txt ⇒ treated as disallowed); `Crawl-delay` is respected (capped at 10 s).
- Minimum 1 s delay per host, page caps (≤ 25), 2 MB response cap, honest User-Agent.
- No CAPTCHA / anti-bot bypass, no logins, account/cart/admin URLs are never followed.
- E-mail addresses and obvious phone numbers are masked in extracted text; author bylines are not collected.
- Check each site's terms of service before scraping; you are responsible for how you use the data.

## Security
- Only `http`/`https`; ports 80/443/8080/8443; no embedded credentials.
- Every URL **and every redirect hop** is resolved and must map exclusively to globally routable IPs
  (blocks loopback, private, link-local, metadata endpoints, IPv4-mapped IPv6, decimal-IP tricks).
- Streaming download with a hard byte limit (also protects against compressed-response bombs).
- Dataset file names are app-generated hex ids, re-validated against the sessions folder; SQL is parameterised.
- Known limitation: DNS is validated before connecting, so a hostile DNS server could in theory rebind between
  check and connect. For high-risk deployments add an egress proxy enforcing the same rules.

## Known limitations
JavaScript-rendered sites, logins, CAPTCHAs and anti-bot protected sites are detected and reported, not supported.
Product extraction relies on common markup patterns and may not match every shop. AI calls send selected text to
the configured third-party provider.

## Future improvements
Scheduled scraping · more templates · sentiment / advanced NLP · SQL & cloud-storage backends · automated PDF
reports · richer AI insights.

## Screenshots
| Home | Scraper | Analytics |
|---|---|---|
| _add screenshot_ | _add screenshot_ | _add screenshot_ |

## Author
**Your Name** · [GitHub](https://github.com/your-username) · [LinkedIn](https://linkedin.com/in/your-profile) · [Portfolio](https://your-portfolio.example)
