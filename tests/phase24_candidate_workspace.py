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
    root = Path("backend/raw_store/cache/test_phase24") / uuid4().hex
    manual = root / "manual"
    candidates = root / "candidates"
    manual.mkdir(parents=True, exist_ok=True)
    candidates.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", manual)
    monkeypatch.setattr(config, "CANDIDATE_WORKSPACE_DIR", candidates)


def _candidate_payload(**overrides) -> dict:
    payload = {
        "ticker": "NVDA",
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
        "review_status": "unreviewed",
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


def test_phase24_review_notes_history_and_safety(monkeypatch):
    _use_tmp_stores(monkeypatch)
    created = client.post("/api/candidates", json=_candidate_payload()).json()
    assert created["review_note_history"] == []

    note = client.post(
        f"/api/candidates/{created['candidate_id']}/notes",
        json={"note": "Initial workspace review note. Need to verify moat and disruptive innovation evidence.", "note_type": "general", "tags": ["manual-review"]},
    )
    notes = client.get(f"/api/candidates/{created['candidate_id']}/notes").json()
    fetched = client.get(f"/api/candidates/{created['candidate_id']}").json()
    unsafe = client.post(
        f"/api/candidates/{created['candidate_id']}/notes",
        json={"note": "Please buy this now.", "note_type": "general", "tags": []},
    )

    assert note.status_code == 200
    assert note.json()["note_id"].startswith("note_")
    assert notes[0]["note"] == "Initial workspace review note. Need to verify moat and disruptive innovation evidence."
    assert fetched["review_notes"] == notes[0]["note"]
    assert len(fetched["review_note_history"]) == 1
    assert unsafe.status_code == 422
    assert detect_forbidden_language(fetched) == []


def test_phase24_status_transition_validation_and_restore(monkeypatch):
    _use_tmp_stores(monkeypatch)
    created = client.post("/api/candidates", json=_candidate_payload()).json()
    researching = client.patch(f"/api/candidates/{created['candidate_id']}", json={"status": "researching"}).json()
    reviewed = client.patch(f"/api/candidates/{created['candidate_id']}", json={"status": "reviewed"}).json()
    archived = client.delete(f"/api/candidates/{created['candidate_id']}").json()
    invalid = client.patch(f"/api/candidates/{created['candidate_id']}", json={"status": "researching"})
    restored = client.post(f"/api/candidates/{created['candidate_id']}/restore").json()

    assert researching["status"] == "researching"
    assert reviewed["status"] == "reviewed"
    assert archived["status"] == "archived"
    assert invalid.status_code == 422
    assert restored["status"] == "watching"
    assert any(note["note"].startswith("Status changed") for note in restored["review_note_history"])


def test_phase24_analysis_history_appends_compact_metadata(monkeypatch):
    _use_tmp_stores(monkeypatch)
    created = client.post("/api/candidates", json=_candidate_payload()).json()

    from backend.app.services import candidate_workspace as service
    from backend.app.reports.stock_analysis import analyze_stock as real_analyze_stock

    scores = [61, 64]

    def fake_analyze_stock(request):
        response = real_analyze_stock(request)
        response.research_verdict.score = scores.pop(0)
        response.research_verdict.confidence = 0.66
        response.research_verdict.label = "watchlist_candidate"
        response.data_quality_summary.source_quality_grade = "B"
        return AnalyzeStockResponse.model_validate(response.model_dump(mode="json"))

    monkeypatch.setattr(service, "analyze_stock", fake_analyze_stock)
    first = client.post(f"/api/candidates/{created['candidate_id']}/analyze", json={"refresh_evidence_summary": True}).json()
    second = client.post(f"/api/candidates/{created['candidate_id']}/analyze", json={"refresh_evidence_summary": True}).json()
    history = client.get(f"/api/candidates/{created['candidate_id']}/analysis-history").json()

    assert first["candidate"]["analysis_history"][0]["score"] == 61
    assert second["candidate"]["latest_score"] == 64
    assert len(history) == 2
    assert history[-1]["score"] == 64
    assert "analysis" not in history[-1]
    assert second["not_investment_advice"] is True
    assert detect_forbidden_language(second) == []


def test_phase24_candidate_filters_sorting_dashboard_and_badges(monkeypatch):
    _use_tmp_stores(monkeypatch)
    client.post("/api/manual-evidence", json=_manual_payload())
    nvda = client.post("/api/candidates", json=_candidate_payload(priority="high", tags=["AI"])).json()
    msft = client.post("/api/candidates", json=_candidate_payload(ticker="MSFT", priority="medium", tags=["cloud"])).json()
    client.post(f"/api/candidates/{nvda['candidate_id']}/refresh-evidence-summary")
    client.patch(f"/api/candidates/{msft['candidate_id']}", json={"next_review_due_at": "2026-01-01T00:00:00+00:00"})

    by_status = client.get("/api/candidates", params={"status": "watching"}).json()
    by_priority = client.get("/api/candidates", params={"priority": "high"}).json()
    by_tag = client.get("/api/candidates", params={"tag": "AI"}).json()
    stale_only = client.get("/api/candidates", params={"stale_evidence_only": True}).json()
    needs_review = client.get("/api/candidates", params={"needs_review_only": True}).json()
    has_comparison = client.get("/api/candidates", params={"has_comparison_evidence": True}).json()
    missing = client.get("/api/candidates", params={"missing_criterion": "monopoly_power"}).json()
    sorted_rows = client.get("/api/candidates", params={"sort_by": "latest_score", "sort_order": "desc"}).json()
    invalid_sort = client.get("/api/candidates", params={"sort_by": "not_a_field"})
    dashboard = client.get("/api/candidates/dashboard").json()

    assert len(by_status) == 2
    assert [item["ticker"] for item in by_priority] == ["NVDA"]
    assert [item["ticker"] for item in by_tag] == ["NVDA"]
    assert [item["ticker"] for item in stale_only] == ["NVDA"]
    assert len(needs_review) == 2
    assert [item["ticker"] for item in has_comparison] == ["NVDA"]
    assert {item["ticker"] for item in missing} == {"NVDA", "MSFT"}
    assert [item["ticker"] for item in sorted_rows] == sorted([item["ticker"] for item in sorted_rows], reverse=True)
    assert invalid_sort.status_code == 422
    assert dashboard["summary"]["needs_analysis_count"] == 2
    assert dashboard["summary"]["missing_evidence_candidate_count"] == 2
    assert dashboard["summary"]["review_overdue_count"] == 1
    assert dashboard["summary"]["missing_criteria_breakdown"]["monopoly_power"] == 2
    assert dashboard["items"][0]["evidence_badges"]
    assert dashboard["review_queue"][0]["review_reasons"]
    assert dashboard["source_status"]["provider"] == "local_candidate_workspace"
    assert dashboard["not_investment_advice"] is True
    assert '"source_type": "mixed"' not in json.dumps(dashboard)
    assert detect_forbidden_language(dashboard) == []
