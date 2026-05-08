from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.stock_analysis import AnalyzeStockResponse, QualitativeEvidenceInput
from backend.app.utils.forbidden_language import detect_forbidden_language


CandidateStatus = Literal["watching", "researching", "reviewed", "archived"]
CandidatePriority = Literal["low", "medium", "high"]
CandidateReviewNoteType = Literal["general", "evidence_review", "analysis_review", "risk_review", "follow_up"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_candidate_id() -> str:
    return f"candidate_{uuid4().hex}"


def new_note_id() -> str:
    return f"note_{uuid4().hex}"


def new_analysis_snapshot_id(candidate_id: str) -> str:
    return f"analysis_{candidate_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"


def _reject_unsafe_text(value: str | None) -> str | None:
    if value is None:
        return None
    if any(marker.lower() in value.lower() for marker in ["fred_api_key", "sec_edgar_user_agent", "api_key", "apikey", "secret", "token="]):
        raise ValueError("candidate workspace metadata must not include secrets or API key markers")
    if detect_forbidden_language(value):
        raise ValueError("candidate workspace metadata must not include investment-instruction language")
    return value


class CandidateEvidenceSummary(BaseModel):
    manual_evidence_count: int = 0
    active_evidence_count: int = 0
    reviewed_evidence_count: int = 0
    unreviewed_evidence_count: int = 0
    stale_evidence_count: int = 0
    comparison_evidence_count: int = 0
    criteria_covered: list[str] = Field(default_factory=list)
    criteria_missing: list[str] = Field(default_factory=lambda: [
        "monopoly_power",
        "visionary_founder_ceo",
        "disruptive_innovation",
        "network_effect",
        "continuous_r_and_d",
        "mega_trend_fit",
    ])
    peer_companies_mentioned: list[str] = Field(default_factory=list)


class CandidateEvidenceCoverageSummary(BaseModel):
    criteria_covered: list[str] = Field(default_factory=list)
    criteria_missing: list[str] = Field(default_factory=list)
    active_evidence_count: int = 0
    stale_evidence_count: int = 0
    comparison_evidence_count: int = 0


class CandidateAnalysisHistoryItem(BaseModel):
    analysis_snapshot_id: str
    analyzed_at: str
    score: float | None = None
    confidence: float | None = None
    label: str | None = None
    data_quality_grade: str | None = None
    evidence_coverage_summary: CandidateEvidenceCoverageSummary = Field(default_factory=CandidateEvidenceCoverageSummary)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("label", "data_quality_grade")
    @classmethod
    def reject_unsafe_text(cls, value: str | None) -> str | None:
        return _reject_unsafe_text(value)

    @field_validator("limitations")
    @classmethod
    def clean_limitations(cls, values: list[str]) -> list[str]:
        return [text for value in values for text in [_reject_unsafe_text(str(value).strip())] if text]


class CandidateReviewNoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
    note_type: CandidateReviewNoteType = "general"
    related_analysis_snapshot_id: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("note", "related_analysis_snapshot_id")
    @classmethod
    def reject_unsafe_text(cls, value: str | None) -> str | None:
        return _reject_unsafe_text(value)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        return sorted({text for value in values for text in [_reject_unsafe_text(str(value).strip())] if text})


class CandidateReviewNote(CandidateReviewNoteCreate):
    note_id: str = Field(default_factory=new_note_id)
    created_at: str = Field(default_factory=utc_now_iso)
    created_by: Literal["local_user"] = "local_user"


class CandidateEvidenceBadge(BaseModel):
    label: str
    severity: Literal["info", "warning", "success"]
    reason: str

    @field_validator("label", "reason")
    @classmethod
    def reject_unsafe_text(cls, value: str) -> str:
        return _reject_unsafe_text(value) or value


class CandidateResearchItemCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    market: Literal["US"] = "US"
    company_name: str | None = None
    theme: str | None = None
    user_reason: str | None = None
    source_label: str | None = None
    source_date: str | None = None
    priority: CandidatePriority = "medium"
    tags: list[str] = Field(default_factory=list)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("company_name", "theme", "user_reason", "source_label", "source_date")
    @classmethod
    def reject_unsafe_text(cls, value: str | None) -> str | None:
        return _reject_unsafe_text(value)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            text = _reject_unsafe_text(str(value).strip())
            if text:
                cleaned.append(text)
        return sorted(set(cleaned))


class CandidateResearchItemPatch(BaseModel):
    company_name: str | None = None
    theme: str | None = None
    user_reason: str | None = None
    source_label: str | None = None
    source_date: str | None = None
    status: CandidateStatus | None = None
    priority: CandidatePriority | None = None
    tags: list[str] | None = None
    review_notes: str | None = None
    next_review_due_at: str | None = None

    @field_validator("company_name", "theme", "user_reason", "source_label", "source_date", "review_notes", "next_review_due_at")
    @classmethod
    def reject_unsafe_text(cls, value: str | None) -> str | None:
        return _reject_unsafe_text(value)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return sorted({text for value in values for text in [_reject_unsafe_text(str(value).strip())] if text})


class CandidateResearchItem(CandidateResearchItemCreate):
    candidate_id: str = Field(default_factory=new_candidate_id)
    status: CandidateStatus = "watching"
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    last_analyzed_at: str | None = None
    last_analysis_snapshot_id: str | None = None
    latest_score: float | None = None
    latest_confidence: float | None = None
    latest_label: str | None = None
    latest_data_quality_grade: str | None = None
    evidence_summary: CandidateEvidenceSummary = Field(default_factory=CandidateEvidenceSummary)
    next_review_due_at: str | None = None
    review_notes: str | None = None
    review_note_history: list[CandidateReviewNote] = Field(default_factory=list)
    analysis_history: list[CandidateAnalysisHistoryItem] = Field(default_factory=list)
    evidence_badges: list[CandidateEvidenceBadge] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=lambda: [
        "Candidate workspace is user-provided workflow metadata and not investment advice.",
        "Watchlist status is not a recommendation.",
    ])
    not_investment_advice: bool = True


