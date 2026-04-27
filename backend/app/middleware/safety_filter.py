from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


class SafetyViolationError(ValueError):
    """Raised when an API response contains direct trading instructions."""


PROHIBITED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("strong buy", re.compile(r"\bstrong\s+buy\b", re.IGNORECASE)),
    ("buy now", re.compile(r"\bbuy\s+now\b", re.IGNORECASE)),
    ("must buy", re.compile(r"\bmust\s+buy\b", re.IGNORECASE)),
    ("sell now", re.compile(r"\bsell\s+now\b", re.IGNORECASE)),
    ("must sell", re.compile(r"\bmust\s+sell\b", re.IGNORECASE)),
    ("liquidate", re.compile(r"\bliquidate\b", re.IGNORECASE)),
    ("exit position", re.compile(r"\bexit\s+(?:the\s+)?position\b", re.IGNORECASE)),
    ("enter position", re.compile(r"\benter\s+(?:the\s+)?position\b", re.IGNORECASE)),
    ("買進", re.compile("買進")),
    ("賣出", re.compile("賣出")),
    ("持有", re.compile("持有")),
    ("出清", re.compile("出清")),
    ("進場", re.compile("進場")),
    ("離場", re.compile("離場")),
    ("必買", re.compile("必買")),
)


def _iter_string_values(payload: Any) -> Iterable[str]:
    if isinstance(payload, str):
        yield payload
    elif isinstance(payload, dict):
        for value in payload.values():
            yield from _iter_string_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_string_values(item)


def check_safety(response_dict: dict) -> None:
    violations: set[str] = set()
    for value in _iter_string_values(response_dict):
        for label, pattern in PROHIBITED_PATTERNS:
            if pattern.search(value):
                violations.add(label)
    if violations:
        joined = ", ".join(sorted(violations))
        raise SafetyViolationError(f"Unsafe investment instruction phrase detected: {joined}")
