from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.common import DataSourceStatus
from backend.app.schemas.jane_external_evidence import JaneCriteriaExternalEvidenceItem


class PatentRecord(BaseModel):
    patent_id: str = ""
    patent_date: str = ""
    patent_title: str = ""
    assignee_organization: str = ""


class PatentIPEvidence(BaseModel):
    ticker: str
    provider: str = "uspto_patentsview"
    source: str = "uspto_patentsview"
    source_status: DataSourceStatus = Field(default_factory=lambda: DataSourceStatus(provider="uspto_patentsview", source_type="fallback", missing_data=["uspto_patentsview_patent_count"]))
    query_name: str = ""
    patent_count: int = 0
    patent_records: list[PatentRecord] = Field(default_factory=list)
    criteria: list[JaneCriteriaExternalEvidenceItem] = Field(default_factory=list)
    criteria_count: int = 0
    ip_signal: Literal["supportive", "limited", "insufficient_data"] = "insufficient_data"
    manual_checks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    affects_score: bool = False
    not_investment_advice: bool = True
