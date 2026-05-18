from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.app import config
from backend.app.data_sources.sec_edgar_form4 import get_cik_for_ticker
from backend.app.utils.freshness import COMPANY_FILING_FRESHNESS_WINDOW, build_source_status
from backend.app.utils.performance import increment_metric

SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
PROVIDER = "SEC EDGAR companyfacts"
LIMITATION = "SEC Companyfacts values are filing-backed but concept coverage varies by issuer and reporting period."
SAFE_FALLBACK_REASON = "SEC Companyfacts fetch failed; cached or provider fallback used."
PARSER_VERSION = "sec_companyfacts_period_alignment_v17a"


class SecCompanyfactsFetchError(RuntimeError):
    """Raised when SEC Companyfacts cannot be fetched or normalized."""


@dataclass(frozen=True)
class FactSelection:
    metric: str
    concept: str
    unit: str
    value: float
    period: str
    form: str
    filed: str
    fiscal_year: int | None
    fiscal_period: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": "shares" if self.unit == "shares" else "USD",
            "period": self.period,
            "form": self.form,
            "filed": self.filed,
            "concept": f"us-gaap:{self.concept}",
        }


CONCEPTS: dict[str, list[str]] = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "research_and_development_expense": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "total_debt": [
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "ShortTermBorrowings",
        "DebtCurrent",
        "DebtNoncurrent",
    ],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "accounts_receivable": ["AccountsReceivableNetCurrent", "AccountsReceivableNet"],
    "inventory": ["InventoryNet"],
    "shares_outstanding": [
        "EntityCommonStockSharesOutstanding",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ],
}

BALANCE_SHEET_METRICS = {
    "cash_and_equivalents",
    "total_debt",
    "stockholders_equity",
    "accounts_receivable",
    "inventory",
    "shares_outstanding",
}

STATEMENT_METRICS = {
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "research_and_development_expense",
    "operating_cash_flow",
    "capex",
}
STATEMENT_PERIOD_ANCHOR_METRICS = STATEMENT_METRICS - {"capex"}


