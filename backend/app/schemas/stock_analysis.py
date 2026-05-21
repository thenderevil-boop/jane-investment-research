from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.common import DataQualitySummary, DataSourceStatus, HumanVerificationQueueItem, ScoreObject
from backend.app.schemas.daily_report import JaneReferenceConditions
from backend.app.schemas.earnings_transcript import EarningsTranscriptAnalysis
from backend.app.schemas.government_relationship import GovernmentRelationshipEvidence
from backend.app.schemas.jane_external_evidence import JaneCriteriaExternalEvidence
from backend.app.schemas.leadership import LeadershipScore
from backend.app.schemas.macro_regime import MacroRegimeOutput


class StockUserContext(BaseModel):
    friends_asking_about_stock: bool = False
    social_discussion_level: Literal["low", "medium", "high"] = "low"


class ResearchContext(BaseModel):
    theme: str | None = None
    user_reason: str | None = None


class QualitativeEvidenceInput(BaseModel):
    evidence_id: str | None = None
    criterion: str
    criterion_id: int | None = Field(default=None, ge=1, le=20)
    criterion_name: str | None = None
    submetric: str | None = None
    evidence_type: str
    summary: str = ""
    source_label: str = ""
    source_url: str | None = None
    source_date: str | None = None
    confidence: float = 0.5
    user_provided: bool = True
    limitations: list[str] = Field(default_factory=list)
    comparison_context: dict[str, Any] | None = None


class AnalyzeStockRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    market: Literal["US"] = "US"
    period: str = "3Y"
    research_context: ResearchContext | None = None
    user_context: StockUserContext = Field(default_factory=StockUserContext)
    qualitative_evidence: list[QualitativeEvidenceInput] = Field(default_factory=list)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class ResearchVerdict(BaseModel):
    label: Literal["worth_deep_research", "watchlist_candidate", "insufficient_data", "high_risk_context"]
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    summary: str
    confidence_factors: dict[str, list[str]] = Field(
        default_factory=lambda: {"confidence_boosters": [], "confidence_limiters": []}
    )


class CandidateValidationSummary(BaseModel):
    ticker: str
    research_priority: Literal["worth_deep_research", "watchlist_candidate", "insufficient_data", "high_risk_context"]
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    environment_assessment: str
    company_assessment: str
    smart_money_assessment: str
    data_quality_assessment: str
    overall_summary: str
    primary_strengths: list[str]
    primary_risks: list[str]
    missing_or_mock_evidence: list[str]
    next_manual_checks: list[str]


class ValidationQualitySummary(BaseModel):
    ticker: str
    overall_validation_level: Literal["high_quality_validation", "usable_preliminary_validation", "limited_validation", "insufficient_validation"]
    why: str
    primary_supporting_evidence: list[str]
    primary_limiting_factors: list[str]
    manual_review_required: bool
    highest_priority_review_items: list[str]
    data_quality_grade: Literal["A", "B", "C", "D"]
    confidence_cap_applied: bool
    confidence_cap_reason: str | None = None
    not_investment_advice: bool = True


class EvidenceMatrixItem(BaseModel):
    category: Literal[
        "macro_environment",
        "company_profile",
        "financial_quality",
        "valuation_context",
        "sec_financial_facts",
        "fundamentals_cross_check",
        "qualitative_evidence",
        "comparison_evidence",
        "jane_company_quality",
        "financial_statement_signals",
        "leadership_score",
        "legacy_leadership_score",
        "smart_money",
        "insider_activity",
        "institutional_13f",
        "risk_flags",
    ]
    status: Literal["supportive", "neutral", "caution", "insufficient"]
    score: float | None = None
    confidence: float = Field(ge=0, le=1)
    source_quality: Literal["live_backed", "derived_live", "cached_live", "mixed_with_fallback", "user_context", "user_provided", "mock_only", "filing_backed", "provider_backed", "derived_from_mixed_sources", "insufficient"]
    summary: str
    key_evidence: list[str]
    limitations: list[str]
    why_it_matters: str | None = None
    review_priority: Literal["high", "medium", "low", "none"] = "none"
    affects_final_score: bool | None = None
    is_deprecated: bool = False
    replaced_by: str | None = None


