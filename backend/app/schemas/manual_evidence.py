from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal
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
    "competitor_comparison",
    "market_share_comparison",
    "product_capability_comparison",
    "ecosystem_comparison",
    "pricing_power_comparison",
    "switching_cost_comparison",
    "r_and_d_comparison",
    "other",
]
ManualEvidenceReviewStatus = Literal["unreviewed", "reviewed", "rejected", "archived"]
ManualEvidenceComparisonType = Literal[
    "competitor",
    "market_share",
    "product_capability",
    "platform_ecosystem",
    "customer_adoption",
    "pricing_power",
    "switching_cost",
    "r_and_d_intensity",
    "other",
]
ManualEvidenceClaimedAdvantage = Literal["stronger", "similar", "weaker", "unclear"]
ManualEvidenceSourceBasis = Literal[
    "user_note",
    "company_filing",
    "investor_presentation",
    "third_party_research",
    "manual_estimate",
    "other",
]
ManualEvidenceSourceReliability = Literal[
    "user_note",
    "official_company_material",
    "sec_filing_reference",
    "company_investor_relations",
    "reputable_third_party_research",
    "unknown",
    "other",
]
ManualEvidenceQualityLabel = Literal["high", "medium", "low", "incomplete"]
ManualEvidenceThesisDirection = Literal["supportive", "neutral", "challenging", "unknown"]
ManualEvidenceWorkflowStatus = Literal["draft", "review_ready", "accepted", "needs_refresh", "rejected", "archived"]

SECRET_MARKERS = ("FRED_API_KEY", "SEC_EDGAR_USER_AGENT", "api_key", "apikey", "secret", "token=")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_evidence_id() -> str:
    return f"manual_{uuid4().hex}"


def contains_secret_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker.lower() in lowered for marker in SECRET_MARKERS)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _quality_label(score: int) -> ManualEvidenceQualityLabel:
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    if score >= 30:
        return "low"
    return "incomplete"


def _normalize_peer_company(value: str) -> str:
    text = value.strip()
    if text.replace(".", "").replace("-", "").isalnum() and len(text) <= 12:
        return text.upper()
    return text


def _comparison_summary_is_vague(summary: str) -> bool:
    words = [word.strip(".,;:!?()[]{}").lower() for word in summary.split()]
    if len(words) < 8:
        return True
    vague_terms = {"dominant", "best", "amazing", "unbeatable", "clearly", "obviously"}
    specific_terms = {"peer", "competitor", "share", "platform", "ecosystem", "switching", "customer", "developer", "pricing", "capability", "r&d", "rd"}
    return bool(vague_terms & set(words)) and not bool(specific_terms & set(words))


