from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def _analyze(payload: dict | None = None) -> dict:
    request = {"ticker": "NVDA", "market": "US"}
    if payload:
        request.update(payload)
    response = client.post("/api/analyze-stock", json=request)
    assert response.status_code == 200
    return response.json()


def test_validation_os_report_is_present_and_research_only() -> None:
    payload = _analyze()
    report = payload["validation_os_report"]

    assert report["ticker"] == "NVDA"
    assert report["not_investment_advice"] is True
    assert report["scoring_note"] == "Validation OS Report is non-scoring and does not change the final research verdict."
    assert report["report_sections"] == [
        "candidate_context",
        "macro_backdrop",
        "jane_quality",
        "evidence_coverage",
        "financial_signals",
        "smart_money",
        "manual_verification",
        "source_quality",
    ]
    assert "validation workflow" in report["executive_summary"]
    assert detect_forbidden_language(report) == []


def test_validation_os_report_summarizes_existing_analyze_stock_outputs() -> None:
    payload = _analyze()
    report = payload["validation_os_report"]
    coverage = payload["jane_criteria_coverage"]

    assert report["research_label"] == payload["research_verdict"]["label"]
    assert report["validation_level"] == payload["validation_quality_summary"]["overall_validation_level"]
    assert report["data_quality_grade"] == payload["data_quality_summary"]["source_quality_grade"]
    assert report["jane_criteria_coverage_summary"]["covered_count"] == coverage["covered_count"]
    assert report["jane_criteria_coverage_summary"]["partial_count"] == coverage["partial_count"]
    assert report["jane_criteria_coverage_summary"]["insufficient_count"] == coverage["insufficient_count"]
    assert report["jane_criteria_coverage_summary"]["coverage_gap_count"] == coverage["partial_count"] + coverage["insufficient_count"]
    assert report["manual_verification_required"] is True
    assert report["top_manual_checks"]
    assert report["source_quality_caveats"]


def test_validation_os_report_prioritizes_jane_coverage_gaps_from_user_evidence() -> None:
    payload = _analyze(
        {
            "qualitative_evidence": [
                {
                    "criterion": "monopoly_power",
                    "criterion_id": 1,
                    "criterion_name": "Market Monopoly / Entry Barrier",
                    "submetric": "switching_cost",
                    "evidence_type": "switching_cost",
                    "summary": "Customer migration requires workflow retraining and data migration.",
                    "source_label": "user research note",
                    "confidence": 0.6,
                    "user_provided": True,
                    "limitations": ["Manual verification required."],
                }
            ]
        }
    )
    report = payload["validation_os_report"]

    assert report["jane_criteria_coverage_summary"]["partial_count"] >= 1
    assert any(gap["criterion_id"] == 1 for gap in report["top_evidence_gaps"])
    gap = next(gap for gap in report["top_evidence_gaps"] if gap["criterion_id"] == 1)
    assert gap["coverage_status"] == "partial"
    assert "switching_cost" not in gap["missing_submetrics"]


def test_validation_os_report_has_no_forbidden_language_or_secret_leakage() -> None:
    payload = _analyze()
    report_text = json.dumps(payload["validation_os_report"])

    assert detect_forbidden_language(payload["validation_os_report"]) == []
    assert "FRED_API_KEY" not in report_text
    assert "SEC_EDGAR_USER_AGENT" not in report_text
    assert "api_key" not in report_text.lower()
    assert payload["not_investment_advice"] is True
