from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.pipelines.mock_pipeline import build_daily_report

client = TestClient(app)

PROHIBITED_PATTERNS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\bliquidate\b",
    r"\bexit all\b",
    r"\bsell half\b",
    r"\bmust invest\b",
    r"\bguaranteed\b",
]

SCORE_FIELDS = {
    "raw_data",
    "source",
    "source_date",
    "derived_metrics",
    "benchmark",
    "trend",
    "confidence",
    "limitations",
    "missing_data",
}


def assert_no_prohibited_language(payload: dict) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    for pattern in PROHIBITED_PATTERNS:
        assert not re.search(pattern, text), pattern


def assert_score_contract(score: dict) -> None:
    assert SCORE_FIELDS.issubset(score.keys())
    assert 0 <= score["confidence"] <= 1


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == "0.1.0"
    assert payload["not_investment_advice"] is True
    assert_no_prohibited_language(payload)


def test_latest_daily_report_schema_and_score_contracts() -> None:
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "US"
    assert payload["not_investment_advice"] is True
    assert payload["missing_data"]
    assert payload["human_verification_queue"]
    for key in [
        "macro_regime",
        "market_timing",
        "overheat_risk",
        "crisis_risk",
        "smart_money_summary",
    ]:
        assert_score_contract(payload[key])
    for theme in payload["future_themes"]:
        assert_score_contract(theme)
    assert_no_prohibited_language(payload)


def test_analyze_stock_schema_and_score_contracts() -> None:
    response = client.post(
        "/api/analyze-stock",
        json={
            "ticker": "nvda",
            "market": "US",
            "period": "3Y",
            "user_context": {
                "friends_asking_about_stock": False,
                "social_discussion_level": "low",
            },
        },
    )
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
        assert_score_contract(payload[key])
    assert payload["missing_data"]
    assert payload["human_verification_queue"]
    assert_no_prohibited_language(payload)


def test_us_market_only_validation() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "2330", "market": "TW"})
    assert response.status_code == 422


def test_daily_pipeline_scenarios(monkeypatch) -> None:
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", False)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", False)
    normal = build_daily_report("normal")
    fearful = build_daily_report("fearful")
    overheated = build_daily_report("overheated")
    assert normal.macro_regime.label == "normal"
    assert fearful.macro_regime.label == "fear_crisis"
    assert fearful.market_timing.score > normal.market_timing.score
    assert overheated.overheat_risk.label in {"overheated", "high_risk_warning"}
    assert normal.missing_data
    assert fearful.human_verification_queue
