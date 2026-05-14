from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def _use_tmp_stores(monkeypatch):
    root = Path("backend/raw_store/cache/test_phase26") / uuid4().hex
    manual = root / "manual"
    candidates = root / "candidates"
    manual.mkdir(parents=True, exist_ok=True)
    candidates.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", manual)
    monkeypatch.setattr(config, "CANDIDATE_WORKSPACE_DIR", candidates)


def _analyze_payload() -> dict:
    return {
        "ticker": "NVDA",
        "market": "US",
        "research_context": {
            "theme": "AI infrastructure",
            "user_reason": "External trend research",
        },
    }


def test_phase26_analyze_stock_quality_summary_and_legacy_visibility(monkeypatch):
    _use_tmp_stores(monkeypatch)
    response = client.post("/api/analyze-stock", json=_analyze_payload()).json()

    quality = response["validation_quality_summary"]
    assert quality["ticker"] == "NVDA"
    assert quality["overall_validation_level"] in {
        "high_quality_validation",
        "usable_preliminary_validation",
        "limited_validation",
        "insufficient_validation",
    }
    assert quality["not_investment_advice"] is True
    assert "recommend" not in json.dumps(quality).lower()

    legacy = response["leadership_score"]
    assert legacy["deprecated"] is True
    assert legacy["replaced_by"] == "jane_company_quality"
    assert legacy["affects_final_score"] is False

    legacy_row = next(row for row in response["evidence_matrix"] if row["category"] == "legacy_leadership_score")
    assert legacy_row["is_deprecated"] is True
    assert legacy_row["replaced_by"] == "jane_company_quality"
    assert legacy_row["affects_final_score"] is False
    assert legacy_row["review_priority"] == "low"
    assert detect_forbidden_language(response) == []
    assert '"source_type": "mixed"' not in json.dumps(response)


def test_phase26_explanations_breakdowns_and_prioritized_checks(monkeypatch):
    _use_tmp_stores(monkeypatch)
    response = client.post("/api/analyze-stock", json=_analyze_payload()).json()

    cross_explanation = response["fundamentals_cross_check"]["explanation"]
    assert cross_explanation["agreement_level"] == response["fundamentals_cross_check"]["agreement_level"]
    assert isinstance(cross_explanation["metrics_requiring_review"], list)
    assert "always correct" not in json.dumps(cross_explanation).lower()

    smart_breakdown = response["smart_money"]["source_quality_breakdown"]
    assert smart_breakdown["institutional_13f"]["is_delayed_quarterly"] is True
    assert smart_breakdown["institutional_13f"]["is_real_time_signal"] is False
    assert smart_breakdown["options"]["source_type"] == "mock"

    valuation_explanation = response["valuation_context"]["explanation"]
    assert valuation_explanation["valuation_risk_label"] in {"elevated", "moderate", "low", "unavailable"}
    assert valuation_explanation["metrics_used"]

    checks = response["next_manual_checks"]
    assert all("priority_rank" in item and "blocking" in item for item in checks)
    assert [item["priority_rank"] for item in checks] == list(range(1, len(checks) + 1))
    priorities = {"high": 0, "medium": 1, "low": 2}
    assert [priorities[item["priority"]] for item in checks] == sorted(priorities[item["priority"]] for item in checks)
    assert len({(item["area"], item["check"].lower()) for item in checks}) == len(checks)

    assert all("review_priority" in row for row in response["evidence_matrix"])


def test_phase26_export_includes_quality_sections(monkeypatch):
    _use_tmp_stores(monkeypatch)
    payload = {
        **_analyze_payload(),
        "format": "json",
        "include_raw_evidence": False,
        "include_manual_evidence": True,
        "redact_sensitive_fields": True,
    }
    json_export = client.post("/api/analyze-stock/export", json=payload).json()
    report = json_export["report"]
    assert report["validation_quality_summary"]
    assert report["fundamentals_cross_check"]["explanation"]
    assert report["smart_money"]["source_quality_breakdown"]
    assert report["next_manual_checks"][0]["priority_rank"] == 1
    assert report["export_metadata"]["not_investment_advice"] is True

    markdown_export = client.post("/api/analyze-stock/export", json={**payload, "format": "markdown"}).json()
    markdown = markdown_export["report"]
    assert "## Validation Quality Summary" in markdown
    assert "## Source Quality Constraints" in markdown
    assert "## Fundamentals Cross-Check Explanation" in markdown
    assert "## Smart Money Source Quality" in markdown
    assert "## Valuation Risk Context" in markdown
    assert "## Prioritized Manual Checks" in markdown
    assert "Research reference only. Not investment advice." in markdown
