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
    path = Path("backend/raw_store/cache/test_phase54") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", path)


def _adr_payload(**overrides) -> dict:
    payload = {
        "ticker": "NOK",
        "criterion": "visionary_founder_ceo",
        "evidence_type": "filing_reference",
        "summary": "Nokia annual report governance disclosure is stored as ADR manual evidence for local filing review only.",
        "source_label": "Nokia Annual Report FY2025",
        "source_url": "https://example.com/nokia-annual-report-2025.pdf",
        "source_date": None,
        "adr_evidence_type": "annual_report",
        "document_title": "Nokia Annual Report 2025",
        "document_date": "2026-03-05",
        "filing_period": "FY2025",
        "quoted_text": "The annual report governance section describes board ownership and long-term incentive alignment for Nokia leadership.",
        "local_market": "NASDAQ Helsinki",
        "local_ticker": "NOKIA",
        "translation_note": "English annual report; no translation required.",
        "confidence": 0.72,
        "review_status": "unreviewed",
        "source_reliability_label": "official_company_material",
        "limitations": ["Manual ADR filing evidence is user-provided and requires local review."],
        "tags": ["ADR", "manual filing reference"],
        "note_title": "NOK ADR annual-report governance evidence",
        "research_question": "Can official local filing evidence support C2 founder/leadership alignment review completeness?",
        "thesis_direction": "neutral",
        "workflow_status": "review_ready",
    }
    payload.update(overrides)
    return payload


def test_phase54_saved_adr_manual_evidence_uses_document_date_as_source_date_and_preserves_metadata(monkeypatch):
    _use_tmp_store(monkeypatch)

    created = client.post("/api/manual-evidence", json=_adr_payload()).json()
    listed = client.get("/api/manual-evidence", params={"ticker": "NOK"}).json()

    assert created["ticker"] == "NOK"
    assert created["source_date"] == "2026-03-05"
    assert created["adr_evidence_type"] == "annual_report"
    assert created["document_title"] == "Nokia Annual Report 2025"
    assert created["document_date"] == "2026-03-05"
    assert created["filing_period"] == "FY2025"
    assert created["quoted_text"].startswith("The annual report governance section")
    assert created["local_market"] == "NASDAQ Helsinki"
    assert created["local_ticker"] == "NOKIA"
    assert created["translation_note"] == "English annual report; no translation required."
    assert created["user_provided"] is True
    assert any("ADR filing source URL is present" in reason for reason in created["evidence_quality_reasons"])
    assert any("ADR document date is present" in reason for reason in created["evidence_quality_reasons"])
    assert listed[0]["source_date"] == "2026-03-05"
    assert detect_forbidden_language(created) == []


def test_phase54_dashboard_review_queue_surfaces_adr_metadata_without_scoring_language(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post("/api/manual-evidence", json=_adr_payload()).json()

    dashboard = client.get("/api/manual-evidence/dashboard", params={"ticker": "NOK"}).json()
    queue_item = next(item for item in dashboard["review_queue"] if item["evidence_id"] == created["evidence_id"])

    assert queue_item["review_due_reason"] == "unreviewed"
    assert queue_item["source_date"] == "2026-03-05"
    assert queue_item["adr_evidence_type"] == "annual_report"
    assert queue_item["document_title"] == "Nokia Annual Report 2025"
    assert queue_item["document_date"] == "2026-03-05"
    assert queue_item["filing_period"] == "FY2025"
    assert queue_item["local_market"] == "NASDAQ Helsinki"
    assert queue_item["local_ticker"] == "NOKIA"
    assert queue_item["adr_review_label"] == "ADR filing-backed manual review"
    assert queue_item["not_investment_advice"] is True
    assert queue_item["affects_score"] is False
    queue_blob = json.dumps(queue_item)
    assert "user-provided" in queue_blob.lower()
    assert "not independently verified" in queue_blob.lower()
    assert detect_forbidden_language(dashboard) == []


def test_phase54_missing_adr_document_date_enters_review_queue_as_missing_source_date(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post(
        "/api/manual-evidence",
        json=_adr_payload(
            review_status="reviewed",
            reviewed_at="2026-05-21T00:00:00+00:00",
            source_date=None,
            document_date=None,
            document_title="Nokia Governance Web Page",
            adr_evidence_type="governance_page",
        ),
    ).json()

    dashboard = client.get("/api/manual-evidence/dashboard", params={"ticker": "NOK"}).json()
    queue_item = next(item for item in dashboard["review_queue"] if item["evidence_id"] == created["evidence_id"])

    assert created["source_date"] is None
    assert created["document_date"] is None
    assert queue_item["review_due_reason"] == "source_date_missing"
    assert queue_item["adr_evidence_type"] == "governance_page"
    assert queue_item["document_title"] == "Nokia Governance Web Page"
    assert queue_item["adr_review_label"] == "ADR filing metadata incomplete"
    assert "document date" in json.dumps(queue_item).lower()
    assert queue_item["not_investment_advice"] is True
    assert queue_item["affects_score"] is False
