"""Same-domain, politeness-aware crawler that turns pages into records."""
from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

import config
from scraper.fetcher import FetchError, SafeFetcher
from scraper.parser import ExtractOptions, parse_page, parse_product_listing
from scraper.robots_handler import RobotsHandler
from scraper.templates import GLOBAL_SKIP_PATTERNS, ScrapeTemplate, get_template
from utils.helpers import get_domain, normalize_url, same_site
from utils.logger import get_logger
from utils.validators import URLValidationError, validate_url

logger = get_logger("crawler")


@dataclass
class CrawlOptions:
    max_pages: int = 5
    max_links_per_page: int = 10
    timeout: float = config.DEFAULT_TIMEOUT
    delay: float = config.DEFAULT_DELAY
    template_key: str = "generic"
    follow_links: bool = True
    extract: ExtractOptions = field(default_factory=ExtractOptions)

    def clamp(self) -> "CrawlOptions":
        self.max_pages = max(1, min(int(self.max_pages), config.MAX_PAGES_LIMIT))
        self.max_links_per_page = max(0, min(int(self.max_links_per_page), config.MAX_LINKS_PER_PAGE_LIMIT))
        self.delay = max(float(self.delay), config.MIN_DELAY)
        self.timeout = max(1.0, float(self.timeout))
        return self


@dataclass
class CrawlResult:
    start_url: str
    domain: str
    records: list[dict] = field(default_factory=list)
    page_log: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pages_attempted: int = 0
    pages_succeeded: int = 0
    duration: float = 0.0
    status: str = "completed"  # completed | partial | failed | stopped
    error: str = ""


ProgressCallback = Callable[[int, int, str, str], None]


def _matches_any(url: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, url, re.I) for p in patterns)


def _should_follow(url: str, template: ScrapeTemplate) -> bool:
    if _matches_any(url, GLOBAL_SKIP_PATTERNS) or _matches_any(url, template.skip_url_patterns):
        return False
    if template.follow_url_patterns:
        return _matches_any(url, template.follow_url_patterns)
    return True


def crawl(
    start_url: str,
    options: CrawlOptions | None = None,
    fetcher: SafeFetcher | None = None,
    robots: RobotsHandler | None = None,
    progress: ProgressCallback | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> CrawlResult:
    """Crawl ``start_url`` (and same-site links) up to the configured limits."""
    options = (options or CrawlOptions()).clamp()
    template = get_template(options.template_key)
    started = time.monotonic()

    try:
        start = validate_url(start_url)
    except URLValidationError as exc:
        return CrawlResult(start_url, "", status="failed", error=str(exc))

    result = CrawlResult(start_url=start, domain=get_domain(start))
    fetcher = fetcher or SafeFetcher(timeout=options.timeout, delay=options.delay)
    robots = robots or RobotsHandler(fetcher)
    allowed_host = get_domain(start)

    queue: deque[str] = deque([start])
    queued: set[str] = {normalize_url(start)}
    visited_final: set[str] = set()
    emit = progress or (lambda *_: None)

    while queue and result.pages_attempted < options.max_pages:
        if should_stop and should_stop():
            result.status = "stopped"
            break
        url = queue.popleft()
        result.pages_attempted += 1
        emit(result.pages_attempted - 1, options.max_pages, url, "fetching")

        if not robots.can_fetch(url):
            msg = "Disallowed by robots.txt (or robots.txt unavailable) — skipped."
            result.page_log.append({"url": url, "status": "skipped", "message": msg, "records": 0})
            if url == start:
                result.warnings.append(f"The start URL is blocked by robots.txt: {url}")
            continue

        crawl_delay = robots.crawl_delay(url)
        delay = max(options.delay, min(crawl_delay, 10.0)) if crawl_delay else options.delay
        try:
            fetched = fetcher.fetch(url, delay=delay)
        except FetchError as exc:
            logger.info("Fetch failed for %s: %s", url, exc.kind)
            result.page_log.append({"url": url, "status": "error", "message": exc.message, "records": 0})
            if url == start:
                result.error = exc.message
            continue
        except Exception as exc:  # defensive: never crash the UI
            logger.exception("Unexpected error fetching %s", url)
            result.page_log.append({"url": url, "status": "error", "message": f"Unexpected error: {type(exc).__name__}", "records": 0})
            continue

        final_url = fetched.final_url
        final_key = normalize_url(final_url)
        if final_key in visited_final:
            result.page_log.append({"url": url, "status": "skipped", "message": f"Redirects to an already scraped page ({final_url}).", "records": 0})
            continue
        visited_final.add(final_key)
        queued.add(final_key)
        if result.pages_succeeded == 0 and not same_site(get_domain(final_url), allowed_host):
            allowed_host = get_domain(final_url)
            result.warnings.append(f"The start URL redirected to {allowed_host}; crawling is limited to that domain.")

        page_records: list[dict] = []
        try:
            if template.record_type == "product":
                page_records = parse_product_listing(fetched.text, final_url, template, fetched.status_code)
            if not page_records:
                record = parse_page(fetched.text, final_url, options.extract, template, fetched.status_code)
                page_records = [record]
                if template.record_type == "product":
                    result.warnings.append(f"No product cards were detected on {final_url}; extracted it as a normal page.")
            page_links = parse_links_for_follow(fetched.text, final_url)
        except Exception as exc:
            logger.exception("Parsing failed for %s", final_url)
            result.page_log.append({"url": url, "status": "error", "message": f"Could not parse the page ({type(exc).__name__}).", "records": 0})
            continue

        result.pages_succeeded += 1
        result.records.extend(page_records)
        notes = " ".join(r.get("extraction_notes", "") for r in page_records).strip()
        for note in {r.get("extraction_notes", "") for r in page_records if r.get("extraction_notes")}:
            if note not in result.warnings:
                result.warnings.append(f"{final_url}: {note}")
        result.page_log.append({"url": final_url, "status": "ok", "message": notes or "Extracted", "records": len(page_records)})
        emit(result.pages_attempted, options.max_pages, url, "parsed")

        if options.follow_links and options.max_links_per_page > 0:
            added = 0
            for link in page_links:
                if added >= options.max_links_per_page or len(queued) >= config.MAX_PAGES_LIMIT * 20:
                    break
                key = normalize_url(link)
                if key in queued or not same_site(get_domain(link), allowed_host):
                    continue
                if not _should_follow(link, template):
                    continue
                queued.add(key)
                queue.append(link)
                added += 1

    result.duration = time.monotonic() - started
    if result.status != "stopped":
        if result.pages_succeeded == 0:
            result.status = "failed"
            result.error = result.error or "No pages could be scraped."
        elif result.pages_succeeded < result.pages_attempted:
            result.status = "partial"
    if result.status == "completed" and not result.records:
        result.status = "failed"
        result.error = "No data could be extracted."
    return result


def parse_links_for_follow(html: str, base_url: str) -> list[str]:
    """Links found in the page, used for crawl expansion (not limited by extraction options)."""
    from scraper.parser import extract_links, make_soup

    return extract_links(make_soup(html), base_url)