def score_manual_evidence_quality(evidence: dict) -> dict:
    """Score completeness/review-readiness, not objective truth or verification."""

    reasons: list[str] = []
    review_status = str(evidence.get("review_status") or "unreviewed")
    source_date = _parse_date(evidence.get("source_date"))
    expires_at = _parse_date(evidence.get("expires_at"))
    reviewed_at = _parse_datetime(evidence.get("reviewed_at") or evidence.get("last_reviewed_at"))
    today = datetime.now(timezone.utc).date()
    score = 0
    stale_reasons: list[str] = []

    if review_status in {"rejected", "archived"}:
        reasons.append("Rejected or archived evidence is stored for audit but excluded from active scoring.")
    else:
        summary = str(evidence.get("summary") or "").strip()
        if len(summary) >= 30:
            score += 20
            reasons.append("Summary is present and specific.")
        elif summary:
            score += 10
            reasons.append("Summary is present but could be more specific.")
        else:
            reasons.append("Summary is missing.")

        if str(evidence.get("source_label") or "").strip():
            score += 15
            reasons.append("Source label is present.")
        else:
            reasons.append("Source label is missing.")

        if source_date:
            score += 15
            reasons.append("Source date is present.")
        else:
            reasons.append("Source date missing; review freshness cannot be assessed.")

        reliability = str(evidence.get("source_reliability_label") or "unknown")
        if reliability != "unknown":
            score += 10
            reasons.append(f"Source reliability label is {reliability}.")
        else:
            reasons.append("Source reliability label is unknown.")

        confidence = evidence.get("confidence")
        if isinstance(confidence, (int, float)):
            if 0.4 <= float(confidence) <= 0.8:
                score += 10
                reasons.append("User confidence is in a reasonable preliminary range.")
            elif float(confidence) > 0.8:
                score += 5
                reasons.append("User confidence above 0.8 is capped for review readiness.")
            else:
                score += 3
                reasons.append("User confidence is low.")
        else:
            reasons.append("Confidence is missing or invalid.")

        if review_status == "reviewed":
            score += 20
            reasons.append("Evidence has been locally reviewed.")
        elif review_status == "unreviewed":
            score += 5
            reasons.append("Evidence is unreviewed and needs local validation.")

        if evidence.get("limitations"):
            score += 5
            reasons.append("Limitations are documented.")
        else:
            reasons.append("Limitations are missing.")

        if evidence.get("tags"):
            score += 5
            reasons.append("Tags are present.")
        else:
            reasons.append("Tags are missing.")

        comparison = evidence.get("comparison_context") or {}
        if isinstance(comparison, dict) and comparison:
            peer_companies = [value for value in comparison.get("peer_companies") or [] if str(value).strip()]
            comparison_summary = str(comparison.get("comparison_summary") or "").strip()
            source_basis = str(comparison.get("source_basis") or "").strip()
            comparison_period = str(comparison.get("comparison_period") or "").strip()
            comparison_limitations = comparison.get("limitations") or []
            claimed_advantage = str(comparison.get("claimed_advantage") or "unclear")
            if peer_companies:
                score += 10
                reasons.append("Comparison context includes peer companies.")
            else:
                reasons.append("Comparison context is missing peer companies.")
            if len(comparison_summary) >= 40 and not _comparison_summary_is_vague(comparison_summary):
                score += 10
                reasons.append("Comparison summary is present and specific.")
            elif comparison_summary:
                score += 4
                reasons.append("Comparison summary is present but needs more specificity.")
            else:
                reasons.append("Comparison summary is missing.")
            if source_basis or comparison_period:
                score += 5
                reasons.append("Comparison period or source basis is present.")
            else:
                reasons.append("Comparison period and source basis are missing.")
            if comparison_limitations:
                score += 5
                reasons.append("Comparison limitations are documented.")
            if claimed_advantage == "stronger" and (not peer_companies or not source_basis):
                score -= 10
                reasons.append("Claimed stronger advantage lacks peer list or source basis.")
            if comparison_summary and _comparison_summary_is_vague(comparison_summary):
                score -= 10
                reasons.append("Comparison summary is vague or promotional.")

    if source_date:
        age_days = (today - source_date).days
        if age_days > 365:
            stale_reasons.append("source_date older than 365 days")
        if age_days > 730:
            reasons.append("Source date is older than 730 days; quality label cannot be high.")
    if expires_at and expires_at < today:
        stale_reasons.append("manual evidence expired")

    next_review_due_at = None
    if review_status == "reviewed":
        if source_date:
            due_date = source_date + timedelta(days=365)
        elif reviewed_at:
            due_date = reviewed_at.date() + timedelta(days=180)
        else:
            due_date = today + timedelta(days=180)
        next_review_due_at = datetime.combine(due_date, datetime.min.time(), tzinfo=timezone.utc).isoformat()

    is_stale = bool(stale_reasons)
    label = _quality_label(min(100, max(0, int(score))))
    if source_date and (today - source_date).days > 730 and label == "high":
        label = "medium"
    if is_stale and label == "high":
        label = "medium"
    if review_status in {"rejected", "archived"}:
        score = 0
        label = "incomplete"

    return {
        "evidence_quality_score": min(100, max(0, int(score))),
        "evidence_quality_label": label,
        "evidence_quality_reasons": reasons,
        "is_stale": is_stale,
        "stale_reason": "; ".join(stale_reasons) if stale_reasons else None,
        "next_review_due_at": next_review_due_at,
    }


