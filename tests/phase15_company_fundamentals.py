from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import company_profile
from backend.app.main import app
from backend.app.raw_store import repository
from backend.app.reports.stock_analysis import _build_valuation_context
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def workspace_tmp_dir() -> Path:
    path = Path("backend/raw_store/cache/test_phase15") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def live_profile(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "company_name": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors",
        "market": "US",
        "exchange": "NMS",
        "currency": "USD",
        "website": "https://www.nvidia.com",
        "country": "United States",
        "market_cap": 3_000_000_000_000,
        "enterprise_value": 2_990_000_000_000,
        "shares_outstanding": 24_000_000_000,
        "current_price": 125,
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": "2026-05-01",
        "limitations": [],
        "missing_data": [],
    }


def live_fundamentals(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "period": "ttm",
        "latest_fiscal_year": "2026-01-31",
        "latest_quarter": "2026-04-30",
        "revenue_ttm": 130_000_000_000,
        "revenue_yoy_growth_pct": 80.2,
        "revenue_3y_cagr_pct": 54.4,
        "gross_margin_pct": 71.5,
        "operating_margin_pct": 60.1,
        "free_cash_flow_ttm": 60_000_000_000,
        "free_cash_flow_margin_pct": 46.15,
        "cash_and_equivalents": 45_000_000_000,
        "total_debt": 11_000_000_000,
        "net_cash_or_debt": 34_000_000_000,
        "debt_to_equity": 25.0,
        "shares_outstanding": 24_000_000_000,
        "share_dilution_3y_pct": None,
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": "2026-05-01",
        "limitations": [],
        "missing_data": ["share_dilution_3y_pct"],
    }


class FakeTicker:
    info = {
        "longName": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors",
        "exchange": "NMS",
        "currency": "USD",
        "website": "https://www.nvidia.com",
        "country": "United States",
        "marketCap": 3_000_000_000_000,
        "enterpriseValue": 2_990_000_000_000,
        "sharesOutstanding": 24_000_000_000,
        "currentPrice": 125,
        "totalRevenue": 130_000_000_000,
        "revenueGrowth": 0.802,
        "grossMargins": 0.715,
        "operatingMargins": 0.601,
        "freeCashflow": 60_000_000_000,
        "totalCash": 45_000_000_000,
        "totalDebt": 11_000_000_000,
        "debtToEquity": 25.0,
    }
    fast_info = SimpleNamespace(last_price=125, currency="USD", market_cap=3_000_000_000_000, shares=24_000_000_000)
    quarterly_financials = None
    financials = None
    quarterly_cashflow = None
    cashflow = None
    balance_sheet = None


def test_yfinance_company_profile_adapter_normalizes_fixture(monkeypatch):
    monkeypatch.setattr(company_profile, "_load_yfinance", lambda: SimpleNamespace(Ticker=lambda _ticker: FakeTicker()))

    profile = company_profile.fetch_company_profile("nvda")
    fundamentals = company_profile.fetch_company_fundamentals("nvda")

    assert profile["ticker"] == "NVDA"
    assert profile["company_name"] == "NVIDIA Corporation"
    assert profile["source_type"] == "live"
    assert fundamentals["revenue_ttm"] == 130_000_000_000
    assert fundamentals["revenue_yoy_growth_pct"] == 80.2
    assert fundamentals["gross_margin_pct"] == 71.5
    assert fundamentals["free_cash_flow_ttm"] == 60_000_000_000
    assert fundamentals["cash_and_equivalents"] == 45_000_000_000
    assert fundamentals["total_debt"] == 11_000_000_000


def test_analyze_stock_uses_live_company_profile_and_fundamentals(monkeypatch):
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())
    monkeypatch.setattr(config, "USE_LIVE_COMPANY_DATA", True)
    monkeypatch.setattr(company_profile, "fetch_company_profile", live_profile)
    monkeypatch.setattr(company_profile, "fetch_company_fundamentals", live_fundamentals)

    payload = client.post(
        "/api/analyze-stock",
        json={
            "ticker": "NVDA",
            "market": "US",
            "research_context": {"theme": "AI infrastructure", "user_reason": "External trend research"},
        },
    ).json()

    assert payload["not_investment_advice"] is True
    assert payload["company_profile"]["source_status"]["source_type"] == "live"
    assert payload["company_profile"]["research_context"]["theme"] == "AI infrastructure"
    assert payload["financial_quality"]["raw_data"]["revenue_ttm"] == 130_000_000_000
    assert payload["financial_quality"]["raw_data"]["gross_margin_pct"] == 71.5
    assert payload["valuation_context"]["raw_data"]["price_to_sales_ttm"] == 23.0769
    assert payload["valuation_context"]["raw_data"]["ev_to_sales_ttm"] == 23.0
    matrix = {item["category"]: item for item in payload["evidence_matrix"]}
    assert matrix["company_profile"]["source_quality"] == "live_backed"
    assert matrix["financial_quality"]["source_quality"] == "live_backed"
    assert matrix["valuation_context"]["source_quality"] == "derived_live"
    quality = payload["data_quality_summary"]
    assert "company_profile" not in quality["mock_evidence_categories"]
    assert "financial_quality" not in quality["mock_evidence_categories"]
    assert "legacy_leadership_score" in quality["mock_evidence_categories"]
    assert quality["source_quality_grade"] in {"A", "B", "C"}
    assert "company_profile" not in payload["candidate_validation_summary"]["missing_or_mock_evidence"]
    assert payload["leadership_score"]["source_status"]["source_type"] == "mock"
    assert payload["leadership_score"]["deprecated_by"] == "jane_company_quality"
    assert payload["research_verdict"]["confidence"] <= 0.72
    assert any(driver["category"] == "financial_quality" for driver in payload["score_driver_breakdown"]["positive_drivers"])
    assert detect_forbidden_language(payload) == []


def test_company_profile_fallback_is_labeled(monkeypatch):
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())
    monkeypatch.setattr(config, "USE_LIVE_COMPANY_DATA", True)

    def fail_fetch(_ticker: str):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(company_profile, "fetch_company_profile", fail_fetch)
    payload = repository.get_company_profile("NVDA")

    assert payload["source_status"]["source_type"] == "fallback"
    assert payload["source_status"]["fallback_used"] is True
    assert "live yfinance company profile" in payload["missing_data"]


def test_valuation_metrics_are_null_when_denominator_invalid():
    valuation = _build_valuation_context(
        {**live_profile(), "market_cap": 1000, "enterprise_value": 1200},
        {**live_fundamentals(), "revenue_ttm": 0, "free_cash_flow_ttm": -10},
    )

    raw = valuation.raw_data
    assert raw["price_to_sales_ttm"] is None
    assert raw["ev_to_sales_ttm"] is None
    assert raw["price_to_free_cash_flow_ttm"] is None
    assert raw["ev_to_free_cash_flow_ttm"] is None
    assert valuation.missing_data
