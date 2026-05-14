from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.common import DataSourceStatus


class LeadershipCriterion(BaseModel):
    criterion_id: int = Field(ge=1, le=20)
    criterion_name: str
    score: float = Field(ge=0, le=1)
    raw_data: dict[str, Any]
    derived_metrics: dict[str, Any]
    benchmark: dict[str, Any]
    trend: dict[str, Any]
    evidence_summary: str
    source: list[str]
    source_date: str
    confidence: float = Field(ge=0, le=1)
    limitations: list[str]
    missing_data: list[str]
    source_status: DataSourceStatus | None = None


class LeadershipScore(BaseModel):
    name: str = "leadership_score"
    score: float = Field(ge=0, le=20)
    max_score: float = 20
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
    criteria: list[LeadershipCriterion]
    source_status: DataSourceStatus | None = None
    deprecated_by: str | None = None
    deprecated: bool = True
    replaced_by: str | None = "jane_company_quality"
    affects_score: bool = False
    legacy_affects_score: bool = False
    affects_final_score: bool = False
    source_quality: str = "mock_only"
