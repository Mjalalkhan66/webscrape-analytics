"""Minimal, provider-agnostic LLM client (plain ``requests``, no vendor SDK).

Configuration (environment variables or Streamlit secrets):
    AI_PROVIDER   "anthropic" (default) or "openai" (any OpenAI-compatible API)
    AI_API_KEY    generic key; ANTHROPIC_API_KEY / OPENAI_API_KEY also accepted
    AI_MODEL      optional model override
    AI_BASE_URL   optional base URL for OpenAI-compatible providers
Keys are never logged or returned in error messages.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

import requests

from utils.logger import get_logger

logger = get_logger("ai")

DEFAULT_MODELS = {"anthropic": "claude-haiku-5-5", "openai": "gpt-4o-mini"}
DEFAULT_BASE_URLS = {"anthropic": "https://api.anthropic.com", "openai": "https://api.openai.com/v1"}


class AIError(Exception):
    """User-presentable AI failure."""


@dataclass(frozen=True)
class AIConfig:
    provider: str
    api_key: str
    model: str
    base_url: str
    timeout: float = 45.0

    @property
    def label(self) -> str:
        return f"{self.provider} · {self.model}"


def load_config(secrets: Mapping | None = None) -> AIConfig | None:
    """Return the AI configuration, or ``None`` when no API key is available."""

    def get(name: str) -> str:
        value = os.environ.get(name)
        if not value and secrets is not None:
            try:
                value = secrets.get(name)
            except Exception:
                value = None
        return str(value).strip() if value else ""

    provider = (get("AI_PROVIDER") or "anthropic").lower()
    if provider not in DEFAULT_MODELS:
        provider = "openai"
    key = get("AI_API_KEY") or get("ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY")
    if not key:
        return None
    return AIConfig(
        provider=provider,
        api_key=key,
        model=get("AI_MODEL") or DEFAULT_MODELS[provider],
        base_url=(get("AI_BASE_URL") or DEFAULT_BASE_URLS[provider]).rstrip("/"),
    )


def complete(config: AIConfig, system: str, prompt: str, max_tokens: int = 600) -> str:
    """Single-turn completion. Raises :class:`AIError` with a friendly message."""
    try:
        if config.provider == "anthropic":
            resp = requests.post(
                f"{config.base_url}/v1/messages",
                headers={"x-api-key": config.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": config.model, "max_tokens": max_tokens, "system": system,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=config.timeout,
            )
        else:
            resp = requests.post(
                f"{config.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {config.api_key}", "content-type": "application/json"},
                json={"model": config.model, "max_tokens": max_tokens,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
                timeout=config.timeout,
            )
    except requests.exceptions.Timeout as exc:
        raise AIError("The AI provider timed out. Please try again.") from exc
    except requests.exceptions.RequestException as exc:
        logger.warning("AI request failed: %s", type(exc).__name__)
        raise AIError("Could not reach the AI provider.") from exc

    if resp.status_code in (401, 403):
        raise AIError("The AI provider rejected the API key. Check your configuration.")
    if resp.status_code == 429:
        raise AIError("The AI provider rate limit was reached. Wait a moment and retry.")
    if resp.status_code >= 400:
        logger.warning("AI provider returned HTTP %s", resp.status_code)
        raise AIError(f"The AI provider returned an error (HTTP {resp.status_code}).")
    try:
        data = resp.json()
        if config.provider == "anthropic":
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        return data["choices"][0]["message"]["content"].strip()
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AIError("The AI provider returned an unexpected response.") from exc
