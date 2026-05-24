from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from backend.app.raw_store.manual_evidence import list_all_manual_evidence
from backend.app.schemas.manual_evidence import normalize_comparison_context
from backend.app.schemas.manual_evidence_dashboard import (
    ManualEvidenceDashboardFilters,
    ManualEvidenceDashboardQueueItem,
    ManualEvidenceDashboardResponse,
    ManualEvidenceDashboardSourceStatus,
    ManualEvidenceDashboardSummary,
    ManualEvidencePeerCompanyIndexItem,
    ManualEvidenceTickerSummary,
)

JANE_QUALITATIVE_CRITERIA: list[str] = [
    "monopoly_power",
    "visionary_founder_ceo",
    "disruptive_innovation",
    "network_effect",
    "continuous_r_and_d",
    "mega_trend_fit",
]
QUALITY_LABELS = ["high", "medium", "low", "incomplete"]
REVIEW_STATUSES = ["unreviewed", "reviewed", "rejected", "archived"]
QUALITY_RANK = {"incomplete": 0, "low": 1, "medium": 2, "high": 3}
DASHBOARD_LIMITATIONS = [
    "Manual evidence is user-provided and not independently verified.",
    "Dashboard is a review workflow aid, not investment advice.",
]


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _is_active(item: dict[str, Any]) -> bool:
    return item.get("review_status") not in {"archived", "rejected"}


def _comparison_context(item: dict[str, Any]) -> dict[str, Any] | None:
    return normalize_comparison_context(item.get("comparison_context"), item.get("ticker"))


def _has_comparison_context(item: dict[str, Any]) -> bool:
    context = _comparison_context(item)
    return bool(context)


def _peer_companies(item: dict[str, Any]) -> list[str]:
    context = _comparison_context(item) or {}
    return sorted({str(peer).strip().upper() for peer in context.get("peer_companies", []) if str(peer).strip()})


def _is_review_overdue(item: dict[str, Any], now: datetime) -> bool:
    due_at = _parse_datetime(item.get("next_review_due_at"))
    return bool(due_at and due_at <= now)


def _is_expired(item: dict[str, Any], now: datetime) -> bool:
    expires_at = _parse_datetime(item.get("expires_at"))
    return bool(expires_at and expires_at <= now)


def _comparison_claim_needs_review(item: dict[str, Any]) -> bool:
    context = _comparison_context(item) or {}
    if not context:
        return False
    peers = context.get("peer_companies") or []
    if not peers:
        return True
    if context.get("claimed_advantage") != "stronger":
        return False
    has_metric = bool(context.get("metric_name") or context.get("metric_value") or context.get("metric_unit"))
    source_basis = str(context.get("source_basis") or "user_note")
    weak_basis = source_basis in {"user_note", "manual_estimate", "other", ""}
    return weak_basis or not has_metric


def _review_due_reason(item: dict[str, Any], now: datetime) -> str | None:
    if item.get("review_status") == "unreviewed":
        return "unreviewed"
    if _is_review_overdue(item, now):
        return "review_overdue"
    if not item.get("source_date"):
        return "source_date_missing"
    if item.get("evidence_quality_label") in {"low", "incomplete"}:
        return "low_or_incomplete_quality"
    if _comparison_claim_needs_review(item):
        return "comparison_context_needs_review"
    return None


def _adr_review_label(item: dict[str, Any]) -> str | None:
    if not item.get("adr_evidence_type"):
        return None
    if item.get("document_date") and item.get("source_url"):
        return "ADR filing-backed manual review"
    return "ADR filing metadata incomplete"


def _adr_review_guidance(item: dict[str, Any]) -> list[str]:
    if not item.get("adr_evidence_type"):
        return []
    guidance = [
        "ADR / foreign-filer manual evidence is user-provided and not independently verified.",
        "Use this queue item to review the filing reference, quoted text, local-market context, and mapped Jane submetric before marking reviewed.",
        "Manual Evidence Library metadata does not change scoring or verdict semantics.",
    ]
    if not item.get("document_date"):
        guidance.append("Add document date or source date so freshness review can be assessed.")
    return guidance


def _queue_item(item: dict[str, Any], reason: str) -> ManualEvidenceDashboardQueueItem:
    return ManualEvidenceDashboardQueueItem(
        evidence_id=str(item.get("evidence_id") or ""),
        ticker=str(item.get("ticker") or "").upper(),
        criterion=str(item.get("criterion") or ""),
        evidence_type=str(item.get("evidence_type") or ""),
        review_status=str(item.get("review_status") or "unreviewed"),
        evidence_quality_label=str(item.get("evidence_quality_label") or "incomplete"),
        evidence_quality_score=int(item.get("evidence_quality_score") or 0),
        is_stale=bool(item.get("is_stale")),
        stale_reason=item.get("stale_reason"),
        next_review_due_at=item.get("next_review_due_at"),
        review_due_reason=reason,
        summary=str(item.get("summary") or ""),
        source_label=str(item.get("source_label") or ""),
        source_date=item.get("source_date"),
        adr_evidence_type=item.get("adr_evidence_type"),
        document_title=item.get("document_title"),
        document_date=item.get("document_date"),
        filing_period=item.get("filing_period"),
        local_market=item.get("local_market"),
        local_ticker=item.get("local_ticker"),
        adr_review_label=_adr_review_label(item),
        adr_review_guidance=_adr_review_guidance(item),
        affects_score=False,
        not_investment_advice=True,
        has_comparison_context=_has_comparison_context(item),
        peer_companies=_peer_companies(item),
    )


