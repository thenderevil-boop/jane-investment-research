from __future__ import annotations

import json
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.app import config
from backend.app.data.price_reference import warm_price_reference_cache as _warm_price_reference_cache
from backend.app.data.security_map import resolve_security_identifier
from backend.app.data_sources.mock_crisis import MOCK_CRISIS_SCENARIOS
from backend.app.data_sources.mock_data import MARKET_SNAPSHOTS, MOCK_SMART_MONEY_SUMMARY, STOCK_FIXTURES, THEMES
from backend.app.data_sources.mock_macro import MOCK_MACRO_SCENARIOS
from backend.app.engines.sec_13f_aggregation import aggregate_13f_holdings, compare_13f_quarter_over_quarter, summarize_13f_portfolio
from backend.app.engines.sec_13f_target_matching import match_13f_targets, normalize_target_security_map
from backend.app.features.market_features import build_market_snapshot_features
from backend.app.utils.freshness import (
    DAILY_RATE_FRESHNESS_WINDOW,
    DERIVED_FRED_FRESHNESS_WINDOW,
    FORM4_FRESHNESS_WINDOW,
    MONTHLY_MACRO_FRESHNESS_WINDOW,
    THIRTEEN_F_FRESHNESS_WINDOW,
    build_source_status,
)
from backend.app.utils.performance import add_timing, increment_metric


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


def _sec_cache_dir() -> Path:
    path = config.SEC_FORM4_CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sec_13f_cache_dir() -> Path:
    path = config.SEC_13F_CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_key(ticker: str) -> str:
    return ticker.replace("^", "index_").replace("/", "_").upper()


def _manager_cache_key(manager_or_cik: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in manager_or_cik.strip().lower()).strip("_") or "unknown_manager"


def _not_future_iso_date(value: Any, fallback: str = "2026-04-24") -> str:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return fallback
    today = datetime.now(timezone.utc).date()
    if parsed > today:
        return today.isoformat()
    return parsed.isoformat()


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


def _mock_form4_snapshot(ticker: str = "NVDA", reason: str | None = None) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    fixture = read_company_fundamentals(normalized_ticker)
    transactions = deepcopy(fixture.get("smart_money", MOCK_SMART_MONEY_SUMMARY).get("form4_transactions", []))
    source_date = max((item.get("filing_date", "") for item in transactions), default="2026-04-24")
    source_type = "fallback" if reason else "mock"
    limitations = ["Mock Form 4 fixture is used when live SEC Form 4 is disabled or unavailable."]
    missing_data = ["live SEC Form 4 data"]
    payload: dict[str, Any] = {
        "ticker": normalized_ticker,
        "lookback_days": 180,
        "transactions": transactions,
        "source_type": source_type,
        "provider": "mock",
        "source": ["phase1_mock_dataset"],
        "source_date": source_date,
        "limitations": limitations,
        "missing_data": missing_data,
    }
    if reason:
        payload["fallback_used"] = True
        payload["fallback_reason"] = reason
        payload["limitations"].append("Live SEC Form 4 data unavailable; mock fallback used.")
    payload["source_status"] = build_source_status(payload, freshness_window=FORM4_FRESHNESS_WINDOW).model_dump(mode="json")
    for transaction in payload["transactions"]:
        transaction.setdefault("ticker", normalized_ticker)
        transaction.setdefault("transaction_category", transaction.get("transaction_type", "other"))
        transaction.setdefault("source", ["phase1_mock_dataset"])
        transaction.setdefault("source_date", transaction.get("filing_date", source_date))
        transaction.setdefault("limitations", [])
        transaction.setdefault("missing_data", [])
        transaction["source_status"] = payload["source_status"]
    return payload


