from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.common import DataSourceStatus, ScoreObject
from backend.app.schemas.future_theme import FutureTheme
from backend.app.schemas.leadership import LeadershipScore


class ThemesLatestResponse(BaseModel):
    market: Literal["US"] = "US"
    themes: list[FutureTheme]
    limitations: list[str]
    missing_data: list[str]
    not_investment_advice: bool = True


class RawDataResponse(BaseModel):
    ticker: str
    market: Literal["US"] = "US"
    raw_data: dict[str, Any]
    source: list[str]
    source_date: str
    limitations: list[str]
    missing_data: list[str]
    source_status: DataSourceStatus | None = None
    not_investment_advice: bool = True


class TickerSignalsResponse(BaseModel):
    ticker: str
    market: Literal["US"] = "US"
    leadership_score: LeadershipScore
    market_timing_context: ScoreObject
    overheat_risk: ScoreObject
    smart_money: ScoreObject
    financial_quality: ScoreObject
    valuation_context: ScoreObject
    risk_flags: list[str]
    limitations: list[str]
    missing_data: list[str]
    not_investment_advice: bool = True


class DataHealthResponse(BaseModel):
    providers: dict[str, dict[str, Any]]
    limitations: list[str]
    missing_data: list[str]
    not_investment_advice: bool = True


class PriceReferenceWarmupRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    max_tickers: int | None = Field(default=None, ge=1)
    allow_live_fetch: bool = False

    @field_validator("tickers", mode="before")
    @classmethod
    def normalize_tickers(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip().upper() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip().upper() for item in value if str(item).strip()]
        raise ValueError("tickers must be a list or comma-separated string")
