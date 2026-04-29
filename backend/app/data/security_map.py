from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

COMMON_SUFFIXES = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "NEW", "COM"}


def normalize_ticker(ticker: str) -> str:
    return str(ticker or "").strip().upper()


def normalize_cusip(cusip: str) -> str:
    return str(cusip or "").strip().upper()


def normalize_issuer_name(name: str) -> str:
    text = re.sub(r"[^A-Za-z0-9 ]+", " ", str(name or "").upper())
    words = [word for word in text.split() if word]
    trimmed = [word for word in words if word not in COMMON_SUFFIXES]
    return " ".join(trimmed or words)


LOCAL_SECURITY_MAP: dict[str, dict[str, Any]] = {
    "NVDA": {
        "ticker": "NVDA",
        "cusip": "67066G104",
        "issuer_name": "NVIDIA CORPORATION",
        "aliases": ["NVIDIA CORP", "NVIDIA CORPORATION"],
        "exchange": "NASDAQ",
        "confidence_source": "local_static_map",
    },
    "TSLA": {
        "ticker": "TSLA",
        "cusip": "88160R101",
        "issuer_name": "TESLA, INC.",
        "aliases": ["TESLA INC", "TESLA, INC."],
        "exchange": "NASDAQ",
        "confidence_source": "local_static_map",
    },
    "AAPL": {
        "ticker": "AAPL",
        "cusip": "037833100",
        "issuer_name": "APPLE INC",
        "aliases": ["APPLE INC"],
        "exchange": "NASDAQ",
        "confidence_source": "local_static_map",
    },
    "AMZN": {
        "ticker": "AMZN",
        "cusip": "023135106",
        "issuer_name": "AMAZON.COM INC",
        "aliases": ["AMAZON COM INC", "AMAZON.COM INC"],
        "exchange": "NASDAQ",
        "confidence_source": "local_static_map",
    },
    "GOOGL": {
        "ticker": "GOOGL",
        "cusip": "02079K305",
        "issuer_name": "ALPHABET INC CL A",
        "aliases": ["ALPHABET INC", "ALPHABET INC CL A"],
        "exchange": "NASDAQ",
        "confidence_source": "local_static_map",
    },
    "GOOG": {
        "ticker": "GOOG",
        "cusip": "02079K107",
        "issuer_name": "ALPHABET INC CL C",
        "aliases": ["ALPHABET INC", "ALPHABET INC CL C"],
        "exchange": "NASDAQ",
        "confidence_source": "local_static_map",
    },
    "BAC": {
        "ticker": "BAC",
        "cusip": "060505104",
        "issuer_name": "BANK OF AMERICA CORP",
        "aliases": ["BANK AMERICA CORP", "BANK OF AMERICA CORP"],
        "exchange": "NYSE",
        "confidence_source": "local_static_map",
    },
    "KO": {
        "ticker": "KO",
        "cusip": "191216100",
        "issuer_name": "THE COCA-COLA COMPANY",
        "aliases": ["COCA COLA CO", "THE COCA-COLA COMPANY"],
        "exchange": "NYSE",
        "confidence_source": "local_static_map",
    },
    "CVX": {
        "ticker": "CVX",
        "cusip": "166764100",
        "issuer_name": "CHEVRON CORP",
        "aliases": ["CHEVRON CORP NEW", "CHEVRON CORP"],
        "exchange": "NYSE",
        "confidence_source": "local_static_map",
    },
    "AXP": {
        "ticker": "AXP",
        "cusip": "025816109",
        "issuer_name": "AMERICAN EXPRESS CO",
        "aliases": ["AMERICAN EXPRESS CO"],
        "exchange": "NYSE",
        "confidence_source": "local_static_map",
    },
    "MCO": {
        "ticker": "MCO",
        "cusip": "615369105",
        "issuer_name": "MOODYS CORP",
        "aliases": ["MOODYS CORP"],
        "exchange": "NYSE",
        "confidence_source": "local_static_map",
    },
    "OXY": {
        "ticker": "OXY",
        "cusip": "674599105",
        "issuer_name": "OCCIDENTAL PETE CORP",
        "aliases": ["OCCIDENTAL PETE CORP"],
        "exchange": "NYSE",
        "confidence_source": "local_static_map",
    },
    "KHC": {
        "ticker": "KHC",
        "cusip": "500754106",
        "issuer_name": "KRAFT HEINZ CO",
        "aliases": ["KRAFT HEINZ CO"],
        "exchange": "NASDAQ",
        "confidence_source": "local_static_map",
    },
}


def _copy_security(security: dict[str, Any] | None) -> dict[str, Any] | None:
    return deepcopy(security) if security else None


def get_security_by_ticker(ticker: str) -> dict[str, Any] | None:
    return _copy_security(LOCAL_SECURITY_MAP.get(normalize_ticker(ticker)))


def get_security_by_cusip(cusip: str) -> dict[str, Any] | None:
    normalized = normalize_cusip(cusip)
    for security in LOCAL_SECURITY_MAP.values():
        if security["cusip"] == normalized:
            return _copy_security(security)
    return None


def find_security_by_issuer_name(name: str) -> dict[str, Any] | None:
    normalized = normalize_issuer_name(name)
    if not normalized:
        return None
    matches: list[dict[str, Any]] = []
    for security in LOCAL_SECURITY_MAP.values():
        aliases = [security.get("issuer_name", ""), *(security.get("aliases") or [])]
        if normalized in {normalize_issuer_name(alias) for alias in aliases}:
            matches.append(security)
    if len(matches) == 1:
        return _copy_security(matches[0])
    return None


def resolve_security_identifier(ticker: str | None = None, cusip: str | None = None, issuer_name: str | None = None) -> dict[str, Any]:
    security = get_security_by_cusip(cusip or "") if cusip else None
    method = "cusip_exact" if security else ""
    if security is None and ticker:
        security = get_security_by_ticker(ticker)
        method = "ticker_exact" if security else ""
    if security is None and issuer_name:
        security = find_security_by_issuer_name(issuer_name)
        method = "issuer_alias_exact" if security else ""
    return {
        "matched": security is not None,
        "match_method": method or "none",
        "security": security,
        "local_security_map_used": security is not None,
    }
