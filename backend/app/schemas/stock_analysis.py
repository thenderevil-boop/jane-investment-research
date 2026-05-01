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


class AnalyzeStockResponse(BaseModel):
    ticker: str
    market: Literal["US"] = "US"
    analysis_mode: Literal["ticker_validation"] = "ticker_validation"
    research_verdict: ResearchVerdict
    company_profile: dict[str, Any]
    macro_regime: MacroRegimeOutput
    leadership_score: LeadershipScore
    market_timing_context: ScoreObject
    overheat_risk: ScoreObject
    smart_money: ScoreObject
    insider_activity: ScoreObject
    institutional_13f: ScoreObject
    financial_quality: ScoreObject
    valuation_context: ScoreObject
    risk_flags: list[str]
    jane_reference_conditions: JaneReferenceConditions | None = None
    missing_data: list[str]
    human_verification_queue: list[str]
    data_quality: DataQualitySummary | None = None
    source_status: DataSourceStatus | None = None
    not_investment_advice: bool = True
