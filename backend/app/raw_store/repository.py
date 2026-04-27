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
from backend.app.utils.freshness import (
    DAILY_RATE_FRESHNESS_WINDOW,
    DERIVED_FRED_FRESHNESS_WINDOW,
    MONTHLY_MACRO_FRESHNESS_WINDOW,
    build_source_status,
)


INDEX_SYMBOLS = ["SPY", "QQQ"]
VIX_SYMBOL = "^VIX"


def _cache_dir() -> Path:
    path = config.MARKET_DATA_CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _macro_cache_dir() -> Path:
    path = config.MACRO_DATA_CACHE_DIR
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


def _mock_macro_snapshot(scenario: str = "normal", reason: str | None = None) -> dict[str, Any]:
    snapshot = deepcopy(MOCK_MACRO_SCENARIOS.get(scenario, MOCK_MACRO_SCENARIOS["normal"]))
    snapshot["source_type"] = "fallback" if reason else "mock"
    snapshot["provider"] = "mock"
    snapshot["source"] = ["phase5_mock_macro_dataset"]
    snapshot["source_date"] = snapshot.get("source_date", "2026-04-24")
    snapshot.setdefault("limitations", []).append("Mock macro snapshot is used when live macro data is disabled or unavailable.")
    snapshot.setdefault("missing_data", [])
    if reason:
        snapshot["fallback_used"] = True
        snapshot["fallback_reason"] = reason
        snapshot["missing_data"].append("live FRED macro data")
        snapshot["limitations"].append("Live macro data unavailable; mock fallback used.")
    snapshot["source_status"] = build_source_status(snapshot, freshness_window="macro_release_schedule").model_dump(mode="json")
    return snapshot


def write_market_data(ticker: str, data: dict[str, Any]) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    payload = deepcopy(data)
    payload["ticker"] = normalized_ticker
    payload["cached_at"] = datetime.now(timezone.utc).isoformat()
    target = _cache_dir() / f"{_cache_key(normalized_ticker)}.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def write_macro_data(data: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(data)
    payload["cached_at"] = datetime.now(timezone.utc).isoformat()
    target = _macro_cache_dir() / "latest.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _fred_series_summary(series_payload: dict[str, Any], recent_limit: int = 12, fetched_at: str | None = None) -> dict[str, Any]:
    observations = list(series_payload.get("observations", []) or [])
    latest = observations[-1] if observations else {}
    previous = observations[-2] if len(observations) >= 2 else {}
    series_id = str(series_payload.get("series_id") or "")
    freshness_window = DAILY_RATE_FRESHNESS_WINDOW if series_id in {"DGS10", "DGS2"} else MONTHLY_MACRO_FRESHNESS_WINDOW
    raw_status = deepcopy(series_payload.get("source_status")) if isinstance(series_payload.get("source_status"), dict) else None
    if raw_status is not None and fetched_at and not raw_status.get("fetched_at"):
        raw_status["fetched_at"] = fetched_at
    source_status = raw_status or build_source_status(
        {
            "source_type": "live",
            "provider": "FRED",
            "source": ["FRED"],
            "source_date": latest.get("date") or series_payload.get("source_date", ""),
            "fetched_at": fetched_at or series_payload.get("fetched_at"),
            "limitations": series_payload.get("limitations", []),
            "missing_data": series_payload.get("missing_data", []),
        },
        freshness_window=freshness_window,
    ).model_dump(mode="json")
    return {
        "series_id": series_id,
        "latest_date": latest.get("date") or series_payload.get("latest_date") or series_payload.get("source_date", ""),
        "latest_value": latest.get("value") if latest else series_payload.get("latest_value"),
        "previous_value": previous.get("value") if previous else series_payload.get("previous_value"),
        "recent_observations": observations[-recent_limit:],
        "source_status": source_status,
        "limitations": list(series_payload.get("limitations", [])),
        "missing_data": list(series_payload.get("missing_data", [])),
    }


