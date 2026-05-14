from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JaneEvidenceType = Literal["financial_proxy", "qualitative", "semi_structured"]


class JaneCriterion(BaseModel):
    criterion_id: int = Field(ge=1, le=20)
    criterion_name: str
    submetrics: list[str]
    evidence_type: JaneEvidenceType
    auto_derivable_submetrics: list[str]
    requires_user_input_submetrics: list[str]
    financial_proxy_source: str | None = None


class JaneCriteriaResponse(BaseModel):
    criteria: list[JaneCriterion]
    count: int = 20
    not_investment_advice: bool = True