class JaneCriterionCoverageItem(BaseModel):
    criterion_id: int = Field(ge=1, le=20)
    criterion_name: str
    evidence_type: Literal["financial_proxy", "qualitative", "semi_structured"]
    coverage_status: Literal["covered", "partial", "insufficient"]
    source_quality: Literal[
        "filing_backed",
        "derived_live",
        "cached_live",
        "user_context",
        "user_provided",
        "mixed_with_fallback",
        "mock_only",
        "provider_backed",
        "derived_from_mixed_sources",
        "insufficient",
    ]
    confidence: float = Field(ge=0, le=1)
    auto_derivable_submetrics: list[str]
    requires_user_input_submetrics: list[str]
    covered_submetrics: list[str]
    missing_submetrics: list[str]
    evidence_item_count: int = 0
    accepted_evidence_item_count: int = 0
    financial_proxy_source: str | None = None
    requires_human_verification: bool = True
    summary: str
    limitations: list[str]
    next_manual_check: str | None = None


class JaneCriteriaCoverageMatrix(BaseModel):
    criteria: list[JaneCriterionCoverageItem] = Field(default_factory=list)
    covered_count: int = 0
    partial_count: int = 0
    insufficient_count: int = 0
    user_input_required_count: int = 0
    financial_proxy_available_count: int = 0
    source_quality_summary: str = "Jane criteria coverage has not been computed."
    not_investment_advice: bool = True


class ValidationOSEvidenceGap(BaseModel):
    criterion_id: int = Field(ge=1, le=20)
    criterion_name: str
    coverage_status: Literal["partial", "insufficient"]
    missing_submetrics: list[str]
    next_manual_check: str | None = None


class ValidationOSReport(BaseModel):
    ticker: str = ""
    research_label: str = "insufficient_data"
    validation_level: str = "insufficient_validation"
    data_quality_grade: Literal["A", "B", "C", "D"] = "D"
    report_sections: list[str] = Field(default_factory=list)
    executive_summary: str = "Validation OS Report has not been computed."
    macro_backdrop: str = ""
    jane_quality_summary: str = ""
    jane_criteria_coverage_summary: dict[str, int | str] = Field(default_factory=dict)
    financial_signals_summary: str = ""
    smart_money_summary: str = ""
    top_strengths: list[str] = Field(default_factory=list)
    top_limitations: list[str] = Field(default_factory=list)
    top_evidence_gaps: list[ValidationOSEvidenceGap] = Field(default_factory=list)
    top_manual_checks: list[str] = Field(default_factory=list)
    source_quality_caveats: list[str] = Field(default_factory=list)
    manual_verification_required: bool = True
    scoring_note: str = "Validation OS Report is non-scoring and does not change the final research verdict."
    limitations: list[str] = Field(default_factory=list)
    not_investment_advice: bool = True


class AnalyzeStockDataQualitySummary(BaseModel):
    mode: Literal["live_with_fallback", "mixed_preliminary", "mostly_mock", "insufficient"]
    confidence_cap_applied: bool
    confidence_cap_reason: str | None = None
    live_components: int
    mock_components: int
    fallback_components: int
    missing_source_date_components: int
    stale_components: int
    source_quality_grade: Literal["A", "B", "C", "D"]
    source_quality_summary: str
    mock_evidence_categories: list[str]
    fallback_evidence_categories: list[str]
    missing_source_date_categories: list[str]
    excluded_from_scoring: list[str]
    insufficient_evidence_categories: list[str] = Field(default_factory=list)
    company_quality: dict[str, int] = Field(default_factory=dict)
    qualitative_evidence: dict[str, Any] = Field(default_factory=dict)
    sec_companyfacts: dict[str, Any] = Field(default_factory=dict)
    fmp_financials: dict[str, Any] = Field(default_factory=dict)


