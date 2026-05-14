from __future__ import annotations

import json
import time
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def _payload(**overrides) -> dict:
    payload = {
        "ticker": "nvda",
        "criterion": "network_effect",
        "evidence_type": "platform_ecosystem",
        "summary": "CUDA developer ecosystem and software stack are tracked as manual network effect evidence requiring review.",
        "source_label": "User research note",
        "source_url": None,
        "source_date": "2026-05-06",
        "confidence": 0.65,
        "review_status": "unreviewed",
        "limitations": ["Requires manual verification against official filings or independent sources."],
        "tags": ["CUDA", "developer ecosystem"],
    }
    payload.update(overrides)
    return payload


def _use_tmp_store(monkeypatch):
    path = Path("backend/raw_store/cache/test_phase19") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", path)


def test_phase19_manual_evidence_crud_and_ticker_filter(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post("/api/manual-evidence", json=_payload()).json()
    evidence_id = created["evidence_id"]

    assert created["ticker"] == "NVDA"
    assert created["user_provided"] is True
    listed = client.get("/api/manual-evidence", params={"ticker": "NVDA"}).json()
    assert [item["evidence_id"] for item in listed] == [evidence_id]
    fetched = client.get(f"/api/manual-evidence/{evidence_id}").json()
    assert fetched["evidence_id"] == evidence_id
    time.sleep(0.001)
    patched = client.patch(f"/api/manual-evidence/{evidence_id}", json={"review_status": "reviewed"}).json()
    assert patched["review_status"] == "reviewed"
    assert patched["updated_at"] != created["updated_at"]
    archived = client.delete(f"/api/manual-evidence/{evidence_id}").json()
    assert archived["review_status"] == "archived"


def test_phase19_manual_evidence_patch_archive_route_persists(monkeypatch):
    _use_tmp_store(monkeypatch)
    manual_routes = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", []))))
        for route in app.routes
        if "manual-evidence" in getattr(route, "path", "")
    }
    assert ("/api/manual-evidence/{evidence_id}", ("PATCH",)) in manual_routes

    created = client.post("/api/manual-evidence", json=_payload()).json()
    evidence_id = created["evidence_id"]

    time.sleep(0.001)
    archived = client.patch(f"/api/manual-evidence/{evidence_id}", json={"review_status": "archived"}).json()
    fetched = client.get(f"/api/manual-evidence/{evidence_id}").json()
    listed = client.get("/api/manual-evidence", params={"ticker": "NVDA"}).json()

    assert archived["review_status"] == "archived"
    assert archived["updated_at"] != created["updated_at"]
    assert fetched["review_status"] == "archived"
    assert fetched["updated_at"] == archived["updated_at"]
    assert listed[0]["review_status"] == "archived"
    assert listed[0]["updated_at"] == archived["updated_at"]


def test_phase19_manual_evidence_validation_rejects_bad_payloads(monkeypatch):
    _use_tmp_store(monkeypatch)
    assert client.post("/api/manual-evidence", json=_payload(criterion="unsupported")).status_code == 422
    assert client.post("/api/manual-evidence", json=_payload(evidence_type="unsupported")).status_code == 422
    assert client.post("/api/manual-evidence", json=_payload(summary="")).status_code == 422
    assert client.post("/api/manual-evidence", json=_payload(confidence=2)).status_code == 422
    assert client.post("/api/manual-evidence", json=_payload(summary="Contains SEC_EDGAR_USER_AGENT marker")).status_code == 422
    assert client.post("/api/manual-evidence", json=_payload(summary="This is a must invest instruction")).status_code == 422


