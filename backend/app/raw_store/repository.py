from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app import config
from backend.app.data_sources.mock_crisis import MOCK_CRISIS_SCENARIOS
from backend.app.data_sources.mock_data import MARKET_SNAPSHOTS, MOCK_SMART_MONEY_SUMMARY, STOCK_FIXTURES, THEMES
from backend.app.data_sources.mock_macro import MOCK_MACRO_SCENARIOS
from backend.app.features.market_features import build_market_snapshot_features
from backend.app.utils.freshness import build_source_status


INDEX_SYMBOLS = ["SPY", "QQQ"]
VIX_SYMBOL = "^VIX"


def _cache_dir() -> Path:
    path = config.MARKET_DATA_CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_key(ticker: str) -> str:
    return ticker.replace("^", "index_").replace("/", "_").upper()


def _mock_snapshot(scenario: str = "normal", reason: str | None = None) -> dict[str, Any]:
    snapshot = deepcopy(MARKET_SNAPSHOTS.get(scenario, MARKET_SNAPSHOTS["normal"]))
    snapshot["source_type"] = "fallback" if reason else "mock"
    snapshot["source"] = ["phase1_mock_dataset"]
    snapshot["source_date"] = snapshot.get("source_date", "2026-04-24")
    snapshot.setdefault("limitations", []).append("Mock market snapshot is used when live market data is disabled or unavailable.")
    snapshot.setdefault("missing_data", [])
    if reason:
        snapshot["fallback_used"] = True
        snapshot["fallback_reason"] = reason
        snapshot["provider"] = "mock"
        snapshot["missing_data"].append("live market price data")
        snapshot["limitations"].append("Live market data unavailable; mock fallback used.")
    snapshot["source_status"] = build_source_status(snapshot).model_dump(mode="json")
    return snapshot


def write_market_data(ticker: str, data: dict[str, Any]) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    payload = deepcopy(data)
    payload["ticker"] = normalized_ticker
    payload["cached_at"] = datetime.now(timezone.utc).isoformat()
    target = _cache_dir() / f"{_cache_key(normalized_ticker)}.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def get_market_data(ticker: str, use_live: bool | None = None, period: str = "1y", interval: str = "1d") -> dict[str, Any]:
    enabled = config.USE_LIVE_MARKET_DATA if use_live is None else use_live
    normalized_ticker = ticker.strip().upper()
    if not enabled:
        payload = {
            "ticker": normalized_ticker,
            "source_type": "mock",
            "provider": "mock",
            "source": "phase1_mock_dataset",
            "source_date": "2026-04-24",
            "period": period,
            "interval": interval,
            "rows": [],
            "limitations": ["Mock mode is active; live market price adapter was not called."],
            "missing_data": ["live market price data"],
        }
        payload["source_status"] = build_source_status(payload).model_dump(mode="json")
        return payload
    if config.MARKET_DATA_PROVIDER != "yfinance":
        payload = {
            "ticker": normalized_ticker,
            "source_type": "fallback",
            "provider": "mock",
            "source": "phase1_mock_dataset",
            "source_date": "2026-04-24",
            "period": period,
            "interval": interval,
            "rows": [],
            "limitations": [f"Unsupported market data provider: {config.MARKET_DATA_PROVIDER}."],
            "missing_data": ["live market price data"],
            "fallback_used": True,
            "fallback_reason": "unsupported market data provider",
        }
        payload["source_status"] = build_source_status(payload).model_dump(mode="json")
        return payload
    try:
        from backend.app.data_sources.live_market_prices import fetch_ohlcv

        snapshot = fetch_ohlcv(normalized_ticker, period=period, interval=interval)
        snapshot["source_type"] = "live"
        snapshot["provider"] = "yfinance"
        snapshot["source_status"] = build_source_status(snapshot).model_dump(mode="json")
        return write_market_data(normalized_ticker, snapshot)
    except Exception as exc:
        safe_reason = str(exc).splitlines()[0][:180] or "live market price fetch failed"
        payload = {
            "ticker": normalized_ticker,
            "source_type": "fallback",
            "provider": "mock",
            "source": "phase1_mock_dataset",
            "source_date": "2026-04-24",
            "period": period,
            "interval": interval,
            "rows": [],
            "limitations": ["Live market data unavailable; mock fallback used."],
            "missing_data": ["live market price data"],
            "fallback_used": True,
            "fallback_reason": safe_reason,
        }
        payload["source_status"] = build_source_status(payload).model_dump(mode="json")
        return payload


def get_index_market_data(use_live: bool | None = None) -> dict[str, dict[str, Any]]:
    return {symbol: get_market_data(symbol, use_live=use_live) for symbol in INDEX_SYMBOLS}


def get_vix_data(use_live: bool | None = None) -> dict[str, Any]:
    return get_market_data(VIX_SYMBOL, use_live=use_live)


def read_market_data(scenario: str = "normal", use_live: bool | None = None) -> dict[str, Any]:
    enabled = config.USE_LIVE_MARKET_DATA if use_live is None else use_live
    if not enabled:
        return _mock_snapshot(scenario)

    index_data = get_index_market_data(use_live=True)
    vix_data = get_vix_data(use_live=True)
    if any(snapshot.get("source_type") != "live" for snapshot in [*index_data.values(), vix_data]):
        errors = [
            snapshot.get("error")
            for snapshot in [*index_data.values(), vix_data]
            if snapshot.get("error")
        ]
        return _mock_snapshot(scenario, "; ".join(errors) if errors else "live market price fetch failed")

    mock_context = _mock_snapshot(scenario)
    live_features = build_market_snapshot_features(index_data["SPY"], index_data["QQQ"], vix_data)
    merged = {**mock_context, **live_features}
    merged["source_type"] = "live"
    merged["provider"] = "yfinance"
    merged["source_status"] = build_source_status(merged).model_dump(mode="json")
    return merged


def read_macro_data(scenario: str = "normal") -> dict[str, Any]:
    return deepcopy(MOCK_MACRO_SCENARIOS.get(scenario, MOCK_MACRO_SCENARIOS["normal"]))


def read_company_fundamentals(ticker: str = "NVDA") -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    fixture = STOCK_FIXTURES.get(normalized_ticker, STOCK_FIXTURES["NVDA"])
    return deepcopy(fixture)


def read_sec_filings(ticker: str = "NVDA") -> dict[str, Any]:
    fixture = read_company_fundamentals(ticker)
    smart_money = fixture.get("smart_money", MOCK_SMART_MONEY_SUMMARY)
    return deepcopy(
        {
            "institutional_13f": smart_money.get("institutional_13f", {}),
            "form4_transactions": smart_money.get("form4_transactions", []),
            "crisis_scenarios": MOCK_CRISIS_SCENARIOS,
        }
    )


def read_news_mentions() -> list[dict[str, Any]]:
    return deepcopy(
        [
            {
                "theme": theme["theme"],
                "theme_mentions_7d": theme["theme_mentions_7d"],
                "theme_mentions_30d_avg": theme["theme_mentions_30d_avg"],
            }
            for theme in THEMES
        ]
    )


def read_theme_data() -> list[dict[str, Any]]:
    return deepcopy(THEMES)
