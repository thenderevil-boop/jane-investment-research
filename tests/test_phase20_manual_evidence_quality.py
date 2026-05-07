from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.schemas.manual_evidence import score_manual_evidence_quality
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def _use_tmp_store(monkeypatch):
    path = Path("backend/raw_store/cache/test_phase20") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", path)


def _payload(**overrides) -> dict:
    payload = {
        "ticker": "NVDA",
        "criterion": "network_effect",
        "evidence_type": "platform_ecosystem",
        "summary": "CUDA developer ecosystem and software stack are tracked as manual network-effect evidence requiring periodic review.",
        "source_label": "User research note",
        "source_url": None,
        "source_date": "2026-05-06",
        "confidence": 0.65,
        "review_status": "unreviewed",
        "source_reliability_label": "user_note",
        "limitations": ["Requires manual verification against official filings or independent sources."],
        "tags": ["CUDA", "developer ecosystem"],
    }
    payload.update(overrides)
    return payload


def test_phase20_post_and_get_compute_quality_fields(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post("/api/manual-evidence", json=_payload()).json()
    fetched = client.get(f"/api/manual-evidence/{created['evidence_id']}").json()

    assert created["evidence_quality_score"] > 0
    assert created["evidence_quality_label"] in {"medium", "high", "low", "incomplete"}
    assert created["source_reliability_label"] == "user_note"
    assert created["is_stale"] is False
    assert fetched["evidence_quality_score"] == created["evidence_quality_score"]


def test_phase20_patch_reviewed_sets_review_metadata_and_recomputes_quality(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post("/api/manual-evidence", json=_payload(source_reliability_label="unknown")).json()
    patched = client.patch(
        f"/api/manual-evidence/{created['evidence_id']}",
        json={
            "review_status": "reviewed",
            "review_notes": "Reviewed locally against user notes; still not independently verified.",
            "source_reliability_label": "company_investor_relations",
        },
    ).json()

    assert patched["review_status"] == "reviewed"
    assert patched["reviewed_at"]
    assert patched["last_reviewed_at"]
    assert patched["reviewed_by"] == "local_user"
    assert patched["review_notes"].startswith("Reviewed locally")
    assert patched["source_reliability_label"] == "company_investor_relations"
    assert patched["evidence_quality_score"] >= created["evidence_quality_score"]


def test_phase20_missing_and_old_dates_affect_quality_and_staleness(monkeypatch):
    _use_tmp_store(monkeypatch)
    missing_date = client.post("/api/manual-evidence", json=_payload(source_date=None)).json()
    old_date = client.post("/api/manual-evidence", json=_payload(source_date="2023-01-01", summary="Old CUDA ecosystem note requiring refresh.")).json()
    expired = client.post("/api/manual-evidence", json=_payload(expires_at="2026-01-01", summary="Expired CUDA ecosystem note requiring refresh.")).json()

    assert "source date" in " ".join(missing_date["evidence_quality_reasons"]).lower()
    assert old_date["is_stale"] is True
    assert "365 days" in old_date["stale_reason"]
    assert expired["is_stale"] is True
    assert "expired" in expired["stale_reason"]


def test_phase20_analyze_stock_uses_review_quality_and_stale_counts(monkeypatch):
    _use_tmp_store(monkeypatch)
    reviewed = client.post("/api/manual-evidence", json=_payload(review_status="reviewed", source_reliability_label="company_investor_relations")).json()
    stale = client.post(
        "/api/manual-evidence",
        json=_payload(
            criterion="visionary_founder_ceo",
            evidence_type="founder_operator",
            summary="Old founder tenure evidence requiring refresh against current management materials.",
            source_date="2023-01-01",
            review_status="unreviewed",
        ),
    ).json()
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    assessment = response["qualitative_evidence_assessment"]
    quality = response["data_quality_summary"]["qualitative_evidence"]
    criteria = {item["name"]: item for item in response["jane_company_quality"]["criteria"]}
    drivers = json.dumps(response["score_driver_breakdown"])
    checks = json.dumps(response["next_manual_checks"])

    assert {reviewed["review_status"], stale["review_status"]} == {"reviewed", "unreviewed"}
    assert assessment["reviewed_active_count"] == 1
    assert assessment["unreviewed_active_count"] == 1
    assert assessment["quality_score_average"] is not None
    assert assessment["stale_count"] == 1
    assert quality["reviewed_active_count"] == 1
    assert quality["stale_count"] == 1
    assert criteria["network_effect"]["verification_level"] == "user_provided"
    assert criteria["network_effect"]["evidence_strength"] in {"weak", "moderate"}
    assert criteria["visionary_founder_ceo"]["evidence_strength"] == "weak"
    assert "reviewed_manual_qualitative_evidence" in drivers
    assert "stale_manual_evidence_requires_refresh" in drivers
    assert "Refresh stale manual evidence or archive it" in checks
    assert response["not_investment_advice"] is True
    assert detect_forbidden_language(response) == []
    assert '"source_type": "mixed"' not in json.dumps(response)


def test_phase20_archived_and_rejected_remain_ignored_after_quality_fields(monkeypatch):
    _use_tmp_store(monkeypatch)
    archived = client.post("/api/manual-evidence", json=_payload(review_status="archived")).json()
    rejected = client.post("/api/manual-evidence", json=_payload(review_status="rejected", summary="Rejected manual evidence note.")).json()
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    assessment = response["qualitative_evidence_assessment"]
    criteria = {item["name"]: item for item in response["jane_company_quality"]["criteria"]}

    assert archived["evidence_quality_score"] == 0
    assert rejected["evidence_quality_score"] == 0
    assert assessment["accepted_evidence_count"] == 0
    assert assessment["archived_or_rejected_ignored_count"] == 2
    assert criteria["network_effect"]["status"] == "insufficient"


def test_phase20_quality_scoring_is_not_truth_or_verification_score():
    result = score_manual_evidence_quality(
        {
            "summary": "Specific manual ecosystem claim requiring review.",
            "source_label": "User note",
            "source_date": "2026-05-06",
            "source_reliability_label": "company_investor_relations",
            "confidence": 0.65,
            "review_status": "reviewed",
            "limitations": ["Manual verification required."],
            "tags": ["ecosystem"],
        }
    )

    assert result["evidence_quality_score"] >= 80
    assert any("locally reviewed" in reason for reason in result["evidence_quality_reasons"])
