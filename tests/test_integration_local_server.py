"""Exercises the real requests-based fetch/crawl path against a throwaway local HTTP server.

The SSRF validator is intentionally bypassed here (it would — correctly — block 127.0.0.1);
validator behaviour itself is covered in test_validators.py.
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import scraper.crawler as crawler
from scraper.crawler import CrawlOptions, crawl
from scraper.fetcher import FetchError, SafeFetcher
from scraper.robots_handler import RobotsHandler

ARTICLE = ("<html><head><title>Local Article</title><meta charset='utf-8'></head><body><article><h1>Local Article</h1>"
           "<p>" + "Energy markets are changing quickly as solar power grows across regions. " * 6 + "</p>"
           "<a href='/page2'>two</a><a href='/private/secret'>secret</a><a href='/old'>old</a></article></body></html>")


class Handler(BaseHTTPRequestHandler):
    hits: list[str] = []

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="text/html; charset=utf-8", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Handler.hits.append(self.path)
        if self.path == "/robots.txt":
            self._send(200, b"User-agent: *\nDisallow: /private/\n", "text/plain")
        elif self.path == "/":
            self._send(200, ARTICLE.encode())
        elif self.path == "/page2":
            self._send(200, ARTICLE.replace("Local Article", "Second Page").encode())
        elif self.path == "/old":
            self._send(301, b"", headers={"Location": "/page2"})
        elif self.path == "/big":
            self._send(200, b"x" * 300_000)
        elif self.path == "/pdf":
            self._send(200, b"%PDF", "application/pdf")
        elif self.path == "/forbidden":
            self._send(403, b"no")
        else:
            self._send(404, b"nf")


@pytest.fixture(scope="module")
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture
def fetcher():
    return SafeFetcher(delay=0, timeout=5, max_bytes=100_000, validator=lambda u: u)


def test_real_crawl(server, fetcher, monkeypatch):
    monkeypatch.setattr(crawler, "validate_url", lambda u: u)
    Handler.hits.clear()
    res = crawl(server + "/", CrawlOptions(max_pages=6, max_links_per_page=10, delay=0), fetcher=fetcher)
    titles = sorted(r["title"] for r in res.records)
    assert titles == ["Local Article", "Second Page"]            # /old redirect lands on /page2 (de-duplicated by URL)
    assert "/private/secret" not in Handler.hits                  # robots.txt honoured
    assert res.pages_succeeded >= 2 and res.status in {"completed", "partial"}


def test_real_fetch_errors(server, fetcher):
    for path, kind in [("/forbidden", "http_403"), ("/missing", "http_404"), ("/big", "too_large"), ("/pdf", "not_html")]:
        with pytest.raises(FetchError) as e:
            fetcher.fetch(server + path)
        assert e.value.kind == kind, path


def test_real_redirect_and_robots(server, fetcher):
    assert fetcher.fetch(server + "/old").final_url.endswith("/page2")
    r = RobotsHandler(fetcher)
    assert r.can_fetch(server + "/page2") and not r.can_fetch(server + "/private/x")


def test_real_validator_blocks_local_server(server):
    res = crawl(server + "/", CrawlOptions(delay=0))  # real validator, no bypass
    assert res.status == "failed" and "not allowed" in res.error.lower()


def test_connection_refused():
    f = SafeFetcher(delay=0, timeout=2, validator=lambda u: u)
    with pytest.raises(FetchError) as e:
        f.fetch("http://127.0.0.1:1/")
    assert e.value.kind == "connection"