class QualitativeEvidenceAssessmentItem(BaseModel):
    evidence_id: str | None = None
    origin: Literal["saved_library", "request_scoped"] = "request_scoped"
    review_status: str | None = None
    criterion: str
    criterion_id: int | None = None
    criterion_name: str | None = None
    submetric: str | None = None
    evidence_type: str
    summary: str
    source_label: str
    source_date: str | None = None
    source_quality: Literal["user_provided", "filing_backed", "derived_live", "insufficient", "rejected"]
    accepted: bool
    acceptance_reason: str
    confidence: float = Field(ge=0, le=1)
    limitations: list[str]
    missing_data: list[str]
    evidence_quality_score: float = Field(default=0, ge=0, le=100)
    evidence_quality_label: Literal["high", "medium", "low", "incomplete"] = "incomplete"
    evidence_quality_reasons: list[str] = Field(default_factory=list)
    is_stale: bool = False
    stale_reason: str | None = None
    next_review_due_at: str | None = None
    source_reliability_label: str = "unknown"
    note_title: str | None = None
    research_question: str | None = None
    thesis_direction: Literal["supportive", "neutral", "challenging", "unknown"] = "unknown"
    workflow_status: Literal["draft", "review_ready", "accepted", "needs_refresh", "rejected", "archived"] = "draft"
    comparison_context: dict[str, Any] | None = None


class QualitativeEvidenceAssessment(BaseModel):
    ticker: str
    evidence_count: int
    accepted_evidence_count: int
    rejected_evidence_count: int
    saved_evidence_count: int = 0
    request_evidence_count: int = 0
    deduplicated_count: int = 0
    reviewed_count: int = 0
    unreviewed_count: int = 0
    reviewed_active_count: int = 0
    unreviewed_active_count: int = 0
    archived_or_rejected_ignored_count: int = 0
    quality_score_average: float | None = None
    high_quality_count: int = 0
    medium_quality_count: int = 0
    low_quality_count: int = 0
    incomplete_count: int = 0
    stale_count: int = 0
    review_due_count: int = 0
    criteria_covered: list[str]
    criteria_still_insufficient: list[str]
    source_quality_summary: str
    evidence_items: list[QualitativeEvidenceAssessmentItem]
    source_status: DataSourceStatus
    limitations: list[str]
    missing_data: list[str]


class ComparisonEvidenceAssessmentItem(BaseModel):
    evidence_id: str | None = None
    origin: Literal["saved_library", "request_scoped"] = "request_scoped"
    criterion: str
    evidence_type: str
    comparison_type: str
    peer_companies: list[str]
    claimed_advantage: str
    comparison_summary: str
    source_basis: str
    review_status: str | None = None
    evidence_quality_score: float = Field(default=0, ge=0, le=100)
    evidence_quality_label: Literal["high", "medium", "low", "incomplete"] = "incomplete"
    is_stale: bool = False
    accepted: bool
    limitations: list[str]


class ComparisonEvidenceAssessment(BaseModel):
    ticker: str
    comparison_evidence_count: int
    accepted_comparison_count: int
    reviewed_comparison_count: int
    stale_comparison_count: int
    criteria_supported: list[str]
    peer_companies_mentioned: list[str]
    claimed_advantage_breakdown: dict[str, int]
    source_quality: Literal["user_provided", "insufficient"]
    limitations: list[str]
    missing_data: list[str]
    items: list[ComparisonEvidenceAssessmentItem]
    source_status: DataSourceStatus


class JaneCompanyQualityCriterion(BaseModel):
    name: str
    display_name: str
    score: float | None = Field(default=None, ge=0, le=100)
    max_score: float = 10
    status: Literal["supportive", "neutral", "caution", "insufficient"]
    source_quality: Literal["live_backed", "derived_live", "cached_live", "user_context", "user_provided", "filing_backed", "derived_from_mixed_sources", "insufficient", "mock_only"]
    affects_score: bool
    evidence_strength: Literal["none", "weak", "moderate", "strong"] = "none"
    verification_level: Literal["user_provided", "filing_backed", "derived_live", "independently_verified", "insufficient"] = "insufficient"
    evidence: list[str]
    limitations: list[str]
    missing_data: list[str]


class JaneCompanyQuality(BaseModel):
    name: str = "jane_company_quality_score"
    score: float = Field(ge=0, le=100)
    max_score: float = 100
    confidence: float = Field(ge=0, le=1)
    label: Literal["evidence_backed", "preliminary", "insufficient_data"]
    criteria: list[JaneCompanyQualityCriterion]
    source_status: DataSourceStatus
    limitations: list[str]
    missing_data: list[str]


