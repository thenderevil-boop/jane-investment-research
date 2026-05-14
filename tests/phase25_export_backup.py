from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.schemas.stock_analysis import AnalyzeStockResponse
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def _use_tmp_stores(monkeypatch):
    root = Path("backend/raw_store/cache/test_phase25") / uuid4().hex
    manual = root / "manual"
    candidates = root / "candidates"
    manual.mkdir(parents=True, exist_ok=True)
    candidates.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", manual)
    monkeypatch.setattr(config, "CANDIDATE_WORKSPACE_DIR", candidates)


def _manual_payload(**overrides) -> dict:
    payload = {
        "ticker": "NVDA",
        "criterion": "network_effect",
        "evidence_type": "platform_ecosystem",
        "summary": "CUDA developer ecosystem and software stack are tracked as manual network effect evidence requiring review.",
        "source_label": "User research note",
        "source_url": "https://example.com/user-note",
        "source_date": "2026-05-06",
        "confidence": 0.65,
        "review_status": "unreviewed",
        "limitations": ["Requires manual verification against official filings or independent sources."],
        "tags": ["CUDA"],
    }
    payload.update(overrides)
    return payload


def _candidate_payload(**overrides) -> dict:
    payload = {
        "ticker": "NVDA",
        "market": "US",
        "theme": "AI infrastructure",
        "user_reason": "External trend research candidate",
        "source_label": "User watchlist note",
        "source_date": "2026-05-08",
        "priority": "high",
        "tags": ["AI", "GPU"],
    }
    payload.update(overrides)
    return payload


def _export_payload(**overrides) -> dict:
    payload = {
        "ticker": "NVDA",
        "market": "US",
        "research_context": {
            "theme": "AI infrastructure",
            "user_reason": "External trend research",
        },
        "format": "json",
        "include_raw_evidence": False,
        "include_manual_evidence": True,
        "redact_sensitive_fields": True,
    }
    payload.update(overrides)
    return payload


def test_phase25_analyze_stock_export_json_default(monkeypatch):
    _use_tmp_stores(monkeypatch)
    response = client.post("/api/analyze-stock/export", json=_export_payload()).json()
    report = response["report"]

    assert response["export_id"].startswith("export_")
    assert response["format"] == "json"
    assert response["ticker"] == "NVDA"
    assert response["filename"].startswith("jane-validation-NVDA-")
    assert response["filename"].endswith(".json")
    assert response["not_investment_advice"] is True
    assert response["source_status"]["provider"] == "analyze_stock_export"
    assert report["export_metadata"]["schema_version"] == "phase25_validation_export_v1"
    assert report["export_metadata"]["not_investment_advice"] is True
    assert report["validation_summary"]["ticker"] == "NVDA"
    assert report["data_quality_summary"]
    assert isinstance(report["evidence_matrix"], list)
    assert report["score_driver_breakdown"]
    assert isinstance(report["next_manual_checks"], list)
    assert "raw_evidence" not in report
    assert detect_forbidden_language(response) == []
    assert '"source_type": "mixed"' not in json.dumps(response)


def test_phase25_analyze_stock_export_raw_evidence_is_optional_and_redacted(monkeypatch):
    _use_tmp_stores(monkeypatch)
    from backend.app.services import export_service
    from backend.app.reports.stock_analysis import analyze_stock as real_analyze_stock

    def fake_analyze_stock(request):
        result = real_analyze_stock(request)
        data = result.model_dump(mode="json")
        data["company_profile"]["provider_url"] = "https://query1.finance.yahoo.com/v8/finance/chart/NVDA?token=SECRET"
        data["company_profile"]["local_path"] = "D:\\jane-investment-research\\backend\\raw_store\\cache\\provider.json"
        return AnalyzeStockResponse.model_validate(data)

    monkeypatch.setattr(export_service, "analyze_stock", fake_analyze_stock)
    response = client.post("/api/analyze-stock/export", json=_export_payload(include_raw_evidence=True)).json()
    text = json.dumps(response)

    assert "raw_evidence" in response["report"]
    assert "query1.finance.yahoo.com" not in text
    assert "D:\\jane-investment-research" not in text
    assert "[redacted_url]" in text
    assert detect_forbidden_language(response) == []


