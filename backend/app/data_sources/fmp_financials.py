from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlencode

import requests

from backend.app.data_sources.external_provider_base import ExternalProviderStatus
from backend.app.data_sources.provider_registry import require_provider_enabled
from backend.app.raw_store.fmp_financials_cache import load_cached_fmp_financials, save_fmp_financials_snapshot

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"


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


def _pct(numerator: Any, denominator: Any) -> float | None:
    n = _safe_float(numerator)
    d = _safe_float(denominator)
    if n is None or d is None or d == 0:
        return None
    return round(n / d * 100, 4)


def _growth_pct(current: Any, previous: Any) -> float | None:
    c = _safe_float(current)
    p = _safe_float(previous)
    if c is None or p is None or p == 0:
        return None
    return round((c - p) / abs(p) * 100, 4)


def _first_record(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    if isinstance(payload, dict):
        data = payload.get("data") or payload.get("records") or payload.get("financials")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        return payload
    return {}


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data = payload.get("data") or payload.get("records") or payload.get("financials") or []
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def _metric(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record and record.get(name) is not None:
            return record.get(name)
    return None


def _source_date(*records: dict[str, Any]) -> str:
    dates = []
    for record in records:
        for key in ("filingDate", "date", "acceptedDate"):
            value = str(record.get(key) or "")[:10]
            if value:
                dates.append(value)
    return max(dates) if dates else ""


def disabled_fmp_financial_proxy(ticker: str, reason: str) -> dict[str, Any]:
    status = ExternalProviderStatus(
        provider="fmp_financials",
        source_type="unknown",
        fallback_used=False,
        fallback_reason=reason,
        limitations=[reason[:180]],
        missing_data=["fmp_financial_statements", "fmp_ttm_ratios"],
    ).to_data_source_status()
    return {
        "ticker": ticker.strip().upper(),
        "available": False,
        "provider": "fmp_financials",
        "source_type": "unknown",
        "source_status": status.model_dump(mode="json"),
        "latest_fiscal_year": None,
        "reported_currency": None,
        "filing_date": None,
        "facts": {},
        "derived_metrics": {},
        "ttm_ratios": {},
        "limitations": status.limitations,
        "missing_data": status.missing_data,
    }


def _proxy_from_raw(ticker: str, raw_payload: dict[str, Any], *, source_type: str, fetched_at: str | None = None, fallback_reason: str | None = None) -> dict[str, Any]:
    income_records = _records(raw_payload.get("income_statement"))
    latest_income = income_records[0] if income_records else {}
    previous_income = income_records[1] if len(income_records) > 1 else {}
    balance = _first_record(raw_payload.get("balance_sheet"))
    cash_flow = _first_record(raw_payload.get("cash_flow"))
    ratios = _first_record(raw_payload.get("ratios_ttm"))

    revenue = _metric(latest_income, "revenue")
    gross_profit = _metric(latest_income, "grossProfit")
    operating_income = _metric(latest_income, "operatingIncome", "operatingIncomeLoss")
    net_income = _metric(latest_income, "netIncome", "netIncomeLoss")
    rd_expense = _metric(latest_income, "researchAndDevelopmentExpenses", "researchAndDevelopmentExpense")
    operating_cash_flow = _metric(cash_flow, "netCashProvidedByOperatingActivities", "operatingCashFlow")
    capex = _metric(cash_flow, "capitalExpenditure", "capitalExpenditures")
    free_cash_flow = _metric(cash_flow, "freeCashFlow")
    if free_cash_flow is None and operating_cash_flow is not None and capex is not None:
        ocf_value = _safe_float(operating_cash_flow)
        capex_value = _safe_float(capex)
        if ocf_value is not None and capex_value is not None:
            free_cash_flow = ocf_value + capex_value

    facts = {
        "revenue": _safe_number(revenue),
        "gross_profit": _safe_number(gross_profit),
        "operating_income": _safe_number(operating_income),
        "net_income": _safe_number(net_income),
        "research_and_development_expense": _safe_number(rd_expense),
        "operating_cash_flow": _safe_number(operating_cash_flow),
        "capex": _safe_number(capex),
        "free_cash_flow": _safe_number(free_cash_flow),
        "cash_and_equivalents": _safe_number(_metric(balance, "cashAndCashEquivalents", "cashAndCashEquivalentsAtCarryingValue")),
        "total_debt": _safe_number(_metric(balance, "totalDebt", "shortTermDebtAndLongTermDebtTotal")),
        "stockholders_equity": _safe_number(_metric(balance, "totalStockholdersEquity", "stockholdersEquity")),
    }
    facts = {key: value for key, value in facts.items() if value is not None}
    derived = {
        "revenue_yoy_growth_pct": _growth_pct(revenue, _metric(previous_income, "revenue")),
        "gross_margin_pct": _pct(gross_profit, revenue),
        "operating_margin_pct": _pct(operating_income, revenue),
        "net_income_margin_pct": _pct(net_income, revenue),
        "rd_to_revenue_pct": _pct(rd_expense, revenue),
        "free_cash_flow_ttm": _safe_number(free_cash_flow),
        "free_cash_flow_margin_pct": _pct(free_cash_flow, revenue),
        "net_cash_or_debt": None,
        "debt_to_equity": _pct(_metric(balance, "totalDebt"), _metric(balance, "totalStockholdersEquity", "stockholdersEquity")),
    }
    cash = _safe_float(facts.get("cash_and_equivalents"))
    debt = _safe_float(facts.get("total_debt"))
    if cash is not None and debt is not None:
        derived["net_cash_or_debt"] = _safe_number(cash - debt)
    derived = {key: value for key, value in derived.items() if value is not None}
    ttm_ratios = {
        "price_to_earnings_ttm": _safe_number(_metric(ratios, "priceToEarningsRatioTTM", "peRatioTTM")),
        "price_to_free_cash_flow_ttm": _safe_number(_metric(ratios, "priceToFreeCashFlowsRatioTTM", "priceToFreeCashFlowRatioTTM")),
        "return_on_equity_ttm": _safe_number(_metric(ratios, "returnOnEquityTTM", "roeTTM")),
        "free_cash_flow_per_share_ttm": _safe_number(_metric(ratios, "freeCashFlowPerShareTTM")),
    }
    ttm_ratios = {key: value for key, value in ttm_ratios.items() if value is not None}
    source_date = _source_date(latest_income, balance, cash_flow, ratios)
    missing = []
    for key in ["revenue", "gross_profit", "operating_income", "research_and_development_expense", "free_cash_flow"]:
        if key not in facts:
            missing.append(f"fmp_{key}")
    if not ttm_ratios:
        missing.append("fmp_ttm_ratios")
    limitations = [
        "FMP financial statements are provider-normalized financial proxies, not SEC filing-backed facts.",
        "ADR and non-US issuer values may be reported in local currency and require manual period/currency review.",
    ]
    if fallback_reason:
        limitations.append(fallback_reason[:180])
    status = ExternalProviderStatus(
        provider="fmp_financials",
        source_type=source_type,  # type: ignore[arg-type]
        source_date=source_date,
        fetched_at=fetched_at,
        cache_hit=source_type == "cached_live",
        fallback_used=bool(fallback_reason),
        fallback_reason=fallback_reason,
        limitations=limitations,
        missing_data=missing,
    ).to_data_source_status(freshness_window="fmp_financial_cache")
    return {
        "ticker": ticker.strip().upper(),
        "available": bool(facts or derived or ttm_ratios),
        "provider": "fmp_financials",
        "source_type": source_type,
        "source_status": status.model_dump(mode="json"),
        "latest_fiscal_year": str(latest_income.get("fiscalYear") or latest_income.get("calendarYear") or latest_income.get("year") or "") or None,
        "reported_currency": latest_income.get("reportedCurrency") or balance.get("reportedCurrency") or cash_flow.get("reportedCurrency"),
        "filing_date": latest_income.get("filingDate") or latest_income.get("date"),
        "facts": facts,
        "derived_metrics": derived,
        "ttm_ratios": ttm_ratios,
        "limitations": limitations,
        "missing_data": missing,
    }


def _fallback_from_cache(ticker: str, reason: str, ttl_days: int) -> dict[str, Any] | None:
    cached = load_cached_fmp_financials(ticker, ttl_days=ttl_days)
    if not cached:
        return None
    return _proxy_from_raw(
        ticker,
        cached.get("payload", cached),
        source_type="cached_live",
        fetched_at=cached.get("fetched_at"),
        fallback_reason="FMP live financial statements fetch failed; using cached financial snapshot.",
    )


def fetch_fmp_financial_proxy(ticker: str, http_get: Callable[..., Any] | None = None) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    try:
        provider_config = require_provider_enabled("fmp")
    except RuntimeError as exc:
        return disabled_fmp_financial_proxy(normalized_ticker, str(exc))

    getter = http_get or requests.get
    query = urlencode({"limit": 4, "apikey": provider_config.api_key})
    endpoints = {
        "income_statement": f"{FMP_BASE_URL}/income-statement/{normalized_ticker}?{query}",
        "balance_sheet": f"{FMP_BASE_URL}/balance-sheet-statement/{normalized_ticker}?{query}",
        "cash_flow": f"{FMP_BASE_URL}/cash-flow-statement/{normalized_ticker}?{query}",
        "ratios_ttm": f"{FMP_BASE_URL}/ratios-ttm/{normalized_ticker}?{urlencode({'apikey': provider_config.api_key})}",
    }
    raw_payload: dict[str, Any] = {}
    try:
        for key, url in endpoints.items():
            response = getter(url, timeout=15)
            status_code = int(getattr(response, "status_code", 200) or 200)
            if status_code == 429:
                cached = _fallback_from_cache(normalized_ticker, "FMP financial provider was rate limited.", provider_config.cache_ttl_days)
                if cached:
                    return cached
                status = ExternalProviderStatus(provider="fmp_financials", source_type="fallback", rate_limited=True, fallback_used=True, fallback_reason="FMP financial provider was rate limited.", missing_data=["fmp_financial_statements"]).to_data_source_status()
                payload = disabled_fmp_financial_proxy(normalized_ticker, "FMP financial provider was rate limited.")
                payload["source_status"] = status.model_dump(mode="json")
                payload["source_type"] = "fallback"
                return payload
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            raw_payload[key] = response.json()
    except Exception as exc:  # noqa: BLE001 - provider boundary must degrade safely.
        safe_reason = str(exc).replace(provider_config.api_key, "[REDACTED]")[:180]
        cached = _fallback_from_cache(normalized_ticker, safe_reason, provider_config.cache_ttl_days)
        if cached:
            return cached
        payload = disabled_fmp_financial_proxy(normalized_ticker, "FMP live financial statements fetch failed.")
        payload["source_type"] = "fallback"
        payload["source_status"]["source_type"] = "fallback"
        payload["source_status"]["fallback_used"] = True
        payload["source_status"]["fallback_reason"] = "FMP live financial statements fetch failed."
        payload["source_status"]["limitations"].append(safe_reason)
        return payload

    proxy = _proxy_from_raw(normalized_ticker, raw_payload, source_type="live", fetched_at=datetime.now(timezone.utc).isoformat())
    if proxy["available"]:
        save_fmp_financials_snapshot(normalized_ticker, raw_payload, fetched_at=datetime.now(timezone.utc))
    return proxy


def get_fmp_financial_proxy(ticker: str) -> dict[str, Any]:
    return fetch_fmp_financial_proxy(ticker)