def _mock_13f_snapshot(manager_or_cik: str = "mock_manager", ticker: str = "NVDA", reason: str | None = None) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    fixture = read_company_fundamentals(normalized_ticker)
    raw = deepcopy(fixture.get("smart_money", MOCK_SMART_MONEY_SUMMARY).get("institutional_13f", {}))
    source_type = "fallback" if reason else "mock"
    safe_filing_date = _not_future_iso_date(raw.get("filing_date"), fallback="2026-04-24")
    holding = {
        "manager_cik": "",
        "accession_number": "mock-13f",
        "filing_date": safe_filing_date,
        "report_date": raw.get("quarter", "2026-Q1"),
        "issuer_name": raw.get("issuer_name"),
        "title_of_class": "COM",
        "cusip": raw.get("cusip"),
        "reported_value_raw": raw.get("market_value"),
        "reported_value_unit": "as_reported",
        "value_usd": raw.get("market_value"),
        "value_unit_confidence": "low",
        "value_normalization_note": "Mock 13F value preserved as reported.",
        "shares_or_principal_amount": raw.get("shares"),
        "share_type": "SH",
        "put_call": "",
        "investment_discretion": "",
        "other_manager": "",
        "voting_authority_sole": None,
        "voting_authority_shared": None,
        "voting_authority_none": None,
        "source": ["phase1_mock_dataset"],
        "source_status": {},
    }
    payload: dict[str, Any] = {
        "manager": manager_or_cik,
        "manager_cik": "",
        "lookback_quarters": config.SEC_13F_LOOKBACK_QUARTERS,
        "filings": [
            {
                "accession_number": "mock-13f",
                "filing_date": safe_filing_date,
                "report_date": raw.get("quarter", "2026-Q1"),
                "form": "13F-HR",
                "primary_document": "mock.xml",
            }
        ],
        "holdings": [holding],
        "fixture_summary": raw,
        "source_type": source_type,
        "provider": "mock",
        "source": ["phase1_mock_dataset"],
        "source_date": safe_filing_date,
        "limitations": [
            "Mock 13F fixture is used when live SEC 13F is disabled or unavailable.",
            "Fallback mock 13F does not boost smart-money score.",
            "13F is delayed quarterly evidence and should not be interpreted as real-time institutional flow.",
        ],
        "missing_data": ["live SEC 13F data"],
    }
    if reason:
        payload["fallback_used"] = True
        payload["fallback_reason"] = reason
        payload["limitations"].append("Live SEC 13F data unavailable; mock fallback used.")
    payload["source_status"] = build_source_status(payload, freshness_window=THIRTEEN_F_FRESHNESS_WINDOW).model_dump(mode="json")
    for row in payload["holdings"]:
        row["source_status"] = payload["source_status"]
    return payload


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


