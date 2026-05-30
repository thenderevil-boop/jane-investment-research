from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
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
    CandidateAnalysisHistoryItem,
    CandidateAnalyzeRequest,
    CandidateAnalyzeResponse,
    CandidateDashboardResponse,
    CandidateDashboardSummary,
    CandidateEvidenceBadge,
    CandidateEvidenceCoverageSummary,
    CandidateEvidenceSummary,
    CandidateReadinessComparisonItem,
    CandidateReadinessComparisonResponse,
    CandidateReadinessComparisonSummary,
    CandidateReadinessEvidenceCompleteness,
    CandidateReadinessTopGap,
    CandidateResearchItem,
    CandidateResearchItemCreate,
    CandidateResearchItemPatch,
    CandidateReviewNote,
    CandidateReviewNoteCreate,
    CandidateWorkspaceSourceStatus,
    new_analysis_snapshot_id,
)
from backend.app.schemas.manual_evidence_dashboard import ManualEvidenceTickerSummary
from backend.app.schemas.stock_analysis import AnalyzeStockRequest, ResearchContext
from backend.app.services.manual_evidence_dashboard import build_ticker_evidence_summary


WORKSPACE_LIMITATIONS = [
    "Candidate workspace is user-provided workflow metadata and not investment advice.",
    "Watchlist status is not a recommendation.",
    "Candidate workspace does not discover stocks or fetch external sources.",
]
ANALYSIS_HISTORY_LIMIT = 20
STALE_ANALYSIS_DAYS = 14
JANE_QUALITATIVE_CRITERIA = [
    "monopoly_power",
    "visionary_founder_ceo",
    "disruptive_innovation",
    "network_effect",
    "continuous_r_and_d",
    "mega_trend_fit",
]
ALLOWED_STATUS_TRANSITIONS = {
    "watching": {"researching", "reviewed", "archived"},
    "researching": {"reviewed", "watching", "archived"},
    "reviewed": {"researching", "archived"},
    "archived": set(),
}


def _candidate(row: dict[str, Any]) -> CandidateResearchItem:
    return _decorate_candidate(CandidateResearchItem.model_validate(row))


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_overdue(value: str | None, now: datetime) -> bool:
    parsed = _parse_dt(value)
    return bool(parsed and parsed <= now)


def _is_analysis_stale(item: CandidateResearchItem, now: datetime) -> bool:
    parsed = _parse_dt(item.last_analyzed_at)
    return bool(parsed and parsed < now - timedelta(days=STALE_ANALYSIS_DAYS))


