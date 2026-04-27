from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.app.schemas.common import DataQualitySummary, DataSourceStatus

DAILY_MARKET_FRESHNESS_WINDOW = "latest_expected_trading_day"
DAILY_RATE_FRESHNESS_WINDOW = "daily_rate_5_business_days"
MONTHLY_MACRO_FRESHNESS_WINDOW = "monthly_macro_latest_observation"
DERIVED_FRED_FRESHNESS_WINDOW = "derived_from_FRED"
MOCK_LIMITATION = "Mock data is a non-live research reference and is excluded from stale-data counts."
FALLBACK_LIMITATION = "Live market data unavailable; mock fallback used."
MONTHLY_FRED_LIMITATION = "Monthly FRED series are evaluated using observation-month freshness, not latest trading-day freshness."


def parse_source_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _latest_expected_trading_day(as_of: date | None = None) -> date:
    current = as_of or datetime.now(timezone.utc).date()
    if current.weekday() == 5:
        return current - timedelta(days=1)
    if current.weekday() == 6:
        return current - timedelta(days=2)
    return current


def is_daily_market_data_fresh(source_date: Any, as_of: date | None = None) -> bool:
    parsed = parse_source_date(source_date)
    if parsed is None:
        return False
    latest = _latest_expected_trading_day(as_of)
    return parsed >= latest


def _business_days_between(start: date, end: date) -> int:
    if start > end:
        return 0
    count = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            count += 1
    return count


def is_daily_rate_data_fresh(source_date: Any, as_of: date | None = None) -> bool:
    parsed = parse_source_date(source_date)
    if parsed is None:
        return False
    current = as_of or datetime.now(timezone.utc).date()
    return _business_days_between(parsed, current) <= 5


def is_monthly_macro_data_fresh(source_date: Any, as_of: date | None = None) -> bool:
    parsed = parse_source_date(source_date)
    if parsed is None:
        return False
    current = as_of or datetime.now(timezone.utc).date()
    return parsed >= current - timedelta(days=70)


def is_source_fresh_for_window(source_date: Any, freshness_window: str, as_of: date | None = None) -> bool:
    if freshness_window == DAILY_RATE_FRESHNESS_WINDOW:
        return is_daily_rate_data_fresh(source_date, as_of=as_of)
    if freshness_window == MONTHLY_MACRO_FRESHNESS_WINDOW:
        return is_monthly_macro_data_fresh(source_date, as_of=as_of)
    if freshness_window == DAILY_MARKET_FRESHNESS_WINDOW:
        return is_daily_market_data_fresh(source_date, as_of=as_of)
    return is_daily_market_data_fresh(source_date, as_of=as_of)


def _source_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value:
        return [value]
    return []


def _provider(payload: dict[str, Any], source_type: str) -> str:
    explicit = payload.get("provider")
    if explicit:
        return str(explicit)
    sources = _source_list(payload.get("source"))
    if source_type == "fallback":
        return "mock"
    if sources:
        return sources[0]
    return "unknown"


def _status_type(payload: dict[str, Any]) -> str:
    raw_type = str(payload.get("source_type") or "").lower()
    if raw_type in {"live", "mock", "fallback", "derived"}:
        return raw_type
    if payload.get("fallback_used") or payload.get("fallback_reason") or payload.get("error") or payload.get("live_market_data_error"):
        return "fallback"
    sources = " ".join(_source_list(payload.get("source"))).lower()
    if "yfinance" in sources:
        return "live"
    if "mock" in sources or "phase" in sources:
        return "mock"
    return "unknown"


