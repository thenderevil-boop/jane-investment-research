from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from backend.app.raw_store.candidate_workspace import (
    archive_candidate_item as store_archive_candidate_item,
    create_candidate_item as store_create_candidate_item,
    get_candidate_item as store_get_candidate_item,
    list_candidate_items as store_list_candidate_items,
    update_candidate_item as store_update_candidate_item,
)
from backend.app.raw_store.manual_evidence import list_manual_evidence
from backend.app.reports.stock_analysis import analyze_stock
from backend.app.schemas.candidate_workspace import (
    CandidateAnalyzeRequest,
    CandidateAnalyzeResponse,
    CandidateDashboardResponse,
    CandidateDashboardSummary,
    CandidateEvidenceSummary,
    CandidateResearchItem,
    CandidateResearchItemCreate,
    CandidateResearchItemPatch,
    CandidateWorkspaceSourceStatus,
)
from backend.app.schemas.manual_evidence_dashboard import ManualEvidenceTickerSummary
from backend.app.schemas.stock_analysis import AnalyzeStockRequest, ResearchContext
from backend.app.services.manual_evidence_dashboard import build_ticker_evidence_summary


WORKSPACE_LIMITATIONS = [
    "Candidate workspace is user-provided workflow metadata and not investment advice.",
    "Watchlist status is not a recommendation.",
    "Candidate workspace does not discover stocks or fetch external sources.",
]


def _candidate(row: dict[str, Any]) -> CandidateResearchItem:
    return CandidateResearchItem.model_validate(row)


def _evidence_summary_from_ticker_summary(summary: ManualEvidenceTickerSummary) -> CandidateEvidenceSummary:
    return CandidateEvidenceSummary(
        manual_evidence_count=summary.total_evidence_count,
        active_evidence_count=summary.active_evidence_count,
        reviewed_evidence_count=summary.reviewed_count,
        unreviewed_evidence_count=summary.unreviewed_count,
        stale_evidence_count=summary.stale_count,
        comparison_evidence_count=summary.comparison_evidence_count,
        criteria_covered=summary.criteria_covered,
        criteria_missing=summary.criteria_missing,
        peer_companies_mentioned=summary.peer_companies_mentioned,
    )


def build_candidate_evidence_summary(ticker: str) -> tuple[CandidateEvidenceSummary, str | None]:
    rows = list_manual_evidence(ticker.strip().upper())
    summary = build_ticker_evidence_summary(ticker.strip().upper(), rows)
    return _evidence_summary_from_ticker_summary(summary), summary.next_review_due_at


def list_candidate_items(
    *,
    include_archived: bool = False,
    ticker: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    tag: str | None = None,
    stale_evidence_only: bool = False,
) -> list[CandidateResearchItem]:
    rows = [_candidate(row) for row in store_list_candidate_items(include_archived=include_archived)]
    if ticker:
        rows = [item for item in rows if item.ticker == ticker.strip().upper()]
    if status:
        rows = [item for item in rows if item.status == status]
    if priority:
        rows = [item for item in rows if item.priority == priority]
    if tag:
        tag_key = tag.strip().lower()
        rows = [item for item in rows if tag_key in {value.lower() for value in item.tags}]
    if stale_evidence_only:
        rows = [item for item in rows if item.evidence_summary.stale_evidence_count > 0]
    return sorted(rows, key=lambda item: (item.status == "archived", item.priority != "high", item.ticker, item.created_at))


def get_candidate_item(candidate_id: str) -> CandidateResearchItem | None:
    row = store_get_candidate_item(candidate_id)
    return _candidate(row) if row else None


def create_candidate_item(payload: CandidateResearchItemCreate) -> CandidateResearchItem:
    item = CandidateResearchItem.model_validate(payload.model_dump(mode="json"))
    summary, next_due = build_candidate_evidence_summary(item.ticker)
    item.evidence_summary = summary
    item.next_review_due_at = next_due
    return _candidate(store_create_candidate_item(item))


def update_candidate_item(candidate_id: str, patch: CandidateResearchItemPatch) -> CandidateResearchItem | None:
    row = store_update_candidate_item(candidate_id, patch)
    return _candidate(row) if row else None


def archive_candidate_item(candidate_id: str) -> CandidateResearchItem | None:
    row = store_archive_candidate_item(candidate_id)
    return _candidate(row) if row else None


