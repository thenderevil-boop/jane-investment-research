from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.reports.stock_analysis import MOCK_LEADERSHIP_CONFIDENCE_CAP
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def walk_source_types(value):
    if isinstance(value, dict):
        if value.get("source_type") == "mixed":
            raise AssertionError("source_type must not use mixed")
        for child in value.values():
            walk_source_types(child)
    elif isinstance(value, list):
        for child in value:
            walk_source_types(child)


def test_analyze_stock_is_primary_ticker_validation_shape() -> None:
    response = client.post(
        "/api/analyze-stock",
        json={
            "ticker": "NVDA",
            "market": "US",
            "research_context": {
                "theme": "AI infrastructure",
                "user_reason": "External trend research",
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["ticker"] == "NVDA"
    assert payload["market"] == "US"
    assert payload["analysis_mode"] == "ticker_validation"
    assert payload["not_investment_advice"] is True
    assert payload["research_verdict"]["label"] in {
        "worth_deep_research",
        "watchlist_candidate",
        "insufficient_data",
        "high_risk_context",
    }
    assert payload["macro_regime"]["derived_metrics"]["scoring_model"]["version"] == "macro_v12_5"
    assert payload["macro_regime"]["macro_score_explanation"]["scoring_model_version"] == "macro_v12_5"
    assert payload["jane_reference_conditions"]["affects_score"] is False
    assert all(condition["score_contribution_allowed"] is False for condition in payload["jane_reference_conditions"]["conditions"])
    assert "insider_activity" in payload
    assert payload["insider_activity"]["raw_data"]["transactions"] is not None
    assert "institutional_13f" in payload
    assert payload["institutional_13f"]["raw_data"]["portfolio_summary"] is not None
    assert payload["smart_money"]["raw_data"]["institutional_13f"]["target_matches"] is not None
    assert payload["leadership_score"]["source_status"]["source_type"] == "mock"
    assert payload["research_verdict"]["confidence"] <= MOCK_LEADERSHIP_CONFIDENCE_CAP
    assert "Mock evidence limits confidence." in payload["research_verdict"]["summary"]
    assert any("Mock evidence limits analyze-stock confidence" in item for item in payload["data_quality"]["limitations"])
    assert "future_themes" not in payload
    assert detect_forbidden_language(payload) == []
    walk_source_types(payload)


def test_excluded_macro_indicators_do_not_affect_analyze_stock_score() -> None:
    payload = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    scoring_model = payload["macro_regime"]["derived_metrics"]["scoring_model"]
    contributions = payload["macro_regime"]["derived_metrics"]["component_contributions"]
    contribution_names = {item["name"] for item in contributions}
    excluded = {item["name"]: item for item in scoring_model["excluded_indicators"]}

    assert scoring_model["total_weight"] == 100
    assert excluded["ism_manufacturing_pmi"]["weight"] == 0
    assert excluded["ism_manufacturing_pmi"]["affects_score"] is False
    assert excluded["cnn_fear_greed"]["weight"] == 0
    assert excluded["cnn_fear_greed"]["affects_score"] is False
    assert "ism_manufacturing_pmi" not in contribution_names
    assert "cnn_fear_greed" not in contribution_names
    assert "mock_context_score" not in contribution_names

    text = json.dumps(payload, sort_keys=True).lower()
    assert '"source_type": "mixed"' not in text
