"""Safe HTTP fetching: SSRF-checked redirects, size limits, per-host delay, friendly errors."""
from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import UnicodeDammit

import config
from utils.helpers import get_domain
from utils.logger import get_logger
from utils.validators import URLValidationError, validate_url

logger = get_logger("fetcher")

HTML_TYPES = ("text/html", "application/xhtml+xml")
TEXT_TYPES = ("text/",)
_REDIRECT_CODES = {301, 302, 303, 307, 308}


class FetchError(Exception):
    """A fetch failure with a machine-readable ``kind`` and a user-facing message."""

    def __init__(self, kind: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.status_code = status_code


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    text: str
    content_type: str
    elapsed: float


class SafeFetcher:
    """HTTP client that never follows a redirect without re-validating it."""

    def __init__(
        self,
        timeout: float = config.DEFAULT_TIMEOUT,
        delay: float = config.DEFAULT_DELAY,
        max_bytes: int = config.MAX_RESPONSE_BYTES,
        max_redirects: int = config.MAX_REDIRECTS,
        user_agent: str = config.USER_AGENT,
        session: requests.Session | None = None,
        validator=validate_url,
    ):
        self.timeout = timeout
        self.delay = max(delay, 0.0)
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.user_agent = user_agent
        self.session = session or requests.Session()
        self._validator = validator
        self._last_request: dict[str, float] = {}

    # ------------------------------------------------------------------
    def _wait_for_host(self, host: str, delay: float | None = None) -> None:
        wait_for = self.delay if delay is None else delay
        last = self._last_request.get(host)
        if last is not None:
            remaining = wait_for - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request[host] = time.monotonic()

    def fetch(
        self,
        url: str,
        allowed_types: tuple[str, ...] = HTML_TYPES,
        delay: float | None = None,
    ) -> FetchResult:
        """Fetch ``url`` and return decoded text. Raises :class:`FetchError`."""
        current = url
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5,*/*;q=0.1",
            "Accept-Language": "en;q=0.9,*;q=0.5",
        }
        for _ in range(self.max_redirects + 1):
            try:
                current = self._validator(current)
            except URLValidationError as exc:
                raise FetchError("blocked", str(exc)) from exc

            self._wait_for_host(get_domain(current), delay)
            started = time.monotonic()
            try:
                with self.session.get(
                    current,
                    headers=headers,
                    timeout=(min(self.timeout, 10), self.timeout),
                    stream=True,
                    allow_redirects=False,
                ) as resp:
                    status = resp.status_code
                    if status in _REDIRECT_CODES:
                        location = resp.headers.get("Location")
                        if not location:
                            raise FetchError("http_error", "Redirect without a target location.", status)
                        current = urljoin(current, location)
                        logger.info("Redirect %s -> %s", status, current)
                        continue
                    self._raise_for_status(resp)
                    content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
                    if content_type and not content_type.startswith(allowed_types):
                        raise FetchError(
                            "not_html",
                            f"The URL returned '{content_type}', not an HTML page.",
                            status,
                        )
                    declared = resp.headers.get("Content-Length", "")
                    if declared.isdigit() and int(declared) > self.max_bytes:
                        raise FetchError("too_large", self._too_large_msg(), status)
                    raw = self._read_limited(resp)
                    text = self._decode(raw, resp.headers.get("Content-Type", ""))
                    return FetchResult(
                        url=url,
                        final_url=current,
                        status_code=status,
                        text=text,
                        content_type=content_type,
                        elapsed=time.monotonic() - started,
                    )
            except FetchError:
                raise
            except requests.exceptions.Timeout as exc:
                raise FetchError(
                    "timeout", f"The request timed out after {self.timeout:.0f}s. Try a longer timeout."
                ) from exc
            except requests.exceptions.SSLError as exc:
                raise FetchError("ssl", "The site's SSL certificate could not be verified.") from exc
            except requests.exceptions.TooManyRedirects as exc:
                raise FetchError("too_many_redirects", "The site redirected too many times.") from exc
            except requests.exceptions.ConnectionError as exc:
                raise FetchError("connection", "Could not connect to the site. Check the URL and your network.") from exc
            except requests.exceptions.RequestException as exc:
                logger.warning("Unexpected request error for %s: %s", current, exc)
                raise FetchError("request", "The request failed unexpectedly.") from exc
        raise FetchError("too_many_redirects", f"The site redirected more than {self.max_redirects} times.")

    # ------------------------------------------------------------------
    def _too_large_msg(self) -> str:
        return f"The page is larger than the {self.max_bytes / 1_000_000:.1f} MB limit and was skipped."

    def _read_limited(self, resp: requests.Response) -> bytes:
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=16_384):
            total += len(chunk)
            if total > self.max_bytes:
                raise FetchError("too_large", self._too_large_msg(), resp.status_code)
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _decode(raw: bytes, content_type_header: str) -> str:
        overrides = []
        if "charset=" in content_type_header.lower():
            overrides.append(content_type_header.lower().split("charset=")[-1].split(";")[0].strip())
        dammit = UnicodeDammit(raw, known_definite_encodings=overrides, is_html=True)
        return dammit.unicode_markup or raw.decode("utf-8", errors="replace")

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        code = resp.status_code
        if code < 400:
            return
        if code == 403:
            raise FetchError(
                "http_403",
                "Access forbidden (HTTP 403). The site refuses automated access — it may use anti-bot "
                "protection. This tool does not bypass such protections.",
                code,
            )
        if code == 401:
            raise FetchError("http_401", "This page requires authentication (HTTP 401) and cannot be scraped.", code)
        if code in (404, 410):
            raise FetchError("http_404", f"Page not found (HTTP {code}).", code)
        if code == 429:
            retry = resp.headers.get("Retry-After")
            hint = f" The site asks to retry after {retry}s." if retry else ""
            raise FetchError(
                "http_429",
                f"The site is rate limiting requests (HTTP 429).{hint} Increase the delay and try again later.",
                code,
            )
        if code >= 500:
            raise FetchError("http_5xx", f"The server reported an error (HTTP {code}). Try again later.", code)
        raise FetchError("http_error", f"The server returned HTTP {code}.", code)
