from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.common import DataSourceStatus


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
    source_status: DataSourceStatus | None = None
    institutional_13f: dict[str, Any] | None = None
