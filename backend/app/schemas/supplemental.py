from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from backend.app.schemas.common import ScoreObject
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
