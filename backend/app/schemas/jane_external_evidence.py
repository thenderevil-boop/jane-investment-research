from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.common import DataSourceStatus


class JaneCriteriaExternalEvidenceItem(BaseModel):
    criterion_id: int = Field(ge=1, le=20)
    criterion_name: str
    source: str = "fmp_earnings_transcript"
    source_quality: Literal["provider_backed", "cached_live", "insufficient"] = "insufficient"
    support_level: Literal["supportive", "partial", "insufficient_data"] = "insufficient_data"
    confidence: float = Field(default=0, ge=0, le=1)
    covered_submetrics: list[str] = Field(default_factory=list)
    evidence_snippets: list[str] = Field(default_factory=list)
    manual_checks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    requires_manual_review: bool = True
    affects_score: bool = False


class JaneCriteriaExternalEvidence(BaseModel):
    ticker: str
    provider: str = "fmp"
    source: str = "fmp_earnings_transcript"
    source_status: DataSourceStatus = Field(default_factory=lambda: DataSourceStatus(provider="fmp", missing_data=["fmp_earnings_transcripts"]))
    criteria: list[JaneCriteriaExternalEvidenceItem] = Field(default_factory=list)
    criteria_count: int = 0
    manual_checks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    affects_score: bool = False
    not_investment_advice: bool = True
