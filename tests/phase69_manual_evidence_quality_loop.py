from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app

client = TestClient(app)


def _use_tmp_store(monkeypatch, tmp_path):
    store = tmp_path / "manual_evidence"
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", store)
    return store


def _payload(**overrides):
    today = date.today().isoformat()
    payload = {
        "ticker": "NVDA",
        "criterion": "monopoly_power",
        "evidence_type": "market_share",
        "summary": "NVIDIA data-center accelerator ecosystem shows durable market-share and switching-cost evidence from source material.",
        "source_label": "Manual source review packet",
        "source_url": "https://example.com/nvda-moat-review",
        "source_date": today,
        "confidence": 0.65,
        "review_status": "reviewed",
        "source_reliability_label": "reputable_third_party_research",
        "limitations": ["Manual evidence requires local review against original source."],
        "tags": ["phase69", "moat"],
        "linked_gap_id": "NVDA_C1_manual_evidence",
        "linked_criterion_id": 1,
        "linked_submetrics": ["moat_evidence"],
    }
    payload.update(overrides)
    return payload


def _c1_gap(payload: dict) -> dict:
    return next(item for item in payload["evidence_gap_inbox"]["items"] if item["gap_id"] == "NVDA_C1_manual_evidence")


def _c1_coverage(payload: dict) -> dict:
    return next(item for item in payload["jane_criteria_coverage"]["criteria"] if item["criterion_id"] == 1)


def test_phase69_manual_evidence_persists_resolution_metadata(monkeypatch, tmp_path) -> None:
    _use_tmp_store(monkeypatch, tmp_path)

    created = client.post("/api/manual-evidence", json=_payload()).json()

    assert created["linked_gap_id"] == "NVDA_C1_manual_evidence"
    assert created["linked_criterion_id"] == 1
    assert created["linked_submetrics"] == ["moat_evidence"]
    assert created["resolution_status"] == "resolved_for_review"
    assert created["review_state"] == "reviewed"
    assert created["freshness_state"] == "fresh"
    assert created["missing_required_fields"] == []
    assert "does not affect final score" in created["evidence_quality_note"].lower()
    assert created["affects_score"] is False
    assert created["final_score_unchanged"] is True
    assert created["not_investment_advice"] is True


def test_phase69_evidence_gap_inbox_surfaces_linked_manual_evidence_state(monkeypatch, tmp_path) -> None:
    _use_tmp_store(monkeypatch, tmp_path)
    baseline = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    baseline_verdict = baseline["research_verdict"]["label"]
    client.post("/api/manual-evidence", json=_payload())

    payload = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    gap = _c1_gap(payload)

    assert gap["manual_evidence_resolution"]["linked_gap_id"] == "NVDA_C1_manual_evidence"
    assert gap["manual_evidence_resolution"]["linked_criterion_id"] == 1
    assert gap["manual_evidence_resolution"]["linked_evidence_count"] == 1
    assert len(gap["manual_evidence_resolution"]["linked_evidence_ids"]) == 1
    assert gap["manual_evidence_resolution"]["resolution_status"] == "resolved_for_review"
    assert gap["manual_evidence_resolution"]["review_state"] == "reviewed"
    assert gap["manual_evidence_resolution"]["freshness_state"] == "fresh"
    assert gap["manual_evidence_resolution"]["missing_required_fields"] == []
    assert gap["manual_evidence_resolution"]["affects_score"] is False
    assert gap["manual_evidence_resolution"]["final_score_unchanged"] is True
    assert gap["manual_evidence_resolution"]["not_investment_advice"] is True
    assert payload["research_verdict"]["label"] == baseline_verdict


def test_phase69_coverage_matrix_shows_manual_evidence_review_and_freshness_state(monkeypatch, tmp_path) -> None:
    _use_tmp_store(monkeypatch, tmp_path)
    old_date = (date.today() - timedelta(days=800)).isoformat()
    client.post(
        "/api/manual-evidence",
        json=_payload(
            source_date=old_date,
            review_status="unreviewed",
            source_url=None,
            source_reliability_label="unknown",
        ),
    )

    payload = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    coverage = _c1_coverage(payload)

    resolution = coverage["manual_evidence_resolution"]
    assert resolution["linked_criterion_id"] == 1
    assert resolution["linked_evidence_count"] == 1
    assert resolution["resolution_status"] == "stale"
    assert resolution["review_state"] == "pending_review"
    assert resolution["freshness_state"] == "stale"
    assert "source_url" in resolution["missing_required_fields"]
    assert resolution["affects_score"] is False
    assert resolution["final_score_unchanged"] is True
    assert resolution["not_investment_advice"] is True


def test_phase69_archived_or_rejected_manual_evidence_does_not_resolve_gap(monkeypatch, tmp_path) -> None:
    _use_tmp_store(monkeypatch, tmp_path)
    client.post("/api/manual-evidence", json=_payload(review_status="rejected"))
    client.post("/api/manual-evidence", json=_payload(review_status="archived", source_url="https://example.com/archived"))

    payload = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()
    gap = _c1_gap(payload)

    resolution = gap["manual_evidence_resolution"]
    assert resolution["linked_evidence_count"] == 0
    assert resolution["resolution_status"] == "unresolved"
    assert resolution["review_state"] == "none"
    assert resolution["freshness_state"] == "none"
    assert resolution["affects_score"] is False
    assert resolution["final_score_unchanged"] is True
