"""Configurable extraction strategies.

A template is *data*, not code: CSS selector lists tried in order, falling back
to generic heuristics when nothing matches. This keeps the scraper usable on
sites with different HTML structures without hard-coding any one site.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ScrapeTemplate:
    key: str
    name: str
    description: str
    record_type: str = "page"  # "page" or "product"
    container_selectors: tuple[str, ...] = ()
    exclude_selectors: tuple[str, ...] = ("nav", "footer", "aside", "form", "header nav")
    title_selectors: tuple[str, ...] = ()
    content_selectors: tuple[str, ...] = ()
    date_selectors: tuple[str, ...] = ()
    item_selectors: tuple[str, ...] = ()
    item_name_selectors: tuple[str, ...] = ()
    item_price_selectors: tuple[str, ...] = ()
    item_link_selectors: tuple[str, ...] = ()
    follow_url_patterns: tuple[str, ...] = ()  # regexes; empty = follow any same-site link
    skip_url_patterns: tuple[str, ...] = ()


# Never follow account / checkout style pages (private or personal areas).
GLOBAL_SKIP_PATTERNS: tuple[str, ...] = (
    r"/(login|log-in|signin|sign-in|signup|sign-up|register|account|my-account|profile|cart|checkout|"
    r"basket|admin|wp-admin|wp-login|password|logout|unsubscribe)(/|$|\?)",
    r"\.(pdf|zip|gz|rar|7z|exe|dmg|apk|mp3|mp4|avi|mov|wmv|jpg|jpeg|png|gif|webp|svg|ico|css|js|json|xml|"
    r"docx?|xlsx?|pptx?|csv)(\?|$)",
)

TEMPLATES: dict[str, ScrapeTemplate] = {
    "generic": ScrapeTemplate(
        key="generic",
        name="General informational website",
        description="Heuristic extraction that works on most static, server-rendered pages.",
        container_selectors=("main", "[role=main]", "#content", ".content", "article", "body"),
        date_selectors=("time[datetime]", "[itemprop=datePublished]", ".date", ".published"),
    ),
    "news": ScrapeTemplate(
        key="news",
        name="News / article website",
        description="Targets article bodies, headlines and publication timestamps.",
        container_selectors=("article", "[itemtype*=Article]", "main", "[role=main]", "#content"),
        title_selectors=("article h1", "h1.headline", "h1[itemprop=headline]", "h1"),
        content_selectors=("article .article-body", "[itemprop=articleBody]", ".story-body", ".article-content", "article"),
        date_selectors=("time[datetime]", "[itemprop=datePublished]", ".published", ".timestamp", ".date"),
        skip_url_patterns=(r"/(tag|tags|topic|topics|author|authors|video|videos|live|podcasts?)/",),
    ),
    "blog": ScrapeTemplate(
        key="blog",
        name="Blog",
        description="Targets blog post bodies (WordPress-style and static-site themes).",
        container_selectors=("article", ".post", ".entry", "main", "#content"),
        title_selectors=("h1.entry-title", "h1.post-title", "article h1", "h1"),
        content_selectors=(".entry-content", ".post-content", ".post-body", "[itemprop=articleBody]", "article"),
        date_selectors=("time.entry-date", "time[datetime]", ".post-date", ".published", ".date"),
        skip_url_patterns=(r"/(tag|tags|category|categories|author|feed|comments?)/", r"[?&](replytocom|share)="),
    ),
    "products": ScrapeTemplate(
        key="products",
        name="Public product listing",
        description="Extracts one record per product card (name, price, link) and follows pagination only.",
        record_type="product",
        container_selectors=("main", "#content", "body"),
        exclude_selectors=("nav", "footer", "aside"),
        item_selectors=(
            "[itemtype*='schema.org/Product']", "li.product", "article.product_pod", "div.product",
            ".product-card", ".product-item", ".product-tile", "[data-product-id]", "li.grid__item",
        ),
        item_name_selectors=("[itemprop=name]", "h3 a", "h2 a", "h3", "h2", ".product-title", ".product-name", "a[title]"),
        item_price_selectors=("[itemprop=price]", ".price_color", ".price", ".product-price", "[class*=price]"),
        item_link_selectors=("a[href]",),
        follow_url_patterns=(r"[?&](page|p|pg)=\d+", r"/page[-/]?\d+", r"/catalogue/page", r"/collections/[^/]+\?page="),
    ),
}


def get_template(key: str) -> ScrapeTemplate:
    return TEMPLATES.get(key, TEMPLATES["generic"])


def template_config(template: ScrapeTemplate) -> dict:
    """JSON-friendly view of a template, used for the preview in the UI."""
    data = asdict(template)
    return {k: v for k, v in data.items() if v not in ((), "", None)}
