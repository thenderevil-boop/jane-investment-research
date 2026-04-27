from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
