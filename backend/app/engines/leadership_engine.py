from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_data import MOCK_SOURCE, MOCK_SOURCE_DATE
from backend.app.schemas.leadership import LeadershipCriterion, LeadershipScore
from backend.app.utils.confidence import source_confidence_weights

LIMITATION = "Phase 3 deterministic mock leadership engine; no live source connection."

CRITERIA: list[tuple[int, str, list[str]]] = [
    (1, "Market Monopoly / Entry Barrier", ["switching_cost", "network_effect", "economies_of_scale", "intangible_assets", "regulatory_moat", "ip_moat", "customer_lock_in", "infrastructure_necessity"]),
    (2, "Visionary Founder / CEO", ["founder_is_ceo", "long_term_vision_consistency", "milestone_execution_record", "founder_ownership", "crisis_execution_history"]),
    (3, "Early Market Skepticism", ["negative_analyst_consensus", "media_skepticism", "short_interest_proxy", "product_category_disbelief"]),
    (4, "Disruptive Innovation", ["new_category_creation", "cost_curve_disruption", "business_model_disruption", "user_workflow_replacement"]),
    (5, "Technology and R&D Commitment", ["rd_percent_of_revenue", "patent_quality", "product_release_cadence", "technical_benchmark_advantage"]),
    (6, "Scalable Business Model", ["gross_margin_expansion", "operating_leverage", "low_marginal_cost", "platform_economics"]),
    (7, "Brand and Fandom", ["organic_search_trend", "social_mentions", "customer_advocacy", "pricing_power"]),
    (8, "Data Advantage", ["proprietary_data_loop", "personalization_loop", "usage_improves_product", "hard_to_replicate_dataset"]),
    (9, "Capital Allocation Ability", ["roic", "reinvestment_effectiveness", "acquisition_discipline", "shareholder_dilution_control"]),
    (10, "Free Cash Flow Creation", ["positive_fcf", "fcf_margin", "fcf_growth_trend", "cash_conversion_quality"]),
    (11, "Mega Trend Alignment", ["jane_theme_alignment", "industry_cagr", "policy_support", "capital_inflow"]),
    (12, "Talent Attraction and Retention", ["hiring_trend", "key_executive_retention", "technical_team_reputation", "employee_review_trend"]),
    (13, "Global Market Expansion", ["international_revenue_mix", "global_tam", "geographic_expansion", "global_partnerships"]),
    (14, "Life-Changing / Necessary Product", ["mission_critical_usage", "daily_or_weekly_usage", "customer_dependency", "infrastructure_role"]),
    (15, "Regulatory / Government Relationship", ["government_contracts", "regulatory_licenses", "policy_alignment", "defense_or_infrastructure_status"]),
    (16, "Network Effects", ["user_growth_increases_value", "marketplace_liquidity", "developer_ecosystem", "data_network_effect"]),
    (17, "Mission and Narrative Power", ["clear_long_term_mission", "founder_narrative_consistency", "brand_story_adoption", "investor_narrative_durability"]),
    (18, "Patents and IP", ["patent_count", "patent_relevance", "defensibility", "licensing_evidence"]),
    (19, "VC / Institutional Support", ["institutional_support", "fund_support", "strategic_investors", "ownership_quality"]),
    (20, "Retention / Repurchase Rate", ["net_revenue_retention", "churn", "repeat_purchase", "cohort_retention", "subscription_renewal"]),
]


def _label(total: float) -> str:
    if total >= 16:
        return "worth_deep_research"
    if total >= 12:
        return "watchlist_candidate"
    return "weak_candidate"


def _confidence(supported_count: int, missing_data: list[str], override: float | None = None) -> float:
    if override is not None:
        return max(0, min(1, round(override, 2)))
    data_completeness = min(1.0, supported_count / 3)
    if missing_data:
        data_completeness = min(data_completeness, 0.35)
    recency, reliability = source_confidence_weights("mock")
    return round(data_completeness * 0.40 + recency * 0.30 + reliability * 0.30, 2)


def _score_from_supported_count(count: int) -> float:
    if count >= 3:
        return 1.0
    if count >= 1:
        return 0.5
    return 0.0


