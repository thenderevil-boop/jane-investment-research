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
    path = Path("backend/raw_store/cache/test_phase22") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", path)


def _payload(**overrides) -> dict:
    payload = {
        "ticker": "NVDA",
        "criterion": "network_effect",
        "evidence_type": "ecosystem_comparison",
        "summary": "CUDA ecosystem is tracked as manual comparison context against ROCm and oneAPI; this requires manual verification.",
        "source_label": "User competitor research note",
        "source_url": None,
        "source_date": "2026-05-07",
        "confidence": 0.65,
        "review_status": "unreviewed",
        "source_reliability_label": "user_note",
        "comparison_context": {
            "comparison_type": "platform_ecosystem",
            "subject_company": "NVDA",
            "peer_companies": ["amd", "intc"],
            "comparison_summary": "CUDA ecosystem is manually noted as stronger than ROCm and oneAPI for developer adoption, pending source review.",
            "claimed_advantage": "stronger",
            "metric_name": None,
            "metric_value": None,
            "metric_unit": None,
            "comparison_period": "2026",
            "source_basis": "user_note",
            "limitations": ["Manual comparison requires independent verification."],
        },
        "limitations": ["Requires manual verification against official filings or independent sources."],
        "tags": ["manual evidence"],
    }
    payload.update(overrides)
    return payload


def test_phase22_dashboard_empty(monkeypatch):
    _use_tmp_store(monkeypatch)
    response = client.get("/api/manual-evidence/dashboard").json()

    assert response["summary"]["total_evidence_count"] == 0
    assert response["summary"]["active_evidence_count"] == 0
    assert response["source_status"]["source_type"] == "derived"
    assert response["source_status"]["provider"] == "local_manual_evidence_library"
    assert response["not_investment_advice"] is True
    assert detect_forbidden_language(response) == []
    assert '"source_type": "mixed"' not in json.dumps(response)


def test_phase22_dashboard_counts_queues_ticker_summary_and_peer_index(monkeypatch):
    _use_tmp_store(monkeypatch)
    reviewed = client.post(
        "/api/manual-evidence",
        json=_payload(review_status="reviewed", source_reliability_label="reputable_third_party_research"),
    ).json()
    unreviewed = client.post(
        "/api/manual-evidence",
        json=_payload(
            criterion="visionary_founder_ceo",
            evidence_type="founder_operator",
            summary="Founder operator note requiring manual verification from company materials.",
            comparison_context=None,
        ),
    ).json()
    stale = client.post(
        "/api/manual-evidence",
        json=_payload(
            ticker="MSFT",
            criterion="continuous_r_and_d",
            evidence_type="r_and_d_intensity",
            summary="Old R and D intensity note requiring refresh against newer filings.",
            source_date="2023-01-01",
            comparison_context=None,
        ),
    ).json()
    archived = client.post(
        "/api/manual-evidence",
        json=_payload(
            ticker="NVDA",
            summary="Archived comparison context kept for audit only.",
            review_status="archived",
        ),
    ).json()
    rejected = client.post(
        "/api/manual-evidence",
        json=_payload(
            ticker="AMD",
            criterion="mega_trend_fit",
            evidence_type="user_provided_note",
            summary="Rejected trend fit note kept for audit only.",
            review_status="rejected",
            comparison_context=None,
        ),
    ).json()

    response = client.get("/api/manual-evidence/dashboard").json()
    summary = response["summary"]
    nvda = next(item for item in response["ticker_summaries"] if item["ticker"] == "NVDA")
    peers = {item["peer_company"]: item for item in response["peer_company_index"]}

    assert {reviewed["review_status"], unreviewed["review_status"], stale["review_status"]} == {"reviewed", "unreviewed"}
    assert {archived["review_status"], rejected["review_status"]} == {"archived", "rejected"}
    assert summary["total_evidence_count"] == 3
    assert summary["active_evidence_count"] == 3
    assert summary["archived_count"] == 0
    assert summary["rejected_count"] == 0
    assert summary["reviewed_count"] == 1
    assert summary["unreviewed_count"] == 2
    assert summary["stale_count"] == 1
    assert summary["review_due_count"] == 1
    assert summary["review_scheduled_count"] == 1
    assert summary["review_overdue_count"] == 0
    assert summary["comparison_evidence_count"] == 1
    assert nvda["active_evidence_count"] == 2
    assert "network_effect" in nvda["criteria_covered"]
    assert "monopoly_power" in nvda["criteria_missing"]
    assert nvda["peer_companies_mentioned"] == ["AMD", "INTC"]
    assert {"AMD", "INTC"}.issubset(peers)
    assert peers["AMD"]["tickers"] == ["NVDA"]
    assert peers["INTC"]["claimed_advantage_breakdown"]["stronger"] == 1
    assert any(item["evidence_id"] == unreviewed["evidence_id"] for item in response["review_queue"])
    assert any(item["evidence_id"] == reviewed["evidence_id"] and item["review_due_reason"] == "comparison_context_needs_review" for item in response["review_queue"])
    assert any(item["evidence_id"] == stale["evidence_id"] for item in response["stale_queue"])
    assert not response["audit_queue"]
    assert detect_forbidden_language(response) == []


def test_phase22_dashboard_includes_audit_items_when_requested(monkeypatch):
    _use_tmp_store(monkeypatch)
    client.post("/api/manual-evidence", json=_payload(review_status="archived", summary="Archived manual evidence for audit only."))
    client.post("/api/manual-evidence", json=_payload(review_status="rejected", summary="Rejected manual evidence for audit only."))

    default_response = client.get("/api/manual-evidence/dashboard").json()
    audit_response = client.get("/api/manual-evidence/dashboard", params={"include_archived": True, "include_rejected": True}).json()

    assert default_response["summary"]["total_evidence_count"] == 0
    assert audit_response["summary"]["total_evidence_count"] == 2
    assert audit_response["summary"]["archived_count"] == 1
    assert audit_response["summary"]["rejected_count"] == 1
    assert len(audit_response["audit_queue"]) == 2


def test_phase22_dashboard_filters(monkeypatch):
    _use_tmp_store(monkeypatch)
    client.post("/api/manual-evidence", json=_payload(review_status="reviewed"))
    client.post(
        "/api/manual-evidence",
        json=_payload(
            ticker="MSFT",
            criterion="continuous_r_and_d",
            evidence_type="r_and_d_intensity",
            source_date="2023-01-01",
            comparison_context=None,
        ),
    )

    nvda = client.get("/api/manual-evidence/dashboard", params={"ticker": "NVDA"}).json()
    stale = client.get("/api/manual-evidence/dashboard", params={"stale_only": True}).json()
    comparison = client.get("/api/manual-evidence/dashboard", params={"has_comparison_context": True}).json()
    unreviewed = client.get("/api/manual-evidence/dashboard", params={"review_status": "unreviewed"}).json()

    assert [item["ticker"] for item in nvda["ticker_summaries"]] == ["NVDA"]
    assert stale["summary"]["stale_count"] == 1
    assert [item["ticker"] for item in stale["ticker_summaries"]] == ["MSFT"]
    assert comparison["summary"]["comparison_evidence_count"] == 1
    assert unreviewed["summary"]["unreviewed_count"] == 1
