from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


LIMITATION = "Yfinance company data is suitable for MVP research reference only and may be delayed, incomplete, or unavailable."


class CompanyDataFetchError(RuntimeError):
    """Raised when yfinance cannot provide usable company profile or fundamentals data."""


def _load_yfinance():
    try:
        import yfinance as yf  # type: ignore
    except ImportError as exc:
        raise CompanyDataFetchError("yfinance is not installed.") from exc
    return yf


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if hasattr(value, "item"):
            value = value.item()
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _first_number(*values: Any) -> float | None:
    for value in values:
        parsed = _as_float(value)
        if parsed is not None:
            return parsed
    return None


def _get_row(statement: Any, names: list[str]) -> list[float]:
    if statement is None or getattr(statement, "empty", True):
        return []
    for name in names:
        try:
            if name in statement.index:
                row = statement.loc[name]
                values = [_as_float(value) for value in row.tolist()]
                return [value for value in values if value is not None]
        except Exception:
            continue
    return []


def _latest(values: list[float]) -> float | None:
    return values[0] if values else None


def _sum_recent(values: list[float], count: int = 4) -> float | None:
    if not values:
        return None
    return round(sum(values[:count]), 6)


def _pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator * 100, 4)


def _fraction_to_pct(value: Any) -> float | None:
    parsed = _as_float(value)
    if parsed is None:
        return None
    return round(parsed * 100, 4)


def _yoy(latest: float | None, prior: float | None) -> float | None:
    if latest is None or prior in (None, 0):
        return None
    return round((latest - prior) / abs(prior) * 100, 4)


def _cagr(latest: float | None, old: float | None, years: int) -> float | None:
    if latest is None or old is None or latest <= 0 or old <= 0 or years <= 0:
        return None
    return round(((latest / old) ** (1 / years) - 1) * 100, 4)


def _period_label(statement: Any) -> str | None:
    columns = getattr(statement, "columns", None)
    if columns is None or len(columns) == 0:
        return None
    return str(columns[0])[:10]


def _normalize_profile(ticker: str, info: dict[str, Any], fast_info: Any) -> dict[str, Any]:
    current_price = _first_number(
        getattr(fast_info, "last_price", None),
        info.get("currentPrice"),
        info.get("regularMarketPrice"),
        info.get("previousClose"),
    )
    missing_data = [
        field
        for field, value in {
            "company_name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "exchange": info.get("exchange") or info.get("fullExchangeName"),
            "currency": info.get("currency") or getattr(fast_info, "currency", None),
            "market_cap": _first_number(info.get("marketCap"), getattr(fast_info, "market_cap", None)),
            "enterprise_value": _as_float(info.get("enterpriseValue")),
            "shares_outstanding": _first_number(info.get("sharesOutstanding"), getattr(fast_info, "shares", None)),
            "current_price": current_price,
        }.items()
        if value in (None, "")
    ]
    return {
        "ticker": ticker,
        "company_name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market": "US",
        "exchange": info.get("exchange") or info.get("fullExchangeName"),
        "currency": info.get("currency") or getattr(fast_info, "currency", None),
        "website": info.get("website"),
        "country": info.get("country"),
        "market_cap": _first_number(info.get("marketCap"), getattr(fast_info, "market_cap", None)),
        "enterprise_value": _as_float(info.get("enterpriseValue")),
        "shares_outstanding": _first_number(info.get("sharesOutstanding"), getattr(fast_info, "shares", None)),
        "current_price": current_price,
        "source": ["yfinance"],
        "source_type": "live",
        "provider": "yfinance",
        "source_date": datetime.now(timezone.utc).date().isoformat(),
        "limitations": [LIMITATION],
        "missing_data": missing_data,
    }