def read_sec_form4_data(ticker: str) -> dict[str, Any] | None:
    target = _sec_cache_dir() / f"{_cache_key(ticker)}_form4.json"
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def read_sec_13f_data(manager_or_cik: str) -> dict[str, Any] | None:
    target = _sec_13f_cache_dir() / f"{_manager_cache_key(manager_or_cik)}_13f.json"
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def write_sec_13f_data(manager_or_cik: str, data: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(data)
    payload["manager"] = manager_or_cik
    payload["provider"] = "SEC EDGAR"
    payload["source"] = ["SEC EDGAR"]
    payload["cached_at"] = datetime.now(timezone.utc).isoformat()
    target = _sec_13f_cache_dir() / f"{_manager_cache_key(manager_or_cik)}_13f.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _sanitize_sec_13f_cached_payload(cached: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(cached)
    payload["provider"] = "SEC EDGAR"
    payload["source"] = ["SEC EDGAR"]
    payload["limitations"] = [item for item in payload.get("limitations", []) if "sec-api" not in str(item).lower()]
    payload["missing_data"] = [item for item in payload.get("missing_data", []) if "sec-api" not in str(item).lower()]
    for holding in payload.get("holdings", []) or []:
        holding["source"] = ["SEC EDGAR"]
        if "reported_value_raw" not in holding and "value_usd_thousands_raw" in holding:
            raw_value = holding.get("value_usd_thousands_raw")
            holding["reported_value_raw"] = raw_value
            holding["reported_value_unit"] = "as_reported"
            holding["value_usd"] = raw_value
            holding["value_unit_confidence"] = "low"
            holding["value_normalization_note"] = "Legacy cached 13F value was migrated by preserving the reported value because no reliable unit disambiguation reference was available."
        holding.pop("value_usd_thousands_raw", None)
        try:
            from backend.app.data_sources.sec_edgar_13f import enrich_13f_holding_with_local_context

            holding.update(enrich_13f_holding_with_local_context(holding))
        except Exception:
            pass
        if isinstance(holding.get("source_status"), dict):
            holding["source_status"]["provider"] = "SEC EDGAR"
    return payload


def _cached_sec_13f_if_fresh(manager_or_cik: str) -> dict[str, Any] | None:
    cached = read_sec_13f_data(manager_or_cik)
    if not cached:
        increment_metric("cache_miss_count")
        return None
    cached_at = cached.get("cached_at") or cached.get("fetched_at")
    try:
        cached_dt = datetime.fromisoformat(str(cached_at).replace("Z", "+00:00"))
    except ValueError:
        increment_metric("cache_miss_count")
        return None
    if datetime.now(timezone.utc) - cached_dt.astimezone(timezone.utc) > timedelta(days=config.SEC_13F_CACHE_TTL_DAYS):
        increment_metric("cache_miss_count")
        return None
    increment_metric("cache_hit_count")
    payload = _sanitize_sec_13f_cached_payload(cached)
    payload["source_type"] = "cached_live"
    payload["provider"] = "SEC EDGAR"
    payload["source"] = ["SEC EDGAR"]
    payload["source_status"] = build_source_status(
        {**payload, "source_type": "cached_live", "provider": "SEC EDGAR", "fallback_used": False},
        freshness_window=THIRTEEN_F_FRESHNESS_WINDOW,
    ).model_dump(mode="json")
    for holding in payload.get("holdings", []) or []:
        holding["source_status"] = payload["source_status"]
    return payload


def _cached_sec_13f_after_failure(manager_or_cik: str, reason: str) -> dict[str, Any] | None:
    cached = read_sec_13f_data(manager_or_cik)
    if not cached:
        increment_metric("cache_miss_count")
        return None
    increment_metric("cache_hit_count")
    payload = _sanitize_sec_13f_cached_payload(cached)
    payload["source_type"] = "cached_live"
    payload["provider"] = "SEC EDGAR"
    payload["source"] = ["SEC EDGAR"]
    payload.setdefault("limitations", []).append("Live SEC EDGAR fetch failed; cached 13F data used.")
    payload["source_status"] = build_source_status(
        {
            **payload,
            "source_type": "cached_live",
            "provider": "SEC EDGAR",
            "fallback_used": True,
            "fallback_reason": reason,
            "limitations": payload.get("limitations", []),
        },
        freshness_window=THIRTEEN_F_FRESHNESS_WINDOW,
    ).model_dump(mode="json")
    for holding in payload.get("holdings", []) or []:
        holding["source_status"] = payload["source_status"]
    return payload


def _cached_sec_form4_if_fresh(ticker: str) -> dict[str, Any] | None:
    cached = read_sec_form4_data(ticker)
    if not cached:
        increment_metric("cache_miss_count")
        return None
    cached_at = cached.get("cached_at") or cached.get("fetched_at")
    try:
        cached_dt = datetime.fromisoformat(str(cached_at).replace("Z", "+00:00"))
    except ValueError:
        increment_metric("cache_miss_count")
        return None
    if datetime.now(timezone.utc) - cached_dt.astimezone(timezone.utc) > timedelta(hours=config.SEC_FORM4_CACHE_TTL_HOURS):
        increment_metric("cache_miss_count")
        return None
    increment_metric("cache_hit_count")
    payload = _sanitize_sec_edgar_cached_payload(cached)
    payload["source_type"] = "cached_live"
    payload["provider"] = "SEC EDGAR"
    payload["source"] = ["SEC EDGAR"]
    payload["source_status"] = build_source_status(
        {
            **payload,
            "source_type": "cached_live",
            "provider": "SEC EDGAR",
            "fallback_used": False,
        },
        freshness_window=FORM4_FRESHNESS_WINDOW,
    ).model_dump(mode="json")
    for transaction in payload.get("transactions", []) or []:
        transaction["source_status"] = payload["source_status"]
    return payload


def _cached_sec_form4_after_failure(ticker: str, reason: str) -> dict[str, Any] | None:
    cached = read_sec_form4_data(ticker)
    if not cached:
        increment_metric("cache_miss_count")
        return None
    increment_metric("cache_hit_count")
    payload = _sanitize_sec_edgar_cached_payload(cached)
    payload["source_type"] = "cached_live"
    payload["provider"] = "SEC EDGAR"
    payload["source"] = ["SEC EDGAR"]
    cache_reason = "Live SEC EDGAR Form 4 fetch failed; cached live data used."
    payload.setdefault("limitations", []).append(cache_reason)
    payload["source_status"] = build_source_status(
        {
            **payload,
            "source_type": "cached_live",
            "provider": "SEC EDGAR",
            "fallback_used": True,
            "fallback_reason": cache_reason,
            "limitations": payload.get("limitations", []),
        },
        freshness_window=FORM4_FRESHNESS_WINDOW,
    ).model_dump(mode="json")
    for transaction in payload.get("transactions", []) or []:
        transaction["source_status"] = payload["source_status"]
    return payload


def _sanitize_sec_edgar_cached_payload(cached: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(cached)

    def clean_list(values: Any) -> list[Any]:
        return [item for item in list(values or []) if "sec-api" not in str(item).lower()]

    payload["provider"] = "SEC EDGAR"
    payload["source"] = ["SEC EDGAR"]
    payload["limitations"] = clean_list(payload.get("limitations"))
    payload["missing_data"] = clean_list(payload.get("missing_data"))
    status = payload.get("source_status")
    if isinstance(status, dict):
        status["provider"] = "SEC EDGAR"
        status["source_type"] = "live"
        status["limitations"] = clean_list(status.get("limitations"))
        status["missing_data"] = clean_list(status.get("missing_data"))
    for transaction in payload.get("transactions", []) or []:
        transaction["source"] = ["SEC EDGAR"]
        transaction["limitations"] = clean_list(transaction.get("limitations"))
        transaction["missing_data"] = clean_list(transaction.get("missing_data"))
        if isinstance(transaction.get("source_status"), dict):
            transaction["source_status"]["provider"] = "SEC EDGAR"
            transaction["source_status"]["limitations"] = clean_list(transaction["source_status"].get("limitations"))
            transaction["source_status"]["missing_data"] = clean_list(transaction["source_status"].get("missing_data"))
    return payload


def write_sec_form4_data(ticker: str, data: dict[str, Any]) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    payload = deepcopy(data)
    payload["ticker"] = normalized_ticker
    payload["provider"] = "SEC EDGAR"
    payload["source"] = ["SEC EDGAR"]
    payload["cached_at"] = datetime.now(timezone.utc).isoformat()
    target = _sec_cache_dir() / f"{_cache_key(normalized_ticker)}_form4.json"
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
    if not config.is_fred_api_key_configured():
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
    merged["source_type"] = "derived"
    merged["provider"] = "mixed_FRED_and_mock_macro"
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


def get_sec_form4_transactions(
    ticker: str,
    lookback_days: int | None = None,
    *,
    allow_live_fetch: bool = True,
) -> dict[str, Any]:
    started_at = time.monotonic()
    try:
        normalized_ticker = ticker.strip().upper()
        resolved_lookback_days = lookback_days or config.SEC_FORM4_LOOKBACK_DAYS
        if not config.USE_LIVE_SEC_FORM4:
            payload = _mock_form4_snapshot(normalized_ticker)
            payload["lookback_days"] = resolved_lookback_days
            return payload
        cached = _cached_sec_form4_if_fresh(normalized_ticker)
        if cached:
            cached["lookback_days"] = resolved_lookback_days
            return cached
        if config.SEC_FORM4_PROVIDER != "sec_edgar":
            payload = _mock_form4_snapshot(normalized_ticker, f"unsupported SEC Form 4 provider: {config.SEC_FORM4_PROVIDER}")
            payload["lookback_days"] = resolved_lookback_days
            return payload
        if not config.SEC_EDGAR_USER_AGENT:
            payload = _mock_form4_snapshot(normalized_ticker, "SEC_EDGAR_USER_AGENT missing")
            payload["lookback_days"] = resolved_lookback_days
            return payload
        if not allow_live_fetch:
            increment_metric("bounded_fetch_skipped_count")
            payload = _mock_form4_snapshot(normalized_ticker, "live SEC EDGAR fetch disabled for report request")
            payload["lookback_days"] = resolved_lookback_days
            return payload
        try:
            from backend.app.data_sources.sec_edgar_form4 import fetch_insider_transactions

            snapshot = fetch_insider_transactions(normalized_ticker, lookback_days=resolved_lookback_days)
            if snapshot.get("bounded_fetch_exhausted"):
                cached_after_budget = _cached_sec_form4_after_failure(normalized_ticker, "SEC Form 4 fetch was bounded for performance.")
                if cached_after_budget:
                    cached_after_budget["lookback_days"] = resolved_lookback_days
                    return cached_after_budget
            snapshot["source_status"] = build_source_status(snapshot, freshness_window=FORM4_FRESHNESS_WINDOW).model_dump(mode="json")
            return write_sec_form4_data(normalized_ticker, snapshot)
        except Exception as exc:
            safe_reason = str(exc).splitlines()[0][:180] or "live SEC Form 4 fetch failed"
            cached_after_failure = _cached_sec_form4_after_failure(normalized_ticker, safe_reason)
            if cached_after_failure:
                cached_after_failure["lookback_days"] = resolved_lookback_days
                return cached_after_failure
            payload = _mock_form4_snapshot(normalized_ticker, safe_reason)
            payload["lookback_days"] = resolved_lookback_days
            return payload
    finally:
        add_timing("sec_form4_ms", started_at)


def get_sec_13f_holdings(
    manager_or_cik: str,
    lookback_quarters: int | None = None,
    *,
    allow_live_fetch: bool = True,
    ticker: str = "NVDA",
) -> dict[str, Any]:
    started_at = time.monotonic()
    try:
        resolved_lookback_quarters = lookback_quarters or config.SEC_13F_LOOKBACK_QUARTERS
        if not config.USE_LIVE_SEC_13F:
            payload = _mock_13f_snapshot(manager_or_cik, ticker)
            payload["lookback_quarters"] = resolved_lookback_quarters
            return payload
        cached = _cached_sec_13f_if_fresh(manager_or_cik)
        if cached:
            cached["lookback_quarters"] = resolved_lookback_quarters
            return cached
        if config.SEC_13F_PROVIDER != "sec_edgar":
            payload = _mock_13f_snapshot(manager_or_cik, ticker, f"unsupported SEC 13F provider: {config.SEC_13F_PROVIDER}")
            payload["lookback_quarters"] = resolved_lookback_quarters
            return payload
        if not config.SEC_EDGAR_USER_AGENT:
            payload = _mock_13f_snapshot(manager_or_cik, ticker, "SEC_EDGAR_USER_AGENT missing")
            payload["lookback_quarters"] = resolved_lookback_quarters
            return payload
        if not allow_live_fetch:
            increment_metric("bounded_fetch_skipped_count")
            payload = _mock_13f_snapshot(manager_or_cik, ticker, "live SEC EDGAR 13F fetch disabled for report request")
            payload["lookback_quarters"] = resolved_lookback_quarters
            return payload
        try:
            from backend.app.data_sources.sec_edgar_13f import fetch_13f_holdings_for_manager

            snapshot = fetch_13f_holdings_for_manager(manager_or_cik, lookback_quarters=resolved_lookback_quarters)
            snapshot["source_status"] = build_source_status(snapshot, freshness_window=THIRTEEN_F_FRESHNESS_WINDOW).model_dump(mode="json")
            return write_sec_13f_data(manager_or_cik, snapshot)
        except Exception as exc:
            safe_reason = str(exc).splitlines()[0][:180] or "live SEC 13F fetch failed"
            cached_after_failure = _cached_sec_13f_after_failure(manager_or_cik, safe_reason)
            if cached_after_failure:
                cached_after_failure["lookback_quarters"] = resolved_lookback_quarters
                return cached_after_failure
            payload = _mock_13f_snapshot(manager_or_cik, ticker, safe_reason)
            payload["lookback_quarters"] = resolved_lookback_quarters
            return payload
    finally:
        add_timing("sec_13f_ms", started_at)


def _sec_13f_derived_provider(snapshot: dict[str, Any]) -> str:
    status = snapshot.get("source_status") if isinstance(snapshot.get("source_status"), dict) else {}
    source_type = status.get("source_type") or snapshot.get("source_type")
    provider = status.get("provider") or snapshot.get("provider")
    if source_type in {"live", "cached_live"} and provider == "SEC EDGAR":
        return "derived_from_SEC_EDGAR_13F"
    return "derived_from_mock_13f"


def _sec_13f_derived_status(snapshot: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    underlying_status = snapshot.get("source_status") if isinstance(snapshot.get("source_status"), dict) else {}
    provider = _sec_13f_derived_provider(snapshot)
    limitations = sorted(set([*summary.get("limitations", []), *snapshot.get("limitations", []), *underlying_status.get("limitations", [])]))
    missing_data = sorted(set([*summary.get("missing_data", []), *snapshot.get("missing_data", []), *underlying_status.get("missing_data", [])]))
    return build_source_status(
        {
            "source_type": "derived",
            "provider": provider,
            "source_date": summary.get("latest_report_date") or snapshot.get("source_date") or underlying_status.get("source_date") or "",
            "fetched_at": snapshot.get("cached_at") or snapshot.get("fetched_at") or underlying_status.get("fetched_at"),
            "is_fresh": underlying_status.get("is_fresh") if isinstance(underlying_status.get("is_fresh"), bool) else None,
            "fallback_used": bool(snapshot.get("fallback_used") or underlying_status.get("fallback_used")),
            "fallback_reason": snapshot.get("fallback_reason") or underlying_status.get("fallback_reason"),
            "limitations": limitations,
            "missing_data": missing_data,
        },
        freshness_window=THIRTEEN_F_FRESHNESS_WINDOW,
    ).model_dump(mode="json")


def get_sec_13f_summary(
    manager_or_cik: str,
    lookback_quarters: int | None = None,
    *,
    allow_live_fetch: bool = True,
    ticker: str = "NVDA",
) -> dict[str, Any]:
    snapshot = get_sec_13f_holdings(manager_or_cik, lookback_quarters, allow_live_fetch=allow_live_fetch, ticker=ticker)
    summary = summarize_13f_portfolio(snapshot.get("holdings", []) or [])
    summary["source_status"] = _sec_13f_derived_status(snapshot, summary)
    summary["source_type"] = "derived"
    summary["provider"] = summary["source_status"]["provider"]
    summary["underlying_source_status"] = snapshot.get("source_status")
    summary["underlying_source_type"] = snapshot.get("source_type")
    summary["fallback_used"] = summary["source_status"].get("fallback_used", False)
    return summary


def get_sec_13f_target_matches(
    manager_or_cik: str,
    targets: dict[str, Any] | None = None,
    *,
    allow_live_fetch: bool = True,
    ticker: str = "NVDA",
) -> dict[str, Any]:
    summary = get_sec_13f_summary(manager_or_cik, allow_live_fetch=allow_live_fetch, ticker=ticker)
    target_map = normalize_target_security_map(targets or {"ticker": ticker})
    matches = match_13f_targets(summary.get("grouped_holdings", []), target_map)
    return {
        **matches,
        "source_status": summary.get("source_status"),
        "missing_data": sorted(set([*target_map.get("missing_data", []), *matches.get("missing_data", [])])),
        "limitations": sorted(set([*summary.get("limitations", []), *matches.get("limitations", [])])),
    }


def _holdings_by_latest_two_periods(holdings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    periods = sorted({str(row.get("report_date") or "") for row in holdings if row.get("report_date")}, reverse=True)
    if len(periods) < 2:
        return [], [], ["prior SEC 13F quarter unavailable"]
    current_period, prior_period = periods[0], periods[1]
    current = [row for row in holdings if str(row.get("report_date") or "") == current_period]
    prior = [row for row in holdings if str(row.get("report_date") or "") == prior_period]
    return current, prior, []


def get_sec_13f_qoq_comparison(
    manager_or_cik: str,
    *,
    allow_live_fetch: bool = True,
    ticker: str = "NVDA",
) -> dict[str, Any]:
    snapshot = get_sec_13f_holdings(manager_or_cik, allow_live_fetch=allow_live_fetch, ticker=ticker)
    holdings = snapshot.get("holdings", []) or []
    current_rows, prior_rows, missing_data = _holdings_by_latest_two_periods(holdings)
    current_grouped = aggregate_13f_holdings(current_rows).get("grouped_holdings", []) if current_rows else []
    prior_grouped = aggregate_13f_holdings(prior_rows).get("grouped_holdings", []) if prior_rows else []
    qoq_changes = compare_13f_quarter_over_quarter(current_grouped, prior_grouped) if current_grouped and prior_grouped else []
    source_status = build_source_status(
        {
            "source_type": "derived",
            "provider": _sec_13f_derived_provider(snapshot),
            "source_date": max((item.get("current_report_date") for item in qoq_changes if item.get("current_report_date")), default=snapshot.get("source_date", "")),
            "fetched_at": snapshot.get("cached_at") or snapshot.get("fetched_at"),
            "fallback_used": bool(snapshot.get("fallback_used")),
            "fallback_reason": snapshot.get("fallback_reason"),
            "limitations": ["QoQ 13F comparison reflects reported quarterly change only and is not real-time activity."],
            "missing_data": missing_data,
        },
        freshness_window=THIRTEEN_F_FRESHNESS_WINDOW,
    ).model_dump(mode="json")
    return {
        "qoq_changes": qoq_changes,
        "source_status": source_status,
        "limitations": source_status.get("limitations", []),
        "missing_data": missing_data,
    }


def _mapped_13f_tickers_from_holdings(holdings: list[dict[str, Any]]) -> list[str]:
    tickers: list[str] = []
    seen: set[str] = set()
    for row in holdings or []:
        ticker = str(row.get("mapped_ticker") or "").strip().upper()
        if not ticker:
            security = resolve_security_identifier(cusip=row.get("cusip"), issuer_name=row.get("issuer_name")).get("security") or {}
            ticker = str(security.get("ticker") or "").strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def warm_price_reference_cache(tickers: list[str], max_tickers: int | None = None, allow_live_fetch: bool = False) -> dict[str, object]:
    return _warm_price_reference_cache(
        tickers,
        max_tickers=max_tickers or config.PRICE_REFERENCE_CACHE_WARMUP_MAX_TICKERS,
        allow_live_fetch=allow_live_fetch,
    )


def _target_13f_managers(fixture_summary: dict[str, Any]) -> list[str]:
    configured = [item.strip() for item in config.SEC_13F_TARGET_MANAGERS.split(",") if item.strip()]
    if configured:
        return configured
    fixture_manager = str(fixture_summary.get("institution_name") or "").strip()
    return [fixture_manager or "mock_manager"]


def read_sec_filings(ticker: str = "NVDA", *, allow_live_fetch: bool | None = None) -> dict[str, Any]:
    fixture = read_company_fundamentals(ticker)
    smart_money = fixture.get("smart_money", MOCK_SMART_MONEY_SUMMARY)
    institutional_fixture = smart_money.get("institutional_13f", {})
    resolved_allow_live = config.ALLOW_LIVE_FETCH_ON_REPORT_REQUEST if allow_live_fetch is None else allow_live_fetch
    form4_snapshot = get_sec_form4_transactions(
        ticker,
        allow_live_fetch=resolved_allow_live,
    )
    managers = _target_13f_managers(institutional_fixture)
    thirteen_f_snapshots = [
        get_sec_13f_holdings(manager, allow_live_fetch=resolved_allow_live, ticker=ticker)
        for manager in managers[:5]
    ]
    primary_13f_snapshot = thirteen_f_snapshots[0] if thirteen_f_snapshots else _mock_13f_snapshot("mock_manager", ticker)
    primary_manager = managers[0] if managers else "mock_manager"
    if config.PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT:
        mapped_tickers = _mapped_13f_tickers_from_holdings(primary_13f_snapshot.get("holdings", []) or [])
        warm_price_reference_cache(
            mapped_tickers,
            max_tickers=config.PRICE_REFERENCE_CACHE_WARMUP_MAX_TICKERS,
            allow_live_fetch=True,
        )
        primary_13f_snapshot = get_sec_13f_holdings(primary_manager, allow_live_fetch=False, ticker=ticker)
        thirteen_f_snapshots = [primary_13f_snapshot, *thirteen_f_snapshots[1:]]
    target_map = {
        "ticker": ticker,
        "cusip": institutional_fixture.get("cusip"),
        "issuer_name": institutional_fixture.get("issuer_name"),
    }
    thirteen_f_summary = get_sec_13f_summary(primary_manager, allow_live_fetch=resolved_allow_live, ticker=ticker)
    thirteen_f_matches = get_sec_13f_target_matches(primary_manager, target_map, allow_live_fetch=resolved_allow_live, ticker=ticker)
    thirteen_f_qoq = get_sec_13f_qoq_comparison(primary_manager, allow_live_fetch=resolved_allow_live, ticker=ticker)
    return deepcopy(
        {
            "institutional_13f": smart_money.get("institutional_13f", {}),
            "institutional_13f_snapshot": primary_13f_snapshot,
            "institutional_13f_snapshots": thirteen_f_snapshots,
            "institutional_13f_source_status": primary_13f_snapshot.get("source_status"),
            "institutional_13f_summary": thirteen_f_summary,
            "institutional_13f_target_matches": thirteen_f_matches,
            "institutional_13f_qoq_comparison": thirteen_f_qoq,
            "form4_transactions": form4_snapshot.get("transactions", []),
            "form4_source_status": form4_snapshot.get("source_status"),
            "form4_snapshot": form4_snapshot,
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
