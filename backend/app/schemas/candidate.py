from __future__ import annotations

from pydantic import BaseModel, Field


class StockCandidate(BaseModel):
    ticker: str
    company_name: str
    theme: str
    leadership_score: float = Field(ge=0)
    smart_money_score: float = Field(ge=0, le=100)
    market_timing_score: float = Field(ge=0, le=100)
    overheat_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    label: str
    source: list[str]
    source_date: str
    confidence: float = Field(ge=0, le=1)
    limitations: list[str]
    missing_data: list[str]