def test_phase25_markdown_export_contains_required_sections(monkeypatch):
    _use_tmp_stores(monkeypatch)
    response = client.post("/api/analyze-stock/export", json=_export_payload(format="markdown")).json()
    report = response["report"]

    assert response["format"] == "markdown"
    assert response["filename"].endswith(".md")
    assert isinstance(report, str)
    assert "Ticker Validation Report: NVDA" in report
    assert "Research reference only. Not investment advice." in report
    assert "## Validation Summary" in report
    assert "## Data Quality" in report
    assert "## Next Manual Checks" in report
    assert detect_forbidden_language(response) == []


def test_phase25_export_does_not_persist_request_scoped_evidence_or_change_score(monkeypatch):
    _use_tmp_stores(monkeypatch)
    request_evidence = {
        "criterion": "network_effect",
        "evidence_type": "platform_ecosystem",
        "summary": "Request scoped ecosystem claim requiring manual verification.",
        "source_label": "User temporary note",
        "source_date": "2026-05-08",
        "confidence": 0.6,
        "user_provided": True,
        "limitations": ["Request scoped only."],
    }
    base = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US", "qualitative_evidence": [request_evidence]}).json()
    exported = client.post("/api/analyze-stock/export", json=_export_payload(qualitative_evidence=[request_evidence])).json()
    listed = client.get("/api/manual-evidence", params={"ticker": "NVDA"}).json()

    assert exported["report"]["validation_summary"]["score"] == base["research_verdict"]["score"]
    assert exported["report"]["validation_summary"]["confidence"] == base["research_verdict"]["confidence"]
    assert listed == []
    assert exported["report"]["qualitative_evidence_assessment"]["request_evidence_count"] == 1


def test_phase25_local_backup_export_reads_local_stores(monkeypatch):
    _use_tmp_stores(monkeypatch)
    active_manual = client.post("/api/manual-evidence", json=_manual_payload()).json()
    archived_manual = client.post("/api/manual-evidence", json=_manual_payload(criterion="mega_trend_fit", evidence_type="user_provided_note", summary="Archived theme evidence stored for audit.", review_status="archived")).json()
    rejected_manual = client.post("/api/manual-evidence", json=_manual_payload(criterion="visionary_founder_ceo", evidence_type="founder_operator", summary="Rejected founder evidence stored for audit.", review_status="rejected")).json()
    active_candidate = client.post("/api/candidates", json=_candidate_payload()).json()
    archived_candidate = client.post("/api/candidates", json=_candidate_payload(ticker="MSFT")).json()
    client.delete(f"/api/candidates/{archived_candidate['candidate_id']}")

    backup = client.get(
        "/api/local-backup/export",
        params={
            "include_manual_evidence": True,
            "include_candidate_workspace": True,
            "include_archived": False,
            "include_rejected": False,
        },
    ).json()

    manual_ids = {item["evidence_id"] for item in backup["manual_evidence"]["items"]}
    candidate_ids = {item["candidate_id"] for item in backup["candidate_workspace"]["items"]}
    assert backup["backup_metadata"]["schema_version"] == "phase25_local_backup_v1"
    assert backup["not_investment_advice"] is True
    assert backup["source_status"]["provider"] == "local_backup_export"
    assert manual_ids == {active_manual["evidence_id"]}
    assert archived_manual["evidence_id"] not in manual_ids
    assert rejected_manual["evidence_id"] not in manual_ids
    assert candidate_ids == {active_candidate["candidate_id"]}

    audit_backup = client.get(
        "/api/local-backup/export",
        params={
            "include_manual_evidence": True,
            "include_candidate_workspace": True,
            "include_archived": True,
            "include_rejected": True,
        },
    ).json()
    audit_manual_ids = {item["evidence_id"] for item in audit_backup["manual_evidence"]["items"]}
    audit_candidate_ids = {item["candidate_id"] for item in audit_backup["candidate_workspace"]["items"]}
    assert {active_manual["evidence_id"], archived_manual["evidence_id"], rejected_manual["evidence_id"]} <= audit_manual_ids
    assert archived_candidate["candidate_id"] in audit_candidate_ids
    assert "cache/sec" not in json.dumps(audit_backup)
    assert detect_forbidden_language(audit_backup) == []


def test_phase25_local_backup_does_not_call_analyze_stock(monkeypatch):
    _use_tmp_stores(monkeypatch)
    from backend.app.services import export_service

    def fail_analyze_stock(_request):
        raise AssertionError("local backup must not call analyze-stock")

    monkeypatch.setattr(export_service, "analyze_stock", fail_analyze_stock)
    response = client.get("/api/local-backup/export").json()

    assert response["source_status"]["provider"] == "local_backup_export"
    assert response["not_investment_advice"] is True