def _compact_fred_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw_series = snapshot.get("raw_series", {}) or {}
    raw_summaries = {name: _fred_series_summary(payload, fetched_at=snapshot.get("fetched_at")) for name, payload in raw_series.items()}
    is_fresh = all(summary.get("source_status", {}).get("is_fresh") for summary in raw_summaries.values())
    source_status = build_source_status(
        {
            "source_type": "derived",
            "provider": "derived_from_FRED",
            "source": ["FRED"],
            "source_date": snapshot.get("source_date", ""),
            "fetched_at": snapshot.get("fetched_at"),
            "is_fresh": is_fresh,
            "limitations": snapshot.get("limitations", []),
            "missing_data": snapshot.get("missing_data", []),
        },
        freshness_window=DERIVED_FRED_FRESHNESS_WINDOW,
    ).model_dump(mode="json")
    return {
        "source_type": snapshot.get("source_type", "live"),
        "provider": snapshot.get("provider", "FRED"),
        "source": snapshot.get("source", ["FRED"]),
        "source_date": snapshot.get("source_date", ""),
        "fetched_at": snapshot.get("fetched_at"),
        "indicators": deepcopy(snapshot.get("indicators", {})),
        "raw_series": raw_summaries,
        "source_status": source_status,
        "limitations": list(snapshot.get("limitations", [])),
        "missing_data": list(snapshot.get("missing_data", [])),
    }


