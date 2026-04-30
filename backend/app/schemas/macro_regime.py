from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.common import DataSourceStatus


class MacroIndicatorComponent(BaseModel):
    name: str
    score: float = Field(ge=0, le=100)
    raw_data: dict[str, Any]
    derived_metrics: dict[str, Any]
    benchmark: dict[str, Any]
    trend: dict[str, Any]
    source: list[str]
    source_date: str
    confidence: float = Field(ge=0, le=1)
    limitations: list[str]
    missing_data: list[str]
    source_status: DataSourceStatus | None = None


class MacroDataQuality(BaseModel):
    fred_backed_fields: list[str]
    mock_context_fields: list[str]
    derived_from_fred_fields: list[str]
    yfinance_backed_fields: list[str] = Field(default_factory=list)
    derived_from_yfinance_fields: list[str] = Field(default_factory=list)
    live_macro_fields_count: int
    mock_macro_fields_count: int
    derived_macro_fields_count: int
    yfinance_macro_fields_count: int = 0
    has_mock_macro_context: bool
    mock_context_score_weight_pct: float
    fred_backed_score_weight_pct: float
    live_or_cached_context_score_weight_pct: float = 0
    confidence_adjustment_applied: bool
    limitations: list[str]
    excluded_indicators: list[dict[str, Any]] = Field(default_factory=list)


class MacroRegimeOutput(BaseModel):
    name: str = "macro_regime_score"
    score: float = Field(ge=0, le=100)
    max_score: float = 100
    label: str
    raw_data: dict[str, Any]
    derived_metrics: dict[str, Any]
    benchmark: dict[str, Any]
    trend: dict[str, Any]
    source: list[str]
    source_date: str
    confidence: float = Field(ge=0, le=1)
    components: list[MacroIndicatorComponent]
    limitations: list[str]
    missing_data: list[str]
    source_status: DataSourceStatus | None = None
    macro_data_quality: MacroDataQuality | None = None
