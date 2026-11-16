import pytest

from scraper.crawler import CrawlOptions, crawl
from scraper.fetcher import FetchError, FetchResult, SafeFetcher
from scraper.parser import ExtractOptions, parse_date, parse_page, parse_product_listing
from scraper.robots_handler import RobotsHandler
from scraper.templates import get_template, template_config

URL = "https://example.com/news/solar"


def test_metadata_extraction(fixture_html):
    rec = parse_page(fixture_html("article.html"), URL, template=get_template("news"))
    assert rec["title"] == "Solar Power Growth Hits Record High"
    assert rec["meta_description"].startswith("Solar energy installations")
    assert rec["publication_date"] == "2024-03-15"
    assert rec["domain"] == "example.com"
    assert rec["h1"] == ["Solar Power Growth Hits Record High"]
    assert rec["h2"] == ["Why installations are surging"] and rec["h3"] == ["Falling costs"]


def test_links_images_and_pii(fixture_html):
    rec = parse_page(fixture_html("article.html"), URL)
    assert "https://example.com/news/wind-power" in rec["links"]
    assert "https://other.org/x" in rec["links"]
    assert all(l.startswith("http") and "#" not in l and "mailto" not in l for l in rec["links"])
    assert rec["images"] == [{"src": "https://example.com/img/solar.jpg", "alt": "Solar panels"}]
    assert "newsroom@example.com" not in rec["content"] + rec["paragraphs"]
    assert rec["word_count"] > 20 and rec["content_length"] == len(rec["content"])


def test_extract_options_disable(fixture_html):
    opts = ExtractOptions(headings=False, links=False, images=False, date=False, article=False, paragraphs=False)
    rec = parse_page(fixture_html("article.html"), URL, opts)
    assert rec["h1"] == [] and rec["links"] == [] and rec["images"] == [] and rec["publication_date"] == ""
    assert rec["content"] == "" and rec["paragraphs"] == ""


def test_javascript_page_flagged(fixture_html):
    rec = parse_page(fixture_html("js_app.html"), "https://spa.example.com/")
    assert "JavaScript" in rec["extraction_notes"]


def test_captcha_flagged():
    rec = parse_page("<html><head><title>Just a moment...</title></head><body><div class='cf-challenge'></div></body></html>", URL)
    assert "CAPTCHA" in rec["extraction_notes"]


def test_malformed_html_does_not_crash(fixture_html):
    rec = parse_page(fixture_html("malformed.html"), URL)
    assert rec["title"] and rec["url"] == URL
    assert "https://example.com/ok" in rec["links"]
    assert parse_page("", URL)["title"] == ""


def test_parse_date():
    assert parse_date("March 3, 2023") == "2023-03-03"
    assert parse_date("2023-03-03T10:00:00Z") == "2023-03-03"
    assert parse_date("garbage") == "" and parse_date("") == "" and parse_date("2999-01-01") == ""


def test_product_listing(fixture_html):
    tpl = get_template("products")
    items = parse_product_listing(fixture_html("products.html"), "https://shop.example.com/shop", tpl)
    assert [i["title"] for i in items] == ["Blue Widget", "Red Widget"]  # duplicate removed
    assert items[0]["price"] == "$19.99" and items[0]["url"] == "https://shop.example.com/item/1"
    assert items[0]["record_type"] == "product"


def test_template_config_preview():
    cfg = template_config(get_template("news"))
    assert cfg["key"] == "news" and "container_selectors" in cfg


# ---- crawler with a fake fetcher (no network) ---------------------------------
class FakeFetcher(SafeFetcher):
    def __init__(self, pages):
        super().__init__(delay=0, validator=lambda u: u)
        self.pages, self.calls = pages, []

    def fetch(self, url, allowed_types=(), delay=None):
        self.calls.append(url)
        if url not in self.pages:
            raise FetchError("http_404", "Page not found (HTTP 404).", 404)
        body = self.pages[url]
        if isinstance(body, FetchError):
            raise body
        return FetchResult(url, url, 200, body, "text/html", 0.0)


@pytest.fixture(autouse=True)
def no_dns(monkeypatch):
    monkeypatch.setattr("scraper.crawler.validate_url", lambda u: u if u.endswith("/") or "/" in u[8:] else u + "/")


def test_crawl_same_domain_and_limits(fixture_html):
    page = fixture_html("article.html")
    pages = {
        "https://example.com/robots.txt": "User-agent: *\nDisallow: /private/\n",
        "https://example.com/": "<html><title>Home</title><body><p>Welcome home, this is the landing page of the example site.</p></body></html>",
        "https://example.com/news/solar": page,
        "https://example.com/news/wind-power": page.replace("Solar", "Wind"),
    }
    f = FakeFetcher(pages)
    res = crawl("https://example.com/news/solar", CrawlOptions(max_pages=5, max_links_per_page=10, delay=0), fetcher=f)
    urls = [r["url"] for r in res.records]
    assert urls[0] == "https://example.com/news/solar"
    assert set(urls) == {"https://example.com/news/solar", "https://example.com/news/wind-power", "https://example.com/"}
    assert "https://other.org/x" not in f.calls          # off-domain never fetched
    assert "https://example.com/login" not in f.calls      # account pages skipped
    assert res.status == "completed"


