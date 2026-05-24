from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.manual_evidence import ManualEvidenceCriterion, ManualEvidenceQualityLabel, ManualEvidenceReviewStatus


class ManualEvidenceDashboardSourceStatus(BaseModel):
    source_type: Literal["derived"] = "derived"
    provider: Literal["local_manual_evidence_library"] = "local_manual_evidence_library"
    source_date: str | None = None
    fetched_at: None = None
    is_fresh: bool = True
    freshness_window: Literal["local_evidence_store"] = "local_evidence_store"
    fallback_used: bool = False
    fallback_reason: None = None
    limitations: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)


class ManualEvidenceDashboardFilters(BaseModel):
    ticker: str | None = None
    include_archived: bool = False
    include_rejected: bool = False
    review_status: ManualEvidenceReviewStatus | None = None
    criterion: ManualEvidenceCriterion | None = None
    stale_only: bool = False
    review_due_only: bool = False
    has_comparison_context: bool | None = None
    min_quality_label: ManualEvidenceQualityLabel | None = None


class ManualEvidenceDashboardSummary(BaseModel):
    total_evidence_count: int = 0
    active_evidence_count: int = 0
    reviewed_count: int = 0
    unreviewed_count: int = 0
    stale_count: int = 0
    review_due_count: int = 0
    review_scheduled_count: int = 0
    review_overdue_count: int = 0
    archived_count: int = 0
    rejected_count: int = 0
    comparison_evidence_count: int = 0
    tickers_covered_count: int = 0
    average_quality_score: float | None = None
    quality_label_breakdown: dict[str, int] = Field(default_factory=dict)
    review_status_breakdown: dict[str, int] = Field(default_factory=dict)
    criteria_coverage: dict[str, int] = Field(default_factory=dict)


class ManualEvidenceTickerSummary(BaseModel):
    ticker: str
    total_evidence_count: int = 0
    active_evidence_count: int = 0
    reviewed_count: int = 0
    unreviewed_count: int = 0
    stale_count: int = 0
    review_due_count: int = 0
    review_scheduled_count: int = 0
    review_overdue_count: int = 0
    comparison_evidence_count: int = 0
    criteria_covered: list[str] = Field(default_factory=list)
    criteria_missing: list[str] = Field(default_factory=list)
    peer_companies_mentioned: list[str] = Field(default_factory=list)
    quality_label_breakdown: dict[str, int] = Field(default_factory=dict)
    highest_quality_label: Literal["high", "medium", "low", "incomplete", "none"] = "none"
    next_review_due_at: str | None = None


class ManualEvidenceDashboardQueueItem(BaseModel):
    evidence_id: str
    ticker: str
    criterion: str
    evidence_type: str
    review_status: str
    evidence_quality_label: str
    evidence_quality_score: int
    is_stale: bool
    stale_reason: str | None = None
    next_review_due_at: str | None = None
    review_due_reason: str
    summary: str
    source_label: str
    source_date: str | None = None
    adr_evidence_type: str | None = None
    document_title: str | None = None
    document_date: str | None = None
    filing_period: str | None = None
    local_market: str | None = None
    local_ticker: str | None = None
    adr_review_label: str | None = None
    adr_review_guidance: list[str] = Field(default_factory=list)
    affects_score: bool = False
    not_investment_advice: bool = True
    has_comparison_context: bool
    peer_companies: list[str] = Field(default_factory=list)


class ManualEvidencePeerCompanyIndexItem(BaseModel):
    peer_company: str
    evidence_count: int = 0
    tickers: list[str] = Field(default_factory=list)
    criteria: list[str] = Field(default_factory=list)
    comparison_types: list[str] = Field(default_factory=list)
    claimed_advantage_breakdown: dict[str, int] = Field(default_factory=dict)


class ManualEvidenceDashboardResponse(BaseModel):
    generated_at: str
    source_status: ManualEvidenceDashboardSourceStatus
    summary: ManualEvidenceDashboardSummary
    ticker_summaries: list[ManualEvidenceTickerSummary] = Field(default_factory=list)
    review_queue: list[ManualEvidenceDashboardQueueItem] = Field(default_factory=list)
    stale_queue: list[ManualEvidenceDashboardQueueItem] = Field(default_factory=list)
    audit_queue: list[ManualEvidenceDashboardQueueItem] = Field(default_factory=list)
    peer_company_index: list[ManualEvidencePeerCompanyIndexItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    not_investment_advice: bool = True
