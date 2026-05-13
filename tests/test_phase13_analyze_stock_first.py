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
    assert payload["leadership_score"]["deprecated_by"] == "jane_company_quality"
    assert payload["leadership_score"]["affects_score"] is False
    assert "jane_company_quality" in payload
    assert "financial_statement_signals" in payload
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


def test_phase14_analyze_stock_composition_layers() -> None:
    payload = client.post(
        "/api/analyze-stock",
        json={
            "ticker": "NVDA",
            "market": "US",
            "research_context": {
                "theme": "AI infrastructure",
                "user_reason": "External trend research",
            },
        },
    ).json()

    summary = payload["candidate_validation_summary"]
    assert summary["research_priority"] in {"worth_deep_research", "watchlist_candidate", "insufficient_data", "high_risk_context"}
    assert isinstance(summary["score"], (int, float))
    assert isinstance(summary["confidence"], (int, float))
    for key in ["primary_strengths", "primary_risks", "missing_or_mock_evidence", "next_manual_checks"]:
        assert isinstance(summary[key], list)
        assert summary[key]
    assert "jane company quality" in summary["overall_summary"].lower()

    matrix = {item["category"]: item for item in payload["evidence_matrix"]}
    for category in ["macro_environment", "company_profile", "jane_company_quality", "financial_statement_signals", "legacy_leadership_score", "smart_money", "insider_activity", "institutional_13f"]:
        assert category in matrix
        assert matrix[category]["summary"]
        assert isinstance(matrix[category]["key_evidence"], list)
    macro_scoring = payload["macro_regime"]["macro_data_quality"]["scoring"]
    if macro_scoring["fallback_active_components"] or macro_scoring["active_available_weight_pct"] <= 0:
        assert matrix["macro_environment"]["source_quality"] == "mixed_with_fallback"
    else:
        assert matrix["macro_environment"]["source_quality"] == "derived_live"
    assert matrix["legacy_leadership_score"]["source_quality"] == "mock_only"

    quality = payload["data_quality_summary"]
    assert quality["source_quality_grade"] in {"A", "B", "C", "D"}
    assert "legacy_leadership_score" in quality["mock_evidence_categories"]
    assert "insufficient_evidence_categories" in quality
    assert "company_quality" in quality
    assert "company_profile" in quality["mock_evidence_categories"]
    assert "smart_money" in quality["fallback_evidence_categories"]
    assert "ISM Manufacturing PMI" in quality["excluded_from_scoring"]
    assert "CNN Fear & Greed" in quality["excluded_from_scoring"]

    verdict = payload["research_verdict"]
    assert "confidence_factors" in verdict
    assert verdict["confidence"] <= MOCK_LEADERSHIP_CONFIDENCE_CAP

    drivers = payload["score_driver_breakdown"]
    assert drivers["final_score"] == verdict["score"]
    driver_text = json.dumps(drivers).lower()
    assert "legacy leadership evidence remains mock-only" in driver_text
    assert not any(
        driver["category"] == "leadership_score" and driver["source_quality"] == "mock_only"
        for driver in drivers["positive_drivers"]
    )
    thirteen_f = payload["institutional_13f"]["candidate_specific_evidence"]
    if thirteen_f.get("matched_in_13f") is False:
        assert thirteen_f["score_contribution_allowed"] is False
        assert thirteen_f["interpretation_label"] == "no_reported_13f_position_observed"
    if thirteen_f.get("score_contribution_allowed") is False:
        assert not any(driver["category"] == "institutional_13f" for driver in drivers["positive_drivers"])
    assert "negative trading signal" not in json.dumps(payload["institutional_13f"]).lower()

    assert payload["insider_activity"]["source_quality"] in {"cached_live", "mixed_with_fallback", "mock_only", "insufficient"}
    if payload["insider_activity"]["source_quality"] in {"mixed_with_fallback", "cached_live"}:
        assert "limited" in payload["insider_activity"]["summary"].lower() or "cached" in payload["insider_activity"]["summary"].lower()

    checks = payload["next_manual_checks"]
    assert any(item["priority"] == "high" and item["area"] in {"source_quality", "company_fundamentals"} for item in checks)
    assert payload["not_investment_advice"] is True
    assert detect_forbidden_language(payload) == []
    walk_source_types(payload)
