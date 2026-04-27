from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.common import DataQualitySummary, DataSourceStatus, ScoreObject
from backend.app.schemas.leadership import LeadershipScore


class StockUserContext(BaseModel):
    friends_asking_about_stock: bool = False
    social_discussion_level: Literal["low", "medium", "high"] = "low"


class AnalyzeStockRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    market: Literal["US"] = "US"
    period: str = "3Y"
    user_context: StockUserContext = Field(default_factory=StockUserContext)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class AnalyzeStockResponse(BaseModel):
    ticker: str
    market: Literal["US"] = "US"
    company_profile: dict[str, Any]
    leadership_score: LeadershipScore
    market_timing_context: ScoreObject
    overheat_risk: ScoreObject
    smart_money: ScoreObject
    financial_quality: ScoreObject
    valuation_context: ScoreObject
    risk_flags: list[str]
    missing_data: list[str]
    human_verification_queue: list[str]
    data_quality: DataQualitySummary | None = None
    source_status: DataSourceStatus | None = None
    not_investment_advice: bool = True
