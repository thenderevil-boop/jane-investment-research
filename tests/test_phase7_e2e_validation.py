from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.utils.forbidden_language import detect_forbidden_language, has_forbidden_language

client = TestClient(app)

SCORE_FIELDS = {
    "raw_data",
    "derived_metrics",
    "benchmark",
    "trend",
    "source",
    "source_date",
    "confidence",
    "limitations",
    "missing_data",
}

ALLOWED_LABELS = [
    "favorable_research_environment",
    "watch_for_confirmation",
    "neutral",
    "insufficient_data",
    "normal",
    "elevated_heat",
    "overheated",
    "high_risk_warning",
    "worth_deep_research",
    "risk_warning",
]


def assert_score_contract(score: dict) -> None:
    assert SCORE_FIELDS.issubset(score.keys())
    assert 0 <= score["confidence"] <= 1


def walk_scores(payload):
    if isinstance(payload, dict):
        if SCORE_FIELDS.issubset(payload.keys()):
            yield payload
        for value in payload.values():
            yield from walk_scores(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from walk_scores(item)


def test_daily_report_latest_e2e_schema_contract() -> None:
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    payload = response.json()
    for key in [
        "date",
        "market",
        "macro_regime",
        "crisis",
        "market_timing",
        "overheat_risk",
        "future_themes",
        "stock_candidates",
        "smart_money",
        "risk_notes",
        "missing_data",
        "limitations",
        "not_investment_advice",
    ]:
        assert key in payload
    assert payload["not_investment_advice"] is True
    assert payload["market"] == "US"
    assert payload["date"]
    assert payload["future_themes"]
    assert payload["stock_candidates"]
    assert payload["limitations"]


def test_analyze_stock_e2e_schema_contract() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200
    payload = response.json()
    for key in [
        "ticker",
        "market",
        "company_profile",
        "leadership_score",
        "market_timing_context",
        "overheat_risk",
        "smart_money",
        "financial_quality",
        "valuation_context",
        "risk_flags",
        "missing_data",
        "human_verification_queue",
        "not_investment_advice",
    ]:
        assert key in payload
    assert payload["ticker"] == "NVDA"
    assert payload["not_investment_advice"] is True


def test_every_score_component_has_evidence_contract() -> None:
    daily = client.get("/api/daily-report/latest").json()
    stock = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    scores = list(walk_scores(daily)) + list(walk_scores(stock))
    assert scores
    for score in scores:
        assert_score_contract(score)


def test_forbidden_language_utility_detects_restricted_terms() -> None:
    payload = {"message": "must invest and 進場 are not allowed"}
    detected = detect_forbidden_language(payload)
    assert "must invest" in detected
    assert "進場" in detected


def test_forbidden_language_allows_research_signal_labels() -> None:
    assert has_forbidden_language({"labels": ALLOWED_LABELS}) is False


def test_api_responses_do_not_include_forbidden_language_in_string_values() -> None:
    daily = client.get("/api/daily-report/latest").json()
    stock = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    assert detect_forbidden_language(daily) == []
    assert detect_forbidden_language(stock) == []