def _fred_component_status(
    series_payload: dict[str, Any],
    *,
    source_type: str = "live",
    provider: str = "FRED",
    freshness_window: str | None = None,
    is_fresh: bool | None = None,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    series_id = str(series_payload.get("series_id") or "")
    window = freshness_window or (DAILY_RATE_FRESHNESS_WINDOW if series_id in {"DGS10", "DGS2"} else MONTHLY_MACRO_FRESHNESS_WINDOW)
    payload = {
        "source_type": source_type,
        "provider": provider,
        "source": [series_id] if provider == "FRED" and series_id else [provider],
        "source_date": series_payload.get("source_date", ""),
        "fetched_at": fetched_at or series_payload.get("fetched_at"),
        "limitations": series_payload.get("limitations", []),
        "missing_data": series_payload.get("missing_data", []),
    }
    if is_fresh is not None:
        payload["is_fresh"] = is_fresh
    return build_source_status(payload, freshness_window=window).model_dump(mode="json")


def _derived_fred_status(
    input_statuses: list[tuple[str, dict[str, Any]]],
    *,
    source: list[str],
    fetched_at: str | None,
    limitations: list[str],
    missing_data: list[str] | None = None,
) -> dict[str, Any]:
    stale_inputs = [
        series_id
        for series_id, status in input_statuses
        if status and status.get("is_fresh") is False
    ]
    statuses = [status for _, status in input_statuses]
    input_source_dates = [status.get("source_date") for status in statuses if status.get("source_date")]
    source_date = min(input_source_dates, default="")
    derived_missing = list(missing_data or [])
    derived_limitations = list(limitations)
    for stale_input in stale_inputs:
        derived_missing.append(f"stale input: {stale_input}")
    return build_source_status(
        {
            "source_type": "derived",
            "provider": "derived_from_FRED",
            "source": source,
            "source_date": source_date,
            "fetched_at": fetched_at,
            "is_fresh": not stale_inputs and all(status.get("is_fresh") for status in statuses),
            "limitations": derived_limitations,
            "missing_data": derived_missing,
        },
        freshness_window=DERIVED_FRED_FRESHNESS_WINDOW,
    ).model_dump(mode="json")


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


def get_macro_snapshot(use_live: bool | None = None, scenario: str = "normal") -> dict[str, Any]:
    enabled = config.USE_LIVE_MACRO_DATA if use_live is None else use_live
    if not enabled:
        return _mock_macro_snapshot(scenario)
    if config.MACRO_DATA_PROVIDER != "fred":
        return _mock_macro_snapshot(scenario, f"unsupported macro data provider: {config.MACRO_DATA_PROVIDER}")
    if not config.FRED_API_KEY:
        return _mock_macro_snapshot(scenario, "FRED_API_KEY is missing")
    try:
        from backend.app.data_sources.live_macro_fred import fetch_macro_snapshot

        snapshot = fetch_macro_snapshot()
        snapshot["source_status"] = build_source_status(snapshot, freshness_window="macro_release_schedule").model_dump(mode="json")
        return write_macro_data(snapshot)
    except Exception as exc:
        safe_reason = str(exc).splitlines()[0][:180] or "live FRED macro fetch failed"
        return _mock_macro_snapshot(scenario, safe_reason)


def read_macro_data(scenario: str = "normal", use_live: bool | None = None) -> dict[str, Any]:
    snapshot = get_macro_snapshot(use_live=use_live, scenario=scenario)
    if snapshot.get("source_type") != "live":
        return snapshot

    mock_context = _mock_macro_snapshot(scenario)
    indicators = snapshot.get("indicators", {})
    merged = {**mock_context, **indicators}
    merged["fed_funds_rate"] = indicators.get("fed_funds_rate")
    merged["ten_year_yield"] = indicators.get("ten_year_yield")
    merged["two_year_yield"] = indicators.get("two_year_yield")
    merged["source_type"] = "live"
    merged["provider"] = "FRED"
    merged["source"] = ["FRED", "phase5_mock_macro_dataset"]
    merged["source_date"] = snapshot.get("source_date", mock_context["source_date"])
    merged["fetched_at"] = snapshot.get("fetched_at")
    merged["raw_fred_snapshot"] = _compact_fred_snapshot(snapshot)
    merged["limitations"] = sorted(
        set(
            [
                *snapshot.get("limitations", []),
                "ISM Manufacturing PMI, DXY trend, gold trend, oil trend, Fear & Greed, and equity drawdown context remain mock in Phase 9.",
            ]
        )
    )
    merged["missing_data"] = sorted(set(snapshot.get("missing_data", [])))
    raw_series = snapshot.get("raw_series", {}) or {}
    fetched_at = snapshot.get("fetched_at")
    fred_limitations = snapshot.get("limitations", [])
    fred_missing = snapshot.get("missing_data", [])
    fed_status = _fred_component_status(raw_series.get("fed_funds_rate", {}), fetched_at=fetched_at)
    ten_year_status = _fred_component_status(raw_series.get("ten_year_yield", {}), fetched_at=fetched_at)
    two_year_status = _fred_component_status(raw_series.get("two_year_yield", {}), fetched_at=fetched_at)
    cpi_status = _fred_component_status(raw_series.get("cpi", {}), fetched_at=fetched_at)
    ppi_status = _fred_component_status(raw_series.get("ppi", {}), fetched_at=fetched_at)
    unemployment_status = _fred_component_status(raw_series.get("unemployment_rate", {}), fetched_at=fetched_at)
    spread_status = _derived_fred_status(
        [("DGS10", ten_year_status), ("DGS2", two_year_status)],
        source=["DGS10", "DGS2"],
        fetched_at=fetched_at,
        limitations=fred_limitations,
        missing_data=fred_missing,
    )
    fed_trend_status = _derived_fred_status(
        [("FEDFUNDS", fed_status)],
        source=["FEDFUNDS"],
        fetched_at=fetched_at,
        limitations=fred_limitations,
        missing_data=fred_missing,
    )
    cpi_yoy_status = _derived_fred_status(
        [("CPIAUCSL", cpi_status)],
        source=["CPIAUCSL"],
        fetched_at=fetched_at,
        limitations=fred_limitations,
        missing_data=fred_missing,
    )
    ppi_yoy_status = _derived_fred_status(
        [("PPIACO", ppi_status)],
        source=["PPIACO"],
        fetched_at=fetched_at,
        limitations=fred_limitations,
        missing_data=fred_missing,
    )
    unemployment_trend_status = _derived_fred_status(
        [("UNRATE", unemployment_status)],
        source=["UNRATE"],
        fetched_at=fetched_at,
        limitations=fred_limitations,
        missing_data=fred_missing,
    )
    mock_status = {
        "source_type": "mock",
        "provider": "phase5_mock_macro_dataset",
        "source": ["phase5_mock_macro_dataset"],
        "source_date": mock_context["source_date"],
        "limitations": ["Phase 9 keeps this macro field on mock data."],
        "missing_data": [],
    }
    merged["component_source_status"] = {
        "fed_funds_rate": fed_status,
        "fed_policy_trend": fed_trend_status,
        "ten_year_yield": ten_year_status,
        "two_year_yield": two_year_status,
        "ten_year_minus_two_year_spread_bps": spread_status,
        "cpi_yoy": cpi_yoy_status,
        "ppi_yoy": ppi_yoy_status,
        "unemployment_rate": unemployment_status,
        "unemployment_trend": unemployment_trend_status,
        "ism_manufacturing_pmi": mock_status,
        "dxy_trend": mock_status,
        "gold_trend": mock_status,
        "oil_trend": mock_status,
        "fear_greed": mock_status,
        "vix": mock_status,
        "equity_drawdown": mock_status,
        "gain_from_recent_trough": mock_status,
    }
    merged["source_status"] = build_source_status(
        {
            "source_type": "derived",
            "provider": "mixed_FRED_and_mock_macro",
            "source_date": merged["source_date"],
            "fetched_at": merged.get("fetched_at"),
            "is_fresh": all(
                status.get("is_fresh")
                for status in [fed_status, ten_year_status, two_year_status, cpi_status, ppi_status, unemployment_status]
            ),
            "limitations": merged["limitations"],
            "missing_data": merged["missing_data"],
        },
        freshness_window=DERIVED_FRED_FRESHNESS_WINDOW,
    ).model_dump(mode="json")
    return merged


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