def _fallback_evidence_from_points(points: float) -> dict[int, dict[str, Any]]:
    remaining = max(0.0, min(20.0, points))
    evidence: dict[int, dict[str, Any]] = {}
    for criterion_id, _name, submetrics in CRITERIA:
        if remaining >= 1:
            supported = submetrics[:3]
            remaining -= 1
        elif remaining >= 0.5:
            supported = submetrics[:1]
            remaining -= 0.5
        else:
            supported = []
        evidence[criterion_id] = {
            "supported_submetrics": supported,
            "raw_data": {"mock_supported_submetrics": supported},
            "trend": "up" if supported else "unknown",
        }
    return evidence


def _normalize_evidence(data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    explicit = data.get("leadership_evidence")
    if isinstance(explicit, dict):
        normalized: dict[int, dict[str, Any]] = {}
        for key, value in explicit.items():
            try:
                normalized[int(key)] = value
            except (TypeError, ValueError):
                continue
        return normalized
    return _fallback_evidence_from_points(float(data.get("leadership_points", 0)))


def _criterion_from_evidence(
    criterion_id: int,
    criterion_name: str,
    submetrics: list[str],
    evidence: dict[str, Any] | None,
) -> LeadershipCriterion:
    missing_data: list[str] = []
    if not evidence:
        evidence = {}
        missing_data.append("criterion_evidence")
    supported = [item for item in evidence.get("supported_submetrics", []) if item in submetrics]
    unsupported = [item for item in submetrics if item not in supported]
    raw_data = evidence.get("raw_data") or {
        "supported_submetrics": supported,
        "unsupported_submetrics": unsupported,
    }
    if not supported:
        missing_data.append("supported_submetrics")
    if not raw_data:
        missing_data.append("raw_data")
    score = _score_from_supported_count(len(supported))
    confidence = _confidence(len(supported), missing_data, evidence.get("confidence"))
    return LeadershipCriterion(
        criterion_id=criterion_id,
        criterion_name=criterion_name,
        score=score,
        raw_data=raw_data,
        derived_metrics={
            "supported_submetric_count": len(supported),
            "recognized_submetric_count": len(submetrics),
            "unsupported_submetric_count": len(unsupported),
        },
        benchmark={"full_score_supported_submetrics": 3, "partial_score_supported_submetrics": 1},
        trend={"evidence_trend": evidence.get("trend", "stable" if supported else "unknown")},
        evidence_summary=(
            f"{len(supported)} supported submetrics found for {criterion_name}."
            if supported
            else f"No supported mock evidence found for {criterion_name}."
        ),
        source=evidence.get("source", MOCK_SOURCE),
        source_date=evidence.get("source_date", MOCK_SOURCE_DATE),
        confidence=confidence,
        limitations=evidence.get("limitations", [LIMITATION]),
        missing_data=missing_data,
    )


def evaluate_leadership(data: dict[str, Any]) -> LeadershipScore:
    evidence_by_id = _normalize_evidence(data)
    criteria = [
        _criterion_from_evidence(criterion_id, name, submetrics, evidence_by_id.get(criterion_id))
        for criterion_id, name, submetrics in CRITERIA
    ]
    total = round(sum(criterion.score for criterion in criteria), 2)
    aggregate_missing = sorted(
        {
            f"criterion_{criterion.criterion_id}:{missing_item}"
            for criterion in criteria
            for missing_item in criterion.missing_data
        }
    )
    avg_confidence = round(sum(criterion.confidence for criterion in criteria) / len(criteria), 2)
    return LeadershipScore(
        score=total,
        label=_label(total),
        raw_data={
            "ticker": data.get("ticker"),
            "company_name": data.get("company_name"),
            "theme_count": len(data.get("themes", [])),
        },
        derived_metrics={
            "criteria_count": len(criteria),
            "full_score_criteria": sum(1 for criterion in criteria if criterion.score == 1),
            "partial_score_criteria": sum(1 for criterion in criteria if criterion.score == 0.5),
            "criteria": [criterion.model_dump() for criterion in criteria],
        },
        benchmark={
            "worth_deep_research_minimum": 16,
            "watchlist_candidate_minimum": 12,
            "max_score": 20,
        },
        trend={
            "leadership_evidence": "strong" if total >= 16 else "mixed" if total >= 12 else "weak",
        },
        source=MOCK_SOURCE,
        source_date=MOCK_SOURCE_DATE,
        confidence=avg_confidence,
        limitations=[LIMITATION],
        missing_data=aggregate_missing,
        criteria=criteria,
        deprecated=True,
        replaced_by="jane_company_quality",
        affects_score=False,
        legacy_affects_score=False,
        affects_final_score=False,
        source_quality="mock_only",
    )
