from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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


class VerificationItem(BaseModel):
    area: str
    reason: str
    priority: str = "medium"
