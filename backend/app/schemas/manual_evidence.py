from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from backend.app.utils.forbidden_language import detect_forbidden_language


ManualEvidenceCriterion = Literal[
    "monopoly_power",
    "visionary_founder_ceo",
    "disruptive_innovation",
    "network_effect",
    "continuous_r_and_d",
    "mega_trend_fit",
]
ManualEvidenceType = Literal[
    "market_share",
    "patent",
    "platform_ecosystem",
    "founder_operator",
    "management_tenure",
    "product_disruption",
    "customer_adoption",
    "developer_ecosystem",
    "switching_cost",
    "brand_power",
    "r_and_d_intensity",
    "user_provided_note",
    "filing_reference",
    "other",
]
ManualEvidenceReviewStatus = Literal["unreviewed", "reviewed", "rejected", "archived"]

SECRET_MARKERS = ("FRED_API_KEY", "SEC_EDGAR_USER_AGENT", "api_key", "apikey", "secret", "token=")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_evidence_id() -> str:
    return f"manual_{uuid4().hex}"


def contains_secret_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker.lower() in lowered for marker in SECRET_MARKERS)


class ManualQualitativeEvidenceCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    criterion: ManualEvidenceCriterion
    evidence_type: ManualEvidenceType
    summary: str = Field(min_length=1)
    source_label: str = Field(min_length=1)
    source_url: str | None = None
    source_date: str | None = None
    confidence: float = Field(ge=0, le=1)
    review_status: ManualEvidenceReviewStatus = "unreviewed"
    user_provided: bool = True
    created_by: str | None = "local_user"
    limitations: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("summary", "source_label", "source_url")
    @classmethod
    def reject_secret_markers(cls, value: str | None) -> str | None:
        if value is not None and contains_secret_marker(value):
            raise ValueError("manual evidence must not include secrets or API key markers")
        if value is not None and detect_forbidden_language(value):
            raise ValueError("manual evidence must not include investment-instruction language")
        return value

    @field_validator("user_provided")
    @classmethod
    def force_user_provided(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("manual evidence must be user_provided")
        return True


class ManualQualitativeEvidencePatch(BaseModel):
    summary: str | None = None
    source_label: str | None = None
    source_url: str | None = None
    source_date: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    review_status: ManualEvidenceReviewStatus | None = None
    limitations: list[str] | None = None
    tags: list[str] | None = None

    @field_validator("summary", "source_label", "source_url")
    @classmethod
    def reject_secret_markers(cls, value: str | None) -> str | None:
        if value is not None and contains_secret_marker(value):
            raise ValueError("manual evidence must not include secrets or API key markers")
        if value is not None and detect_forbidden_language(value):
            raise ValueError("manual evidence must not include investment-instruction language")
        return value


class ManualQualitativeEvidence(ManualQualitativeEvidenceCreate):
    evidence_id: str = Field(default_factory=new_evidence_id)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