def test_crawl_respects_max_pages_and_robots(fixture_html):
    page = fixture_html("article.html").replace('href="/news/wind-power"', 'href="/private/x"')
    f = FakeFetcher({"https://example.com/robots.txt": "User-agent: *\nDisallow: /private/\n", "https://example.com/a": page})
    res = crawl("https://example.com/a", CrawlOptions(max_pages=3, delay=0), fetcher=f)
    assert "https://example.com/private/x" not in f.calls
    assert len(res.records) == 1


def test_crawl_failure_messages():
    f = FakeFetcher({"https://example.com/robots.txt": FetchError("http_404", "nf", 404),
                     "https://example.com/x": FetchError("http_429", "rate limited (HTTP 429)", 429)})
    res = crawl("https://example.com/x", CrawlOptions(delay=0), fetcher=f)
    assert res.status == "failed" and "429" in res.error and res.records == []


def test_crawl_invalid_url():
    import scraper.crawler as c
    from utils.validators import URLValidationError
    def boom(u): raise URLValidationError("blocked")
    c.validate_url = boom
    res = crawl("http://127.0.0.1", CrawlOptions())
    assert res.status == "failed" and res.error == "blocked"


def test_robots_handler(fixture_html):
    f = FakeFetcher({"https://example.com/robots.txt": fixture_html("robots.txt")})
    r = RobotsHandler(f)
    assert r.can_fetch("https://example.com/public") and not r.can_fetch("https://example.com/private/a")
    assert r.crawl_delay("https://example.com/") == 2.0
    # unreachable robots.txt => fail closed
    r2 = RobotsHandler(FakeFetcher({"https://down.com/robots.txt": FetchError("timeout", "t")}))
    assert not r2.can_fetch("https://down.com/")
    r3 = RobotsHandler(FakeFetcher({}))  # 404 => allow
    assert r3.can_fetch("https://none.com/x")


# ---- fetcher redirect safety (mocked HTTP session) ------------------------------
class _Resp:
    def __init__(self, status=200, headers=None, body=b"<html></html>"):
        self.status_code, self.headers, self._body = status, headers or {"Content-Type": "text/html"}, body
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def iter_content(self, chunk_size=0):
        for i in range(0, len(self._body), 1000):
            yield self._body[i:i + 1000]


class _Session:
    def __init__(self, responses): self.responses, self.requested = responses, []
    def get(self, url, **kw):
        self.requested.append(url)
        assert kw["allow_redirects"] is False
        return self.responses[url]


def test_fetcher_blocks_redirect_to_internal():
    from utils.validators import URLValidationError
    def validator(u):
        if "169.254" in u: raise URLValidationError("Private, loopback and internal addresses are not allowed.")
        return u
    s = _Session({"https://example.com/": _Resp(302, {"Location": "http://169.254.169.254/latest"})})
    f = SafeFetcher(delay=0, session=s, validator=validator)
    with pytest.raises(FetchError) as e:
        f.fetch("https://example.com/")
    assert e.value.kind == "blocked" and s.requested == ["https://example.com/"]


@pytest.mark.parametrize("status,kind", [(403, "http_403"), (404, "http_404"), (429, "http_429"), (500, "http_5xx")])
def test_fetcher_http_errors(status, kind):
    f = SafeFetcher(delay=0, session=_Session({"https://example.com/": _Resp(status)}), validator=lambda u: u)
    with pytest.raises(FetchError) as e:
        f.fetch("https://example.com/")
    assert e.value.kind == kind


def test_fetcher_size_limit_and_content_type():
    big = _Resp(body=b"x" * 5000)
    with pytest.raises(FetchError) as e:
        SafeFetcher(delay=0, max_bytes=2000, session=_Session({"https://example.com/": big}), validator=lambda u: u).fetch("https://example.com/")
    assert e.value.kind == "too_large"
    pdf = _Resp(headers={"Content-Type": "application/pdf"})
    with pytest.raises(FetchError) as e:
        SafeFetcher(delay=0, session=_Session({"https://example.com/": pdf}), validator=lambda u: u).fetch("https://example.com/")
    assert e.value.kind == "not_html"


def test_fetcher_follows_valid_redirect():
    s = _Session({"https://example.com/": _Resp(301, {"Location": "/new"}), "https://example.com/new": _Resp(body="héllo".encode())})
    res = SafeFetcher(delay=0, session=s, validator=lambda u: u).fetch("https://example.com/")
    assert res.final_url == "https://example.com/new" and "héllo" in res.text