def normalize_comparison_context(value: dict[str, Any] | None, ticker: str | None = None) -> dict[str, Any] | None:
    if not value:
        return None
    context = dict(value)
    if not context.get("subject_company") and ticker:
        context["subject_company"] = ticker.strip().upper()
    peers = context.get("peer_companies") or []
    if isinstance(peers, str):
        peers = [part.strip() for part in peers.split(",")]
    context["peer_companies"] = sorted({_normalize_peer_company(str(peer)) for peer in peers if str(peer).strip()})
    context.setdefault("claimed_advantage", "unclear")
    context.setdefault("source_basis", "user_note")
    context.setdefault("limitations", [])
    return context


def enrich_manual_evidence_quality(evidence: dict) -> dict:
    row = dict(evidence)
    row.setdefault("review_status", "unreviewed")
    row.setdefault("reviewed_at", None)
    row.setdefault("reviewed_by", None)
    row.setdefault("review_notes", None)
    row.setdefault("source_reliability_label", "unknown")
    row.setdefault("expires_at", None)
    row.setdefault("last_reviewed_at", row.get("reviewed_at"))
    row.setdefault("limitations", [])
    row.setdefault("tags", [])
    row.setdefault("note_title", None)
    row.setdefault("research_question", None)
    row.setdefault("thesis_direction", "unknown")
    row.setdefault("workflow_status", "draft")
    row.setdefault("user_provided", True)
    row["comparison_context"] = normalize_comparison_context(row.get("comparison_context"), row.get("ticker"))
    row.update(score_manual_evidence_quality(row))
    return row


class ManualEvidenceComparisonContext(BaseModel):
    comparison_type: ManualEvidenceComparisonType
    subject_company: str | None = None
    peer_companies: list[str] = Field(default_factory=list)
    comparison_summary: str = Field(min_length=1)
    claimed_advantage: ManualEvidenceClaimedAdvantage = "unclear"
    metric_name: str | None = None
    metric_value: float | str | None = None
    metric_unit: str | None = None
    comparison_period: str | None = None
    source_basis: ManualEvidenceSourceBasis = "user_note"
    limitations: list[str] = Field(default_factory=list)

    @field_validator("subject_company")
    @classmethod
    def normalize_subject_company(cls, value: str | None) -> str | None:
        return _normalize_peer_company(value) if value else value

    @field_validator("peer_companies")
    @classmethod
    def normalize_peer_companies(cls, value: list[str]) -> list[str]:
        return sorted({_normalize_peer_company(str(peer)) for peer in value if str(peer).strip()})

    @field_validator("comparison_summary", "metric_name", "metric_unit", "comparison_period")
    @classmethod
    def reject_secret_markers(cls, value: str | None) -> str | None:
        if value is not None and contains_secret_marker(value):
            raise ValueError("manual evidence comparison context must not include secrets or API key markers")
        if value is not None and detect_forbidden_language(value):
            raise ValueError("manual evidence comparison context must not include investment-instruction language")
        return value


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
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    review_notes: str | None = None
    source_reliability_label: ManualEvidenceSourceReliability = "unknown"
    expires_at: str | None = None
    last_reviewed_at: str | None = None
    next_review_due_at: str | None = None
    user_provided: bool = True
    created_by: str | None = "local_user"
    limitations: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    note_title: str | None = None
    research_question: str | None = None
    thesis_direction: ManualEvidenceThesisDirection = "unknown"
    workflow_status: ManualEvidenceWorkflowStatus = "draft"
    comparison_context: ManualEvidenceComparisonContext | None = None
    evidence_quality_score: int = Field(default=0, ge=0, le=100)
    evidence_quality_label: ManualEvidenceQualityLabel = "incomplete"
    evidence_quality_reasons: list[str] = Field(default_factory=list)
    is_stale: bool = False
    stale_reason: str | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("summary", "source_label", "source_url", "review_notes", "note_title", "research_question")
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
    review_notes: str | None = None
    source_reliability_label: ManualEvidenceSourceReliability | None = None
    expires_at: str | None = None
    limitations: list[str] | None = None
    tags: list[str] | None = None
    note_title: str | None = None
    research_question: str | None = None
    thesis_direction: ManualEvidenceThesisDirection | None = None
    workflow_status: ManualEvidenceWorkflowStatus | None = None
    comparison_context: ManualEvidenceComparisonContext | None = None

    @field_validator("summary", "source_label", "source_url", "review_notes", "note_title", "research_question")
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