def build_source_status(
    payload: dict[str, Any] | None = None,
    *,
    source_type: str | None = None,
    provider: str | None = None,
    source_date: str | None = None,
    fetched_at: str | None = None,
    freshness_window: str = DAILY_MARKET_FRESHNESS_WINDOW,
    fallback_used: bool | None = None,
    fallback_reason: str | None = None,
    limitations: list[str] | None = None,
    missing_data: list[str] | None = None,
    as_of: date | None = None,
) -> DataSourceStatus:
    data = payload or {}
    resolved_type = source_type or _status_type(data)
    resolved_source_date = source_date if source_date is not None else str(data.get("source_date") or "")
    resolved_fallback = bool(
        fallback_used
        if fallback_used is not None
        else resolved_type == "fallback" or data.get("fallback_used") or data.get("error") or data.get("live_market_data_error")
    )
    resolved_reason = fallback_reason or data.get("fallback_reason") or data.get("error") or data.get("live_market_data_error")
    status_missing = list(missing_data if missing_data is not None else data.get("missing_data", []) or [])
    status_limitations = list(limitations if limitations is not None else data.get("limitations", []) or [])
    if freshness_window == MONTHLY_MACRO_FRESHNESS_WINDOW and MONTHLY_FRED_LIMITATION not in status_limitations:
        status_limitations.append(MONTHLY_FRED_LIMITATION)
    if not resolved_source_date:
        status_missing.append("source_date")
    if resolved_type == "mock" and MOCK_LIMITATION not in status_limitations:
        status_limitations.append(MOCK_LIMITATION)
    if resolved_fallback and FALLBACK_LIMITATION not in status_limitations:
        status_limitations.append(FALLBACK_LIMITATION)
    explicit_is_fresh = data.get("is_fresh")
    if isinstance(explicit_is_fresh, bool):
        is_fresh = explicit_is_fresh
    elif resolved_type == "mock":
        is_fresh = True
    elif resolved_type == "unknown":
        is_fresh = False
    else:
        is_fresh = is_source_fresh_for_window(resolved_source_date, freshness_window, as_of=as_of)
    return DataSourceStatus(
        source_type=resolved_type,  # type: ignore[arg-type]
        provider=provider or _provider(data, resolved_type),
        source_date=resolved_source_date,
        fetched_at=fetched_at if fetched_at is not None else data.get("cached_at") or data.get("fetched_at"),
        is_fresh=is_fresh,
        freshness_window=freshness_window,
        fallback_used=resolved_fallback,
        fallback_reason=str(resolved_reason) if resolved_reason else None,
        limitations=sorted(set(status_limitations)),
        missing_data=sorted(set(status_missing)),
    )


def summarize_data_quality(statuses: list[DataSourceStatus]) -> DataQualitySummary:
    live = sum(1 for item in statuses if item.source_type == "live")
    mock = sum(1 for item in statuses if item.source_type == "mock")
    fallback = sum(1 for item in statuses if item.source_type == "fallback" or item.fallback_used)
    missing_source_date = sum(1 for item in statuses if not parse_source_date(item.source_date))
    stale = sum(1 for item in statuses if item.source_type in {"live", "fallback", "derived"} and parse_source_date(item.source_date) and not item.is_fresh)
    total = max(1, len(statuses))
    if fallback:
        mode = "live_with_fallback"
    elif live == 0:
        mode = "all_mock"
    elif live / total >= 0.5:
        mode = "mostly_live"
    else:
        mode = "mixed"
    limitations: list[str] = []
    if mock:
        limitations.append("Some components still use mock data.")
    if fallback:
        limitations.append("Some components use fallback data because live data was unavailable.")
    if stale:
        limitations.append("Some live, fallback, or derived components are stale.")
    if missing_source_date:
        limitations.append("Some components are missing source dates.")
    providers = {item.provider for item in statuses}
    windows = {item.freshness_window for item in statuses}
    if "FRED" in providers or "derived_from_FRED" in providers:
        fred_windows = sorted(
            window
            for window in windows
            if window in {DAILY_RATE_FRESHNESS_WINDOW, MONTHLY_MACRO_FRESHNESS_WINDOW, DERIVED_FRED_FRESHNESS_WINDOW}
        )
        limitations.append(f"FRED macro freshness windows active: {', '.join(fred_windows)}.")
    return DataQualitySummary(
        mode=mode,  # type: ignore[arg-type]
        live_components=live,
        mock_components=mock,
        fallback_components=fallback,
        stale_components=stale,
        missing_source_date_components=missing_source_date,
        limitations=limitations,
    )
