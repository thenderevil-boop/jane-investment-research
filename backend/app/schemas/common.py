from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DataSourceStatus(BaseModel):
    source_type: Literal["live", "cached_live", "mock", "fallback", "derived", "unknown"] = "unknown"
    provider: str = "unknown"
    source_date: str = ""
    fetched_at: str | None = None
    is_fresh: bool = False
    freshness_window: str = "unknown"
    fallback_used: bool = False
    fallback_reason: str | None = None
    limitations: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)


class DataQualitySummary(BaseModel):
    mode: Literal["all_mock", "mixed", "mostly_live", "live_with_fallback"] = "all_mock"
    live_components: int = 0
    mock_components: int = 0
    fallback_components: int = 0
    stale_components: int = 0
    missing_source_date_components: int = 0
    limitations: list[str] = Field(default_factory=list)
    macro: dict[str, Any] | None = None


class ScoreObject(BaseModel):
    name: str
    score: float
    max_score: float = 100
    label: str
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
    source_quality_breakdown: dict[str, Any] | None = None
    explanation: dict[str, Any] | None = None


class VerificationItem(BaseModel):
    area: str
    reason: str
    priority: str = "medium"
