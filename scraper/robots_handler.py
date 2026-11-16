"""robots.txt support (cached per origin, fail-closed when robots.txt is unreachable)."""
from __future__ import annotations

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import config
from scraper.fetcher import TEXT_TYPES, FetchError, SafeFetcher
from utils.logger import get_logger

logger = get_logger("robots")


class RobotsHandler:
    """Check whether a URL may be fetched according to the site's robots.txt.

    Policy: 404/410 -> everything allowed; 401/403 or server/network failure ->
    everything disallowed (conservative); otherwise the parsed rules apply.
    """

    def __init__(self, fetcher: SafeFetcher, user_agent: str = config.USER_AGENT):
        self.fetcher = fetcher
        self.user_agent = user_agent
        self._parsers: dict[str, RobotFileParser | bool] = {}

    @staticmethod
    def _origin(url: str) -> str:
        p = urlsplit(url)
        return f"{p.scheme}://{p.netloc}"

    def _load(self, origin: str) -> RobotFileParser | bool:
        """Return a parser, ``True`` (allow all) or ``False`` (disallow all)."""
        if origin in self._parsers:
            return self._parsers[origin]
        robots_url = f"{origin}/robots.txt"
        result: RobotFileParser | bool
        try:
            fetched = self.fetcher.fetch(robots_url, allowed_types=TEXT_TYPES)
            parser = RobotFileParser()
            parser.parse(fetched.text.splitlines())
            result = parser
        except FetchError as exc:
            if exc.kind == "http_404":
                result = True
            elif exc.kind == "not_html":
                result = True  # robots.txt served as odd content type: treat as absent
            else:
                logger.warning("robots.txt unavailable for %s (%s); treating as disallowed", origin, exc.kind)
                result = False
        self._parsers[origin] = result
        return result

    def can_fetch(self, url: str) -> bool:
        parser = self._load(self._origin(url))
        if isinstance(parser, bool):
            return parser
        return parser.can_fetch(self.user_agent, url) and parser.can_fetch("*", url)

    def crawl_delay(self, url: str) -> float | None:
        parser = self._load(self._origin(url))
        if isinstance(parser, bool):
            return None
        delay = parser.crawl_delay(self.user_agent) or parser.crawl_delay("*")
        return float(delay) if delay else None
