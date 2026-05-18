from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.manual_evidence import ManualQualitativeEvidence
from backend.app.schemas.stock_analysis import AnalyzeStockResponse, QualitativeEvidenceInput
from backend.app.utils.forbidden_language import detect_forbidden_language

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_schema() -> dict:
    return json.loads(_read("schemas/analyze_stock.schema.json"))


def _normalize(value: dict) -> dict:
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False))


def test_committed_analyze_stock_schema_matches_pydantic_response_schema() -> None:
    committed = _normalize(_load_schema())
    generated = _normalize(AnalyzeStockResponse.model_json_schema())

    assert committed == generated


def test_phase27b_qualitative_evidence_metadata_contract_is_documented() -> None:
    props = QualitativeEvidenceInput.model_json_schema()["properties"]

    for field in ["criterion_id", "criterion_name", "submetric"]:
        assert field in props
        assert field in _read("docs/API_SPEC.md")
        assert field in _read("frontend/src/types.ts")

    criterion_id_schema = props["criterion_id"]["anyOf"][0]
    assert criterion_id_schema["minimum"] == 1
    assert criterion_id_schema["maximum"] == 20


def test_phase28_and_phase29_response_fields_are_in_schema_docs_and_types() -> None:
    schema = _load_schema()
    top_level_props = schema["properties"]
    defs = schema["$defs"]
    api_spec = _read("docs/API_SPEC.md")
    frontend_types = _read("frontend/src/types.ts")

    for field in ["jane_criteria_coverage", "validation_os_report"]:
        assert field in top_level_props
        assert field in api_spec
        assert field in frontend_types

    for definition in [
        "JaneCriterionCoverageItem",
        "JaneCriteriaCoverageMatrix",
        "ValidationOSEvidenceGap",
        "ValidationOSReport",
    ]:
        assert definition in defs
        assert definition in frontend_types


def test_phase33_research_note_workflow_contract_is_documented() -> None:
    schema = _load_schema()
    evidence_item_props = schema["$defs"]["QualitativeEvidenceAssessmentItem"]["properties"]
    manual_evidence_props = ManualQualitativeEvidence.model_json_schema()["properties"]
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    frontend_types = _read("frontend/src/types.ts")

    for field in ["note_title", "research_question", "thesis_direction", "workflow_status"]:
        assert field in evidence_item_props
        assert field in manual_evidence_props
        assert field in api_spec
        assert field in readme
        assert field in changelog
        assert field in frontend_types

    assert "ManualEvidenceThesisDirection" in frontend_types
    assert "ManualEvidenceWorkflowStatus" in frontend_types


def test_phase_status_documents_are_at_phase30_or_newer() -> None:
    for path in ["README.md", "AGENTS.md", "docs/API_SPEC.md", "docs/CHANGELOG.md"]:
        text = _read(path)
        assert "Phase 30" in text, path

    readme = _read("README.md")
    agents = _read("AGENTS.md")
    changelog = _read("docs/CHANGELOG.md")
    assert "contract" in readme.lower()
    assert "contract" in agents.lower()
    assert "contract" in changelog.lower()


def test_live_analyze_stock_payload_has_documented_phase28_and_phase29_fields() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["not_investment_advice"] is True
    assert "jane_criteria_coverage" in payload
    assert "validation_os_report" in payload
    assert payload["validation_os_report"]["not_investment_advice"] is True
    assert payload["jane_criteria_coverage"]["not_investment_advice"] is True
    assert detect_forbidden_language(payload) == []
