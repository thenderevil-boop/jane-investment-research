from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import company_profile
from backend.app.main import app
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def _tmp_cache() -> Path:
    path = Path("backend/raw_store/cache/test_phase16") / uuid4().hex
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


def _live_fundamentals(ticker: str = "NVDA", include_rd: bool = False) -> dict:
    payload = {
        "ticker": ticker,
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
        "accounts_receivable": None,
        "receivables_to_revenue_pct": None,
        "inventory": None,
        "inventory_to_revenue_pct": None,
        "shares_outstanding": 24_000_000_000,
        "share_dilution_3y_pct": None,
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": "2026-05-01",
        "limitations": [],
        "missing_data": ["accounts_receivable", "inventory", "share_dilution_3y_pct"],
    }
    if include_rd:
        payload["rd_expense_ttm"] = 12_000_000_000
        payload["rd_to_revenue_pct"] = 9.23
    return payload


def _walk_no_mixed(value):
    if isinstance(value, dict):
        assert value.get("source_type") != "mixed"
        for child in value.values():
            _walk_no_mixed(child)
    elif isinstance(value, list):
        for child in value:
            _walk_no_mixed(child)


def _payload(monkeypatch, *, include_rd: bool = False, theme: str = "AI infrastructure") -> dict:
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "USE_LIVE_COMPANY_DATA", True)
    monkeypatch.setattr(company_profile, "fetch_company_profile", _live_profile)
    monkeypatch.setattr(company_profile, "fetch_company_fundamentals", lambda ticker: _live_fundamentals(ticker, include_rd=include_rd))
    response = client.post(
        "/api/analyze-stock",
        json={
            "ticker": "NVDA",
            "market": "US",
            "research_context": {"theme": theme, "user_reason": "External trend research"},
        },
    )
    assert response.status_code == 200
    return response.json()


def test_jane_company_quality_phase16_contract(monkeypatch):
    payload = _payload(monkeypatch)
    quality = payload["jane_company_quality"]
    criteria = {item["name"]: item for item in quality["criteria"]}

    assert payload["not_investment_advice"] is True
    assert quality["name"] == "jane_company_quality_score"
    assert len(quality["criteria"]) == 10
    assert criteria["monopoly_power"]["status"] == "insufficient"
    assert criteria["monopoly_power"]["affects_score"] is False
    assert "market share evidence" in criteria["monopoly_power"]["missing_data"]
    assert criteria["mega_trend_fit"]["source_quality"] == "user_context"
    assert criteria["mega_trend_fit"]["affects_score"] is False
    assert criteria["visionary_founder_ceo"]["status"] == "insufficient"
    assert criteria["disruptive_innovation"]["status"] == "insufficient"
    assert criteria["network_effect"]["status"] == "insufficient"
    assert criteria["scalability"]["source_quality"] == "derived_live"
    assert criteria["scalability"]["affects_score"] is True
    assert criteria["continuous_r_and_d"]["status"] == "insufficient"
    assert criteria["financial_statement_quality"]["source_quality"] == "derived_live"
    assert criteria["balance_sheet_strength"]["source_quality"] == "derived_live"
    assert criteria["cash_flow_quality"]["source_quality"] == "derived_live"
    assert detect_forbidden_language(payload) == []
    _walk_no_mixed(payload)


def test_financial_statement_signals_phase16_contract(monkeypatch):
    payload = _payload(monkeypatch)
    signals = {item["name"]: item for item in payload["financial_statement_signals"]["signals"]}

    assert "revenue_growth_quality" in signals
    assert "operating_margin_strength" in signals
    assert "operating_cash_flow_quality" in signals
    assert signals["revenue_growth_quality"]["status"] == "supportive"
    assert signals["operating_margin_strength"]["status"] == "supportive"
    assert signals["operating_cash_flow_quality"]["status"] == "supportive"
    assert signals["receivables_vs_revenue_risk"]["status"] == "insufficient"
    assert signals["inventory_vs_revenue_risk"]["status"] == "insufficient"
    assert signals["capex_vs_ocf_risk"]["status"] in {"supportive", "neutral", "caution"}
    assert signals["share_dilution_risk"]["status"] == "insufficient"


def test_mock_leadership_is_legacy_and_not_positive_driver(monkeypatch):
    payload = _payload(monkeypatch)
    drivers = payload["score_driver_breakdown"]
    driver_text = json.dumps(drivers).lower()

    assert payload["leadership_score"]["deprecated_by"] == "jane_company_quality"
    assert payload["leadership_score"]["affects_score"] is False
    assert payload["leadership_score"]["source_quality"] == "mock_only"
    assert "mock leadership score clears" not in json.dumps(payload).lower()
    assert not any(driver["category"] in {"leadership_score", "legacy_leadership_score"} for driver in drivers["positive_drivers"])
    assert "qualitative_moat_evidence_insufficient" in driver_text
    assert "founder_ceo_evidence_insufficient" in driver_text
    assert payload["research_verdict"]["confidence"] <= 0.80


def test_quality_summary_matrix_and_theme_context(monkeypatch):
    themed = _payload(monkeypatch, theme="AI infrastructure")
    unthemed = _payload(monkeypatch, theme="")

    assert themed["jane_company_quality"]["score"] == unthemed["jane_company_quality"]["score"]
    assert themed["candidate_validation_summary"]["company_assessment"]
    quality = themed["data_quality_summary"]
    assert "company_quality" in quality
    assert "insufficient_evidence_categories" in quality
    assert "monopoly_power" in quality["insufficient_evidence_categories"]
    assert "founder_ceo_evidence" in themed["candidate_validation_summary"]["missing_or_mock_evidence"]
    matrix = {item["category"]: item for item in themed["evidence_matrix"]}
    assert "jane_company_quality" in matrix
    assert "financial_statement_signals" in matrix
    assert matrix["legacy_leadership_score"]["source_quality"] == "mock_only"

