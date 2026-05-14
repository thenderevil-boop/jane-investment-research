from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.api import routes
from backend.app.main import app
from backend.app.middleware.safety_filter import SafetyViolationError, check_safety
from backend.app.pipelines.mock_pipeline import build_daily_report
from backend.app.raw_store import repository

client = TestClient(app)


def test_safety_filter_detects_direct_trading_instruction_phrases() -> None:
    unsafe_payloads = [
        {"message": "strong buy"},
        {"message": "buy now"},
        {"message": "must buy"},
        {"message": "sell now"},
        {"message": "must sell"},
        {"message": "liquidate"},
        {"message": "exit position"},
        {"message": "enter position"},
        {"message": "買進"},
        {"message": "賣出"},
        {"message": "持有"},
        {"message": "出清"},
        {"message": "進場"},
        {"message": "離場"},
        {"message": "必買"},
    ]
    for payload in unsafe_payloads:
        with pytest.raises(SafetyViolationError):
            check_safety(payload)


def test_safety_filter_allows_legitimate_research_phrases() -> None:
    check_safety(
        {
            "phrases": [
                "insider buying",
                "insider selling",
                "buy transaction",
                "sell-side analyst",
                "net insider buy value",
            ]
        }
    )


def test_daily_report_latest_passes_safety_check() -> None:
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    check_safety(response.json())


def test_analyze_stock_passes_safety_check() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200
    check_safety(response.json())


def test_daily_report_returns_internal_safe_error_on_safety_violation(monkeypatch: pytest.MonkeyPatch) -> None:
    def unsafe_report():
        report = build_daily_report()
        report.risk_notes.append("buy now")
        return report

    monkeypatch.setattr(routes.config, "DAILY_REPORT_READ_MODE", "compute")
    monkeypatch.setattr(routes, "build_daily_report", unsafe_report)
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "error": "internal_safety_filter_blocked_response",
            "not_investment_advice": True,
        }
    }


def test_raw_store_repository_mock_functions_return_valid_mock_data() -> None:
    assert repository.read_market_data()["vix"] > 0
    assert repository.read_macro_data()["cpi_yoy"] >= 0
    assert repository.read_company_fundamentals("NVDA")["company_name"] == "NVIDIA Corporation"
    assert repository.read_sec_filings("NVDA")["institutional_13f"]
    assert repository.read_news_mentions()
    assert repository.read_theme_data()
