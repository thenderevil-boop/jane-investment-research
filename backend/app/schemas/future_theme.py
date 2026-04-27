from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.common import DataSourceStatus


class FutureTheme(BaseModel):
    name: str = "theme_score"
    theme: str
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
    limitations: list[str]
    missing_data: list[str]
    candidate_companies: list[str]
    source_status: DataSourceStatus | None = None
