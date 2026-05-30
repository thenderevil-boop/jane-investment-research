from __future__ import annotations

from typing import Any

ALLOWED_EVIDENCE_TYPES = {"financial_proxy", "qualitative", "semi_structured"}


def _criterion(
    criterion_id: int,
    criterion_name: str,
    submetrics: list[str],
    evidence_type: str,
    auto_derivable_submetrics: list[str] | None = None,
    financial_proxy_source: str | None = None,
    requires_user_input_submetrics: list[str] | None = None,
) -> dict[str, Any]:
    auto = auto_derivable_submetrics or []
    requires_user = requires_user_input_submetrics
    if requires_user is None:
        requires_user = [submetric for submetric in submetrics if submetric not in auto]
    return {
        "criterion_id": criterion_id,
        "criterion_name": criterion_name,
        "submetrics": submetrics,
        "evidence_type": evidence_type,
        "auto_derivable_submetrics": auto,
        "requires_user_input_submetrics": requires_user,
        "financial_proxy_source": financial_proxy_source,
    }


JANE_CRITERIA: list[dict[str, Any]] = [
    _criterion(1, "Market Monopoly / Entry Barrier", ["switching_cost", "network_effect", "economies_of_scale", "intangible_assets", "regulatory_moat", "ip_moat", "customer_lock_in", "infrastructure_necessity"], "qualitative"),
    _criterion(2, "Visionary Founder / CEO", ["founder_is_ceo", "long_term_vision_consistency", "milestone_execution_record", "founder_ownership", "crisis_execution_history"], "financial_proxy", ["founder_ownership"], "yfinance"),
    _criterion(3, "Early Market Skepticism", ["negative_analyst_consensus", "media_skepticism", "short_interest_proxy", "product_category_disbelief"], "financial_proxy", ["short_interest_proxy"], "yfinance"),
    _criterion(4, "Disruptive Innovation", ["new_category_creation", "cost_curve_disruption", "business_model_disruption", "user_workflow_replacement"], "qualitative"),
    _criterion(5, "Technology and R&D Commitment", ["rd_percent_of_revenue", "patent_quality", "product_release_cadence", "technical_benchmark_advantage"], "semi_structured", ["rd_percent_of_revenue"], "yfinance"),
    _criterion(6, "Scalable Business Model", ["gross_margin_expansion", "operating_leverage", "low_marginal_cost", "platform_economics"], "financial_proxy", ["gross_margin_expansion", "operating_leverage"], "yfinance"),
    _criterion(7, "Brand and Fandom", ["organic_search_trend", "social_mentions", "customer_advocacy", "pricing_power"], "qualitative"),
    _criterion(8, "Data Advantage", ["proprietary_data_loop", "personalization_loop", "usage_improves_product", "hard_to_replicate_dataset"], "qualitative"),
    _criterion(9, "Capital Allocation Ability", ["roic", "reinvestment_effectiveness", "acquisition_discipline", "shareholder_dilution_control"], "financial_proxy", ["roic", "reinvestment_effectiveness"], "yfinance_sec"),
    _criterion(10, "Free Cash Flow Creation", ["positive_fcf", "fcf_margin", "fcf_growth_trend", "cash_conversion_quality"], "financial_proxy", ["positive_fcf", "fcf_margin", "fcf_growth_trend", "cash_conversion_quality"], "yfinance"),
    _criterion(11, "Mega Trend Alignment", ["jane_theme_alignment", "industry_cagr", "policy_support", "capital_inflow"], "qualitative"),
    _criterion(12, "Talent Attraction and Retention", ["hiring_trend", "key_executive_retention", "technical_team_reputation", "employee_review_trend"], "qualitative"),
    _criterion(13, "Global Market Expansion", ["international_revenue_mix", "global_tam", "geographic_expansion", "global_partnerships"], "semi_structured", ["international_revenue_mix"], "sec_companyfacts"),
    _criterion(14, "Life-Changing / Necessary Product", ["mission_critical_usage", "daily_or_weekly_usage", "customer_dependency", "infrastructure_role"], "qualitative"),
    _criterion(15, "Regulatory / Government Relationship", ["government_contracts", "regulatory_licenses", "policy_alignment", "defense_or_infrastructure_status"], "semi_structured", ["government_contracts"], "sec_companyfacts"),
    _criterion(16, "Network Effects", ["user_growth_increases_value", "marketplace_liquidity", "developer_ecosystem", "data_network_effect"], "qualitative"),
    _criterion(17, "Mission and Narrative Power", ["clear_long_term_mission", "founder_narrative_consistency", "brand_story_adoption", "investor_narrative_durability"], "qualitative"),
    _criterion(18, "Patents and IP", ["patent_count", "patent_relevance", "defensibility", "licensing_evidence"], "semi_structured", ["patent_count"], "uspto_patentsview"),
    _criterion(19, "VC / Institutional Support", ["institutional_support", "fund_support", "strategic_investors", "ownership_quality"], "financial_proxy", ["institutional_support", "fund_support"], "sec_13f"),
    _criterion(20, "Retention / Repurchase Rate", ["net_revenue_retention", "churn", "repeat_purchase", "cohort_retention", "subscription_renewal"], "semi_structured", [], None, ["net_revenue_retention", "churn", "cohort_retention"]),
]


def get_criterion_by_id(criterion_id: int) -> dict[str, Any]:
    for criterion in JANE_CRITERIA:
        if criterion["criterion_id"] == criterion_id:
            return criterion
    raise ValueError(f"Unknown Research criterion_id: {criterion_id}")
