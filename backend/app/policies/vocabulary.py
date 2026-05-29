from __future__ import annotations


ROUTE_VOCABULARY = frozenset([
    "daily_report",
    "stock_research",
    "operations",
    "evidence_library",
    "candidate_workspace",
])

RESEARCH_STATUS_VOCABULARY = frozenset([
    "high_conviction_candidate",
    "watchlist_candidate",
    "needs_evidence_before_research",
    "deprioritize_data_gaps",
])

BLOCKER_VOCABULARY = frozenset([
    "manual_evidence_gap",
    "data_source_fallback",
    "qualitative_evidence_missing",
    "provider_disabled",
    "cache_stale",
    "adR_coverage_limited",
])

NON_SCORING_FLAGS = frozenset([
    "affects_score",
    "final_score_unchanged",
    "not_investment_advice",
    "non_scoring_workflow",
])
