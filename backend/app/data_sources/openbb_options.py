from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlencode

import requests

from backend.app.data_sources.external_provider_base import ExternalProviderStatus
from backend.app.data_sources.provider_registry import require_provider_enabled
from backend.app.raw_store.openbb_options_cache import load_cached_openbb_options, save_openbb_options_snapshot

OPTIONS_LIMITATIONS = [
    "OpenBB/Stockgrid options blocks are supplemental research context only and may reflect hedging, spreads, or liquidity routing.",
    "Large option block sentiment is provider-normalized and requires manual review of contract, price action, and open interest context.",
]


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_number(value: Any) -> int | float | None:
    number = _safe_float(value)
    if number is None:
        return None
    if number.is_integer():
        return int(number)
    return number


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "results", "records", "items", "blocks"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _first_present(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record and record.get(name) is not None:
            return record.get(name)
    return None


def _source_date(records: list[dict[str, Any]]) -> str:
    dates: list[str] = []
    for record in records:
        for key in ("trade_date", "date", "timestamp", "created_at"):
            value = str(record.get(key) or "")[:10]
            if value:
                dates.append(value)
    return max(dates) if dates else ""


def disabled_openbb_options_activity(ticker: str, reason: str) -> dict[str, Any]:
    status = ExternalProviderStatus(
        provider="openbb_stockgrid",
        source_type="unknown",
        fallback_reason=reason,
        limitations=[reason[:180], *OPTIONS_LIMITATIONS],
        missing_data=["openbb_stockgrid_options"],
    ).to_data_source_status(freshness_window="openbb_options_cache")
    return {
        "ticker": ticker.strip().upper(),
        "available": False,
        "provider": "openbb_stockgrid",
        "source_type": "unknown",
        "source_status": status.model_dump(mode="json"),
        "options_activity": {},
        "normalized_blocks": [],
        "derived_metrics": {},
        "limitations": status.limitations,
        "missing_data": status.missing_data,
    }


def _normalize_block(record: dict[str, Any]) -> dict[str, Any]:
    premium = _safe_number(_first_present(record, "premium", "size", "value", "notional", "total_premium"))
    volume = _safe_number(_first_present(record, "volume", "option_volume", "contracts"))
    open_interest = _safe_number(_first_present(record, "open_interest", "openInterest", "oi"))
    option_type = str(_first_present(record, "option_type", "type", "put_call", "putCall") or "").strip().lower()
    sentiment_score = _safe_float(_first_present(record, "sentiment_score", "sentimentScore", "sentiment"))
    if sentiment_score is None:
        sentiment = str(record.get("sentiment") or "").lower()
        sentiment_score = 0.75 if sentiment in {"bullish", "positive"} else 0.25 if sentiment in {"bearish", "negative"} else 0.5 if sentiment else None
    return {
        "symbol": str(record.get("symbol") or record.get("ticker") or "").upper(),
        "trade_date": str(_first_present(record, "trade_date", "date", "timestamp") or "")[:10],
        "expiration_date": str(_first_present(record, "expiration", "expiration_date", "expiry") or "")[:10],
        "option_type": option_type or None,
        "order_type": str(_first_present(record, "order_type", "orderType", "trade_type", "type") or "").strip().lower() or None,
        "sentiment": record.get("sentiment"),
        "sentiment_score": round(sentiment_score, 4) if sentiment_score is not None else None,
        "premium": premium,
        "volume": volume,
        "open_interest": open_interest,
    }


def _options_payload_from_raw(ticker: str, raw_payload: Any, *, source_type: str, fetched_at: str | None = None, fallback_reason: str | None = None) -> dict[str, Any]:
    raw_records = _records(raw_payload)
    blocks = [_normalize_block(record) for record in raw_records]
    blocks = [block for block in blocks if any(value is not None and value != "" for value in block.values())]
    option_volume = sum(float(block.get("volume") or 0) for block in blocks)
    open_interest = sum(float(block.get("open_interest") or 0) for block in blocks)
    call_volume = sum(float(block.get("volume") or 0) for block in blocks if block.get("option_type") in {"call", "calls", "c"})
    put_volume = sum(float(block.get("volume") or 0) for block in blocks if block.get("option_type") in {"put", "puts", "p"})
    total_premium = sum(float(block.get("premium") or 0) for block in blocks)
    sentiment_values = [float(block["sentiment_score"]) for block in blocks if isinstance(block.get("sentiment_score"), (int, float))]
    source_date = _source_date(raw_records)
    volume_to_oi = round(option_volume / open_interest, 2) if open_interest else None
    call_put_ratio = round(call_volume / put_volume, 2) if put_volume else None
    weighted_sentiment = round(sum(sentiment_values) / len(sentiment_values), 4) if sentiment_values else None
    missing = []
    if not blocks:
        missing.append("openbb_stockgrid_options")
    if not option_volume:
        missing.append("option_volume")
    if not open_interest:
        missing.append("open_interest")
    limitations = [*OPTIONS_LIMITATIONS]
    if fallback_reason:
        limitations.append(fallback_reason[:180])
    status = ExternalProviderStatus(
        provider="openbb_stockgrid",
        source_type=source_type,  # type: ignore[arg-type]
        source_date=source_date,
        fetched_at=fetched_at,
        cache_hit=source_type == "cached_live",
        fallback_used=bool(fallback_reason),
        fallback_reason=fallback_reason,
        limitations=limitations,
        missing_data=missing,
    ).to_data_source_status(freshness_window="openbb_options_cache")
    options_activity = {
        "option_volume": int(option_volume) if option_volume.is_integer() else option_volume,
        "open_interest": int(open_interest) if open_interest.is_integer() else open_interest,
        "call_put_ratio": call_put_ratio,
        "implied_volatility": None,
        "expiration_date": max((block.get("expiration_date") or "" for block in blocks), default="") or None,
        "abnormal_volume_ratio": volume_to_oi,
        "direction_consistent_with_price_action": weighted_sentiment is not None and weighted_sentiment >= 0.6,
        "provider": "openbb_stockgrid",
        "source_status": status.model_dump(mode="json"),
        "large_block_count": len(blocks),
        "total_premium": int(total_premium) if total_premium.is_integer() else total_premium,
        "sentiment_score": weighted_sentiment,
    }
    return {
        "ticker": ticker.strip().upper(),
        "available": bool(blocks),
        "provider": "openbb_stockgrid",
        "source_type": source_type,
        "source_status": status.model_dump(mode="json"),
        "options_activity": options_activity if blocks else {},
        "normalized_blocks": blocks[:25],
        "derived_metrics": {
            "large_block_count": len(blocks),
            "total_premium": int(total_premium) if total_premium.is_integer() else total_premium,
            "weighted_sentiment_score": weighted_sentiment,
            "call_volume": int(call_volume) if call_volume.is_integer() else call_volume,
            "put_volume": int(put_volume) if put_volume.is_integer() else put_volume,
        },
        "limitations": limitations,
        "missing_data": missing,
    }


def _fallback_from_cache(ticker: str, reason: str, ttl_days: int) -> dict[str, Any] | None:
    cached = load_cached_openbb_options(ticker, ttl_days=ttl_days)
    if not cached:
        return None
    return _options_payload_from_raw(
        ticker,
        cached.get("payload", cached),
        source_type="cached_live",
        fetched_at=cached.get("fetched_at"),
        fallback_reason="OpenBB Stockgrid live fetch failed; using cached options snapshot.",
    )


def fetch_openbb_options_activity(ticker: str, http_get: Callable[..., Any] | None = None) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    try:
        provider_config = require_provider_enabled("openbb")
    except RuntimeError as exc:
        return disabled_openbb_options_activity(normalized_ticker, str(exc))
    getter = http_get or requests.get
    base_url = (provider_config.base_url or "http://127.0.0.1:6900").rstrip("/")
    query = urlencode({"symbol": normalized_ticker, "provider": "stockgrid"})
    # OpenBB sidecar deployments can route this path to the configured Stockgrid provider.
    url = f"{base_url}/api/v1/derivatives/options/unusual?{query}"
    try:
        response = getter(url, timeout=15)
        status_code = int(getattr(response, "status_code", 200) or 200)
        if status_code == 429:
            cached = _fallback_from_cache(normalized_ticker, "OpenBB Stockgrid provider was rate limited.", provider_config.cache_ttl_days)
            if cached:
                return cached
            payload = disabled_openbb_options_activity(normalized_ticker, "OpenBB Stockgrid provider was rate limited.")
            payload["source_type"] = "fallback"
            payload["source_status"]["source_type"] = "fallback"
            payload["source_status"]["fallback_used"] = True
            return payload
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        raw_payload = response.json()
    except Exception as exc:  # noqa: BLE001 - provider boundary must degrade safely.
        safe_reason = str(exc)[:180]
        cached = _fallback_from_cache(normalized_ticker, safe_reason, provider_config.cache_ttl_days)
        if cached:
            return cached
        payload = disabled_openbb_options_activity(normalized_ticker, "OpenBB Stockgrid live fetch failed.")
        payload["source_type"] = "fallback"
        payload["source_status"]["source_type"] = "fallback"
        payload["source_status"]["fallback_used"] = True
        payload["source_status"]["fallback_reason"] = "OpenBB Stockgrid live fetch failed."
        payload["source_status"]["limitations"].append(safe_reason)
        return payload
    payload = _options_payload_from_raw(normalized_ticker, raw_payload, source_type="live", fetched_at=datetime.now(timezone.utc).isoformat())
    if payload["available"]:
        save_openbb_options_snapshot(normalized_ticker, raw_payload, fetched_at=datetime.now(timezone.utc))
    return payload


def get_openbb_options_activity(ticker: str) -> dict[str, Any]:
    return fetch_openbb_options_activity(ticker)