def _quality_breakdown(items: list[dict[str, Any]]) -> dict[str, int]:
    return {label: sum(1 for item in items if item.get("evidence_quality_label") == label) for label in QUALITY_LABELS}


def _status_breakdown(items: list[dict[str, Any]]) -> dict[str, int]:
    return {status: sum(1 for item in items if item.get("review_status") == status) for status in REVIEW_STATUSES}


def _average_quality(items: list[dict[str, Any]]) -> float | None:
    scores = [float(item.get("evidence_quality_score")) for item in items if isinstance(item.get("evidence_quality_score"), (int, float))]
    return round(sum(scores) / len(scores), 2) if scores else None


def _highest_quality_label(items: list[dict[str, Any]]) -> str:
    labels = [str(item.get("evidence_quality_label") or "incomplete") for item in items]
    if not labels:
        return "none"
    return max(labels, key=lambda label: QUALITY_RANK.get(label, -1))


def _criteria_covered(items: list[dict[str, Any]]) -> list[str]:
    return sorted({str(item.get("criterion")) for item in items if _is_active(item) and item.get("criterion") in JANE_QUALITATIVE_CRITERIA})


def _earliest_review_due(items: list[dict[str, Any]]) -> str | None:
    due_values = [str(item.get("next_review_due_at")) for item in items if item.get("next_review_due_at")]
    return sorted(due_values)[0] if due_values else None


def _passes_filters(item: dict[str, Any], filters: ManualEvidenceDashboardFilters, now: datetime) -> bool:
    if not filters.include_archived and item.get("review_status") == "archived":
        return False
    if not filters.include_rejected and item.get("review_status") == "rejected":
        return False
    if filters.ticker and str(item.get("ticker") or "").upper() != filters.ticker.strip().upper():
        return False
    if filters.review_status and item.get("review_status") != filters.review_status:
        return False
    if filters.criterion and item.get("criterion") != filters.criterion:
        return False
    if filters.stale_only and not (item.get("is_stale") or _is_expired(item, now)):
        return False
    if filters.review_due_only and not item.get("next_review_due_at"):
        return False
    if filters.has_comparison_context is not None and _has_comparison_context(item) is not filters.has_comparison_context:
        return False
    if filters.min_quality_label:
        item_rank = QUALITY_RANK.get(str(item.get("evidence_quality_label") or "incomplete"), 0)
        if item_rank < QUALITY_RANK[filters.min_quality_label]:
            return False
    return True


def build_review_queue(evidence_items: list[dict[str, Any]], now: datetime | None = None) -> list[ManualEvidenceDashboardQueueItem]:
    now = now or datetime.now(timezone.utc)
    queue = [
        _queue_item(item, reason)
        for item in evidence_items
        if _is_active(item)
        for reason in [_review_due_reason(item, now)]
        if reason
    ]
    return sorted(queue, key=lambda item: (item.next_review_due_at or "9999", item.ticker, item.evidence_id))


def build_stale_queue(evidence_items: list[dict[str, Any]], now: datetime | None = None) -> list[ManualEvidenceDashboardQueueItem]:
    now = now or datetime.now(timezone.utc)
    queue = [
        _queue_item(item, item.get("stale_reason") or "manual_evidence_expired")
        for item in evidence_items
        if _is_active(item) and (item.get("is_stale") or _is_expired(item, now))
    ]
    return sorted(queue, key=lambda item: (item.ticker, item.evidence_id))


def build_ticker_evidence_summary(ticker: str, evidence_items: list[dict[str, Any]], now: datetime | None = None) -> ManualEvidenceTickerSummary:
    now = now or datetime.now(timezone.utc)
    active = [item for item in evidence_items if _is_active(item)]
    covered = _criteria_covered(active)
    return ManualEvidenceTickerSummary(
        ticker=ticker,
        total_evidence_count=len(evidence_items),
        active_evidence_count=len(active),
        reviewed_count=sum(1 for item in active if item.get("review_status") == "reviewed"),
        unreviewed_count=sum(1 for item in active if item.get("review_status") == "unreviewed"),
        stale_count=sum(1 for item in active if item.get("is_stale") or _is_expired(item, now)),
        review_due_count=sum(1 for item in active if item.get("next_review_due_at")),
        review_scheduled_count=sum(1 for item in active if item.get("next_review_due_at")),
        review_overdue_count=sum(1 for item in active if _is_review_overdue(item, now)),
        comparison_evidence_count=sum(1 for item in active if _has_comparison_context(item)),
        criteria_covered=covered,
        criteria_missing=[criterion for criterion in JANE_QUALITATIVE_CRITERIA if criterion not in covered],
        peer_companies_mentioned=sorted({peer for item in active for peer in _peer_companies(item)}),
        quality_label_breakdown=_quality_breakdown(active),
        highest_quality_label=_highest_quality_label(active),
        next_review_due_at=_earliest_review_due(active),
    )


