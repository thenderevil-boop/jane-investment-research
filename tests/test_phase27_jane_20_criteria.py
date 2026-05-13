from __future__ import annotations

import json
from pathlib import Path

from backend.app.reports.stock_analysis import _build_qualitative_evidence_assessment


CANONICAL_CRITERIA = [
    "monopoly_power",
    "visionary_founder_ceo",
    "early_skepticism",
    "disruptive_innovation",
    "superior_technology_r_and_d",
    "scalable_business_model",
    "brand_power_fandom",
    "data_advantage",
    "capital_allocation",
    "cash_flow_creation",
    "mega_trend_fit",
    "talent_attraction_retention",
    "global_expansion",
    "life_changing_necessary_product",
    "regulatory_government_relationship",
    "network_effect",
    "mission_narrative_power",
    "patents_ip",
    "vc_institutional_support",
    "retention_repurchase_rate",
]

LEGACY_SIX_CRITERIA = [
    "monopoly_power",
    "visionary_founder_ceo",
    "disruptive_innovation",
    "network_effect",
    "continuous_r_and_d",
    "mega_trend_fit",
]


def _evidence_item(criterion: str) -> dict:
    return {
        "criterion": criterion,
        "evidence_type": "user_provided_note",
        "summary": f"Specific {criterion} claim requiring manual verification with cited user evidence.",
        "source_label": "User research note",
        "source_date": "2026-05-13",
        "confidence": 0.6,
        "user_provided": True,
        "limitations": ["Requires manual verification."],
    }


def test_phase27_canonical_json_exists_with_exactly_20_unique_criteria():
    path = Path("backend/app/data/jane_leadership_criteria.json")

    criteria = json.loads(path.read_text(encoding="utf-8"))

    assert [item["name"] for item in criteria] == CANONICAL_CRITERIA
    assert len({item["name"] for item in criteria}) == 20
    assert all(
        set(item) == {
            "name",
            "display_name_zh",
            "display_name_en",
            "description",
            "accepted_evidence_types",
            "manual_check_questions",
            "default_status",
        }
        for item in criteria
    )
    assert all(item["default_status"] == "insufficient" for item in criteria)


def test_phase27_all_20_canonical_criteria_are_accepted_by_qualitative_assessment():
    assessment = _build_qualitative_evidence_assessment(
        "NVDA",
        [_evidence_item(criterion) for criterion in CANONICAL_CRITERIA],
    )

    assert assessment["accepted_evidence_count"] == 20
    assert assessment["rejected_evidence_count"] == 0
    assert assessment["criteria_covered"] == sorted(CANONICAL_CRITERIA)


def test_phase27_unsupported_criterion_is_rejected():
    assessment = _build_qualitative_evidence_assessment("NVDA", [_evidence_item("unsupported_criterion")])

    assert assessment["accepted_evidence_count"] == 0
    assert assessment["rejected_evidence_count"] == 1
    assert assessment["evidence_items"][0]["accepted"] is False
    assert assessment["evidence_items"][0]["acceptance_reason"] == "Rejected because criterion is unsupported."


def test_phase27_legacy_six_qualitative_criteria_still_work():
    assessment = _build_qualitative_evidence_assessment(
        "NVDA",
        [_evidence_item(criterion) for criterion in LEGACY_SIX_CRITERIA],
    )

    assert assessment["accepted_evidence_count"] == 6
    assert assessment["rejected_evidence_count"] == 0
    assert set(LEGACY_SIX_CRITERIA).issubset(set(assessment["criteria_covered"]))
