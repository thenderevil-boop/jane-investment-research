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
    path = Path("backend/raw_store/cache/test_phase21") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", path)


def _comparison_payload(**overrides) -> dict:
    payload = {
        "ticker": "nvda",
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
            "subject_company": "nvda",
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
        "limitations": ["Requires manual verification against official filings or reputable third-party research."],
        "tags": ["CUDA", "ROCm", "oneAPI"],
    }
    payload.update(overrides)
    return payload


def test_phase21_manual_evidence_can_store_comparison_context(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post("/api/manual-evidence", json=_comparison_payload()).json()
    fetched = client.get(f"/api/manual-evidence/{created['evidence_id']}").json()

    assert created["ticker"] == "NVDA"
    assert created["evidence_type"] == "ecosystem_comparison"
    assert created["comparison_context"]["subject_company"] == "NVDA"
    assert created["comparison_context"]["peer_companies"] == ["AMD", "INTC"]
    assert fetched["comparison_context"] == created["comparison_context"]
    assert created["evidence_quality_score"] >= 80


def test_phase21_invalid_comparison_type_rejected(monkeypatch):
    _use_tmp_store(monkeypatch)
    payload = _comparison_payload(
        comparison_context={
            **_comparison_payload()["comparison_context"],
            "comparison_type": "unsupported",
        }
    )
    response = client.post("/api/manual-evidence", json=payload)
    assert response.status_code == 422


def test_phase21_comparison_quality_rewards_peers_and_specific_summary():
    with_peers = score_manual_evidence_quality(_comparison_payload(review_status="reviewed"))
    without_peers_payload = _comparison_payload(review_status="reviewed")
    without_peers_payload["comparison_context"] = {
        **without_peers_payload["comparison_context"],
        "peer_companies": [],
        "comparison_summary": "Clearly dominant.",
    }
    without_peers = score_manual_evidence_quality(without_peers_payload)

    assert with_peers["evidence_quality_score"] > without_peers["evidence_quality_score"]
    assert "Comparison context includes peer companies." in with_peers["evidence_quality_reasons"]
    assert any("vague" in reason.lower() for reason in without_peers["evidence_quality_reasons"])


def test_phase21_analyze_stock_includes_comparison_assessment_and_matrix(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post("/api/manual-evidence", json=_comparison_payload(review_status="reviewed", source_reliability_label="reputable_third_party_research")).json()
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    comparison = response["comparison_evidence_assessment"]
    matrix = {item["category"]: item for item in response["evidence_matrix"]}
    criteria = {item["name"]: item for item in response["jane_company_quality"]["criteria"]}
    drivers = json.dumps(response["score_driver_breakdown"])

    assert created["review_status"] == "reviewed"
    assert comparison["accepted_comparison_count"] == 1
    assert comparison["reviewed_comparison_count"] == 1
    assert comparison["peer_companies_mentioned"] == ["AMD", "INTC"]
    assert comparison["claimed_advantage_breakdown"]["stronger"] == 1
    assert comparison["items"][0]["source_basis"] == "user_note"
    assert matrix["comparison_evidence"]["source_quality"] == "user_provided"
    assert "comparison" in response["data_quality_summary"]["qualitative_evidence"]
    assert criteria["network_effect"]["verification_level"] == "user_provided"
    assert criteria["network_effect"]["status"] != "insufficient"
    assert "reviewed_comparison_evidence" in drivers
    assert response["not_investment_advice"] is True
    assert detect_forbidden_language(response) == []
    assert '"source_type": "mixed"' not in json.dumps(response)


def test_phase21_archived_and_stale_comparison_evidence_are_capped(monkeypatch):
    _use_tmp_store(monkeypatch)
    active = client.post("/api/manual-evidence", json=_comparison_payload(source_date="2023-01-01")).json()
    archived = client.post("/api/manual-evidence", json=_comparison_payload(review_status="archived", summary="Archived comparison context kept for audit only.")).json()
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    comparison = response["comparison_evidence_assessment"]
    assessment = response["qualitative_evidence_assessment"]
    criteria = {item["name"]: item for item in response["jane_company_quality"]["criteria"]}
    checks = json.dumps(response["next_manual_checks"])

    assert active["is_stale"] is True
    assert archived["review_status"] == "archived"
    assert comparison["accepted_comparison_count"] == 1
    assert comparison["stale_comparison_count"] == 1
    assert assessment["archived_or_rejected_ignored_count"] == 1
    assert criteria["network_effect"]["evidence_strength"] == "weak"
    assert "Refresh stale comparison evidence or archive it" in checks


def test_phase21_comparison_without_peers_has_limited_moat_support(monkeypatch):
    _use_tmp_store(monkeypatch)
    payload = _comparison_payload(
        criterion="monopoly_power",
        evidence_type="competitor_comparison",
        comparison_context={
            **_comparison_payload()["comparison_context"],
            "peer_companies": [],
            "comparison_type": "competitor",
            "claimed_advantage": "unclear",
        },
    )
    client.post("/api/manual-evidence", json=payload)
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    criteria = {item["name"]: item for item in response["jane_company_quality"]["criteria"]}
    drivers = json.dumps(response["score_driver_breakdown"])

    assert criteria["monopoly_power"]["source_quality"] == "user_provided"
    assert criteria["monopoly_power"]["evidence_strength"] == "weak"
    assert criteria["monopoly_power"]["score"] <= 2.0
    assert "comparison_evidence_missing_peers" in drivers
