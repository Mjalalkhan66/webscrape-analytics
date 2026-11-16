"""HTML parsing: metadata, headings, content, links, images, dates and limitation detection."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urldefrag, urljoin

import trafilatura
from bs4 import BeautifulSoup, Tag
from dateutil import parser as date_parser

import config
from scraper.templates import ScrapeTemplate, get_template
from utils.helpers import collapse_whitespace, get_domain, redact_pii, truncate, utc_now_iso
from utils.logger import get_logger

logger = get_logger("parser")

_PRICE_RE = re.compile(r"(?:[$€£¥₹]|Rs\.?|PKR|USD|EUR|GBP|INR)\s?\d[\d,]*(?:\.\d{1,2})?", re.I)
_DATE_META = (
    ("property", "article:published_time"), ("property", "og:article:published_time"),
    ("name", "article:published_time"), ("name", "pubdate"), ("name", "publishdate"),
    ("name", "date"), ("name", "dc.date"), ("name", "dc.date.issued"), ("name", "dcterms.created"),
    ("itemprop", "datePublished"), ("property", "og:published_time"), ("name", "parsely-pub-date"),
    ("name", "sailthru.date"),
)
_NOISE_TAGS = ("script", "style", "noscript", "template", "iframe", "svg", "canvas", "object", "embed")


@dataclass
class ExtractOptions:
    """Which parts of a page to extract."""
    headings: bool = True
    paragraphs: bool = True
    article: bool = True
    links: bool = True
    images: bool = True
    date: bool = True


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def make_soup(html: str) -> BeautifulSoup:
    """Parse possibly malformed HTML; falls back to the stdlib parser if lxml fails."""
    try:
        return BeautifulSoup(html or "", "lxml")
    except Exception:  # pragma: no cover - lxml failure is rare
        logger.warning("lxml failed; falling back to html.parser")
        return BeautifulSoup(html or "", "html.parser")


def _text(el: Tag | None) -> str:
    return collapse_whitespace(el.get_text(" ", strip=True)) if el is not None else ""


def _first(root: Tag, selectors: tuple[str, ...]) -> Tag | None:
    for sel in selectors:
        try:
            found = root.select_one(sel)
        except Exception:  # invalid selector in a custom template
            continue
        if found is not None:
            return found
    return None


def _json_ld_objects(soup: BeautifulSoup) -> list[dict]:
    objects: list[dict] = []
    for script in soup.find_all("script", type=re.compile(r"ld\+json", re.I)):
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                objects.append(item)
                graph = item.get("@graph")
                if isinstance(graph, list):
                    stack.extend(graph)
            elif isinstance(item, list):
                stack.extend(item)
    return objects


def parse_date(value: str | None) -> str:
    """Parse a date string to ``YYYY-MM-DD`` ('' if invalid or implausible)."""
    if not value or not str(value).strip():
        return ""
    try:
        dt = date_parser.parse(str(value).strip(), fuzzy=False)
    except (ValueError, OverflowError, TypeError):
        return ""
    now = datetime.now(timezone.utc)
    aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if dt.year < 1990 or aware > now + timedelta(days=1):
        return ""
    return dt.strftime("%Y-%m-%d")


def extract_publication_date(soup: BeautifulSoup, json_ld: list[dict], template: ScrapeTemplate) -> str:
    """Try template selectors, meta tags, JSON-LD and ``<time>`` tags, in that order."""
    for sel in template.date_selectors:
        try:
            el = soup.select_one(sel)
        except Exception:
            continue
        if el is not None:
            parsed = parse_date(el.get("datetime") or el.get("content") or _text(el))
            if parsed:
                return parsed
    for attr, name in _DATE_META:
        el = soup.find("meta", attrs={attr: name})
        if el is not None:
            parsed = parse_date(el.get("content"))
            if parsed:
                return parsed
    for obj in json_ld:
        for key in ("datePublished", "dateCreated", "uploadDate"):
            parsed = parse_date(obj.get(key) if isinstance(obj.get(key), str) else None)
            if parsed:
                return parsed
    el = soup.find("time", attrs={"datetime": True})
    if el is not None:
        return parse_date(el.get("datetime"))
    return ""


def extract_links(soup: BeautifulSoup, base_url: str, limit: int = 500) -> list[str]:
    """Absolute, de-duplicated http(s) links without fragments."""
    base_tag = soup.find("base", href=True)
    base = urljoin(base_url, base_tag["href"]) if base_tag else base_url
    seen: dict[str, None] = {}
    for a in soup.find_all("a", href=True):
        href = (a["href"] or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue
        try:
            absolute, _ = urldefrag(urljoin(base, href))
        except ValueError:
            continue
        if absolute.lower().startswith(("http://", "https://")) and absolute not in seen:
            seen[absolute] = None
            if len(seen) >= limit:
                break
    return list(seen)


def extract_images(soup: BeautifulSoup, base_url: str, limit: int = 100) -> list[dict]:
    images: list[dict] = []
    seen: set[str] = set()
    for img in soup.find_all("img"):
        src = (img.get("src") or img.get("data-src") or img.get("data-lazy-src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        absolute = urljoin(base_url, src)
        if not absolute.lower().startswith(("http://", "https://")) or absolute in seen:
            continue
        seen.add(absolute)
        images.append({"src": absolute, "alt": collapse_whitespace(img.get("alt"))})
        if len(images) >= limit:
            break
    return images


def detect_limitations(soup: BeautifulSoup, html: str, text_length: int) -> list[str]:
    """Return human-readable warnings for pages this scraper cannot handle well."""
    notes: list[str] = []
    title = _text(soup.title).lower()
    lowered = (html or "")[:200_000].lower()
    protection = ("just a moment", "attention required", "access denied", "are you a robot", "verify you are human")
    if any(t in title for t in protection) or any(
        m in lowered for m in ("g-recaptcha", "h-captcha", "cf-challenge", "cf-turnstile", "px-captcha")
    ):
        notes.append("The page shows a CAPTCHA or anti-bot challenge. This tool does not bypass such protections.")
    if text_length < 200:
        scripts = len(soup.find_all("script"))
        spa_markers = ('id="root"', 'id="__next"', 'id="app"', "ng-app", 'id="__nuxt"', "data-reactroot")
        if scripts >= 5 or any(m in lowered for m in spa_markers):
            notes.append(
                "Little text was found and the page relies on JavaScript. Content rendered in the browser "
                "cannot be extracted by this scraper."
            )
        elif soup.find("input", attrs={"type": "password"}):
            notes.append("This looks like a login page. Authenticated content cannot be scraped.")
        else:
            notes.append("Very little text content was found on this page.")
    return notes


# ----------------------------------------------------------------------------
# page parsing
# ----------------------------------------------------------------------------
def _paragraphs(container: Tag, min_len: int = 20, cap: int = 200) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for p in container.find_all("p"):
        text = _text(p)
        if len(text) >= min_len and text not in seen:
            seen.add(text)
            out.append(text)
            if len(out) >= cap:
                break
    return out


def _headings(container: Tag, level: str, cap: int = 50) -> list[str]:
    out: list[str] = []
    for h in container.find_all(level):
        text = _text(h)
        if text and text not in out:
            out.append(text)
            if len(out) >= cap:
                break
    return out


def parse_page(
    html: str,
    url: str,
    options: ExtractOptions | None = None,
    template: ScrapeTemplate | None = None,
    status_code: int | None = None,
) -> dict:
    """Parse one HTML page into a flat record dict. Never raises on malformed HTML."""
    options = options or ExtractOptions()
    template = template or get_template("generic")
    soup = make_soup(html)
    json_ld = _json_ld_objects(soup)

    # Links/images/date use the complete document.
    links = extract_links(soup, url) if options.links else []
    images = extract_images(soup, url) if options.images else []
    pub_date = extract_publication_date(soup, json_ld, template) if options.date else ""

    meta_desc_el = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    meta_description = collapse_whitespace(meta_desc_el.get("content")) if meta_desc_el else ""

    # Title
    title_el = _first(soup, template.title_selectors) if template.title_selectors else None
    og_title = soup.find("meta", attrs={"property": "og:title"})
    title = _text(title_el) or (collapse_whitespace(og_title.get("content")) if og_title else "")
    if not title:
        title = _text(soup.title) or _text(soup.find("h1"))

    # Remove noise, then work on the content container.
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()
    body = soup.body or soup
    container = _first(body, template.container_selectors) or body
    for sel in template.exclude_selectors:
        try:
            for el in container.select(sel):
                if el is not container:
                    el.decompose()
        except Exception:
            continue

    h1 = _headings(container, "h1") if options.headings else []
    h2 = _headings(container, "h2") if options.headings else []
    h3 = _headings(container, "h3") if options.headings else []
    paragraphs = _paragraphs(container)

    content = ""
    if options.article:
        content_el = _first(container, template.content_selectors) if template.content_selectors else None
        if content_el is not None:
            content = "\n\n".join(_paragraphs(content_el, min_len=1)) or _text(content_el)
        if len(content) < 200:
            try:
                extracted = trafilatura.extract(
                    html, url=url, include_comments=False, include_tables=False, favor_precision=True
                )
            except Exception as exc:  # trafilatura can fail on odd markup
                logger.debug("trafilatura failed for %s: %s", url, exc)
                extracted = None
            if extracted and len(extracted) > len(content):
                content = extracted
        if len(content) < 200 and paragraphs:
            content = "\n\n".join(paragraphs)
    content = truncate(redact_pii(content.strip()), config.MAX_CONTENT_CHARS)
    paragraph_text = truncate(redact_pii("\n\n".join(paragraphs)), config.MAX_CONTENT_CHARS) if options.paragraphs else ""

    notes = detect_limitations(soup, html, max(len(content), len(paragraph_text)))
    domain = get_domain(url)
    return {
        "url": url,
        "domain": domain,
        "title": title,
        "meta_description": meta_description,
        "h1": h1,
        "h2": h2,
        "h3": h3,
        "paragraphs": paragraph_text,
        "content": content,
        "word_count": len(content.split()),
        "content_length": len(content),
        "links": links,
        "links_count": len(links),
        "images": images,
        "image_count": len(images),
        "publication_date": pub_date,
        "price": "",
        "record_type": "page",
        "template": template.key,
        "status_code": status_code,
        "scraped_at": utc_now_iso(),
        "extraction_notes": " ".join(notes),
    }


def parse_product_listing(
    html: str, url: str, template: ScrapeTemplate, status_code: int | None = None
) -> list[dict]:
    """Extract one record per product card on a listing page."""
    soup = make_soup(html)
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()
    items: list[Tag] = []
    for sel in template.item_selectors:
        try:
            found = soup.select(sel)
        except Exception:
            continue
        if len(found) >= 2:  # a real listing has several cards
            items = found
            break
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    now = utc_now_iso()
    for item in items[:200]:
        name_el = _first(item, template.item_name_selectors)
        name = collapse_whitespace(name_el.get("title") if name_el is not None and name_el.get("title") else _text(name_el))
        if not name:
            continue
        link_el = _first(item, template.item_link_selectors)
        link = urljoin(url, link_el["href"]) if link_el is not None and link_el.get("href") else url
        link = urldefrag(link)[0]
        price_el = _first(item, template.item_price_selectors)
        price_text = _text(price_el) or ""
        price_match = _PRICE_RE.search(price_text) or _PRICE_RE.search(_text(item))
        price = price_match.group(0) if price_match else price_text
        key = (link, name)
        if key in seen:
            continue
        seen.add(key)
        text = redact_pii(_text(item))
        imgs = extract_images(item, url, limit=5)
        records.append({
            "url": link, "domain": get_domain(link), "title": name, "meta_description": "",
            "h1": [], "h2": [], "h3": [], "paragraphs": "",
            "content": truncate(text, config.MAX_CONTENT_CHARS), "word_count": len(text.split()),
            "content_length": len(text), "links": [link], "links_count": 1, "images": imgs,
            "image_count": len(imgs), "publication_date": "", "price": price, "record_type": "product",
            "template": template.key, "status_code": status_code, "scraped_at": now,
            "extraction_notes": "",
        })
    return records
