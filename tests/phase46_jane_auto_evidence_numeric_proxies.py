from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import company_profile
from backend.app.main import app

client = TestClient(app)


def _tmp_cache() -> Path:
    path = Path("backend/raw_store/cache/test_phase46") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _live_profile(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "company_name": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors",
        "market": "US",
        "exchange": "NMS",
        "currency": "USD",
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


def _live_fundamentals(*, short_ratio: float | None = None, rd_to_revenue_pct: float | None = None) -> dict:
    payload = {
        "ticker": "NVDA",
        "period": "ttm",
        "latest_fiscal_year": "2026-01-31",
        "latest_quarter": "2026-04-30",
        "revenue_ttm": 130_000_000_000,
        "revenue_yoy_growth_pct": 80.2,
        "revenue_3y_cagr_pct": 54.4,
        "gross_margin_pct": 71.5,
        "operating_margin_pct": 60.1,
        "net_income_ttm": 55_000_000_000,
        "net_income_margin_pct": 42.3,
        "operating_cash_flow_ttm": 64_000_000_000,
        "capex_ttm": -4_000_000_000,
        "free_cash_flow_ttm": 60_000_000_000,
        "free_cash_flow_margin_pct": 46.15,
        "cash_and_equivalents": 45_000_000_000,
        "total_debt": 11_000_000_000,
        "net_cash_or_debt": 34_000_000_000,
        "debt_to_equity": 25.0,
        "shares_outstanding": 24_000_000_000,
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": "2026-05-01",
        "limitations": [],
        "missing_data": [],
    }
    if short_ratio is not None:
        payload["short_ratio"] = short_ratio
        payload["shortRatio"] = short_ratio
    if rd_to_revenue_pct is not None:
        payload["rd_expense_ttm"] = round(payload["revenue_ttm"] * rd_to_revenue_pct / 100)
        payload["rd_to_revenue_pct"] = rd_to_revenue_pct
    return payload


def _analyze(monkeypatch, fundamentals: dict) -> dict:
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "USE_LIVE_COMPANY_DATA", True)
    monkeypatch.setattr(company_profile, "fetch_company_profile", _live_profile)
    monkeypatch.setattr(company_profile, "fetch_company_fundamentals", lambda ticker: fundamentals)
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200
    return response.json()


def _coverage_row(payload: dict, criterion_id: int) -> dict:
    return next(item for item in payload["jane_criteria_coverage"]["criteria"] if item["criterion_id"] == criterion_id)


def _quality_criterion(payload: dict, name: str) -> dict:
    return next(item for item in payload["jane_company_quality"]["criteria"] if item["name"] == name)


def test_c3_auto_derives_from_short_ratio(monkeypatch) -> None:
    payload = _analyze(monkeypatch, _live_fundamentals(short_ratio=12.4))

    row = _coverage_row(payload, 3)
    assert row["evidence_type"] == "financial_proxy"
    assert row["coverage_status"] == "partial"
    assert row["source_quality"] == "derived_live"
    assert "short_interest_proxy" in row["covered_submetrics"]
    assert row["accepted_evidence_item_count"] >= 1
    assert "auto-derived proxy" in " ".join(row["limitations"]).lower()


def test_c3_does_not_cover_when_short_interest_proxy_missing(monkeypatch) -> None:
    payload = _analyze(monkeypatch, _live_fundamentals())

    row = _coverage_row(payload, 3)
    assert row["coverage_status"] == "insufficient"
    assert "short_interest_proxy" not in row["covered_submetrics"]


def test_c5_auto_derives_from_rd_to_revenue(monkeypatch) -> None:
    payload = _analyze(monkeypatch, _live_fundamentals(rd_to_revenue_pct=18.5))

    row = _coverage_row(payload, 5)
    assert row["coverage_status"] == "partial"
    assert row["source_quality"] == "derived_live"
    assert "rd_percent_of_revenue" in row["covered_submetrics"]
    assert row["accepted_evidence_item_count"] >= 1

    rd_quality = _quality_criterion(payload, "continuous_r_and_d")
    assert rd_quality["status"] == "supportive"
    assert rd_quality["source_quality"] == "derived_live"


def test_c5_rd_proxy_can_come_from_fmp_backed_adr_financials(monkeypatch) -> None:
    fundamentals = _live_fundamentals(rd_to_revenue_pct=24.4)
    fundamentals["provider"] = "derived_from_yfinance_and_FMP_financials"
    fundamentals["source_type"] = "derived"
    fundamentals["source"] = ["yfinance", "FMP financial statements"]
    fundamentals["fmp_financial_proxy_used"] = True
    fundamentals["fmp_backed_fields"] = ["rd_expense_ttm", "rd_to_revenue_pct"]

    payload = _analyze(monkeypatch, fundamentals)

    row = _coverage_row(payload, 5)
    assert row["coverage_status"] == "partial"
    assert row["source_quality"] == "derived_from_mixed_sources"
    assert "rd_percent_of_revenue" in row["covered_submetrics"]