def _review_reasons(item: CandidateResearchItem, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    summary = item.evidence_summary
    if item.last_analyzed_at is None:
        reasons.append("no_analysis")
    elif _is_analysis_stale(item, now):
        reasons.append("stale_analysis")
    if summary.stale_evidence_count > 0:
        reasons.append("stale_evidence")
    if summary.unreviewed_evidence_count > 0:
        reasons.append("unreviewed_evidence")
    for criterion in summary.criteria_missing:
        if criterion in JANE_QUALITATIVE_CRITERIA:
            reasons.append(f"missing_{criterion}")
    if summary.comparison_evidence_count > 0 and summary.unreviewed_evidence_count > 0:
        reasons.append("comparison_evidence_needs_validation")
    return sorted(set(reasons))


def _evidence_badges(item: CandidateResearchItem) -> list[CandidateEvidenceBadge]:
    summary = item.evidence_summary
    badges: list[CandidateEvidenceBadge] = []
    if summary.criteria_missing:
        badges.append(CandidateEvidenceBadge(label="evidence_missing", severity="warning", reason="One or more qualitative criteria lack active local evidence."))
    if summary.stale_evidence_count > 0:
        badges.append(CandidateEvidenceBadge(label="stale_evidence", severity="warning", reason="One or more local manual evidence items is stale."))
    if summary.unreviewed_evidence_count > 0:
        badges.append(CandidateEvidenceBadge(label="unreviewed_evidence", severity="warning", reason="One or more local manual evidence items is awaiting review."))
    if summary.comparison_evidence_count > 0:
        badges.append(CandidateEvidenceBadge(label="comparison_evidence_present", severity="info", reason="User-provided comparison evidence is present and needs manual validation."))
    if "network_effect" in summary.criteria_covered:
        badges.append(CandidateEvidenceBadge(label="network_effect_covered", severity="success", reason="Local manual evidence covers network effect."))
    if "visionary_founder_ceo" in summary.criteria_covered:
        badges.append(CandidateEvidenceBadge(label="founder_ceo_covered", severity="success", reason="Local manual evidence covers founder or CEO context."))
    if "monopoly_power" in summary.criteria_missing:
        badges.append(CandidateEvidenceBadge(label="monopoly_power_missing", severity="warning", reason="Local manual evidence is missing monopoly or moat context."))
    if "disruptive_innovation" in summary.criteria_missing:
        badges.append(CandidateEvidenceBadge(label="disruptive_innovation_missing", severity="warning", reason="Local manual evidence is missing disruptive innovation context."))
    if item.last_analyzed_at is None:
        badges.append(CandidateEvidenceBadge(label="latest_analysis_missing", severity="warning", reason="Candidate has no stored analysis metadata."))
    if item.latest_data_quality_grade:
        severity = "success" if item.latest_data_quality_grade == "A" else "info" if item.latest_data_quality_grade == "B" else "warning"
        badges.append(CandidateEvidenceBadge(label=f"data_quality_{item.latest_data_quality_grade}", severity=severity, reason="Latest analysis data-quality grade metadata."))
    return badges


def _decorate_candidate(item: CandidateResearchItem, now: datetime | None = None) -> CandidateResearchItem:
    data = item.model_dump(mode="json")
    data["evidence_badges"] = [badge.model_dump(mode="json") for badge in _evidence_badges(item)]
    data["review_reasons"] = _review_reasons(item, now)
    return CandidateResearchItem.model_validate(data)


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
    needs_review_only: bool = False,
    has_comparison_evidence: bool | None = None,
    missing_criterion: str | None = None,
    data_quality_grade: str | None = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
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
    if needs_review_only:
        rows = [item for item in rows if item.review_reasons]
    if has_comparison_evidence is not None:
        rows = [item for item in rows if (item.evidence_summary.comparison_evidence_count > 0) is has_comparison_evidence]
    if missing_criterion:
        criterion = missing_criterion.strip()
        rows = [item for item in rows if criterion in item.evidence_summary.criteria_missing]
    if data_quality_grade:
        rows = [item for item in rows if item.latest_data_quality_grade == data_quality_grade.strip().upper()]
    reverse = sort_order == "desc"
    priority_rank = {"high": 3, "medium": 2, "low": 1}
    sortable: dict[str, Any] = {
        "updated_at": lambda item: item.updated_at or "",
        "created_at": lambda item: item.created_at or "",
        "priority": lambda item: priority_rank.get(item.priority, 0),
        "latest_score": lambda item: item.latest_score if item.latest_score is not None else -1,
        "latest_confidence": lambda item: item.latest_confidence if item.latest_confidence is not None else -1,
        "next_review_due_at": lambda item: item.next_review_due_at or "",
        "stale_evidence_count": lambda item: item.evidence_summary.stale_evidence_count,
        "active_evidence_count": lambda item: item.evidence_summary.active_evidence_count,
    }
    if sort_by not in sortable:
        raise ValueError(f"Invalid candidate sort_by: {sort_by}")
    if sort_order not in {"asc", "desc"}:
        raise ValueError("Invalid candidate sort_order: use asc or desc")
    return sorted(rows, key=lambda item: (sortable[sort_by](item), item.ticker, item.candidate_id), reverse=reverse)


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
    existing = get_candidate_item(candidate_id)
    if not existing:
        return None
    if patch.status and patch.status != existing.status:
        if patch.status not in ALLOWED_STATUS_TRANSITIONS.get(existing.status, set()):
            raise ValueError(f"Invalid candidate status transition from {existing.status} to {patch.status}.")
    row = store_update_candidate_item(candidate_id, patch)
    if row and patch.status and patch.status != existing.status:
        note = CandidateReviewNoteCreate(note=f"Status changed from {existing.status} to {patch.status}.", note_type="general", tags=["status"])
        row = _append_candidate_note(row, note).model_dump(mode="json")
    return _candidate(row) if row else None


def archive_candidate_item(candidate_id: str) -> CandidateResearchItem | None:
    row = store_archive_candidate_item(candidate_id)
    return _candidate(row) if row else None


def restore_candidate_item(candidate_id: str) -> CandidateResearchItem | None:
    existing = get_candidate_item(candidate_id)
    if not existing:
        return None
    if existing.status != "archived":
        return update_candidate_item(candidate_id, CandidateResearchItemPatch(status="watching"))
    row = store_update_candidate_item(candidate_id, {"status": "watching"})
    if not row:
        return None
    note = CandidateReviewNoteCreate(note="Status changed from archived to watching.", note_type="general", tags=["status", "restore"])
    return _append_candidate_note(row, note)


def _append_candidate_note(row: dict[str, Any], payload: CandidateReviewNoteCreate) -> CandidateResearchItem:
    item = CandidateResearchItem.model_validate(row)
    note = CandidateReviewNote.model_validate(payload.model_dump(mode="json"))
    data = item.model_dump(mode="json")
    data["review_notes"] = note.note
    data["review_note_history"] = [*data.get("review_note_history", []), note.model_dump(mode="json")]
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    stored = store_create_candidate_item(CandidateResearchItem.model_validate(data))
    return _candidate(stored)


def add_candidate_note(candidate_id: str, payload: CandidateReviewNoteCreate) -> CandidateReviewNote | None:
    item = get_candidate_item(candidate_id)
    if not item:
        return None
    updated = _append_candidate_note(item.model_dump(mode="json"), payload)
    return updated.review_note_history[-1] if updated.review_note_history else None


def list_candidate_notes(candidate_id: str) -> list[CandidateReviewNote] | None:
    item = get_candidate_item(candidate_id)
    return item.review_note_history if item else None


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
    analyzed_at = datetime.now(timezone.utc).isoformat()
    snapshot_id = new_analysis_snapshot_id(candidate_id)
    coverage = CandidateEvidenceCoverageSummary(
        criteria_covered=item.evidence_summary.criteria_covered,
        criteria_missing=item.evidence_summary.criteria_missing,
        active_evidence_count=item.evidence_summary.active_evidence_count,
        stale_evidence_count=item.evidence_summary.stale_evidence_count,
        comparison_evidence_count=item.evidence_summary.comparison_evidence_count,
    )
    history_item = CandidateAnalysisHistoryItem(
        analysis_snapshot_id=snapshot_id,
        analyzed_at=analyzed_at,
        score=analysis_result.research_verdict.score,
        confidence=analysis_result.research_verdict.confidence,
        label=analysis_result.research_verdict.label,
        data_quality_grade=analysis_result.data_quality_summary.source_quality_grade,
        evidence_coverage_summary=coverage,
        limitations=sorted({
            *list(getattr(analysis_result.data_quality_summary, "fallback_evidence_categories", []) or []),
            *list(getattr(analysis_result.data_quality_summary, "mock_evidence_categories", []) or []),
            *list(getattr(analysis_result.candidate_validation_summary, "missing_or_mock_evidence", []) or []),
        })[:10],
    )
    history = [*item.analysis_history, history_item][-ANALYSIS_HISTORY_LIMIT:]
    updated = {
        "last_analyzed_at": analyzed_at,
        "last_analysis_snapshot_id": snapshot_id,
        "latest_score": analysis_result.research_verdict.score,
        "latest_confidence": analysis_result.research_verdict.confidence,
        "latest_label": analysis_result.research_verdict.label,
        "latest_data_quality_grade": analysis_result.data_quality_summary.source_quality_grade,
        "analysis_history": [entry.model_dump(mode="json") for entry in history],
    }
    row = {**item.model_dump(mode="json"), **updated}
    store_create_candidate_item(CandidateResearchItem.model_validate(row))
    return _candidate(row)


def list_candidate_analysis_history(candidate_id: str) -> list[CandidateAnalysisHistoryItem] | None:
    item = get_candidate_item(candidate_id)
    return item.analysis_history if item else None


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
    return bool(item.review_reasons)



def _candidate_readiness_item(item: CandidateResearchItem) -> CandidateReadinessComparisonItem:
    summary = item.evidence_summary
    missing = [criterion for criterion in summary.criteria_missing if criterion in JANE_QUALITATIVE_CRITERIA]
    completeness = CandidateReadinessEvidenceCompleteness(
        covered_count=len(summary.criteria_covered),
        missing_count=len(missing),
        active_evidence_count=summary.active_evidence_count,
        stale_evidence_count=summary.stale_evidence_count,
        unreviewed_evidence_count=summary.unreviewed_evidence_count,
        criteria_covered=summary.criteria_covered,
        criteria_missing=missing,
    )
    if missing:
        criterion = missing[0]
        state = "needs_evidence_before_comparison"
        top_gap = CandidateReadinessTopGap(
            gap_type="manual_evidence_required",
            criterion=criterion,
            source_route="manual_evidence",
            reason=f"Candidate is missing local evidence for {criterion} before readiness comparison is meaningful.",
        )
        next_action = f"Add or review manual evidence for {criterion}."
        route_hint = "manual_evidence"
    elif item.last_analyzed_at is None:
        state = "needs_analysis_refresh"
        top_gap = CandidateReadinessTopGap(
            gap_type="analysis_refresh_required",
            source_route="stock_research",
            reason="Candidate has local evidence coverage but no stored analysis snapshot.",
        )
        next_action = "Run or refresh Stock Research analysis for this candidate."
        route_hint = "stock_research"
    elif summary.stale_evidence_count > 0 or summary.unreviewed_evidence_count > 0:
        state = "review_queue_attention"
        top_gap = CandidateReadinessTopGap(
            gap_type="review_queue_attention",
            source_route="evidence_library",
            reason="Candidate has stale or unreviewed local evidence that should be checked before comparison.",
        )
        next_action = "Review stale or unreviewed evidence in the Evidence Library."
        route_hint = "evidence_library"
    else:
        state = "comparison_ready_for_review"
        top_gap = CandidateReadinessTopGap()
        next_action = "Compare readiness context manually; this is not a score ranking."
        route_hint = "stock_research"
    return CandidateReadinessComparisonItem(
        candidate_id=item.candidate_id,
        ticker=item.ticker,
        company_name=item.company_name,
        theme=item.theme,
        status=item.status,
        priority=item.priority,
        latest_label=item.latest_label,
        latest_data_quality_grade=item.latest_data_quality_grade,
        readiness_state=state,
        evidence_completeness=completeness,
        top_gap=top_gap,
        next_action=next_action,
        route_hint=route_hint,
    )


def build_candidate_readiness_comparison(include_archived: bool = False) -> CandidateReadinessComparisonResponse:
    now = datetime.now(timezone.utc)
    items = [item for item in list_candidate_items(include_archived=include_archived) if include_archived or item.status != "archived"]
    comparison_items = [_candidate_readiness_item(item) for item in items]
    priority_rank = {
        "needs_evidence_before_comparison": 0,
        "review_queue_attention": 1,
        "needs_analysis_refresh": 2,
        "comparison_ready_for_review": 3,
    }
    comparison_items = sorted(
        comparison_items,
        key=lambda item: (
            priority_rank.get(item.readiness_state, 9),
            item.evidence_completeness.active_evidence_count,
            -item.evidence_completeness.missing_count,
            item.ticker,
        ),
    )
    source_dates = sorted({item.updated_at[:10] for item in items if item.updated_at})
    return CandidateReadinessComparisonResponse(
        generated_at=now.isoformat(),
        source_status=CandidateWorkspaceSourceStatus(
            source_date=source_dates[-1] if source_dates else None,
            limitations=WORKSPACE_LIMITATIONS,
        ),
        summary=CandidateReadinessComparisonSummary(
            candidate_count=len(comparison_items),
            comparison_ready_count=sum(1 for item in comparison_items if item.readiness_state == "comparison_ready_for_review"),
            needs_manual_evidence_count=sum(1 for item in comparison_items if item.readiness_state == "needs_evidence_before_comparison"),
            needs_analysis_refresh_count=sum(1 for item in comparison_items if item.readiness_state == "needs_analysis_refresh"),
            review_queue_attention_count=sum(1 for item in comparison_items if item.readiness_state == "review_queue_attention"),
        ),
        items=comparison_items,
        missing_data=[] if comparison_items else ["candidate workspace is empty"],
    )


def build_candidate_dashboard(include_archived: bool = False) -> CandidateDashboardResponse:
    now = datetime.now(timezone.utc)
    items = list_candidate_items(include_archived=include_archived)
    active = [item for item in items if item.status != "archived"]
    scores = [float(item.latest_score) for item in active if item.latest_score is not None]
    grade_counts = Counter(item.latest_data_quality_grade for item in active if item.latest_data_quality_grade)
    review_queue = [item for item in active if _needs_review(item)]
    source_dates = sorted({item.updated_at[:10] for item in items if item.updated_at})
    status_counts = Counter(item.status for item in items)
    priority_counts = Counter(item.priority for item in active)
    missing_criteria = Counter(criterion for item in active for criterion in item.evidence_summary.criteria_missing if criterion in JANE_QUALITATIVE_CRITERIA)
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
            needs_analysis_count=sum(1 for item in active if item.last_analyzed_at is None),
            stale_analysis_count=sum(1 for item in active if _is_analysis_stale(item, now)),
            missing_evidence_candidate_count=sum(1 for item in active if item.evidence_summary.criteria_missing),
            review_overdue_count=sum(1 for item in active if _is_overdue(item.next_review_due_at, now)),
            status_breakdown=dict(sorted(status_counts.items())),
            priority_breakdown=dict(sorted(priority_counts.items())),
            missing_criteria_breakdown={criterion: missing_criteria.get(criterion, 0) for criterion in JANE_QUALITATIVE_CRITERIA},
            average_latest_score=round(sum(scores) / len(scores), 2) if scores else None,
            data_quality_grade_breakdown=dict(sorted(grade_counts.items())),
        ),
        items=items,
        review_queue=review_queue,
        limitations=WORKSPACE_LIMITATIONS,
        missing_data=[] if items else ["candidate workspace is empty"],
    )
