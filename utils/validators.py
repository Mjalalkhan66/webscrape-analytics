"""URL validation and SSRF protection.

``validate_url`` must be called for the user-supplied URL *and* for every
redirect target. It enforces:

* only ``http`` / ``https`` schemes
* no embedded credentials
* an allow-list of ports
* no localhost / internal-looking host names
* every resolved IP address must be globally routable (blocks loopback,
  private, link-local, multicast, reserved and cloud-metadata ranges)

Note: validating DNS before connecting leaves a small DNS-rebinding window.
For a hardened deployment, put the app behind an egress proxy that enforces
the same rules (see README, "Security").
"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit, urlunsplit

import config


class URLValidationError(ValueError):
    """Raised with a user-friendly message when a URL is not acceptable."""


_BLOCKED_HOSTS = {
    "localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback",
    "metadata.google.internal", "metadata",
}
_BLOCKED_SUFFIXES = (
    ".localhost", ".local", ".internal", ".lan", ".home", ".corp", ".intranet", ".private",
)
_DANGEROUS_SCHEMES = re.compile(r"^(javascript|data|file|ftp|mailto|tel|vbscript|gopher|ssh):", re.I)
MAX_URL_LENGTH = 2048


def is_public_ip(value: str) -> bool:
    """True only for globally routable unicast addresses."""
    try:
        ip = ipaddress.ip_address(value.split("%")[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def _resolve(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise URLValidationError(f"The host '{host}' could not be resolved. Check the address.") from exc
    except UnicodeError as exc:
        raise URLValidationError("The host name is not valid.") from exc
    return [info[4][0] for info in infos]


def validate_url(url: str, resolve_dns: bool = True) -> str:
    """Validate ``url`` and return a normalised version.

    Raises :class:`URLValidationError` if the URL is unsafe or malformed.
    """
    raw = (url or "").strip()
    if not raw:
        raise URLValidationError("Please enter a URL.")
    if len(raw) > MAX_URL_LENGTH:
        raise URLValidationError("The URL is too long.")
    if any(ch in raw for ch in ("\n", "\r", "\t", "\x00", " ")):
        raise URLValidationError("The URL contains invalid characters.")
    if _DANGEROUS_SCHEMES.match(raw):
        raise URLValidationError("Only http:// and https:// URLs are allowed.")
    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")

    try:
        parts = urlsplit(raw)
        port = parts.port
        host = parts.hostname
    except ValueError as exc:
        raise URLValidationError("The URL is malformed.") from exc

    if parts.scheme.lower() not in {"http", "https"}:
        raise URLValidationError("Only http:// and https:// URLs are allowed.")
    if parts.username or parts.password:
        raise URLValidationError("URLs containing credentials are not allowed.")
    if not host:
        raise URLValidationError("The URL has no host name.")

    host = host.lower().rstrip(".")
    default_port = 443 if parts.scheme.lower() == "https" else 80
    effective_port = port or default_port
    if effective_port not in config.ALLOWED_PORTS:
        raise URLValidationError(f"Port {effective_port} is not allowed (use 80, 443, 8080 or 8443).")

    # IP literal?
    try:
        ipaddress.ip_address(host)
        is_literal = True
    except ValueError:
        is_literal = False

    if is_literal:
        if not is_public_ip(host):
            raise URLValidationError("Private, loopback and internal addresses are not allowed.")
    else:
        if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_SUFFIXES):
            raise URLValidationError("Internal and local host names are not allowed.")
        if "." not in host:
            raise URLValidationError("Please enter a fully qualified domain name (e.g. example.com).")
        try:
            host.encode("idna")
        except UnicodeError as exc:
            raise URLValidationError("The host name is not valid.") from exc
        if resolve_dns:
            addresses = _resolve(host, effective_port)
            if not addresses or not all(is_public_ip(a) for a in addresses):
                raise URLValidationError(
                    "This host resolves to a private or internal address and cannot be scraped."
                )

    netloc = host if is_literal is False else (f"[{host}]" if ":" in host else host)
    if port and port != default_port:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))