def refresh_candidate_evidence_summary(candidate_id: str) -> CandidateResearchItem | None:
    item = get_candidate_item(candidate_id)
    if not item:
        return None
    summary, next_due = build_candidate_evidence_summary(item.ticker)
    row = store_update_candidate_item(
        candidate_id,
        {
            "next_review_due_at": next_due,
        },
    )
    if not row:
        return None
    row["evidence_summary"] = summary.model_dump(mode="json")
    row["updated_at"] = datetime.now(timezone.utc).isoformat()
    store_create_candidate_item(CandidateResearchItem.model_validate(row))
    return _candidate(row)


def refresh_candidate_analysis_snapshot(candidate_id: str, analysis_result) -> CandidateResearchItem | None:
    item = get_candidate_item(candidate_id)
    if not item:
        return None
    updated = {
        "last_analyzed_at": datetime.now(timezone.utc).isoformat(),
        "last_analysis_snapshot_id": f"analysis_{candidate_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "latest_score": analysis_result.research_verdict.score,
        "latest_confidence": analysis_result.research_verdict.confidence,
        "latest_label": analysis_result.research_verdict.label,
        "latest_data_quality_grade": analysis_result.data_quality_summary.source_quality_grade,
    }
    row = {**item.model_dump(mode="json"), **updated}
    store_create_candidate_item(CandidateResearchItem.model_validate(row))
    return _candidate(row)


def analyze_candidate(candidate_id: str, payload: CandidateAnalyzeRequest) -> CandidateAnalyzeResponse | None:
    item = get_candidate_item(candidate_id)
    if not item:
        return None
    request = AnalyzeStockRequest(
        ticker=item.ticker,
        market="US",
        research_context=ResearchContext(theme=item.theme, user_reason=item.user_reason),
        qualitative_evidence=payload.qualitative_evidence,
    )
    analysis = analyze_stock(request)
    candidate = refresh_candidate_analysis_snapshot(candidate_id, analysis)
    if payload.refresh_evidence_summary:
        candidate = refresh_candidate_evidence_summary(candidate_id)
    return CandidateAnalyzeResponse(candidate=candidate or item, analysis=analysis)


def _needs_review(item: CandidateResearchItem) -> bool:
    summary = item.evidence_summary
    return (
        summary.stale_evidence_count > 0
        or summary.unreviewed_evidence_count > 0
        or bool(summary.criteria_missing)
        or item.last_analyzed_at is None
    )


def build_candidate_dashboard(include_archived: bool = False) -> CandidateDashboardResponse:
    now = datetime.now(timezone.utc)
    items = list_candidate_items(include_archived=include_archived)
    active = [item for item in items if item.status != "archived"]
    scores = [float(item.latest_score) for item in active if item.latest_score is not None]
    grade_counts = Counter(item.latest_data_quality_grade for item in active if item.latest_data_quality_grade)
    review_queue = [item for item in active if _needs_review(item)]
    source_dates = sorted({item.updated_at[:10] for item in items if item.updated_at})
    return CandidateDashboardResponse(
        generated_at=now.isoformat(),
        source_status=CandidateWorkspaceSourceStatus(
            source_date=source_dates[-1] if source_dates else None,
            limitations=WORKSPACE_LIMITATIONS,
        ),
        summary=CandidateDashboardSummary(
            total_candidates=len(items),
            active_candidates=len(active),
            watching_count=sum(1 for item in active if item.status == "watching"),
            researching_count=sum(1 for item in active if item.status == "researching"),
            reviewed_count=sum(1 for item in active if item.status == "reviewed"),
            archived_count=sum(1 for item in items if item.status == "archived"),
            high_priority_count=sum(1 for item in active if item.priority == "high"),
            stale_evidence_candidate_count=sum(1 for item in active if item.evidence_summary.stale_evidence_count > 0),
            needs_review_count=len(review_queue),
            with_comparison_evidence_count=sum(1 for item in active if item.evidence_summary.comparison_evidence_count > 0),
            average_latest_score=round(sum(scores) / len(scores), 2) if scores else None,
            data_quality_grade_breakdown=dict(sorted(grade_counts.items())),
        ),
        items=items,
        review_queue=review_queue,
        limitations=WORKSPACE_LIMITATIONS,
        missing_data=[] if items else ["candidate workspace is empty"],
    )
