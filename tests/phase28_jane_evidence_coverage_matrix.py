from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def _analyze(payload: dict | None = None) -> dict:
    request = {"ticker": "NVDA", "market": "US"}
    if payload:
        request.update(payload)
    response = client.post("/api/analyze-stock", json=request)
    assert response.status_code == 200
    return response.json()


def _row(payload: dict, criterion_id: int) -> dict:
    return next(item for item in payload["jane_criteria_coverage"]["criteria"] if item["criterion_id"] == criterion_id)


def test_jane_coverage_matrix_has_20_canonical_rows_when_no_user_evidence() -> None:
    payload = _analyze()
    matrix = payload["jane_criteria_coverage"]

    assert len(matrix["criteria"]) == 20
    assert matrix["covered_count"] == 0
    assert matrix["insufficient_count"] >= 1
    assert matrix["not_investment_advice"] is True
    assert {item["criterion_id"] for item in matrix["criteria"]} == set(range(1, 21))


def test_jane_coverage_rows_include_required_fields() -> None:
    payload = _analyze()
    item = _row(payload, 1)

    assert item["criterion_id"] == 1
    assert item["criterion_name"]
    assert item["coverage_status"] in {"covered", "partial", "insufficient"}
    assert isinstance(item["covered_submetrics"], list)
    assert isinstance(item["missing_submetrics"], list)
    assert item["requires_human_verification"] is True
    assert item["next_manual_check"]


def test_request_scoped_canonical_evidence_marks_submetric_covered() -> None:
    payload = _analyze(
        {
            "qualitative_evidence": [
                {
                    "criterion": "monopoly_power",
                    "criterion_id": 1,
                    "criterion_name": "Market Monopoly / Entry Barrier",
                    "submetric": "switching_cost",
                    "evidence_type": "switching_cost",
                    "summary": "Customer migration requires workflow retraining and data migration.",
                    "source_label": "user research note",
                    "confidence": 0.6,
                    "user_provided": True,
                    "limitations": ["Manual verification required."],
                }
            ],
        }
    )

    row = _row(payload, 1)
    assert row["coverage_status"] == "partial"
    assert "switching_cost" in row["covered_submetrics"]
    assert "switching_cost" not in row["missing_submetrics"]
    assert row["evidence_item_count"] == 1
    assert row["accepted_evidence_item_count"] == 1
    assert row["source_quality"] == "user_provided"


def test_rejected_evidence_does_not_mark_coverage() -> None:
    payload = _analyze(
        {
            "qualitative_evidence": [
                {
                    "criterion": "monopoly_power",
                    "criterion_id": 1,
                    "criterion_name": "Market Monopoly / Entry Barrier",
                    "submetric": "switching_cost",
                    "evidence_type": "switching_cost",
                    "summary": "",
                    "source_label": "user research note",
                    "confidence": 0.6,
                    "user_provided": True,
                    "limitations": ["Manual verification required."],
                }
            ],
        }
    )

    row = _row(payload, 1)
    assert "switching_cost" not in row["covered_submetrics"]
    assert row["coverage_status"] == "insufficient"
    assert row["accepted_evidence_item_count"] == 0


def test_phase28_preserves_existing_evidence_matrix_and_legacy_boundary() -> None:
    payload = _analyze()

    broad_matrix = {item["category"]: item for item in payload["evidence_matrix"]}
    assert "jane_company_quality" in broad_matrix
    assert "legacy_leadership_score" in broad_matrix
    assert payload["leadership_score"]["deprecated"] is True
    assert payload["leadership_score"]["affects_final_score"] is False
    assert payload["leadership_score"]["source_quality"] == "mock_only"
