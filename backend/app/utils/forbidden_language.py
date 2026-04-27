from __future__ import annotations

import re
from typing import Any

FORBIDDEN_PATTERNS = {
    "buy": re.compile(r"\bbuy\b", re.IGNORECASE),
    "sell": re.compile(r"\bsell\b", re.IGNORECASE),
    "hold": re.compile(r"\bhold\b", re.IGNORECASE),
    "liquidate": re.compile(r"\bliquidate\b", re.IGNORECASE),
    "enter": re.compile(r"\benter\b", re.IGNORECASE),
    "exit": re.compile(r"\bexit\b", re.IGNORECASE),
    "exit position": re.compile(r"\bexit\s+position\b", re.IGNORECASE),
    "enter position": re.compile(r"\benter\s+position\b", re.IGNORECASE),
    "must invest": re.compile(r"\bmust\s+invest\b", re.IGNORECASE),
    "買進": re.compile("買進"),
    "賣出": re.compile("賣出"),
    "持有": re.compile("持有"),
    "出清": re.compile("出清"),
    "進場": re.compile("進場"),
    "離場": re.compile("離場"),
    "必買": re.compile("必買"),
}


def iter_string_values(payload: Any):
    if isinstance(payload, str):
        yield payload
    elif isinstance(payload, dict):
        for value in payload.values():
            yield from iter_string_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from iter_string_values(item)


def detect_forbidden_language(payload: Any) -> list[str]:
    detected: set[str] = set()
    for value in iter_string_values(payload):
        for label, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(value):
                detected.add(label)
    return sorted(detected)


def has_forbidden_language(payload: Any) -> bool:
    return bool(detect_forbidden_language(payload))
