"""
LLM client — calls the Gemini REST API via httpx (no heavy SDK dependency).

Exposes a single `complete(prompt: str) -> str` used by the healing engine tiers.
To swap provider later, only this file needs changing.

Gemini REST docs:
  POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_DEFAULT_TIMEOUT = 60  # seconds


def complete(prompt: str, temperature: float = 0.2) -> str:
    """Send a prompt to Gemini and return the text response."""
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file.")

    url = f"{_GEMINI_BASE}/{settings.gemini_model}:generateContent"
    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }

    response = httpx.post(
        url,
        params={"key": settings.gemini_api_key},
        json=payload,
        timeout=_DEFAULT_TIMEOUT,
    )
    response.raise_for_status()

    body = response.json()
    text: str = body["candidates"][0]["content"]["parts"][0]["text"]
    logger.debug("LLM response length=%d", len(text))
    return text