def test_phase19_saved_manual_evidence_loads_into_analyze_stock(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post("/api/manual-evidence", json=_payload()).json()
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    assessment = response["qualitative_evidence_assessment"]
    criteria = {item["name"]: item for item in response["jane_company_quality"]["criteria"]}
    quality = response["data_quality_summary"]
    drivers = response["score_driver_breakdown"]["positive_drivers"]

    assert assessment["saved_evidence_count"] == 1
    assert assessment["request_evidence_count"] == 0
    assert assessment["evidence_items"][0]["evidence_id"] == created["evidence_id"]
    assert assessment["evidence_items"][0]["origin"] == "saved_library"
    assert assessment["evidence_items"][0]["review_status"] == "unreviewed"
    assert criteria["network_effect"]["source_quality"] == "user_provided"
    assert criteria["network_effect"]["status"] != "insufficient"
    assert response["jane_company_quality"]["label"] != "evidence_backed"
    assert quality["qualitative_evidence"]["saved_library_count"] == 1
    assert "qualitative_evidence" not in quality["mock_evidence_categories"]
    assert "qualitative_evidence" not in quality["fallback_evidence_categories"]
    assert any(driver["name"] == "saved_manual_qualitative_evidence" and driver["effect"] == "preliminary_positive" for driver in drivers)
    assert response["not_investment_advice"] is True
    assert detect_forbidden_language(response) == []
    assert '"source_type": "mixed"' not in json.dumps(response)


def test_phase19_saved_and_request_evidence_merge_and_deduplicate(monkeypatch):
    _use_tmp_store(monkeypatch)
    saved = client.post("/api/manual-evidence", json=_payload()).json()
    request_item = {
        "criterion": "visionary_founder_ceo",
        "evidence_type": "founder_operator",
        "summary": "User notes long-tenured founder-led management as a qualitative factor requiring manual verification.",
        "source_label": "User research note",
        "source_url": None,
        "source_date": "2026-05-06",
        "confidence": 0.6,
        "user_provided": True,
        "limitations": ["Requires verification from official company biography or filings."],
    }
    duplicate = {
        "criterion": saved["criterion"],
        "evidence_type": saved["evidence_type"],
        "summary": saved["summary"],
        "source_label": saved["source_label"],
        "source_url": saved["source_url"],
        "source_date": saved["source_date"],
        "confidence": saved["confidence"],
        "user_provided": True,
        "limitations": saved["limitations"],
    }
    response = client.post(
        "/api/analyze-stock",
        json={"ticker": "NVDA", "market": "US", "qualitative_evidence": [request_item, duplicate]},
    ).json()
    assessment = response["qualitative_evidence_assessment"]
    origins = {item["criterion"]: item["origin"] for item in assessment["evidence_items"]}

    assert assessment["saved_evidence_count"] == 1
    assert assessment["request_evidence_count"] == 1
    assert assessment["deduplicated_count"] == 1
    assert origins["network_effect"] == "saved_library"
    assert origins["visionary_founder_ceo"] == "request_scoped"
    assert "saved_manual_qualitative_evidence" in json.dumps(response["score_driver_breakdown"])
    assert "user_provided_qualitative_evidence" in json.dumps(response["score_driver_breakdown"])


def test_phase19_archived_and_rejected_saved_evidence_do_not_affect_analysis(monkeypatch):
    _use_tmp_store(monkeypatch)
    archived = client.post("/api/manual-evidence", json=_payload(review_status="archived")).json()
    rejected = client.post("/api/manual-evidence", json=_payload(criterion="visionary_founder_ceo", evidence_type="founder_operator", summary="Founder operator note requiring manual verification.", review_status="rejected")).json()
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    assessment = response["qualitative_evidence_assessment"]
    criteria = {item["name"]: item for item in response["jane_company_quality"]["criteria"]}

    assert {archived["review_status"], rejected["review_status"]} == {"archived", "rejected"}
    assert assessment["saved_evidence_count"] == 0
    assert assessment["archived_or_rejected_ignored_count"] == 2
    assert all(item["evidence_id"] not in {archived["evidence_id"], rejected["evidence_id"]} for item in assessment["evidence_items"])
    assert criteria["network_effect"]["status"] == "insufficient"
    assert criteria["visionary_founder_ceo"]["status"] == "insufficient"


def test_phase19_reviewed_and_unreviewed_saved_evidence_still_load(monkeypatch):
    _use_tmp_store(monkeypatch)
    reviewed = client.post("/api/manual-evidence", json=_payload(review_status="reviewed")).json()
    unreviewed = client.post(
        "/api/manual-evidence",
        json=_payload(
            criterion="visionary_founder_ceo",
            evidence_type="founder_operator",
            summary="Founder operator note requiring manual verification.",
            review_status="unreviewed",
        ),
    ).json()
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    assessment = response["qualitative_evidence_assessment"]
    criteria = {item["name"]: item for item in response["jane_company_quality"]["criteria"]}
    accepted_ids = {item["evidence_id"] for item in assessment["evidence_items"] if item["accepted"]}

    assert assessment["saved_evidence_count"] == 2
    assert assessment["reviewed_count"] == 1
    assert assessment["unreviewed_count"] == 1
    assert accepted_ids == {reviewed["evidence_id"], unreviewed["evidence_id"]}
    assert criteria["network_effect"]["source_quality"] == "user_provided"
    assert criteria["visionary_founder_ceo"]["source_quality"] == "user_provided"
    assert criteria["network_effect"]["status"] != "insufficient"
    assert criteria["visionary_founder_ceo"]["status"] != "insufficient"
