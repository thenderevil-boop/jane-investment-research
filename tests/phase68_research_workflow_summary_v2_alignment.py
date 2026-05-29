from __future__ import annotations

from copy import deepcopy

from backend.app.reports.stock_analysis import (
    _build_evidence_gap_inbox,
    _build_research_workflow_summary,
    analyze_stock,
)
from backend.app.schemas.stock_analysis import AnalyzeStockRequest, ResearchWorkflowSummary
from backend.app.utils.forbidden_language import detect_forbidden_language


def _base_response():
    return analyze_stock(AnalyzeStockRequest(ticker="NVDA", market="US"))


def test_phase68_workflow_summary_v2_promotes_blocking_manual_gap_to_dominant_workflow_route() -> None:
    response = _base_response()
    criteria = deepcopy(response.jane_criteria_coverage.criteria)
    for item in criteria:
        if item.criterion_id == 1:
            item.coverage_status = "insufficient"
            item.requires_human_verification = True
            item.missing_submetrics = ["moat_evidence"]
            item.next_manual_check = "Add filing-backed or source-backed moat evidence"
    response.jane_criteria_coverage.criteria = criteria

    inbox = _build_evidence_gap_inbox(response)
    summary = _build_research_workflow_summary(response, evidence_gap_inbox=inbox)

    assert summary["version"] == "phase68_research_workflow_summary_v2"
    assert summary["workflow_alignment_version"] == "phase68_workflow_alignment_v1"
    assert summary["dominant_blocker"] == "manual_evidence_gap"
    assert summary["dominant_route"] == "manual_evidence"
    assert summary["dominant_gap_id"].endswith("_C1_manual_evidence")
    assert summary["dominant_criterion_id"] == 1
    assert "C1" in summary["dominant_reason"]
    assert summary["aligned_with_evidence_gap_inbox"] is True
    assert summary["aligned_with_source_health_actions"] is True
    assert summary["affects_score"] is False
    assert summary["final_score_unchanged"] is True
    assert summary["not_investment_advice"] is True
    assert detect_forbidden_language(summary["dominant_reason"]) == []

    validated = ResearchWorkflowSummary.model_validate(summary)
    assert validated.dominant_route == "manual_evidence"


def test_phase68_workflow_summary_v2_routes_source_setup_and_cache_blockers_to_operations() -> None:
    response = _base_response()
    criteria = deepcopy(response.jane_criteria_coverage.criteria)
    for item in criteria:
        if item.criterion_id in {1, 2, 5, 11}:
            item.coverage_status = "covered"
            item.requires_human_verification = False
            item.missing_submetrics = []
        if item.criterion_id == 19:
            item.coverage_status = "partial"
            item.missing_submetrics = ["institutional_support", "fund_support"]
    response.jane_criteria_coverage.criteria = criteria
    response.institutional_13f["candidate_specific_evidence"] = {"matched_in_13f": False}
    response.insider_activity["source_status"] = {"source_type": "fallback", "fallback_used": True}

    inbox = _build_evidence_gap_inbox(response)
    summary = _build_research_workflow_summary(response, evidence_gap_inbox=inbox)

    assert summary["dominant_blocker"] in {"source_health_action", "provider_cache_refresh"}
    assert summary["dominant_route"] == "operations"
    assert summary["dominant_provider"] in {"sec_13f", "sec_form4"}
    assert summary["dominant_gap_id"]
    assert "Operations" in summary["dominant_reason"]
    assert summary["affects_score"] is False
    assert summary["final_score_unchanged"] is True


def test_phase68_workflow_summary_v2_has_safe_none_state_when_no_gap_items_exist() -> None:
    response = _base_response()
    response.evidence_gap_inbox.items = []

    summary = _build_research_workflow_summary(
        response,
        evidence_gap_inbox={
            "version": "phase64_evidence_gap_inbox_v1",
            "items": [],
            "summary": {"total_count": 0},
            "affects_score": False,
            "final_score_unchanged": True,
            "not_investment_advice": True,
        },
    )

    assert summary["dominant_blocker"] == "none"
    assert summary["dominant_route"] == "stock_research"
    assert summary["dominant_reason"] == "No dominant Evidence Gap Inbox blocker is currently surfaced."
    assert summary["dominant_gap_id"] is None
    assert summary["dominant_provider"] is None
    assert summary["affects_score"] is False
    assert summary["final_score_unchanged"] is True
