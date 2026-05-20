from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.common import DataSourceStatus
from backend.app.schemas.jane_external_evidence import JaneCriteriaExternalEvidenceItem


class GovernmentRecipientCandidate(BaseModel):
    recipient_name: str
    recipient_hash: str | None = None
    uei: str | None = None
    duns: str | None = None
    source: str = "usaspending_recipient_autocomplete"


class GovernmentAwardRecord(BaseModel):
    award_id: str
    recipient_name: str
    awarding_agency: str
    obligated_amount: float = 0
    award_date: str = ""
    award_type: str = ""
    description: str = ""


class GovernmentAwardingAgencySummary(BaseModel):
    agency: str
    obligated_amount: float = 0
    award_count: int = 0


class GovernmentRelationshipEvidence(BaseModel):
    ticker: str
    provider: str = "usaspending"
    source: str = "usaspending_contract_awards"
    source_status: DataSourceStatus = Field(default_factory=lambda: DataSourceStatus(provider="usaspending", source_type="fallback", missing_data=["usaspending_contract_awards"]))
    query_name: str = ""
    recipient_candidates: list[GovernmentRecipientCandidate] = Field(default_factory=list)
    award_records: list[GovernmentAwardRecord] = Field(default_factory=list)
    total_obligated_amount: float = 0
    award_count: int = 0
    top_awarding_agencies: list[GovernmentAwardingAgencySummary] = Field(default_factory=list)
    criteria: list[JaneCriteriaExternalEvidenceItem] = Field(default_factory=list)
    criteria_count: int = 0
    relationship_signal: Literal["supportive", "limited", "insufficient_data"] = "insufficient_data"
    manual_checks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    affects_score: bool = False
    not_investment_advice: bool = True
