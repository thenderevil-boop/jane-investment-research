from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def _use_tmp_store(monkeypatch):
    path = Path("backend/raw_store/cache/test_phase33") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", path)


def _payload(**overrides) -> dict:
    payload = {
        "ticker": "NVDA",
        "criterion": "network_effect",
        "evidence_type": "platform_ecosystem",
        "summary": "CUDA developer ecosystem and software stack are tracked as manual network-effect evidence for Jane qualitative review.",
        "source_label": "User research note",
        "source_url": None,
        "source_date": "2026-05-06",
        "confidence": 0.65,
        "review_status": "unreviewed",
        "source_reliability_label": "user_note",
        "limitations": ["Requires manual verification against official filings or independent sources."],
        "tags": ["CUDA", "developer ecosystem"],
        "note_title": "NVDA CUDA ecosystem lock-in thesis",
        "research_question": "Does CUDA create durable developer switching costs for Jane network-effect criteria?",
        "thesis_direction": "supportive",
        "workflow_status": "draft",
    }
    payload.update(overrides)
    return payload


def test_phase33_manual_evidence_persists_research_note_workflow_metadata(monkeypatch):
    _use_tmp_store(monkeypatch)

    created = client.post("/api/manual-evidence", json=_payload()).json()
    fetched = client.get(f"/api/manual-evidence/{created['evidence_id']}").json()
    listed = client.get("/api/manual-evidence", params={"ticker": "NVDA"}).json()

    assert created["note_title"] == "NVDA CUDA ecosystem lock-in thesis"
    assert created["research_question"].startswith("Does CUDA create durable")
    assert created["thesis_direction"] == "supportive"
    assert created["workflow_status"] == "draft"
    assert fetched["note_title"] == created["note_title"]
    assert listed[0]["workflow_status"] == "draft"
    assert detect_forbidden_language(created) == []


def test_phase33_patch_promotes_research_note_to_accepted_workflow(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post("/api/manual-evidence", json=_payload()).json()

    patched = client.patch(
        f"/api/manual-evidence/{created['evidence_id']}",
        json={
            "note_title": "Reviewed NVDA CUDA ecosystem thesis",
            "research_question": "Which evidence supports durable CUDA ecosystem switching costs?",
            "thesis_direction": "supportive",
            "workflow_status": "accepted",
            "review_status": "reviewed",
            "review_notes": "Accepted for local Jane evidence library after source review; still user-provided.",
        },
    ).json()

    assert patched["note_title"] == "Reviewed NVDA CUDA ecosystem thesis"
    assert patched["workflow_status"] == "accepted"
    assert patched["review_status"] == "reviewed"
    assert patched["reviewed_at"]
    assert patched["last_reviewed_at"]


def test_phase33_analyze_stock_exposes_research_note_workflow_for_saved_library(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post("/api/manual-evidence", json=_payload(workflow_status="accepted", review_status="reviewed")).json()

    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    assessment = response["qualitative_evidence_assessment"]
    item = assessment["evidence_items"][0]

    assert assessment["saved_evidence_count"] == 1
    assert item["evidence_id"] == created["evidence_id"]
    assert item["origin"] == "saved_library"
    assert item["note_title"] == "NVDA CUDA ecosystem lock-in thesis"
    assert item["research_question"].startswith("Does CUDA create durable")
    assert item["thesis_direction"] == "supportive"
    assert item["workflow_status"] == "accepted"
    assert item["accepted"] is True
    assert response["not_investment_advice"] is True
    assert detect_forbidden_language(response) == []
    assert "SEC_EDGAR_USER_AGENT" not in json.dumps(response)


def test_phase33_research_note_fields_reject_secrets_and_investment_instructions(monkeypatch):
    _use_tmp_store(monkeypatch)

    secret_response = client.post("/api/manual-evidence", json=_payload(note_title="contains FRED_API_KEY marker"))
    instruction_response = client.post("/api/manual-evidence", json=_payload(research_question="Should I buy this stock now?"))

    assert secret_response.status_code == 422
    assert instruction_response.status_code == 422