def _normalize_fundamentals(ticker: str, info: dict[str, Any], ticker_obj: Any) -> dict[str, Any]:
    quarterly_financials = getattr(ticker_obj, "quarterly_financials", None)
    annual_financials = getattr(ticker_obj, "financials", None)
    quarterly_cashflow = getattr(ticker_obj, "quarterly_cashflow", None)
    annual_cashflow = getattr(ticker_obj, "cashflow", None)
    balance_sheet = getattr(ticker_obj, "balance_sheet", None)

    quarterly_revenue = _get_row(quarterly_financials, ["Total Revenue", "Operating Revenue"])
    annual_revenue = _get_row(annual_financials, ["Total Revenue", "Operating Revenue"])
    quarterly_gross_profit = _get_row(quarterly_financials, ["Gross Profit"])
    quarterly_operating_income = _get_row(quarterly_financials, ["Operating Income", "Operating Income or Loss"])
    quarterly_net_income = _get_row(quarterly_financials, ["Net Income", "Net Income Common Stockholders"])
    quarterly_rd = _get_row(quarterly_financials, ["Research And Development", "Research Development"])
    operating_cashflow = _get_row(quarterly_cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    capex = _get_row(quarterly_cashflow, ["Capital Expenditure", "Capital Expenditures"])
    if not operating_cashflow:
        operating_cashflow = _get_row(annual_cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    if not capex:
        capex = _get_row(annual_cashflow, ["Capital Expenditure", "Capital Expenditures"])
    if not quarterly_net_income:
        quarterly_net_income = _get_row(annual_financials, ["Net Income", "Net Income Common Stockholders"])
    if not quarterly_rd:
        quarterly_rd = _get_row(annual_financials, ["Research And Development", "Research Development"])

    revenue_ttm = _first_number(info.get("totalRevenue"), _sum_recent(quarterly_revenue), _latest(annual_revenue))
    latest_quarter_revenue = _latest(quarterly_revenue)
    prior_year_quarter_revenue = quarterly_revenue[4] if len(quarterly_revenue) > 4 else None
    revenue_yoy = _first_number(
        _fraction_to_pct(info.get("revenueGrowth")),
        _yoy(latest_quarter_revenue, prior_year_quarter_revenue),
    )
    revenue_3y_cagr = _cagr(_latest(annual_revenue), annual_revenue[3] if len(annual_revenue) > 3 else None, 3)
    gross_margin = _first_number(
        _fraction_to_pct(info.get("grossMargins")),
        _pct(_sum_recent(quarterly_gross_profit), revenue_ttm),
    )
    operating_margin = _first_number(
        _fraction_to_pct(info.get("operatingMargins")),
        _pct(_sum_recent(quarterly_operating_income), revenue_ttm),
    )
    operating_cashflow_ttm = _sum_recent(operating_cashflow)
    capex_ttm = _sum_recent(capex)
    free_cash_flow_ttm = _first_number(
        info.get("freeCashflow"),
        None if operating_cashflow_ttm is None else operating_cashflow_ttm + (capex_ttm or 0),
    )
    cash_values = _get_row(balance_sheet, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
    debt_values = _get_row(balance_sheet, ["Total Debt", "Long Term Debt And Capital Lease Obligation", "Long Term Debt"])
    equity_values = _get_row(balance_sheet, ["Stockholders Equity", "Total Stockholder Equity"])
    receivable_values = _get_row(balance_sheet, ["Accounts Receivable", "Net Receivables"])
    inventory_values = _get_row(balance_sheet, ["Inventory"])
    cash = _first_number(info.get("totalCash"), _latest(cash_values))
    debt = _first_number(info.get("totalDebt"), _latest(debt_values))
    equity = _latest(equity_values)
    net_income_ttm = _sum_recent(quarterly_net_income)
    rd_expense_ttm = _sum_recent(quarterly_rd)
    receivables = _latest(receivable_values)
    inventory = _latest(inventory_values)
    shares = _as_float(info.get("sharesOutstanding"))

    metrics = {
        "ticker": ticker,
        "period": "ttm" if revenue_ttm is not None else "latest_fiscal_year",
        "latest_fiscal_year": _period_label(annual_financials),
        "latest_quarter": _period_label(quarterly_financials),
        "revenue_ttm": revenue_ttm,
        "revenue_yoy_growth_pct": revenue_yoy,
        "revenue_3y_cagr_pct": revenue_3y_cagr,
        "gross_margin_pct": gross_margin,
        "operating_margin_pct": operating_margin,
        "net_income_ttm": net_income_ttm,
        "net_income_margin_pct": _pct(net_income_ttm, revenue_ttm),
        "operating_cash_flow_ttm": operating_cashflow_ttm,
        "capex_ttm": capex_ttm,
        "free_cash_flow_ttm": free_cash_flow_ttm,
        "free_cash_flow_margin_pct": _pct(free_cash_flow_ttm, revenue_ttm),
        "rd_expense_ttm": rd_expense_ttm,
        "rd_to_revenue_pct": _pct(rd_expense_ttm, revenue_ttm),
        "short_ratio": _as_float(info.get("shortRatio")),
        "short_percent_of_float": _fraction_to_pct(info.get("shortPercentOfFloat")),
        "held_percent_insiders": _fraction_to_pct(info.get("heldPercentInsiders")),
        "heldPercentInsiders": _as_float(info.get("heldPercentInsiders")),
        "shares_short": _as_float(info.get("sharesShort")),
        "shares_short_prior_month": _as_float(info.get("sharesShortPriorMonth")),
        "cash_and_equivalents": cash,
        "total_debt": debt,
        "net_cash_or_debt": round((cash or 0) - (debt or 0), 6) if cash is not None or debt is not None else None,
        "debt_to_equity": _first_number(info.get("debtToEquity"), _pct(debt, equity)),
        "accounts_receivable": receivables,
        "receivables_to_revenue_pct": _pct(receivables, revenue_ttm),
        "inventory": inventory,
        "inventory_to_revenue_pct": _pct(inventory, revenue_ttm),
        "shares_outstanding": shares,
        "share_dilution_3y_pct": None,
    }
    required = [
        "revenue_ttm",
        "revenue_yoy_growth_pct",
        "gross_margin_pct",
        "free_cash_flow_ttm",
        "cash_and_equivalents",
        "total_debt",
    ]
    missing_data = [field for field in required if metrics.get(field) is None]
    return {
        **metrics,
        "source": ["yfinance"],
        "source_type": "live",
        "provider": "yfinance",
        "source_date": datetime.now(timezone.utc).date().isoformat(),
        "limitations": [LIMITATION, "Yfinance fundamentals may combine company-reported values with provider-normalized fields."],
        "missing_data": missing_data,
    }


def fetch_company_profile(ticker: str) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise CompanyDataFetchError("Ticker is required.")
    yf = _load_yfinance()
    ticker_obj = yf.Ticker(normalized_ticker)
    info = ticker_obj.info or {}
    if not info:
        raise CompanyDataFetchError(f"No company profile returned for {normalized_ticker}.")
    return _normalize_profile(normalized_ticker, info, getattr(ticker_obj, "fast_info", None))


def fetch_company_fundamentals(ticker: str) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise CompanyDataFetchError("Ticker is required.")
    yf = _load_yfinance()
    ticker_obj = yf.Ticker(normalized_ticker)
    info = ticker_obj.info or {}
    if not info:
        raise CompanyDataFetchError(f"No company fundamentals returned for {normalized_ticker}.")
    return _normalize_fundamentals(normalized_ticker, info, ticker_obj)