class FinancialStatementSignal(BaseModel):
    name: str
    status: Literal["supportive", "neutral", "caution", "insufficient"]
    source_quality: Literal["live_backed", "derived_live", "filing_backed", "yfinance_backed", "derived_from_mixed_sources", "insufficient"]
    evidence: list[str]
    limitations: list[str]
    missing_data: list[str]


class FinancialStatementSignals(BaseModel):
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    label: Literal["strong", "adequate", "caution", "insufficient"]
    signals: list[FinancialStatementSignal]
    source_status: DataSourceStatus
    limitations: list[str]
    missing_data: list[str]


class JaneQualityMethodologyReference(BaseModel):
    framework: str = "Jane 7-principle company quality framework"
    principles: list[str]
    affects_score: bool = True
    limitations: list[str]


class ScoreDriver(BaseModel):
    name: str
    category: str
    effect: Literal["positive", "preliminary_positive", "limiting", "negative", "insufficient"]
    source_quality: str
    summary: str


class ScoreDriverBreakdown(BaseModel):
    final_score: float = Field(ge=0, le=100)
    final_confidence: float = Field(ge=0, le=1)
    positive_drivers: list[ScoreDriver]
    negative_or_limiting_drivers: list[ScoreDriver]
    neutral_drivers: list[ScoreDriver]


class NextManualCheck(BaseModel):
    priority: Literal["high", "medium", "low"]
    area: Literal["company_fundamentals", "leadership", "qualitative_evidence", "filings", "smart_money", "valuation", "risk", "source_quality"]
    check: str
    reason: str
    priority_rank: int = Field(default=999, ge=1)
    blocking: bool = False
    category: str | None = None
    related_evidence_category: str | None = None
    reason_short: str = ""


class AnalyzeStockResponse(BaseModel):
    ticker: str
    market: Literal["US"] = "US"
    analysis_mode: Literal["ticker_validation"] = "ticker_validation"
    research_verdict: ResearchVerdict
    candidate_validation_summary: CandidateValidationSummary
    validation_quality_summary: ValidationQualitySummary
    evidence_matrix: list[EvidenceMatrixItem]
    jane_criteria_coverage: JaneCriteriaCoverageMatrix = Field(default_factory=JaneCriteriaCoverageMatrix)
    validation_os_report: ValidationOSReport = Field(default_factory=ValidationOSReport)
    data_quality_summary: AnalyzeStockDataQualitySummary
    score_driver_breakdown: ScoreDriverBreakdown
    next_manual_checks: list[NextManualCheck]
    qualitative_evidence_assessment: QualitativeEvidenceAssessment
    comparison_evidence_assessment: ComparisonEvidenceAssessment
    earnings_transcript_analysis: EarningsTranscriptAnalysis
    jane_criteria_external_evidence: JaneCriteriaExternalEvidence
    government_relationship_evidence: GovernmentRelationshipEvidence
    company_profile: dict[str, Any]
    macro_regime: MacroRegimeOutput
    leadership_score: LeadershipScore
    jane_company_quality: JaneCompanyQuality
    financial_statement_signals: FinancialStatementSignals
    sec_financial_facts: dict[str, Any] = Field(default_factory=dict)
    fmp_financial_proxy: dict[str, Any] = Field(default_factory=dict)
    fundamentals_cross_check: dict[str, Any] = Field(default_factory=dict)
    market_timing_context: ScoreObject
    overheat_risk: ScoreObject
    smart_money: ScoreObject
    insider_activity: dict[str, Any]
    institutional_13f: dict[str, Any]
    financial_quality: ScoreObject
    valuation_context: ScoreObject
    risk_flags: list[str]
    jane_reference_conditions: JaneReferenceConditions | None = None
    jane_quality_methodology_reference: JaneQualityMethodologyReference | None = None
    missing_data: list[str]
    human_verification_queue: list[str | HumanVerificationQueueItem]
    data_quality: DataQualitySummary | None = None
    source_status: DataSourceStatus | None = None
    not_investment_advice: bool = True
