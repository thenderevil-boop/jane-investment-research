from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import company_profile
from backend.app.main import app

client = TestClient(app)


def _tmp_cache() -> Path:
    path = Path("backend/raw_store/cache/test_phase50") / uuid4().hex
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


def _live_fundamentals(
    *,
    held_percent_insiders: float | None = None,
    short_ratio: float | None = None,
    short_percent_of_float: float | None = None,
) -> dict:
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
    if held_percent_insiders is not None:
        payload["held_percent_insiders"] = held_percent_insiders
        payload["heldPercentInsiders"] = held_percent_insiders / 100
    if short_ratio is not None:
        payload["short_ratio"] = short_ratio
        payload["shortRatio"] = short_ratio
    if short_percent_of_float is not None:
        payload["short_percent_of_float"] = short_percent_of_float
        payload["shortPercentOfFloat"] = short_percent_of_float / 100
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


def test_c2_auto_derives_founder_ownership_from_significant_insider_ownership(monkeypatch) -> None:
    payload = _analyze(monkeypatch, _live_fundamentals(held_percent_insiders=12.5))

    row = _coverage_row(payload, 2)
    assert row["coverage_status"] == "partial"
    assert row["evidence_type"] == "financial_proxy"
    assert row["financial_proxy_source"] == "yfinance"
    assert row["source_quality"] == "derived_live"
    assert "founder_ownership" in row["covered_submetrics"]
    assert "founder_is_ceo" in row["missing_submetrics"]
    assert row["requires_human_verification"] is True
    assert row["accepted_evidence_item_count"] >= 1
    assert "Insider ownership" in row["summary"]
    assert "does not confirm founder-operator" in " ".join(row["limitations"])


def test_c2_low_insider_ownership_does_not_cover_founder_ownership(monkeypatch) -> None:
    payload = _analyze(monkeypatch, _live_fundamentals(held_percent_insiders=0.8))

    row = _coverage_row(payload, 2)
    assert row["coverage_status"] == "insufficient"
    assert "founder_ownership" not in row["covered_submetrics"]


def test_c3_high_skepticism_uses_short_ratio_or_percent_thresholds(monkeypatch) -> None:
    payload = _analyze(monkeypatch, _live_fundamentals(short_ratio=12.0, short_percent_of_float=16.0))

    row = _coverage_row(payload, 3)
    assert row["coverage_status"] == "partial"
    assert "short_interest_proxy" in row["covered_submetrics"]
    assert "high_skepticism" in row["summary"]
    assert "Short ratio 12.0x" in row["summary"]
    assert "16.0% of float short" in row["summary"]
    assert "ADR wrapper-level" in " ".join(row["limitations"])


def test_c3_moderate_skepticism_can_use_short_ratio_threshold(monkeypatch) -> None:
    payload = _analyze(monkeypatch, _live_fundamentals(short_ratio=6.0, short_percent_of_float=4.0))

    row = _coverage_row(payload, 3)
    assert row["coverage_status"] == "partial"
    assert "short_interest_proxy" in row["covered_submetrics"]
    assert "moderate_skepticism" in row["summary"]


def test_c3_very_low_short_interest_does_not_inject_proxy(monkeypatch) -> None:
    payload = _analyze(monkeypatch, _live_fundamentals(short_ratio=0.5, short_percent_of_float=2.0))

    row = _coverage_row(payload, 3)
    assert row["coverage_status"] == "insufficient"
    assert "short_interest_proxy" not in row["covered_submetrics"]
