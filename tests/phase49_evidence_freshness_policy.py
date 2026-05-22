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
    path = Path("backend/raw_store/cache/test_phase49") / uuid4().hex
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
        "source_date": "2023-01-01",
        "confidence": 0.65,
        "review_status": "unreviewed",
        "source_reliability_label": "user_note",
        "limitations": ["Requires manual verification against official filings or independent sources."],
        "tags": ["CUDA", "developer ecosystem"],
        "note_title": "NVDA CUDA ecosystem lock-in thesis",
        "research_question": "Does CUDA create durable developer switching costs for Jane network-effect criteria?",
        "thesis_direction": "supportive",
        "workflow_status": "accepted",
    }
    payload.update(overrides)
    return payload


def test_phase49_analyze_stock_exposes_non_scoring_freshness_policy(monkeypatch):
    _use_tmp_store(monkeypatch)
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})

    assert response.status_code == 200
    payload = response.json()
    policy = payload["evidence_freshness_policy"]

    assert policy["policy_version"] == "phase49_evidence_freshness_v1"
    assert policy["manual_evidence_max_age_days"] == 365
    assert policy["reviewed_evidence_review_days"] == 365
    assert policy["data_source_windows"]["market_data"] == "latest_expected_trading_day"
    assert policy["data_source_windows"]["sec_13f"] == "quarterly_filing_delay"
    assert policy["affects_score"] is False
    assert policy["not_investment_advice"] is True
    assert payload["stale_review_queue"]["not_investment_advice"] is True
    assert detect_forbidden_language(payload) == []


def test_phase49_stale_manual_evidence_is_added_to_review_queue(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post("/api/manual-evidence", json=_payload()).json()
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()

    queue = response["stale_review_queue"]
    items = queue["items"]
    stale_item = next(item for item in items if item.get("evidence_id") == created["evidence_id"])

    assert queue["stale_count"] >= 1
    assert queue["high_priority_count"] >= 1
    assert stale_item["category"] == "qualitative_evidence"
    assert stale_item["trigger"] == "stale_manual_evidence"
    assert stale_item["priority"] == "high"
    assert stale_item["recommended_action"] == "refresh_or_archive"
    assert stale_item["blocks_confidence_upgrade"] is True
    assert stale_item["affects_score"] is False
    assert stale_item["source_date"] == "2023-01-01"
    assert "365" in stale_item["reason"]
    assert "stale_review_queue" in response["data_quality_summary"]["excluded_from_scoring"]
    assert "Review stale evidence queue" in json.dumps(response["next_manual_checks"])


def test_phase49_review_due_manual_evidence_is_added_to_queue(monkeypatch):
    _use_tmp_store(monkeypatch)
    created = client.post(
        "/api/manual-evidence",
        json=_payload(
            criterion="visionary_founder_ceo",
            evidence_type="founder_operator",
            source_date="2025-01-01",
            review_status="reviewed",
            source_reliability_label="company_investor_relations",
            summary="Reviewed founder-operator evidence that is now due for a scheduled freshness review.",
        ),
    ).json()
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()

    queue = response["stale_review_queue"]
    due_item = next(item for item in queue["items"] if item.get("evidence_id") == created["evidence_id"])

    assert queue["review_due_count"] >= 1
    assert due_item["trigger"] in {"review_due", "stale_manual_evidence"}
    assert due_item["review_due_at"]
    assert due_item["recommended_action"] in {"review_evidence", "refresh_or_archive"}
    assert due_item["blocks_confidence_upgrade"] is True
    assert due_item["affects_score"] is False


def test_phase49_stale_source_quality_category_is_added_to_queue(monkeypatch):
    _use_tmp_store(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", False)
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"}).json()

    queue = response["stale_review_queue"]
    source_items = [item for item in queue["items"] if item["trigger"] == "stale_source_status"]

    assert queue["source_stale_count"] == len(source_items)
    assert source_items
    assert all(item["category"] for item in source_items)
    assert all(item["affects_score"] is False for item in source_items)
    assert all(item["recommended_action"] == "verify_or_refresh_source" for item in source_items)
