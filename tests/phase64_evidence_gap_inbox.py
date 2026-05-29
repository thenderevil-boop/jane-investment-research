from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.reports.stock_analysis import _build_evidence_gap_inbox, analyze_stock
from backend.app.schemas.stock_analysis import AnalyzeStockRequest
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def _base_response():
    return analyze_stock(AnalyzeStockRequest(ticker="NVDA", market="US"))


def _criterion(response, criterion_id: int):
    return next(item for item in response.jane_criteria_coverage.criteria if item.criterion_id == criterion_id)


def test_evidence_gap_inbox_is_present_and_non_scoring_for_api_payload() -> None:
    payload = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    inbox = payload["evidence_gap_inbox"]

    assert inbox["version"] == "phase64_evidence_gap_inbox_v1"
    assert inbox["not_investment_advice"] is True
    assert inbox["affects_score"] is False
    assert inbox["final_score_unchanged"] is True
    assert isinstance(inbox["items"], list)
    assert inbox["summary"]["total_count"] == len(inbox["items"])
    assert detect_forbidden_language(inbox) == []

    for item in inbox["items"]:
        assert item["not_investment_advice"] is True
        assert item["affects_score"] is False
        assert item["priority"] in {"high", "medium", "low"}
        assert item["gap_type"] in {
            "manual_evidence_required",
            "source_setup_required",
            "provider_cache_refresh_required",
            "provider_limitation",
            "adr_or_foreign_filer_limitation",
            "optional_context",
        }
        assert item["source_route"] in {"manual_evidence", "operations", "stock_research", "evidence_dashboard"}


def test_evidence_gap_inbox_prioritizes_core_manual_coverage_gaps() -> None:
    response = _base_response()
    criteria = deepcopy(response.jane_criteria_coverage.criteria)
    for item in criteria:
        if item.criterion_id == 1:
            item.coverage_status = "insufficient"
            item.missing_submetrics = ["moat_evidence"]
            item.next_manual_check = "Document monopoly/moat evidence for C1"
        if item.criterion_id == 2:
            item.coverage_status = "partial"
            item.missing_submetrics = ["founder_is_ceo"]
            item.next_manual_check = "Confirm founder-operator status"
    response.jane_criteria_coverage.criteria = criteria

    inbox = _build_evidence_gap_inbox(response)
    items = inbox["items"]

    c1 = next(item for item in items if item["criterion_id"] == 1)
    c2 = next(item for item in items if item["criterion_id"] == 2)
    assert c1["priority"] == "high"
    assert c1["gap_type"] == "manual_evidence_required"
    assert c1["source_route"] == "manual_evidence"
    assert c1["blocks_research_status"] is True
    assert c1["recommended_action"] == "Document monopoly/moat evidence for C1"
    assert c2["recommended_action"] == "Confirm founder-operator status"


def test_evidence_gap_inbox_routes_13f_and_form4_to_operations() -> None:
    response = _base_response()
    criteria = deepcopy(response.jane_criteria_coverage.criteria)
    for item in criteria:
        if item.criterion_id == 19:
            item.coverage_status = "insufficient"
            item.missing_submetrics = ["institutional_support", "fund_support"]
            item.limitations = ["No candidate-specific 13F target match observed."]
    response.jane_criteria_coverage.criteria = criteria
    response.institutional_13f["candidate_specific_evidence"] = {"matched_in_13f": False}
    response.insider_activity["source_status"] = {"source_type": "fallback", "fallback_used": True}

    inbox = _build_evidence_gap_inbox(response)
    items = inbox["items"]

    c19 = next(item for item in items if item["criterion_id"] == 19)
    form4 = next(item for item in items if item["gap_id"].endswith("form4_source_setup"))
    assert c19["gap_type"] in {"provider_cache_refresh_required", "source_setup_required"}
    assert c19["source_route"] == "operations"
    assert c19["recommended_action"] == "Check 13F cache in Operations and refresh"
    assert form4["gap_type"] == "source_setup_required"
    assert form4["recommended_action"] == "Verify SEC EDGAR user agent configuration"


def test_evidence_gap_inbox_routes_adr_structural_limits_without_blocking_score() -> None:
    response = _base_response()
    response.ticker = "NOK"
    response.foreign_filer_coverage_diagnostics.is_foreign_filer_or_adr = True
    response.foreign_filer_coverage_diagnostics.detected_signals = ["adr"]

    inbox = _build_evidence_gap_inbox(response)
    item = next(gap for gap in inbox["items"] if gap["gap_type"] == "adr_or_foreign_filer_limitation")

    assert item["priority"] == "medium"
    assert item["source_route"] == "manual_evidence"
    assert item["blocks_research_status"] is False
    assert "ADR" in item["recommended_action"] or "local" in item["recommended_action"]
    assert inbox["summary"]["adr_or_foreign_filer_limitation_count"] >= 1
