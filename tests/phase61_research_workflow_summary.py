from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.reports.stock_analysis import _build_research_workflow_summary, analyze_stock
from backend.app.schemas.stock_analysis import AnalyzeStockRequest
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


ALLOWED_RESEARCH_STATUSES = {
    "high_conviction_candidate",
    "watchlist_candidate",
    "needs_evidence_before_research",
    "deprioritize_data_gaps",
}


def _base_response():
    return analyze_stock(AnalyzeStockRequest(ticker="NVDA", market="US"))


def _set_coverage(response, covered: int, partial: int) -> None:
    response.jane_criteria_coverage.covered_count = covered
    response.jane_criteria_coverage.partial_count = partial


def test_research_workflow_summary_is_present_and_safe_for_nvda() -> None:
    payload = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    summary = payload["research_workflow_summary"]

    assert summary["version"] == "phase61_v1"
    assert summary["research_status"] in ALLOWED_RESEARCH_STATUSES
    assert summary["not_investment_advice"] is True
    assert len(summary["one_line_summary"]) <= 120
    assert detect_forbidden_language(summary["one_line_summary"]) == []
    assert len(summary["top_3_strengths"]) <= 3
    assert len(summary["top_3_gaps"]) <= 3
    assert len(summary["next_3_research_actions"]) == 3


def test_research_workflow_nvda_phase61_reference_case_is_watchlist() -> None:
    response = _base_response()
    response.research_verdict.score = 45
    response.data_quality_summary.source_quality_grade = "B"
    _set_coverage(response, 3, 3)

    summary = _build_research_workflow_summary(response)

    assert summary["research_status"] == "watchlist_candidate"
    assert summary["confidence"] == "medium"


def test_research_workflow_status_logic_is_deterministic() -> None:
    response = _base_response()

    response.research_verdict.score = 70
    response.data_quality_summary.source_quality_grade = "A"
    _set_coverage(response, 8, 0)
    assert _build_research_workflow_summary(response)["research_status"] == "high_conviction_candidate"

    response.research_verdict.score = 45
    response.data_quality_summary.source_quality_grade = "B"
    _set_coverage(response, 2, 2)
    assert _build_research_workflow_summary(response)["research_status"] == "watchlist_candidate"

    response.research_verdict.score = 55
    response.data_quality_summary.source_quality_grade = "D"
    response.foreign_filer_coverage_diagnostics.is_foreign_filer_or_adr = False
    _set_coverage(response, 4, 0)
    assert _build_research_workflow_summary(response)["research_status"] == "deprioritize_data_gaps"

    response.foreign_filer_coverage_diagnostics.is_foreign_filer_or_adr = True
    response.financial_quality.derived_metrics = {"available_core_metric_count": 2}
    assert _build_research_workflow_summary(response)["research_status"] == "watchlist_candidate"

    response.research_verdict.score = 30
    response.data_quality_summary.source_quality_grade = "C"
    _set_coverage(response, 1, 2)
    assert _build_research_workflow_summary(response)["research_status"] == "needs_evidence_before_research"

    response.research_verdict.score = 29
    response.data_quality_summary.source_quality_grade = "B"
    _set_coverage(response, 8, 0)
    assert _build_research_workflow_summary(response)["research_status"] == "deprioritize_data_gaps"

    response.research_verdict.score = 55
    response.data_quality_summary.source_quality_grade = "D"
    response.foreign_filer_coverage_diagnostics.is_foreign_filer_or_adr = True
    response.financial_quality.derived_metrics = {"available_core_metric_count": 1}
    _set_coverage(response, 4, 0)
    assert _build_research_workflow_summary(response)["research_status"] == "deprioritize_data_gaps"


def test_research_workflow_actions_follow_phase61_rules() -> None:
    response = _base_response()
    criteria = deepcopy(response.jane_criteria_coverage.criteria)
    for item in criteria:
        if item.criterion_id == 1:
            item.coverage_status = "insufficient"
        if item.criterion_id == 2:
            item.coverage_status = "partial"
            item.covered_submetrics = []
            item.missing_submetrics = ["founder_is_ceo"]
    response.jane_criteria_coverage.criteria = criteria
    response.institutional_13f["candidate_specific_evidence"] = {"matched_in_13f": False}
    response.insider_activity["source_status"] = {"source_type": "fallback", "fallback_used": True}
    response.valuation_context.label = "elevated"

    summary = _build_research_workflow_summary(response)

    assert summary["next_3_research_actions"] == [
        "Document monopoly/moat evidence for C1",
        "Check 13F cache in Operations and refresh",
        "Verify SEC EDGAR user agent configuration",
    ]
