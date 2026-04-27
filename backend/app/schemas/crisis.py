from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.common import DataSourceStatus


class CrisisComponent(BaseModel):
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


class CrisisOutput(BaseModel):
    level: str
    confidence: float = Field(ge=0, le=1)
    reference: dict[str, str]
    components: list[CrisisComponent]
    limitations: list[str]
    missing_data: list[str]
    source_status: DataSourceStatus | None = None
