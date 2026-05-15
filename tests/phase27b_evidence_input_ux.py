from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.reports.stock_analysis import _build_qualitative_evidence_assessment
from backend.app.schemas.stock_analysis import QualitativeEvidenceInput


CANONICAL_EVIDENCE = {
    "criterion": "monopoly_power",
    "criterion_id": 1,
    "criterion_name": "Market Monopoly / Entry Barrier",
    "submetric": "switching_cost",
    "evidence_type": "switching_cost",
    "summary": "Customer migration requires workflow retraining and data migration.",
    "source_label": "user research note",
    "confidence": 0.6,
    "user_provided": True,
    "limitations": ["User-provided evidence requires human verification."],
}


def test_phase27b_qualitative_evidence_accepts_optional_canonical_metadata():
    evidence = QualitativeEvidenceInput(**CANONICAL_EVIDENCE)

    assert evidence.criterion_id == 1
    assert evidence.criterion_name == "Market Monopoly / Entry Barrier"
    assert evidence.submetric == "switching_cost"


def test_phase27b_qualitative_evidence_rejects_invalid_canonical_id():
    with pytest.raises(ValidationError):
        QualitativeEvidenceInput(**{**CANONICAL_EVIDENCE, "criterion_id": 21})


def test_phase27b_assessment_preserves_canonical_metadata_for_request_scoped_evidence():
    assessment = _build_qualitative_evidence_assessment(
        "NVDA",
        [QualitativeEvidenceInput(**CANONICAL_EVIDENCE)],
    )

    assert assessment["accepted_evidence_count"] == 1
    item = assessment["evidence_items"][0]
    assert item["origin"] == "request_scoped"
    assert item["criterion"] == "monopoly_power"
    assert item["criterion_id"] == 1
    assert item["criterion_name"] == "Market Monopoly / Entry Barrier"
    assert item["submetric"] == "switching_cost"


def test_phase27b_legacy_request_scoped_evidence_remains_supported():
    evidence = QualitativeEvidenceInput(
        criterion="network_effect",
        evidence_type="platform_ecosystem",
        summary="Developer ecosystem evidence requiring manual verification.",
        source_label="user research note",
        confidence=0.6,
        user_provided=True,
        limitations=["Manual review required."],
    )
    assessment = _build_qualitative_evidence_assessment("NVDA", [evidence])

    assert assessment["accepted_evidence_count"] == 1
    item = assessment["evidence_items"][0]
    assert item["criterion"] == "network_effect"
    assert item["criterion_id"] is None
    assert item["criterion_name"] is None
    assert item["submetric"] is None
