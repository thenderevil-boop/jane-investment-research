from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.engines.jane_criteria_canonical import (
    ALLOWED_EVIDENCE_TYPES,
    JANE_CRITERIA,
    get_criterion_by_id,
)
from backend.app.engines.leadership_engine import CRITERIA
from backend.app.main import app


EXPECTED_IDS = list(range(1, 21))


def test_all_20_criteria_are_present_with_correct_ids() -> None:
    assert [criterion["criterion_id"] for criterion in JANE_CRITERIA] == EXPECTED_IDS
    assert len({criterion["criterion_id"] for criterion in JANE_CRITERIA}) == 20


def test_canonical_names_and_submetrics_match_legacy_criteria_boundary() -> None:
    legacy_by_id = {criterion_id: (name, submetrics) for criterion_id, name, submetrics in CRITERIA}

    for criterion in JANE_CRITERIA:
        expected_name, expected_submetrics = legacy_by_id[criterion["criterion_id"]]
        assert criterion["criterion_name"] == expected_name
        assert criterion["submetrics"] == expected_submetrics


def test_evidence_type_is_allowed() -> None:
    assert ALLOWED_EVIDENCE_TYPES == {"financial_proxy", "qualitative", "semi_structured"}
    assert {criterion["evidence_type"] for criterion in JANE_CRITERIA} <= ALLOWED_EVIDENCE_TYPES


def test_auto_derivable_submetrics_are_subset_of_submetrics() -> None:
    for criterion in JANE_CRITERIA:
        assert set(criterion["auto_derivable_submetrics"]) <= set(criterion["submetrics"])


def test_requires_user_input_submetrics_are_subset_of_submetrics() -> None:
    for criterion in JANE_CRITERIA:
        assert set(criterion["requires_user_input_submetrics"]) <= set(criterion["submetrics"])


def test_auto_derivable_and_requires_user_input_do_not_overlap() -> None:
    for criterion in JANE_CRITERIA:
        assert not set(criterion["auto_derivable_submetrics"]) & set(criterion["requires_user_input_submetrics"])


def test_financial_proxy_source_is_present_only_when_auto_derivable() -> None:
    for criterion in JANE_CRITERIA:
        if criterion["auto_derivable_submetrics"]:
            assert criterion["financial_proxy_source"]
        else:
            assert criterion["financial_proxy_source"] is None


def test_get_criterion_by_id_returns_matching_criterion() -> None:
    criterion = get_criterion_by_id(10)

    assert criterion["criterion_id"] == 10
    assert criterion["criterion_name"] == "Free Cash Flow Creation"


def test_get_criterion_by_id_raises_for_unknown_id() -> None:
    with pytest.raises(ValueError):
        get_criterion_by_id(999)


def test_get_jane_criteria_endpoint_returns_all_criteria_and_safety_flag() -> None:
    client = TestClient(app)

    response = client.get("/api/jane-criteria")

    assert response.status_code == 200
    payload = response.json()
    assert payload["not_investment_advice"] is True
    assert payload["count"] == 20
    assert [criterion["criterion_id"] for criterion in payload["criteria"]] == EXPECTED_IDS
