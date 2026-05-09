from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


SECRET_KEY_MARKERS = (
    "FRED_API_KEY",
    "SEC_EDGAR_USER_AGENT",
    "API_KEY",
    "APIKEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
)

URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
WINDOWS_PATH_RE = re.compile(r"\b[A-Z]:\\[^\s\"'<>]+", re.IGNORECASE)


def _env_secret_values() -> set[str]:
    values: set[str] = set()
    for key, value in os.environ.items():
        if not value or len(value) < 6:
            continue
        if any(marker.lower() in key.lower() for marker in SECRET_KEY_MARKERS):
            values.add(value)
    return values


def _redact_string(value: str) -> str:
    text = value
    for secret in _env_secret_values():
        text = text.replace(secret, "[redacted_secret]")
    text = URL_RE.sub("[redacted_url]", text)
    text = EMAIL_RE.sub("[redacted_email]", text)
    text = WINDOWS_PATH_RE.sub("[redacted_path]", text)
    try:
        cwd = str(Path.cwd())
        if cwd:
            text = text.replace(cwd, "[redacted_path]")
    except OSError:
        pass
    for marker in SECRET_KEY_MARKERS:
        text = re.sub(marker, "[redacted_secret_name]", text, flags=re.IGNORECASE)
    return text


def redact_sensitive_fields(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, list):
        return [redact_sensitive_fields(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(marker.lower() in lowered for marker in SECRET_KEY_MARKERS):
                redacted[key_text] = "[redacted_secret]"
            elif lowered in {"request_url", "provider_url", "raw_provider_url", "url"}:
                redacted[key_text] = "[redacted_url]"
            elif lowered.endswith("_path") or lowered in {"path", "file", "filename"}:
                redacted[key_text] = redact_sensitive_fields(child)
            else:
                redacted[key_text] = redact_sensitive_fields(child)
        return redacted
    return value
