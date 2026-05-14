from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.schemas.stock_analysis import AnalyzeStockResponse
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def _use_tmp_stores(monkeypatch):
    root = Path("backend/raw_store/cache/test_phase23") / uuid4().hex
    manual = root / "manual"
    candidates = root / "candidates"
    manual.mkdir(parents=True, exist_ok=True)
    candidates.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", manual)
    monkeypatch.setattr(config, "CANDIDATE_WORKSPACE_DIR", candidates)


def _candidate_payload(**overrides) -> dict:
    payload = {
        "ticker": "nvda",
        "market": "US",
        "theme": "AI infrastructure",
        "user_reason": "External trend research candidate",
        "source_label": "User watchlist note",
        "source_date": "2026-05-08",
        "priority": "high",
        "tags": ["AI", "GPU", "infrastructure"],
    }
    payload.update(overrides)
    return payload


def _manual_payload(**overrides) -> dict:
    payload = {
        "ticker": "NVDA",
        "criterion": "network_effect",
        "evidence_type": "ecosystem_comparison",
        "summary": "CUDA ecosystem is tracked as manual comparison context against ROCm and oneAPI; this requires manual verification.",
        "source_label": "User competitor research note",
        "source_url": None,
        "source_date": "2023-01-01",
        "confidence": 0.65,
        "review_status": "reviewed",
        "source_reliability_label": "user_note",
        "comparison_context": {
            "comparison_type": "platform_ecosystem",
            "subject_company": "NVDA",
            "peer_companies": ["amd", "intc"],
            "comparison_summary": "CUDA ecosystem is manually noted as stronger than ROCm and oneAPI for developer adoption, pending source review.",
            "claimed_advantage": "stronger",
            "comparison_period": "2026",
            "source_basis": "user_note",
            "limitations": ["Manual comparison requires independent verification."],
        },
        "limitations": ["Requires manual verification against official filings or independent sources."],
        "tags": ["manual evidence"],
    }
    payload.update(overrides)
    return payload


def test_phase23_create_list_get_patch_and_archive_candidate(monkeypatch):
    _use_tmp_stores(monkeypatch)
    created = client.post("/api/candidates", json=_candidate_payload()).json()

    assert created["candidate_id"].startswith("candidate_")
    assert created["ticker"] == "NVDA"
    assert created["status"] == "watching"
    assert created["priority"] == "high"
    assert created["not_investment_advice"] is True

    candidate_id = created["candidate_id"]
    listed = client.get("/api/candidates").json()
    fetched = client.get(f"/api/candidates/{candidate_id}").json()
    patched = client.patch(
        f"/api/candidates/{candidate_id}",
        json={"status": "researching", "priority": "medium", "tags": ["review"], "review_notes": "Needs manual source review."},
    ).json()
    archived = client.delete(f"/api/candidates/{candidate_id}").json()
    default_list = client.get("/api/candidates").json()
    audit_list = client.get("/api/candidates", params={"include_archived": True}).json()

    assert [item["candidate_id"] for item in listed] == [candidate_id]
    assert fetched["candidate_id"] == candidate_id
    assert patched["status"] == "researching"
    assert patched["priority"] == "medium"
    assert patched["tags"] == ["review"]
    assert archived["status"] == "archived"
    assert default_list == []
    assert any(item["candidate_id"] == candidate_id for item in audit_list)
    assert detect_forbidden_language(audit_list) == []


def test_phase23_invalid_status_and_priority_rejected(monkeypatch):
    _use_tmp_stores(monkeypatch)
    created = client.post("/api/candidates", json=_candidate_payload()).json()

    invalid_status = client.patch(f"/api/candidates/{created['candidate_id']}", json={"status": "pending"})
    invalid_priority = client.post("/api/candidates", json=_candidate_payload(priority="urgent"))

    assert invalid_status.status_code == 422
    assert invalid_priority.status_code == 422


