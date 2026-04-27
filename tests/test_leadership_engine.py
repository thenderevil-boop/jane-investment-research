from __future__ import annotations

import json
import re

from backend.app.engines.leadership_engine import CRITERIA, evaluate_leadership

PROHIBITED_PATTERNS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\bliquidate\b",
    r"\bexit all\b",
    r"\bsell half\b",
    r"\bmust invest\b",
    r"\bguaranteed\b",
]

CRITERION_FIELDS = {
    "criterion_id",
    "criterion_name",
    "score",
    "raw_data",
    "derived_metrics",
    "benchmark",
    "trend",
    "evidence_summary",
    "source",
    "source_date",
    "confidence",
    "limitations",
    "missing_data",
}


def assert_no_prohibited_language(payload: dict) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    for pattern in PROHIBITED_PATTERNS:
        assert not re.search(pattern, text), pattern


def build_evidence(supported_count: int, confidence: float | None = None) -> dict[int, dict]:
    evidence = {}
    for criterion_id, _name, submetrics in CRITERIA:
        entry = {
            "supported_submetrics": submetrics[:supported_count],
            "raw_data": {"mock_observations": submetrics[:supported_count]},
            "trend": "up" if supported_count else "unknown",
        }
        if confidence is not None:
            entry["confidence"] = confidence
        evidence[criterion_id] = entry
    return evidence


def assert_criterion_contract(criteria: list[dict]) -> None:
    assert len(criteria) == 20
    for criterion in criteria:
        assert CRITERION_FIELDS.issubset(criterion.keys())
        assert criterion["score"] in {0, 0.5, 1.0}
        assert 0 <= criterion["confidence"] <= 1


def test_full_leadership_score_reaches_worth_deep_research() -> None:
    result = evaluate_leadership(
        {
            "ticker": "FULL",
            "company_name": "Full Evidence Mock",
            "themes": ["AI energy infrastructure"],
            "leadership_evidence": build_evidence(3),
        }
    )
    payload = result.model_dump()
    assert result.score == 20
    assert result.label == "worth_deep_research"
    assert result.derived_metrics["full_score_criteria"] == 20
    assert result.missing_data == []
    assert_criterion_contract(payload["criteria"])
    assert_no_prohibited_language(payload)


def test_partial_leadership_score_uses_half_points() -> None:
    result = evaluate_leadership(
        {
            "ticker": "PART",
            "company_name": "Partial Evidence Mock",
            "themes": ["data center cooling"],
            "leadership_evidence": build_evidence(1),
        }
    )
    assert result.score == 10
    assert result.label == "weak_candidate"
    assert result.derived_metrics["partial_score_criteria"] == 20
    assert all(criterion.score == 0.5 for criterion in result.criteria)
    assert_no_prohibited_language(result.model_dump())


def test_missing_leadership_data_is_explicit_per_criterion() -> None:
    result = evaluate_leadership({"ticker": "MISS", "company_name": "Missing Evidence Mock"})
    payload = result.model_dump()
    assert result.score == 0
    assert result.label == "weak_candidate"
    assert len(result.criteria) == 20
    assert result.missing_data
    assert all(criterion["missing_data"] for criterion in payload["criteria"])
    assert_criterion_contract(payload["criteria"])


def test_low_confidence_flows_to_aggregate_score() -> None:
    result = evaluate_leadership(
        {
            "ticker": "LOWC",
            "company_name": "Low Confidence Mock",
            "themes": ["future industry radar"],
            "leadership_evidence": build_evidence(3, confidence=0.2),
        }
    )
    assert result.score == 20
    assert result.confidence == 0.2
    assert all(criterion.confidence == 0.2 for criterion in result.criteria)
    assert_no_prohibited_language(result.model_dump())