class CandidateAnalyzeRequest(BaseModel):
    refresh_evidence_summary: bool = True
    qualitative_evidence: list[QualitativeEvidenceInput] = Field(default_factory=list)


class CandidateAnalyzeResponse(BaseModel):
    candidate: CandidateResearchItem
    analysis: AnalyzeStockResponse
    not_investment_advice: bool = True


class CandidateWorkspaceSourceStatus(BaseModel):
    source_type: Literal["derived"] = "derived"
    provider: Literal["local_candidate_workspace"] = "local_candidate_workspace"
    source_date: str | None = None
    fetched_at: None = None
    is_fresh: bool = True
    freshness_window: Literal["local_workspace_store"] = "local_workspace_store"
    fallback_used: bool = False
    fallback_reason: None = None
    limitations: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)


class CandidateDashboardSummary(BaseModel):
    total_candidates: int = 0
    active_candidates: int = 0
    watching_count: int = 0
    researching_count: int = 0
    reviewed_count: int = 0
    archived_count: int = 0
    high_priority_count: int = 0
    stale_evidence_candidate_count: int = 0
    needs_review_count: int = 0
    with_comparison_evidence_count: int = 0
    needs_analysis_count: int = 0
    stale_analysis_count: int = 0
    missing_evidence_candidate_count: int = 0
    review_overdue_count: int = 0
    status_breakdown: dict[str, int] = Field(default_factory=dict)
    priority_breakdown: dict[str, int] = Field(default_factory=dict)
    missing_criteria_breakdown: dict[str, int] = Field(default_factory=dict)
    average_latest_score: float | None = None
    data_quality_grade_breakdown: dict[str, int] = Field(default_factory=dict)


class CandidateDashboardResponse(BaseModel):
    generated_at: str
    source_status: CandidateWorkspaceSourceStatus
    summary: CandidateDashboardSummary
    items: list[CandidateResearchItem] = Field(default_factory=list)
    review_queue: list[CandidateResearchItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=lambda: [
        "Candidate workspace is user-provided workflow metadata and not investment advice.",
        "Watchlist status is not a recommendation.",
    ])
    missing_data: list[str] = Field(default_factory=list)
    not_investment_advice: bool = True
