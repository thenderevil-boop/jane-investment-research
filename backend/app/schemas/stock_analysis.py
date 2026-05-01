from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.common import DataQualitySummary, DataSourceStatus, ScoreObject
from backend.app.schemas.daily_report import JaneReferenceConditions
from backend.app.schemas.leadership import LeadershipScore
from backend.app.schemas.macro_regime import MacroRegimeOutput


class StockUserContext(BaseModel):
    friends_asking_about_stock: bool = False
    social_discussion_level: Literal["low", "medium", "high"] = "low"


class ResearchContext(BaseModel):
    theme: str | None = None
    user_reason: str | None = None


class AnalyzeStockRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    market: Literal["US"] = "US"
    period: str = "3Y"
    research_context: ResearchContext | None = None
    user_context: StockUserContext = Field(default_factory=StockUserContext)

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


class EvidenceMatrixItem(BaseModel):
    category: Literal[
        "macro_environment",
        "company_profile",
        "leadership_score",
        "smart_money",
        "insider_activity",
        "institutional_13f",
        "risk_flags",
    ]
    status: Literal["supportive", "neutral", "caution", "insufficient"]
    score: float | None = None
    confidence: float = Field(ge=0, le=1)
    source_quality: Literal["live_backed", "derived_live", "cached_live", "mixed_with_fallback", "mock_only", "insufficient"]
    summary: str
    key_evidence: list[str]
    limitations: list[str]


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


class ScoreDriver(BaseModel):
    name: str
    category: str
    effect: Literal["positive", "limiting", "negative", "insufficient"]
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
    area: Literal["company_fundamentals", "leadership", "filings", "smart_money", "valuation", "risk", "source_quality"]
    check: str
    reason: str


class AnalyzeStockResponse(BaseModel):
    ticker: str
    market: Literal["US"] = "US"
    analysis_mode: Literal["ticker_validation"] = "ticker_validation"
    research_verdict: ResearchVerdict
    candidate_validation_summary: CandidateValidationSummary
    evidence_matrix: list[EvidenceMatrixItem]
    data_quality_summary: AnalyzeStockDataQualitySummary
    score_driver_breakdown: ScoreDriverBreakdown
    next_manual_checks: list[NextManualCheck]
    company_profile: dict[str, Any]
    macro_regime: MacroRegimeOutput
    leadership_score: LeadershipScore
    market_timing_context: ScoreObject
    overheat_risk: ScoreObject
    smart_money: ScoreObject
    insider_activity: dict[str, Any]
    institutional_13f: dict[str, Any]
    financial_quality: ScoreObject
    valuation_context: ScoreObject
    risk_flags: list[str]
    jane_reference_conditions: JaneReferenceConditions | None = None
    missing_data: list[str]
    human_verification_queue: list[str]
    data_quality: DataQualitySummary | None = None
    source_status: DataSourceStatus | None = None
    not_investment_advice: bool = True
