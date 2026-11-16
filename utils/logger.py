"""Logging setup. Logs go to stderr (and optionally to a file via WEBSCRAPE_LOG_FILE)."""
from __future__ import annotations

import logging
import os
import sys

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    level = os.environ.get("WEBSCRAPE_LOG_LEVEL", "INFO").upper()
    root = logging.getLogger("webscrape")
    root.setLevel(level)
    root.propagate = False
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    root.addHandler(stream)
    log_file = os.environ.get("WEBSCRAPE_LOG_FILE")
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(fmt)
            root.addHandler(file_handler)
        except OSError:
            root.warning("Could not open log file %s; logging to stderr only", log_file)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger (``webscrape.<name>``)."""
    _configure()
    return logging.getLogger(f"webscrape.{name}")