def build_peer_company_index(evidence_items: list[dict[str, Any]]) -> list[ManualEvidencePeerCompanyIndexItem]:
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "evidence_count": 0,
        "tickers": set(),
        "criteria": set(),
        "comparison_types": set(),
        "claimed_advantage_breakdown": {"stronger": 0, "similar": 0, "weaker": 0, "unclear": 0},
    })
    for item in evidence_items:
        if not _is_active(item):
            continue
        context = _comparison_context(item) or {}
        for peer in _peer_companies(item):
            bucket = buckets[peer]
            bucket["evidence_count"] += 1
            bucket["tickers"].add(str(item.get("ticker") or "").upper())
            bucket["criteria"].add(str(item.get("criterion") or ""))
            bucket["comparison_types"].add(str(context.get("comparison_type") or "other"))
            claimed = str(context.get("claimed_advantage") or "unclear")
            if claimed not in bucket["claimed_advantage_breakdown"]:
                claimed = "unclear"
            bucket["claimed_advantage_breakdown"][claimed] += 1
    return [
        ManualEvidencePeerCompanyIndexItem(
            peer_company=peer,
            evidence_count=bucket["evidence_count"],
            tickers=sorted(bucket["tickers"]),
            criteria=sorted(bucket["criteria"]),
            comparison_types=sorted(bucket["comparison_types"]),
            claimed_advantage_breakdown=bucket["claimed_advantage_breakdown"],
        )
        for peer, bucket in sorted(buckets.items())
    ]


def _build_summary(evidence_items: list[dict[str, Any]], now: datetime) -> ManualEvidenceDashboardSummary:
    active = [item for item in evidence_items if _is_active(item)]
    covered_counts = {
        criterion: sum(1 for item in active if item.get("criterion") == criterion)
        for criterion in JANE_QUALITATIVE_CRITERIA
    }
    return ManualEvidenceDashboardSummary(
        total_evidence_count=len(evidence_items),
        active_evidence_count=len(active),
        reviewed_count=sum(1 for item in active if item.get("review_status") == "reviewed"),
        unreviewed_count=sum(1 for item in active if item.get("review_status") == "unreviewed"),
        stale_count=sum(1 for item in active if item.get("is_stale") or _is_expired(item, now)),
        review_due_count=sum(1 for item in active if item.get("next_review_due_at")),
        review_scheduled_count=sum(1 for item in active if item.get("next_review_due_at")),
        review_overdue_count=sum(1 for item in active if _is_review_overdue(item, now)),
        archived_count=sum(1 for item in evidence_items if item.get("review_status") == "archived"),
        rejected_count=sum(1 for item in evidence_items if item.get("review_status") == "rejected"),
        comparison_evidence_count=sum(1 for item in active if _has_comparison_context(item)),
        tickers_covered_count=len({str(item.get("ticker") or "").upper() for item in active if item.get("ticker")}),
        average_quality_score=_average_quality(active),
        quality_label_breakdown=_quality_breakdown(active),
        review_status_breakdown=_status_breakdown(evidence_items),
        criteria_coverage=covered_counts,
    )


def summarize_manual_evidence_dashboard(filters: ManualEvidenceDashboardFilters) -> ManualEvidenceDashboardResponse:
    now = datetime.now(timezone.utc)
    rows = list_all_manual_evidence(include_archived=True, include_rejected=True)
    filtered = [item for item in rows if _passes_filters(item, filters, now)]
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in filtered:
        ticker = str(item.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker].append(item)
    audit_items = [
        item
        for item in filtered
        if (
            item.get("review_status") == "archived" and filters.include_archived
        ) or (
            item.get("review_status") == "rejected" and filters.include_rejected
        )
    ]
    source_dates = sorted({str(item.get("source_date")) for item in filtered if item.get("source_date")})
    return ManualEvidenceDashboardResponse(
        generated_at=now.isoformat(),
        source_status=ManualEvidenceDashboardSourceStatus(
            source_date=source_dates[-1] if source_dates else None,
            limitations=DASHBOARD_LIMITATIONS,
            missing_data=[],
        ),
        summary=_build_summary(filtered, now),
        ticker_summaries=[
            build_ticker_evidence_summary(ticker, items, now)
            for ticker, items in sorted(by_ticker.items())
        ],
        review_queue=build_review_queue(filtered, now),
        stale_queue=build_stale_queue(filtered, now),
        audit_queue=[_queue_item(item, f"{item.get('review_status')}_audit") for item in audit_items],
        peer_company_index=build_peer_company_index(filtered),
        limitations=DASHBOARD_LIMITATIONS + [
            "Archived and rejected evidence is excluded unless explicitly requested.",
            "Peer company index is derived only from user-provided comparison_context.",
            "review_due_count and review_scheduled_count count items with any next_review_due_at; review_overdue_count counts items due at or before generation time.",
        ],
        missing_data=[] if filtered else ["manual evidence library is empty"],
    )
