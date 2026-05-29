from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def _use_tmp_stores(monkeypatch):
    root = Path("backend/raw_store/cache/test_phase70") / uuid4().hex
    manual = root / "manual"
    candidates = root / "candidates"
    manual.mkdir(parents=True, exist_ok=True)
    candidates.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", manual)
    monkeypatch.setattr(config, "CANDIDATE_WORKSPACE_DIR", candidates)


def _candidate(ticker: str, *, priority: str = "medium", theme: str = "AI infrastructure") -> dict:
    return {
        "ticker": ticker,
        "market": "US",
        "theme": theme,
        "user_reason": "Externally discovered candidate to validate.",
        "source_label": "User watchlist note",
        "source_date": "2026-05-29",
        "priority": priority,
        "tags": ["phase70"],
    }


def _manual_evidence(ticker: str, criterion: str, **overrides) -> dict:
    payload = {
        "ticker": ticker,
        "criterion": criterion,
        "evidence_type": "ecosystem_comparison",
        "summary": f"{ticker} has user-supplied evidence for {criterion}, pending normal review.",
        "source_label": "User research note",
        "source_date": "2026-05-20",
        "confidence": 0.7,
        "review_status": "reviewed",
        "source_reliability_label": "user_note",
        "limitations": ["Manual evidence requires independent verification."],
    }
    payload.update(overrides)
    return payload


def test_phase70_candidate_readiness_comparison_summarizes_candidates_without_ranking_or_scoring(monkeypatch):
    _use_tmp_stores(monkeypatch)
    client.post("/api/manual-evidence", json=_manual_evidence("NVDA", "network_effect"))
    client.post("/api/manual-evidence", json=_manual_evidence("NVDA", "visionary_founder_ceo"))
    nvda = client.post("/api/candidates", json=_candidate("NVDA", priority="high")).json()
    tsla = client.post("/api/candidates", json=_candidate("TSLA", priority="high", theme="humanoid robotics")).json()
    client.patch(f"/api/candidates/{nvda['candidate_id']}", json={"status": "researching"})
    client.patch(f"/api/candidates/{tsla['candidate_id']}", json={"status": "researching"})

    response = client.get("/api/candidates/readiness-comparison")
    payload = response.json()

    assert response.status_code == 200
    assert payload["version"] == "phase70_candidate_readiness_comparison_v1"
    assert payload["not_investment_advice"] is True
    assert payload["affects_score"] is False
    assert payload["final_score_unchanged"] is True
    assert payload["ranking_policy"] == "not_ranked_by_score_or_recommendation"
    assert payload["summary"]["candidate_count"] == 2
    assert payload["summary"]["needs_manual_evidence_count"] >= 1

    items = payload["items"]
    by_ticker = {item["ticker"]: item for item in items}
    assert set(by_ticker) == {"TSLA", "NVDA"}
    tsla_item = by_ticker["TSLA"]
    nvda_item = by_ticker["NVDA"]
    assert tsla_item["readiness_state"] == "needs_evidence_before_comparison"
    assert tsla_item["top_gap"]["source_route"] == "manual_evidence"
    assert tsla_item["next_action"].startswith("Add or review manual evidence")
    assert nvda_item["readiness_state"] in {"comparison_ready_for_review", "needs_evidence_before_comparison"}
    assert nvda_item["evidence_completeness"]["covered_count"] == 2
    assert nvda_item["evidence_completeness"]["missing_count"] < tsla_item["evidence_completeness"]["missing_count"]
    assert "latest_score" not in tsla_item
    assert detect_forbidden_language(payload) == []


def test_phase70_candidate_readiness_comparison_empty_workspace_boundary(monkeypatch):
    _use_tmp_stores(monkeypatch)
    payload = client.get("/api/candidates/readiness-comparison").json()

    assert payload["version"] == "phase70_candidate_readiness_comparison_v1"
    assert payload["items"] == []
    assert payload["summary"]["candidate_count"] == 0
    assert payload["missing_data"] == ["candidate workspace is empty"]
    assert payload["not_investment_advice"] is True
    assert payload["affects_score"] is False
    assert payload["final_score_unchanged"] is True
