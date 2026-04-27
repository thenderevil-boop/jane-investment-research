from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RiskPostureLabel = Literal[
    "risk_on_watch",
    "balanced_watch",
    "defensive_watch",
    "crisis_watch",
    "overheat_warning",
    "insufficient_data",
]


class RiskAllocationReference(BaseModel):
    risk_posture: RiskPostureLabel
    score: float = Field(ge=0, le=100)
    reference: dict[str, RiskPostureLabel]
    risk_flags: list[str]
    raw_data: dict[str, Any]
    derived_metrics: dict[str, Any]
    benchmark: dict[str, Any]
    trend: dict[str, Any]
    source: list[str]
    source_date: str
    confidence: float = Field(ge=0, le=1)
    limitations: list[str]
    missing_data: list[str]