def cik10(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(10) if text else ""


def companyfacts_endpoint(cik: str) -> str:
    return SEC_COMPANYFACTS_URL.format(cik=cik10(cik))


def _headers() -> dict[str, str]:
    if not config.SEC_EDGAR_USER_AGENT:
        raise SecCompanyfactsFetchError("SEC_EDGAR_USER_AGENT missing")
    return {"User-Agent": config.SEC_EDGAR_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _request_delay() -> None:
    time.sleep(max(0.0, config.SEC_EDGAR_REQUEST_DELAY_SECONDS))


def fetch_companyfacts(cik: str) -> dict[str, Any]:
    cik_padded = cik10(cik)
    if not cik_padded:
        raise SecCompanyfactsFetchError("CIK is required")
    _request_delay()
    increment_metric("network_call_count")
    response = httpx.get(companyfacts_endpoint(cik_padded), headers=_headers(), timeout=config.SEC_COMPANYFACTS_NETWORK_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise SecCompanyfactsFetchError("SEC Companyfacts response was not a JSON object")
    return payload


def fetch_companyfacts_for_ticker(ticker: str) -> dict[str, Any]:
    cik = get_cik_for_ticker(ticker)
    payload = fetch_companyfacts(cik)
    parsed = parse_companyfacts(ticker, cik, payload, source_type="live")
    parsed["_raw_companyfacts_payload"] = payload
    return parsed


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _safe_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        return datetime.fromisoformat(text[:10]).date().isoformat()
    except ValueError:
        return ""


def _unit_payload(concept_payload: dict[str, Any], preferred_units: list[str]) -> tuple[str, list[dict[str, Any]]]:
    units = concept_payload.get("units") if isinstance(concept_payload, dict) else {}
    if not isinstance(units, dict):
        return "", []
    for unit in preferred_units:
        rows = units.get(unit)
        if isinstance(rows, list):
            return unit, [row for row in rows if isinstance(row, dict)]
    return "", []


def _duration_days(row: dict[str, Any]) -> int | None:
    start = _safe_date(row.get("start"))
    end = _safe_date(row.get("end"))
    if not start or not end:
        return None
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days


def _is_annual_row(row: dict[str, Any]) -> bool:
    form = str(row.get("form") or "").upper()
    fp = str(row.get("fp") or "").upper()
    duration = _duration_days(row)
    if form == "10-K" or fp == "FY":
        return duration is None or duration >= 250
    return False


def _fact_from_row(metric: str, concept: str, unit: str, row: dict[str, Any]) -> FactSelection | None:
    value = _as_float(row.get("val"))
    end = _safe_date(row.get("end"))
    filed = _safe_date(row.get("filed"))
    form = str(row.get("form") or "").upper()
    if value is None or not end or form not in {"10-K", "10-Q"}:
        return None
    return FactSelection(
        metric=metric,
        concept=concept,
        unit="shares" if unit == "shares" else "USD",
        value=abs(value) if metric == "capex" else value,
        period=end,
        form=form,
        filed=filed,
        fiscal_year=int(row["fy"]) if str(row.get("fy") or "").isdigit() else None,
        fiscal_period=str(row.get("fp") or ""),
    )


def _select_concept_facts(payload: dict[str, Any], metric: str) -> tuple[FactSelection | None, list[FactSelection], str | None]:
    selected = _facts_for_metric(payload, metric)
    if selected:
        return selected[0], selected, None
    return None, [], f"SEC Companyfacts concept unavailable for {metric}"


def _facts_for_metric(payload: dict[str, Any], metric: str) -> list[FactSelection]:
    facts = payload.get("facts", {}).get("us-gaap", {}) if isinstance(payload, dict) else {}
    preferred_units = ["shares"] if metric == "shares_outstanding" else ["USD"]
    by_period: dict[str, FactSelection] = {}
    for concept in CONCEPTS[metric]:
        concept_payload = facts.get(concept)
        unit, rows = _unit_payload(concept_payload, preferred_units)
        if not rows:
            continue
        if metric in BALANCE_SHEET_METRICS:
            candidates = rows
        else:
            candidates = [row for row in rows if _is_annual_row(row)]
        for row in candidates:
            fact = _fact_from_row(metric, concept, unit, row)
            if fact:
                existing = by_period.get(fact.period)
                if existing is None or fact.filed > existing.filed:
                    by_period[fact.period] = fact
    selected = list(by_period.values())
    selected.sort(key=lambda item: (item.period, item.filed), reverse=True)
    return selected


def _fact_for_period(series: list[FactSelection], period: str) -> FactSelection | None:
    return next((item for item in series if item.period == period), None)


def _latest_period_from(series_by_metric: dict[str, list[FactSelection]], metrics: set[str]) -> str | None:
    return max((item.period for metric in metrics for item in series_by_metric.get(metric, [])), default=None)


def _aligned_statement_selection(series_by_metric: dict[str, list[FactSelection]]) -> tuple[dict[str, FactSelection | None], str | None, list[str], list[str]]:
    limitations: list[str] = []
    missing_data: list[str] = []
    statement_period = _latest_period_from(series_by_metric, STATEMENT_PERIOD_ANCHOR_METRICS)
    selected: dict[str, FactSelection | None] = {}
    for metric in STATEMENT_METRICS:
        fact = _fact_for_period(series_by_metric.get(metric, []), statement_period or "")
        selected[metric] = fact
        if statement_period and fact is None:
            if metric == "capex":
                missing_data.append("capex for latest aligned fiscal year")
            else:
                missing_data.append(f"{metric} for latest aligned fiscal year")
            if series_by_metric.get(metric):
                limitations.append(f"SEC Companyfacts {metric} exists for another fiscal period and was not mixed with {statement_period}.")
    if statement_period and selected.get("revenue") is None:
        limitations.append("SEC Companyfacts latest statement period lacks aligned revenue; revenue-derived metrics require period-alignment review.")
    return selected, statement_period, limitations, missing_data


def _aligned_balance_sheet_selection(series_by_metric: dict[str, list[FactSelection]]) -> tuple[dict[str, FactSelection | None], str | None, list[str], list[str]]:
    limitations: list[str] = []
    missing_data: list[str] = []
    balance_period = _latest_period_from(series_by_metric, BALANCE_SHEET_METRICS)
    selected: dict[str, FactSelection | None] = {}
    for metric in BALANCE_SHEET_METRICS:
        fact = _fact_for_period(series_by_metric.get(metric, []), balance_period or "")
        selected[metric] = fact
        if balance_period and fact is None and series_by_metric.get(metric):
            limitations.append(f"SEC Companyfacts {metric} uses a different balance sheet period and was not mixed with {balance_period}.")
            missing_data.append(f"{metric} for latest aligned balance sheet period")
    return selected, balance_period, limitations, missing_data


def _pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator * 100, 4)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator, 4)


def _yoy(series: list[FactSelection]) -> float | None:
    if len(series) < 2 or series[1].value == 0:
        return None
    return round((series[0].value - series[1].value) / abs(series[1].value) * 100, 4)


def _cagr(series: list[FactSelection]) -> float | None:
    if len(series) < 4 or series[0].value <= 0 or series[3].value <= 0:
        return None
    return round(((series[0].value / series[3].value) ** (1 / 3) - 1) * 100, 4)


def _margin_series(metric_series: list[FactSelection], revenue_series: list[FactSelection]) -> list[float]:
    values: list[float] = []
    for metric_fact in metric_series:
        revenue_fact = _fact_for_period(revenue_series, metric_fact.period)
        value = _pct(metric_fact.value, revenue_fact.value if revenue_fact else None)
        if value is not None and value <= 100:
            values.append(value)
    return values


def _trend_pct(metric_series: list[FactSelection], revenue_series: list[FactSelection]) -> float | None:
    margins = _margin_series(metric_series, revenue_series)
    if len(margins) < 2:
        return None
    return round(margins[0] - margins[-1], 4)


def _fcf_margin_series(ocf_series: list[FactSelection], capex_series: list[FactSelection], revenue_series: list[FactSelection]) -> list[float]:
    values: list[float] = []
    for ocf_fact in ocf_series:
        capex_fact = _fact_for_period(capex_series, ocf_fact.period)
        revenue_fact = _fact_for_period(revenue_series, ocf_fact.period)
        if capex_fact is None or revenue_fact is None:
            continue
        value = _pct(ocf_fact.value - capex_fact.value, revenue_fact.value)
        if value is not None and value <= 100:
            values.append(value)
    return values


def _fcf_margin_trend_pct(ocf_series: list[FactSelection], capex_series: list[FactSelection], revenue_series: list[FactSelection]) -> float | None:
    margins = _fcf_margin_series(ocf_series, capex_series, revenue_series)
    if len(margins) < 2:
        return None
    return round(margins[0] - margins[-1], 4)


def _invalid_ratio(value: float | None) -> bool:
    return value is not None and value > 100


def parse_companyfacts(ticker: str, cik: str, payload: dict[str, Any], *, source_type: str = "live") -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    facts: dict[str, Any] = {}
    series: dict[str, list[dict[str, Any]]] = {}
    missing_data: list[str] = []
    limitations: list[str] = [LIMITATION]
    selected: dict[str, FactSelection | None] = {}
    selected_series: dict[str, list[FactSelection]] = {}
    for metric in CONCEPTS:
        metric_series = _facts_for_metric(payload, metric)
        selected_series[metric] = metric_series
        series[metric] = [item.to_public_dict() for item in metric_series[:4]]
        if not metric_series:
            missing = f"SEC Companyfacts concept unavailable for {metric}"
            missing_data.append(missing)
    statement_selected, statement_period, statement_limitations, statement_missing = _aligned_statement_selection(selected_series)
    balance_selected, balance_period, balance_limitations, balance_missing = _aligned_balance_sheet_selection(selected_series)
    selected.update(statement_selected)
    selected.update(balance_selected)
    limitations.extend(statement_limitations)
    limitations.extend(balance_limitations)
    missing_data.extend(statement_missing)
    missing_data.extend(balance_missing)
    for metric in CONCEPTS:
        fact = selected.get(metric)
        facts[metric] = fact.to_public_dict() if fact else None
    revenue = selected.get("revenue")
    gross_profit = selected.get("gross_profit")
    operating_income = selected.get("operating_income")
    net_income = selected.get("net_income")
    rd_expense = selected.get("research_and_development_expense")
    ocf = selected.get("operating_cash_flow")
    capex = selected.get("capex")
    cash = selected.get("cash_and_equivalents")
    debt = selected.get("total_debt")
    equity = selected.get("stockholders_equity")
    receivables = selected.get("accounts_receivable")
    inventory = selected.get("inventory")
    shares_series = selected_series.get("shares_outstanding", [])
    share_dilution = None
    if len(shares_series) >= 4 and shares_series[3].value > 0:
        share_dilution = round((shares_series[0].value - shares_series[3].value) / shares_series[3].value * 100, 4)
    elif selected.get("shares_outstanding") is None:
        missing_data.append("SEC Companyfacts reliable shares series unavailable; share dilution not inferred.")
    fcf = round(ocf.value - capex.value, 6) if ocf and capex and ocf.period == capex.period else None
    if ocf and capex and ocf.period != capex.period:
        missing_data.append("capex for latest aligned fiscal year")
        limitations.append("SEC Companyfacts CapEx period does not align with OCF; FCF was not calculated.")
    if ocf and capex is None and selected_series.get("capex"):
        limitations.append("SEC Companyfacts CapEx is available only for a different fiscal year; FCF was not calculated.")
    revenue_comparable_to_balance = bool(revenue and balance_period and revenue.period == balance_period)
    if revenue and balance_period and revenue.period != balance_period:
        limitations.append("SEC Companyfacts balance sheet period differs from aligned revenue period; revenue-to-balance-sheet ratios were not calculated.")
    invalid_derived_metrics: dict[str, str] = {}
    derived_metrics = {
        "revenue_yoy_growth_pct": _yoy(selected_series.get("revenue", [])),
        "revenue_3y_cagr_pct": _cagr(selected_series.get("revenue", [])),
        "gross_margin_pct": _pct(gross_profit.value if gross_profit and revenue and gross_profit.period == revenue.period else None, revenue.value if revenue else None),
        "operating_margin_pct": _pct(operating_income.value if operating_income and revenue and operating_income.period == revenue.period else None, revenue.value if revenue else None),
        "net_income_margin_pct": _pct(net_income.value if net_income and revenue and net_income.period == revenue.period else None, revenue.value if revenue else None),
        "rd_to_revenue_pct": _pct(rd_expense.value if rd_expense and revenue and rd_expense.period == revenue.period else None, revenue.value if revenue else None),
        "rd_to_revenue_trend_pct": _trend_pct(selected_series.get("research_and_development_expense", []), selected_series.get("revenue", [])),
        "gross_margin_trend_pct": _trend_pct(selected_series.get("gross_profit", []), selected_series.get("revenue", [])),
        "operating_margin_trend_pct": _trend_pct(selected_series.get("operating_income", []), selected_series.get("revenue", [])),
        "ocf_margin_pct": _pct(ocf.value if ocf and revenue and ocf.period == revenue.period else None, revenue.value if revenue else None),
        "capex_as_pct_of_ocf": _pct(capex.value if capex and ocf and capex.period == ocf.period else None, ocf.value if ocf else None),
        "fcf": fcf,
        "fcf_margin_pct": _pct(fcf if fcf is not None and revenue and ocf and ocf.period == revenue.period else None, revenue.value if revenue else None),
        "fcf_margin_trend_pct": _fcf_margin_trend_pct(selected_series.get("operating_cash_flow", []), selected_series.get("capex", []), selected_series.get("revenue", [])),
        "receivables_to_revenue_pct": _pct(receivables.value if receivables and revenue_comparable_to_balance else None, revenue.value if revenue else None),
        "inventory_to_revenue_pct": _pct(inventory.value if inventory and revenue_comparable_to_balance else None, revenue.value if revenue else None),
        "debt_to_equity": _ratio(debt.value if debt else None, equity.value if equity else None),
        "net_cash_or_debt": round((cash.value if cash else 0) - (debt.value if debt else 0), 6) if cash or debt else None,
        "share_dilution_3y_pct": share_dilution,
    }
    for metric in ["gross_margin_pct", "operating_margin_pct", "net_income_margin_pct", "rd_to_revenue_pct", "fcf_margin_pct"]:
        if _invalid_ratio(derived_metrics.get(metric)):
            derived_metrics[metric] = None
            invalid_derived_metrics[metric] = "invalid_period_alignment"
            missing_data.append(f"{metric}: invalid_period_alignment")
            limitations.append(f"SEC Companyfacts {metric} exceeded 100%; metric was invalidated for period-alignment review.")
    if ocf and (capex is None or capex.period != ocf.period):
        invalid_derived_metrics.setdefault("fcf", "invalid_period_alignment")
        invalid_derived_metrics.setdefault("fcf_margin_pct", "invalid_period_alignment")
        invalid_derived_metrics.setdefault("capex_as_pct_of_ocf", "invalid_period_alignment")
    if revenue is None:
        for metric in ["revenue_yoy_growth_pct", "revenue_3y_cagr_pct", "gross_margin_pct", "operating_margin_pct", "net_income_margin_pct", "rd_to_revenue_pct", "rd_to_revenue_trend_pct", "gross_margin_trend_pct", "operating_margin_trend_pct", "ocf_margin_pct", "fcf_margin_pct", "fcf_margin_trend_pct", "receivables_to_revenue_pct", "inventory_to_revenue_pct"]:
            derived_metrics[metric] = None
            if derived_metrics.get(metric) is None:
                invalid_derived_metrics.setdefault(metric, "invalid_period_alignment")
    if rd_expense is None and selected_series.get("research_and_development_expense"):
        invalid_derived_metrics.setdefault("rd_to_revenue_pct", "invalid_period_alignment")
    latest_filing_date = max((fact.filed for fact in selected.values() if fact and fact.filed), default=None)
    latest_report_period = max((fact.period for fact in selected.values() if fact and fact.period), default=None)
    fetched_at = datetime.now(timezone.utc).isoformat()
    source_status = build_source_status(
        {
            "source_type": source_type,
            "provider": PROVIDER,
            "source_date": latest_filing_date or latest_report_period or "",
            "fetched_at": fetched_at,
            "fallback_used": False,
            "limitations": sorted(set(limitations)),
            "missing_data": sorted(set(missing_data)),
        },
        freshness_window=COMPANY_FILING_FRESHNESS_WINDOW,
    ).model_dump(mode="json")
    return {
        "ticker": normalized_ticker,
        "cik": cik10(cik),
        "parser_version": PARSER_VERSION,
        "latest_filing_date": latest_filing_date,
        "latest_report_period": latest_report_period,
        "facts": facts,
        "fact_series": series,
        "derived_metrics": derived_metrics,
        "invalid_derived_metrics": invalid_derived_metrics,
        "aligned_statement_period": statement_period,
        "aligned_balance_sheet_period": balance_period,
        "source_type": source_type,
        "provider": PROVIDER,
        "source_date": latest_filing_date or latest_report_period or "",
        "fetched_at": fetched_at,
        "source_status": source_status,
        "limitations": sorted(set(limitations)),
        "missing_data": sorted(set(missing_data)),
    }


def unavailable_companyfacts(ticker: str, reason: str) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    missing = ["SEC Companyfacts CIK mapping unavailable"] if "CIK" in reason else ["SEC Companyfacts filing-backed facts"]
    source_status = build_source_status(
        {
            "source_type": "fallback" if "failed" in reason.lower() else "unknown",
            "provider": PROVIDER,
            "source_date": "",
            "fallback_used": "failed" in reason.lower(),
            "fallback_reason": SAFE_FALLBACK_REASON if "failed" in reason.lower() else None,
            "limitations": [LIMITATION],
            "missing_data": missing,
        },
        freshness_window=COMPANY_FILING_FRESHNESS_WINDOW,
    ).model_dump(mode="json")
    return {
        "ticker": normalized_ticker,
        "cik": None,
        "parser_version": PARSER_VERSION,
        "latest_filing_date": None,
        "latest_report_period": None,
        "facts": {metric: None for metric in CONCEPTS},
        "fact_series": {metric: [] for metric in CONCEPTS},
        "derived_metrics": {key: None for key in [
            "revenue_yoy_growth_pct", "revenue_3y_cagr_pct", "gross_margin_pct", "operating_margin_pct",
            "net_income_margin_pct", "rd_to_revenue_pct", "rd_to_revenue_trend_pct", "gross_margin_trend_pct",
            "operating_margin_trend_pct", "ocf_margin_pct", "capex_as_pct_of_ocf", "fcf", "fcf_margin_pct", "fcf_margin_trend_pct",
            "receivables_to_revenue_pct", "inventory_to_revenue_pct", "debt_to_equity", "net_cash_or_debt",
            "share_dilution_3y_pct",
        ]},
        "invalid_derived_metrics": {},
        "aligned_statement_period": None,
        "aligned_balance_sheet_period": None,
        "source_status": source_status,
        "limitations": [LIMITATION],
        "missing_data": missing,
    }
