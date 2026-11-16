"""Small, dependency-free helper functions shared across the app."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

_WS_RE = re.compile(r"\s+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?<![\w/])(?:\+\d{1,3}[\s.-]?)?\(\d{2,4}\)[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?!\w)"
    r"|(?<![\w/])\+\d{1,3}[\s.-]\d{2,4}[\s.-]\d{3,4}[\s.-]?\d{0,4}(?!\w)"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string without microseconds."""
    return utc_now().replace(microsecond=0).isoformat()


def new_session_id() -> str:
    """Random 12-char hex id (filesystem safe, never user supplied)."""
    return uuid.uuid4().hex[:12]


def is_valid_session_id(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{12}", value or ""))


def collapse_whitespace(text: str | None) -> str:
    """Collapse runs of whitespace into single spaces and strip."""
    return _WS_RE.sub(" ", text or "").strip()


def truncate(text: str, limit: int, suffix: str = "…") -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(suffix))].rstrip() + suffix


def redact_pii(text: str) -> str:
    """Best-effort masking of e-mail addresses and obvious phone numbers."""
    text = _EMAIL_RE.sub("[email removed]", text)
    return _PHONE_RE.sub("[phone removed]", text)


def get_domain(url: str) -> str:
    """Lower-case hostname of ``url`` (empty string if it cannot be parsed)."""
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _strip_www(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def same_site(host_a: str, host_b: str) -> bool:
    """True if both hosts are identical, ignoring a leading ``www.``."""
    return bool(host_a) and _strip_www(host_a.lower()) == _strip_www(host_b.lower())


def normalize_url(url: str) -> str:
    """Normalise a URL for de-duplication (lower-case host, no fragment, default port dropped)."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((parts.scheme == "http" and port == 80) or (parts.scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), host, path, parts.query, ""))


def format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "–"
    seconds = float(seconds)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, sec = divmod(int(seconds), 60)
    return f"{minutes}m {sec:02d}s"


def safe_filename(text: str, default: str = "export", max_len: int = 60) -> str:
    """Convert arbitrary text into a safe filename stem."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text or "").strip("._-")
    return (cleaned or default)[:max_len]