def test_phase23_dashboard_empty_and_summary_counts(monkeypatch):
    _use_tmp_stores(monkeypatch)
    empty = client.get("/api/candidates/dashboard").json()
    client.post("/api/candidates", json=_candidate_payload(priority="high"))
    client.post("/api/candidates", json=_candidate_payload(ticker="MSFT", priority="medium", tags=["cloud"]))
    dashboard = client.get("/api/candidates/dashboard").json()

    assert empty["summary"]["total_candidates"] == 0
    assert empty["source_status"]["provider"] == "local_candidate_workspace"
    assert dashboard["summary"]["active_candidates"] == 2
    assert dashboard["summary"]["high_priority_count"] == 1
    assert dashboard["summary"]["needs_review_count"] == 2
    assert dashboard["not_investment_advice"] is True
    assert '"source_type": "mixed"' not in json.dumps(dashboard)
    assert detect_forbidden_language(dashboard) == []


def test_phase23_evidence_summary_counts_comparison_and_missing_criteria(monkeypatch):
    _use_tmp_stores(monkeypatch)
    client.post("/api/manual-evidence", json=_manual_payload())
    created = client.post("/api/candidates", json=_candidate_payload()).json()
    refreshed = client.post(f"/api/candidates/{created['candidate_id']}/refresh-evidence-summary").json()

    summary = refreshed["evidence_summary"]
    assert summary["manual_evidence_count"] == 1
    assert summary["active_evidence_count"] == 1
    assert summary["reviewed_evidence_count"] == 1
    assert summary["stale_evidence_count"] == 1
    assert summary["comparison_evidence_count"] == 1
    assert "network_effect" in summary["criteria_covered"]
    assert "monopoly_power" in summary["criteria_missing"]
    assert summary["peer_companies_mentioned"] == ["AMD", "INTC"]

    dashboard = client.get("/api/candidates/dashboard").json()
    assert dashboard["summary"]["stale_evidence_candidate_count"] == 1
    assert dashboard["summary"]["with_comparison_evidence_count"] == 1
    assert any(item["candidate_id"] == created["candidate_id"] for item in dashboard["review_queue"])


def test_phase23_candidate_analyze_updates_metadata_without_persisting_request_evidence(monkeypatch):
    _use_tmp_stores(monkeypatch)
    created = client.post("/api/candidates", json=_candidate_payload()).json()

    from backend.app.services import candidate_workspace as service
    from backend.app.reports.stock_analysis import analyze_stock as real_analyze_stock

    def fake_analyze_stock(request):
        response = real_analyze_stock(request)
        response.research_verdict.score = 61
        response.research_verdict.confidence = 0.66
        response.research_verdict.label = "watchlist_candidate"
        response.data_quality_summary.source_quality_grade = "C"
        return AnalyzeStockResponse.model_validate(response.model_dump(mode="json"))

    monkeypatch.setattr(service, "analyze_stock", fake_analyze_stock)
    response = client.post(
        f"/api/candidates/{created['candidate_id']}/analyze",
        json={
            "refresh_evidence_summary": True,
            "qualitative_evidence": [
                {
                    "criterion": "network_effect",
                    "evidence_type": "platform_ecosystem",
                    "summary": "Request scoped ecosystem note requiring manual verification.",
                    "source_label": "User temporary note",
                    "source_date": "2026-05-08",
                    "confidence": 0.6,
                    "user_provided": True,
                    "limitations": ["Request scoped only."],
                }
            ],
        },
    ).json()

    candidate = response["candidate"]
    assert candidate["last_analyzed_at"]
    assert candidate["latest_score"] == 61
    assert candidate["latest_confidence"] == 0.66
    assert candidate["latest_label"] == "watchlist_candidate"
    assert candidate["latest_data_quality_grade"] == "C"
    assert response["analysis"]["not_investment_advice"] is True
    assert response["analysis"]["qualitative_evidence_assessment"]["request_evidence_count"] == 1
    assert client.get("/api/manual-evidence", params={"ticker": "NVDA"}).json() == []
    assert detect_forbidden_language(response) == []
