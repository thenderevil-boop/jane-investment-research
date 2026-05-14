from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def test_themes_latest_endpoint_returns_mock_radar() -> None:
    response = client.get("/api/themes/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "US"
    assert payload["not_investment_advice"] is True
    assert payload["themes"]
    assert {"raw_data", "benchmark", "trend", "confidence", "missing_data"}.issubset(payload["themes"][0])
    assert detect_forbidden_language(payload) == []


def test_macro_regime_latest_endpoint_returns_engine_output() -> None:
    response = client.get("/api/macro-regime/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["label"] in {
        "restrictive_or_stress",
        "cautious",
        "neutral_to_constructive",
        "supportive_macro_backdrop",
        "insufficient_data",
    }
    assert payload["components"]
    assert {"raw_data", "derived_metrics", "benchmark", "trend", "source_date"}.issubset(payload)
    assert detect_forbidden_language(payload) == []


def test_raw_data_endpoint_returns_ticker_fixture_snapshot() -> None:
    response = client.get("/api/raw-data/NVDA")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "NVDA"
    assert payload["market"] == "US"
    assert payload["not_investment_advice"] is True
    assert payload["raw_data"]["company_fixture"]["company_name"] == "NVIDIA Corporation"
    assert payload["limitations"]
    assert detect_forbidden_language(payload) == []


def test_signals_endpoint_returns_stock_signal_summary() -> None:
    response = client.get("/api/signals/NVDA")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "NVDA"
    assert payload["market"] == "US"
    assert payload["not_investment_advice"] is True
    for key in [
        "leadership_score",
        "market_timing_context",
        "overheat_risk",
        "smart_money",
        "financial_quality",
        "valuation_context",
    ]:
        assert key in payload
        assert "confidence" in payload[key]
    assert payload["missing_data"]
    assert detect_forbidden_language(payload) == []
