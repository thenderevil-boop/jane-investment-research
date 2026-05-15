from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from backend.app.data_sources.mock_data import DEFAULT_STOCK, MOCK_SOURCE_DATE, STOCK_FIXTURES
from backend.app.engines.jane_criteria_canonical import JANE_CRITERIA
from backend.app.engines.leadership_engine import evaluate_leadership
from backend.app.engines.macro_regime_engine import evaluate_macro_regime
from backend.app.engines.market_timing_engine import evaluate_market_timing
from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.engines.sec_13f_target_matching import build_candidate_13f_evidence
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.pipelines.research_pipeline import _build_jane_reference_conditions, _enrich_source_status, score_object
from backend.app.raw_store.repository import get_company_fundamentals, get_company_profile, get_sec_companyfacts, load_manual_evidence_for_ticker, read_macro_data, read_market_data, read_sec_filings
from backend.app.schemas.common import ScoreObject
from backend.app.schemas.manual_evidence import enrich_manual_evidence_quality, normalize_comparison_context, score_manual_evidence_quality
from backend.app.schemas.stock_analysis import (
    AnalyzeStockDataQualitySummary,
    AnalyzeStockRequest,
    AnalyzeStockResponse,
    CandidateValidationSummary,
    EvidenceMatrixItem,
    FinancialStatementSignals,
    JaneCriteriaCoverageMatrix,
    JaneCompanyQuality,
    NextManualCheck,
    ResearchVerdict,
    ScoreDriverBreakdown,
    ValidationOSReport,
    ValidationQualitySummary,
)
from backend.app.utils.freshness import build_source_status, summarize_data_quality
from backend.app.utils.forbidden_language import detect_forbidden_language

MOCK_LEADERSHIP_CONFIDENCE_CAP = 0.72
MOCK_EVIDENCE_LIMITATION = "Mock evidence limits analyze-stock confidence; treat mock-based components as preliminary validation only."
USER_QUALITATIVE_LIMITATIONS = [
    "User-provided evidence is not independently verified by the system.",
    "This evidence can support preliminary qualitative assessment only.",
    "Manual source review is required.",
]
QUALITATIVE_CORE_CRITERIA = ["monopoly_power", "visionary_founder_ceo", "disruptive_innovation", "network_effect"]
JANE_LEADERSHIP_CRITERIA_PATH = Path(__file__).resolve().parents[1] / "data" / "jane_leadership_criteria.json"
SUPPORTED_QUALITATIVE_EVIDENCE_TYPES = {
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
}
COMPARISON_EVIDENCE_TYPES = {
    "competitor_comparison",
    "market_share_comparison",
    "product_capability_comparison",
    "ecosystem_comparison",
    "pricing_power_comparison",
    "switching_cost_comparison",
    "r_and_d_comparison",
}
SUPPORTED_COMPARISON_TYPES = {
    "competitor",
    "market_share",
    "product_capability",
    "platform_ecosystem",
    "customer_adoption",
    "pricing_power",
    "switching_cost",
    "r_and_d_intensity",
    "other",
}
SUPPORTED_CLAIMED_ADVANTAGES = {"stronger", "similar", "weaker", "unclear"}
JANE_CANONICAL_LEGACY_SLUGS_BY_ID = {
    1: "monopoly_power",
    2: "visionary_founder_ceo",
    3: "early_skepticism",
    4: "disruptive_innovation",
    5: "superior_technology_r_and_d",
    6: "scalable_business_model",
    7: "brand_power_fandom",
    8: "data_advantage",
    9: "capital_allocation",
    10: "cash_flow_creation",
    11: "mega_trend_fit",
    12: "talent_attraction_retention",
    13: "global_expansion",
    14: "life_changing_necessary_product",
    15: "regulatory_government_relationship",
    16: "network_effect",
    17: "mission_narrative_power",
    18: "patents_ip",
    19: "vc_institutional_support",
    20: "retention_repurchase_rate",
}
JANE_CANONICAL_ID_BY_LEGACY_SLUG = {slug: criterion_id for criterion_id, slug in JANE_CANONICAL_LEGACY_SLUGS_BY_ID.items()}
SECRET_MARKERS = ("FRED_API_KEY", "SEC_EDGAR_USER_AGENT", "api_key", "apikey", "secret", "token=")
FALLBACK_QUALITATIVE_ALLOWED_TYPES_BY_CRITERION = {
    "monopoly_power": {"market_share", "switching_cost", "brand_power", "platform_ecosystem", "patent", "market_share_comparison", "pricing_power_comparison", "switching_cost_comparison", "competitor_comparison", "user_provided_note", "other"},
    "visionary_founder_ceo": {"founder_operator", "management_tenure", "filing_reference", "user_provided_note", "other"},
    "early_skepticism": {"customer_adoption", "filing_reference", "product_disruption", "user_provided_note", "other"},
    "disruptive_innovation": {"product_disruption", "patent", "customer_adoption", "r_and_d_intensity", "filing_reference", "product_capability_comparison", "r_and_d_comparison", "user_provided_note", "other"},
    "superior_technology_r_and_d": {"r_and_d_intensity", "patent", "filing_reference", "product_capability_comparison", "r_and_d_comparison", "user_provided_note", "other"},
    "scalable_business_model": {"customer_adoption", "platform_ecosystem", "filing_reference", "competitor_comparison", "user_provided_note", "other"},
    "brand_power_fandom": {"brand_power", "customer_adoption", "pricing_power_comparison", "user_provided_note", "other"},
    "data_advantage": {"platform_ecosystem", "developer_ecosystem", "customer_adoption", "filing_reference", "ecosystem_comparison", "user_provided_note", "other"},
    "capital_allocation": {"filing_reference", "r_and_d_intensity", "competitor_comparison", "user_provided_note", "other"},
    "cash_flow_creation": {"filing_reference", "competitor_comparison", "user_provided_note", "other"},
    "mega_trend_fit": {"customer_adoption", "platform_ecosystem", "filing_reference", "competitor_comparison", "product_capability_comparison", "user_provided_note", "other"},
    "talent_attraction_retention": {"management_tenure", "founder_operator", "filing_reference", "user_provided_note", "other"},
    "global_expansion": {"customer_adoption", "filing_reference", "competitor_comparison", "market_share_comparison", "user_provided_note", "other"},
    "life_changing_necessary_product": {"customer_adoption", "switching_cost", "platform_ecosystem", "product_capability_comparison", "user_provided_note", "other"},
    "regulatory_government_relationship": {"filing_reference", "competitor_comparison", "user_provided_note", "other"},
    "network_effect": {"platform_ecosystem", "developer_ecosystem", "customer_adoption", "switching_cost", "ecosystem_comparison", "switching_cost_comparison", "user_provided_note", "other"},
    "mission_narrative_power": {"founder_operator", "brand_power", "customer_adoption", "user_provided_note", "other"},
    "patents_ip": {"patent", "filing_reference", "product_capability_comparison", "r_and_d_comparison", "user_provided_note", "other"},
    "vc_institutional_support": {"filing_reference", "competitor_comparison", "user_provided_note", "other"},
    "retention_repurchase_rate": {"customer_adoption", "switching_cost", "filing_reference", "competitor_comparison", "user_provided_note", "other"},
}


@lru_cache(maxsize=1)
def load_jane_leadership_criteria() -> list[dict]:
    try:
        with JANE_LEADERSHIP_CRITERIA_PATH.open(encoding="utf-8") as criteria_file:
            criteria = json.load(criteria_file)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(criteria, list):
        return []
    return [item for item in criteria if isinstance(item, dict)]


def _qualitative_allowed_types_by_criterion() -> dict[str, set[str]]:
    allowed = {
        str(item["name"]): set(str(value) for value in item.get("accepted_evidence_types", []))
        for item in load_jane_leadership_criteria()
        if item.get("name")
    }
    if not allowed:
        allowed = {key: set(value) for key, value in FALLBACK_QUALITATIVE_ALLOWED_TYPES_BY_CRITERION.items()}
    allowed["continuous_r_and_d"] = {
        "r_and_d_intensity",
        "patent",
        "filing_reference",
        "user_provided_note",
        "r_and_d_comparison",
        "other",
    }
    return allowed


QUALITATIVE_ALLOWED_TYPES_BY_CRITERION = _qualitative_allowed_types_by_criterion()
SUPPORTED_QUALITATIVE_CRITERIA = set(QUALITATIVE_ALLOWED_TYPES_BY_CRITERION)


def _research_verdict(
    *,
    company_quality_score: float,
    company_quality_confidence: float,
    key_qualitative_insufficient: bool,
    smart_money_score: float,
    macro_score: float,
    overheat_score: float,
    missing_data_count: int,
    confidence_inputs: list[float],
    mock_evidence_present: bool = False,
    fallback_evidence_present: bool = False,
    live_macro_present: bool = False,
    user_qualitative_evidence_present: bool = False,
) -> ResearchVerdict:
    raw_score = company_quality_score * 0.45 + smart_money_score * 0.25 + macro_score * 0.20 + max(0, 100 - overheat_score) * 0.10
    missing_penalty = min(25, missing_data_count * 3)
    score = round(max(0, min(100, raw_score - missing_penalty)), 2)
    confidence = max(0.15, min(1, (sum([*confidence_inputs, company_quality_confidence]) / (len(confidence_inputs) + 1)) - min(0.35, missing_data_count * 0.03)))
    if mock_evidence_present:
        confidence = min(confidence, MOCK_LEADERSHIP_CONFIDENCE_CAP)
    if fallback_evidence_present:
        confidence = min(confidence, 0.75)
    if user_qualitative_evidence_present:
        confidence = min(confidence, 0.80)
    if key_qualitative_insufficient:
        confidence = min(confidence, 0.80)
    confidence = round(confidence, 2)
    if missing_data_count >= 7 or confidence < 0.35:
        label = "insufficient_data"
        summary = "Research reference only. Evidence is incomplete, so this ticker needs human verification before deeper research priority is raised."
    elif overheat_score >= 75:
        label = "high_risk_context"
        summary = "Research reference only. The ticker has elevated risk context, so deeper review should focus on evidence quality and downside scenarios."
    elif score >= 70 and macro_score >= 50:
        label = "worth_deep_research"
        summary = "Research reference only. The ticker is worth deeper research under Jane methodology, with current environment context included."
    elif score >= 45:
        label = "watchlist_candidate"
        summary = "Research reference only. The ticker merits watchlist-level validation while missing or weaker evidence is checked."
    else:
        label = "insufficient_data"
        summary = "Research reference only. Current structured evidence is not strong enough to raise research priority."
    if mock_evidence_present:
        summary = f"{summary} Mock evidence limits confidence."
    boosters = []
    limiters = []
    if live_macro_present:
        boosters.append("Macro environment uses live or derived-live source context.")
    if macro_score >= 56:
        boosters.append("Macro score is neutral-to-constructive under macro_v12_5.")
    if smart_money_score >= 50:
        boosters.append("Aggregate smart-money evidence is at least neutral in the current framework.")
    if company_quality_score >= 60 and company_quality_confidence >= 0.45:
        boosters.append("Jane company quality has partial evidence from financial metrics.")
    if mock_evidence_present:
        limiters.append("Legacy leadership or company-related evidence is mock-based.")
    if key_qualitative_insufficient:
        limiters.append("Key qualitative Jane company quality criteria remain insufficient.")
    if user_qualitative_evidence_present:
        limiters.append("User-provided qualitative evidence is preliminary until independently verified.")
    if fallback_evidence_present:
        limiters.append("One or more smart-money or filing components use fallback or cached-after-failure evidence.")
    if missing_data_count:
        limiters.append(f"{missing_data_count} missing-data items require human verification.")
    return ResearchVerdict(
        label=label,
        score=score,
        confidence=confidence,
        summary=summary,
        confidence_factors={
            "confidence_boosters": boosters,
            "confidence_limiters": limiters,
        },
    )


def _status_dict(value) -> dict:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {}


def _sanitize_api_secret_markers(value):
    if isinstance(value, str):
        return value.replace("SEC_EDGAR_USER_AGENT", "SEC EDGAR User-Agent")
    if isinstance(value, list):
        return [_sanitize_api_secret_markers(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_api_secret_markers(child) for key, child in value.items()}
    return value


def _source_quality_from_status(status: dict, *, category: str = "") -> str:
    source_type = status.get("source_type")
    provider = str(status.get("provider") or "")
    fallback_used = bool(status.get("fallback_used")) or source_type == "fallback"
    if provider == "user_provided_qualitative_evidence":
        return "user_provided"
    if category == "insider_activity" and (source_type == "mock" or fallback_used):
        return "mixed_with_fallback"
    if category == "macro_environment" and source_type == "derived" and provider.startswith("mixed_FRED"):
        return "derived_live"
    if fallback_used:
        return "mixed_with_fallback"
    if category in {"sec_financial_facts"} and source_type in {"live", "cached_live"}:
        return "filing_backed"
    if category == "fundamentals_cross_check":
        return "derived_from_mixed_sources"
    if "SEC_companyfacts" in provider or "SEC companyfacts" in provider:
        return "derived_from_mixed_sources" if source_type == "derived" else "filing_backed"
    if source_type == "mock":
        return "mock_only"
    if source_type == "cached_live":
        return "cached_live"
    if source_type == "live":
        return "live_backed"
    if source_type == "derived":
        if provider == "mixed_smart_money_sources":
            return "mixed_with_fallback" if fallback_used else "derived_live"
        if "mock" in provider.lower():
            return "mixed_with_fallback"
        return "derived_live"
    if category == "risk_flags":
        return "derived_live"
    return "insufficient"


def _contains_secret_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker.lower() in lowered for marker in SECRET_MARKERS)


def _is_promotional_without_specific_claim(summary: str) -> bool:
    words = [word.strip(".,;:!?()[]{}").lower() for word in summary.split()]
    if len(words) < 6:
        return True
    promotional = {"amazing", "best", "dominant", "revolutionary", "unstoppable", "guaranteed", "world-class", "worldclass"}
    specific = {
        "market",
        "share",
        "patent",
        "developer",
        "ecosystem",
        "platform",
        "customer",
        "switching",
        "founder",
        "tenure",
        "filing",
        "r&d",
        "rd",
        "adoption",
        "software",
    }
    has_promotional = bool(promotional & set(words))
    has_specific = bool(specific & set(words)) or any(char.isdigit() for char in summary)
    return has_promotional and not has_specific


def _is_comparison_evidence_item(item: dict) -> bool:
    return bool(item.get("comparison_context")) or str(item.get("evidence_type") or "") in COMPARISON_EVIDENCE_TYPES


def _comparison_context_validation_error(item: dict) -> str | None:
    raw_context = item.get("comparison_context")
    if not raw_context:
        return None
    if not isinstance(raw_context, dict):
        return "Rejected because comparison_context must be an object."
    context = normalize_comparison_context(raw_context, item.get("ticker"))
    item["comparison_context"] = context
    comparison_type = str(context.get("comparison_type") or "").strip()
    claimed_advantage = str(context.get("claimed_advantage") or "unclear").strip()
    summary = str(context.get("comparison_summary") or "").strip()
    source_basis = str(context.get("source_basis") or "").strip()
    text_fields = [
        summary,
        str(context.get("metric_name") or ""),
        str(context.get("metric_unit") or ""),
        str(context.get("comparison_period") or ""),
    ]
    if comparison_type not in SUPPORTED_COMPARISON_TYPES:
        return "Rejected because comparison_type is unsupported."
    if claimed_advantage not in SUPPORTED_CLAIMED_ADVANTAGES:
        return "Rejected because claimed_advantage is unsupported."
    if not summary:
        return "Rejected because comparison_summary is missing."
    if detect_forbidden_language(text_fields):
        return "Rejected because comparison evidence contains investment-instruction language."
    if any(_contains_secret_marker(value) for value in text_fields):
        return "Rejected because comparison evidence appears to include a secret or API key marker."
    if claimed_advantage == "stronger" and not (context.get("peer_companies") and source_basis):
        return None
    return None


def _comparison_context_missing_data(context: dict | None) -> list[str]:
    if not context:
        return []
    missing = []
    if not context.get("peer_companies"):
        missing.append("comparison_peer_companies")
    if not context.get("comparison_period"):
        missing.append("comparison_period")
    if not context.get("source_basis"):
        missing.append("comparison_source_basis")
    return missing


def _qualitative_evidence_by_criterion(assessment: dict | None) -> dict[str, list[dict]]:
    by_criterion: dict[str, list[dict]] = {}
    if not assessment:
        return by_criterion
    for item in assessment.get("evidence_items", []):
        if item.get("accepted"):
            by_criterion.setdefault(str(item.get("criterion")), []).append(item)
    return by_criterion


def _criterion_strength(items: list[dict]) -> str:
    if not items:
        return "none"
    if any(_is_comparison_evidence_item(item) and not (item.get("comparison_context") or {}).get("peer_companies") for item in items):
        return "weak"
    if any(item.get("is_stale") for item in items):
        return "weak"
    if any(item.get("evidence_quality_label") == "incomplete" for item in items):
        return "weak"
    avg_quality = sum(float(item.get("evidence_quality_score") or 0) for item in items) / len(items)
    if avg_quality >= 80 and any(item.get("review_status") == "reviewed" for item in items):
        return "moderate"
    avg_confidence = sum(float(item.get("confidence") or 0) for item in items) / len(items)
    if len(items) >= 3 and avg_confidence >= 0.68:
        return "moderate"
    if avg_confidence >= 0.55 and avg_quality >= 55:
        return "moderate"
    return "weak"


def _build_user_qualitative_criterion(
    name: str,
    display_name: str,
    items: list[dict],
    *,
    default_missing: list[str],
) -> dict | None:
    if not items:
        return None
    confidence = min(0.7, max(float(item.get("confidence") or 0) for item in items))
    avg_quality = sum(float(item.get("evidence_quality_score") or 0) for item in items) / len(items)
    if avg_quality < 30:
        score = 0.5
    elif avg_quality < 55:
        score = 2.0 + min(1.0, len(items) * 0.25)
    else:
        score = 4.0 + min(2.0, len(items) * 0.75) + (1.0 if confidence >= 0.65 else 0)
        if any(item.get("review_status") == "reviewed" for item in items):
            score += 0.5
    if any(item.get("is_stale") for item in items):
        score = min(score, 3.0)
    if name == "monopoly_power" and any(_is_comparison_evidence_item(item) and not (item.get("comparison_context") or {}).get("peer_companies") for item in items):
        score = min(score, 2.0)
    evidence = []
    for item in items:
        if item.get("summary"):
            display_key = str(item.get("evidence_type", "")).replace("_", " ")
            evidence.append(f"{display_key}: {item.get('summary')}")
    missing = sorted(set([missing for item in items for missing in item.get("missing_data", [])]))
    if not missing:
        missing = [f"independent verification for {display_name}"]
    limitations = sorted(set([*USER_QUALITATIVE_LIMITATIONS, *[limitation for item in items for limitation in item.get("limitations", [])]]))
    if any(item.get("review_status") == "reviewed" for item in items):
        limitations.append("Reviewed manual evidence remains user-provided and is not independently verified.")
    if any(item.get("is_stale") for item in items):
        limitations.append("Stale manual evidence is capped and requires refresh.")
    if any(_is_comparison_evidence_item(item) for item in items):
        limitations.append("Manual comparison context supports preliminary review only and requires peer validation.")
    limitations = sorted(set(limitations))
    return _criterion(
        name,
        display_name,
        score=score,
        status="neutral",
        source_quality="user_provided",
        affects_score=True,
        evidence_strength=_criterion_strength(items),
        verification_level="user_provided",
        evidence=evidence,
        limitations=limitations,
        missing_data=missing or default_missing,
    )


def _manual_evidence_dedupe_key(ticker: str, item: dict) -> str:
    if item.get("evidence_id"):
        return f"id:{item.get('evidence_id')}"
    return _manual_evidence_content_key(ticker, item)


def _manual_evidence_content_key(ticker: str, item: dict) -> str:
    parts = [
        ticker.strip().upper(),
        str(item.get("criterion") or "").strip().lower(),
        str(item.get("evidence_type") or "").strip().lower(),
        str(item.get("summary") or "").strip().lower(),
        str(item.get("source_label") or "").strip().lower(),
    ]
    return "hash:" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _build_qualitative_evidence_assessment(ticker: str, evidence_inputs: list, saved_evidence_inputs: list | None = None) -> dict:
    items = []
    latest_source_date: str | None = None
    missing_data: set[str] = set()
    ignored_count = 0
    deduplicated_count = 0
    merged_inputs: list[tuple[dict, str]] = []
    seen_keys: set[str] = set()
    seen_content_keys: set[str] = set()
    for raw_saved in saved_evidence_inputs or []:
        saved_item = raw_saved.model_dump(mode="json") if hasattr(raw_saved, "model_dump") else dict(raw_saved)
        if saved_item.get("review_status") in {"archived", "rejected"}:
            ignored_count += 1
            continue
        key = _manual_evidence_dedupe_key(ticker, saved_item)
        if key in seen_keys:
            deduplicated_count += 1
            continue
        seen_keys.add(key)
        seen_content_keys.add(_manual_evidence_content_key(ticker, saved_item))
        merged_inputs.append((saved_item, "saved_library"))
    for raw_request in evidence_inputs or []:
        request_item = raw_request.model_dump(mode="json") if hasattr(raw_request, "model_dump") else dict(raw_request)
        key = _manual_evidence_dedupe_key(ticker, request_item)
        content_key = _manual_evidence_content_key(ticker, request_item)
        if key in seen_keys or content_key in seen_content_keys:
            deduplicated_count += 1
            continue
        seen_keys.add(key)
        seen_content_keys.add(content_key)
        merged_inputs.append((request_item, "request_scoped"))

    for item, origin in merged_inputs:
        item = enrich_manual_evidence_quality(item)
        criterion = str(item.get("criterion") or "").strip()
        evidence_type = str(item.get("evidence_type") or "").strip()
        comparison_context = normalize_comparison_context(item.get("comparison_context"), ticker)
        item["comparison_context"] = comparison_context
        summary = str(item.get("summary") or "").strip()
        source_label = str(item.get("source_label") or "").strip()
        source_date = item.get("source_date") or None
        confidence = item.get("confidence")
        review_status = item.get("review_status") if origin == "saved_library" else None
        source_reliability_label = str(item.get("source_reliability_label") or "unknown")
        limitations = [str(value) for value in item.get("limitations") or [] if value]
        missing_item: list[str] = []
        reason = "Accepted as preliminary user-provided qualitative evidence."
        accepted = True

        text_fields = [summary, source_label, str(item.get("source_url") or "")]
        if not summary:
            accepted = False
            reason = "Rejected because summary is empty."
        elif criterion not in SUPPORTED_QUALITATIVE_CRITERIA:
            accepted = False
            reason = "Rejected because criterion is unsupported."
        elif evidence_type not in SUPPORTED_QUALITATIVE_EVIDENCE_TYPES:
            accepted = False
            reason = "Rejected because evidence_type is unsupported."
        elif evidence_type not in QUALITATIVE_ALLOWED_TYPES_BY_CRITERION.get(criterion, set()):
            accepted = False
            reason = "Rejected because evidence_type does not support the selected criterion."
        elif comparison_error := _comparison_context_validation_error(item):
            accepted = False
            reason = comparison_error
        elif detect_forbidden_language(text_fields):
            accepted = False
            reason = "Rejected because the evidence contains investment-instruction language."
        elif any(_contains_secret_marker(value) for value in text_fields):
            accepted = False
            reason = "Rejected because the evidence appears to include a secret or API key marker."
        elif _is_promotional_without_specific_claim(summary):
            accepted = False
            reason = "Rejected because the summary is promotional or lacks a specific claim."
        elif not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            accepted = False
            reason = "Rejected because confidence is outside the 0 to 1 range."
        elif not source_label and not source_date:
            accepted = False
            reason = "Rejected because source_label and source_date are both missing."

        if not source_label:
            missing_item.append("source_label")
        if not source_date:
            missing_item.append("source_date")
        missing_item.extend(_comparison_context_missing_data(item.get("comparison_context")))
        if source_date and (latest_source_date is None or str(source_date) > latest_source_date):
            latest_source_date = str(source_date)
        effective_confidence = 0.0 if not isinstance(confidence, (int, float)) else float(confidence)
        if accepted and item.get("user_provided", True) and effective_confidence > 0.8:
            effective_confidence = 0.7
            limitations.append("User-provided confidence above 0.8 is capped to 0.7 unless independently verified.")
        if accepted:
            limitations = sorted(set([*limitations, *USER_QUALITATIVE_LIMITATIONS]))
            if review_status == "unreviewed":
                limitations.append("Manual evidence is unreviewed and requires validation.")
            if item.get("is_stale"):
                limitations.append(f"Manual evidence is stale: {item.get('stale_reason') or 'refresh required'}.")
            if item.get("evidence_quality_label") == "incomplete":
                limitations.append("Manual evidence quality is incomplete and has limited scoring impact.")
            if review_status == "reviewed":
                limitations.append("Reviewed manual evidence remains user-provided and is not independently verified.")
            if _is_comparison_evidence_item(item):
                limitations.append("Comparison evidence is user-provided and requires peer claim validation.")
                if item.get("comparison_context", {}).get("claimed_advantage") == "stronger":
                    limitations.append("Claimed advantage requires measurable, current comparison support.")
        else:
            summary = "Rejected qualitative evidence omitted from response for safety."
            source_label = source_label if source_label and not _contains_secret_marker(source_label) else "redacted"
            limitations = sorted(set([*limitations, "Rejected qualitative evidence does not affect scoring."]))
        missing_data.update(missing_item)
        items.append(
            {
                "evidence_id": item.get("evidence_id"),
                "origin": origin,
                "review_status": review_status,
                "criterion": criterion or "unsupported",
                "criterion_id": item.get("criterion_id"),
                "criterion_name": item.get("criterion_name"),
                "submetric": item.get("submetric"),
                "evidence_type": evidence_type or "unsupported",
                "summary": summary,
                "source_label": source_label,
                "source_date": source_date,
                "source_quality": "user_provided" if accepted else "rejected",
                "accepted": accepted,
                "acceptance_reason": reason,
                "confidence": round(max(0.0, min(1.0, effective_confidence)), 2),
                "limitations": limitations,
                "missing_data": missing_item,
                "evidence_quality_score": item.get("evidence_quality_score", 0),
                "evidence_quality_label": item.get("evidence_quality_label", "incomplete"),
                "evidence_quality_reasons": item.get("evidence_quality_reasons", []),
                "is_stale": bool(item.get("is_stale")),
                "stale_reason": item.get("stale_reason"),
                "next_review_due_at": item.get("next_review_due_at"),
                "source_reliability_label": source_reliability_label,
                "comparison_context": item.get("comparison_context"),
            }
        )

    accepted_items = [item for item in items if item["accepted"]]
    saved_items = [item for item in items if item["origin"] == "saved_library"]
    request_items = [item for item in items if item["origin"] == "request_scoped"]
    accepted_quality_scores = [float(item.get("evidence_quality_score") or 0) for item in accepted_items]
    active_saved_items = [item for item in accepted_items if item["origin"] == "saved_library"]
    criteria_covered = sorted({item["criterion"] for item in accepted_items})
    criteria_still_insufficient = [criterion for criterion in QUALITATIVE_CORE_CRITERIA if criterion not in criteria_covered]
    if not items:
        missing_data.update(QUALITATIVE_CORE_CRITERIA)
    source_status = build_source_status(
        {
            "source_type": "derived",
            "provider": "user_provided_qualitative_evidence",
            "source_date": latest_source_date or "",
            "fallback_used": False,
            "limitations": ["User-provided qualitative evidence is not independently verified by the system."],
            "missing_data": sorted(missing_data),
        },
        freshness_window="user_provided_context",
    ).model_dump(mode="json")
    summary = (
        f"{len(accepted_items)} user-provided qualitative evidence item(s) accepted for preliminary review from saved library and request-scoped inputs."
        if items
        else "No structured qualitative evidence was provided."
    )
    return {
        "ticker": ticker,
        "evidence_count": len(accepted_items),
        "accepted_evidence_count": len(accepted_items),
        "rejected_evidence_count": len(items) - len(accepted_items),
        "saved_evidence_count": len(saved_items),
        "request_evidence_count": len(request_items),
        "deduplicated_count": deduplicated_count,
        "reviewed_count": sum(1 for item in saved_items if item.get("review_status") == "reviewed"),
        "unreviewed_count": sum(1 for item in saved_items if item.get("review_status") == "unreviewed"),
        "reviewed_active_count": sum(1 for item in active_saved_items if item.get("review_status") == "reviewed"),
        "unreviewed_active_count": sum(1 for item in active_saved_items if item.get("review_status") == "unreviewed"),
        "archived_or_rejected_ignored_count": ignored_count,
        "quality_score_average": round(sum(accepted_quality_scores) / len(accepted_quality_scores), 1) if accepted_quality_scores else None,
        "high_quality_count": sum(1 for item in accepted_items if item.get("evidence_quality_label") == "high"),
        "medium_quality_count": sum(1 for item in accepted_items if item.get("evidence_quality_label") == "medium"),
        "low_quality_count": sum(1 for item in accepted_items if item.get("evidence_quality_label") == "low"),
        "incomplete_count": sum(1 for item in items if item.get("evidence_quality_label") == "incomplete"),
        "stale_count": sum(1 for item in accepted_items if item.get("is_stale")),
        "review_due_count": sum(1 for item in accepted_items if item.get("next_review_due_at")),
        "criteria_covered": criteria_covered,
        "criteria_still_insufficient": criteria_still_insufficient,
        "source_quality_summary": summary,
        "evidence_items": items,
        "source_status": source_status,
        "limitations": ["User-provided qualitative evidence is preliminary and requires manual verification."],
        "missing_data": sorted(missing_data),
    }


def _build_comparison_evidence_assessment(ticker: str, qualitative_assessment: dict) -> dict:
    comparison_items = [
        item
        for item in qualitative_assessment.get("evidence_items", [])
        if _is_comparison_evidence_item(item)
    ]
    accepted_items = [item for item in comparison_items if item.get("accepted")]
    peer_companies = sorted(
        {
            str(peer).strip().upper()
            for item in accepted_items
            for peer in (item.get("comparison_context") or {}).get("peer_companies", [])
            if str(peer).strip()
        }
    )
    breakdown = {key: 0 for key in ["stronger", "similar", "weaker", "unclear"]}
    missing_data = set()
    output_items = []
    for item in comparison_items:
        context = normalize_comparison_context(item.get("comparison_context"), ticker) or {}
        claimed_advantage = str(context.get("claimed_advantage") or "unclear")
        if claimed_advantage not in breakdown:
            claimed_advantage = "unclear"
        if item.get("accepted"):
            breakdown[claimed_advantage] += 1
        if not context.get("peer_companies"):
            missing_data.add("comparison_peer_companies")
        if not context.get("comparison_period"):
            missing_data.add("comparison_period")
        output_items.append(
            {
                "evidence_id": item.get("evidence_id"),
                "origin": item.get("origin") or "request_scoped",
                "criterion": item.get("criterion") or "unsupported",
                "evidence_type": item.get("evidence_type") or "unsupported",
                "comparison_type": context.get("comparison_type") or "other",
                "peer_companies": context.get("peer_companies") or [],
                "claimed_advantage": claimed_advantage,
                "comparison_summary": context.get("comparison_summary") or item.get("summary") or "",
                "source_basis": context.get("source_basis") or "user_note",
                "review_status": item.get("review_status"),
                "evidence_quality_score": item.get("evidence_quality_score", 0),
                "evidence_quality_label": item.get("evidence_quality_label", "incomplete"),
                "is_stale": bool(item.get("is_stale")),
                "accepted": bool(item.get("accepted")),
                "limitations": sorted(set([*(item.get("limitations") or []), *((context.get("limitations") or []) if isinstance(context, dict) else [])])),
            }
        )
    latest_source_date = max(
        [str(item.get("source_date")) for item in accepted_items if item.get("source_date")],
        default="",
    )
    source_status = build_source_status(
        {
            "source_type": "derived",
            "provider": "user_provided_comparison_evidence",
            "source_date": latest_source_date,
            "fallback_used": False,
            "limitations": ["User-provided comparison evidence is not independently verified."],
            "missing_data": sorted(missing_data),
        },
        freshness_window="user_provided_context",
    ).model_dump(mode="json")
    limitations = [
        "Comparison evidence is user-provided and not independently verified.",
        "Peer comparison claims require manual validation against current sources.",
    ]
    if any(item.get("is_stale") for item in accepted_items):
        limitations.append("Stale comparison evidence is capped and requires refresh.")
    return {
        "ticker": ticker,
        "comparison_evidence_count": len(comparison_items),
        "accepted_comparison_count": len(accepted_items),
        "reviewed_comparison_count": sum(1 for item in accepted_items if item.get("review_status") == "reviewed"),
        "stale_comparison_count": sum(1 for item in accepted_items if item.get("is_stale")),
        "criteria_supported": sorted({str(item.get("criterion")) for item in accepted_items if item.get("criterion")}),
        "peer_companies_mentioned": peer_companies,
        "claimed_advantage_breakdown": breakdown,
        "source_quality": "user_provided" if accepted_items else "insufficient",
        "limitations": limitations if comparison_items else ["No structured competitor or comparison evidence was provided."],
        "missing_data": sorted(missing_data),
        "items": output_items,
        "source_status": source_status,
    }


def _sec_available(sec_facts: dict) -> bool:
    return _status_dict(sec_facts.get("source_status")).get("source_type") in {"live", "cached_live"} and any(sec_facts.get("facts", {}).values())


def _sec_metric(sec_facts: dict, metric: str):
    return (sec_facts.get("derived_metrics") or {}).get(metric)


def _sec_fact_value(sec_facts: dict, fact_name: str):
    fact = (sec_facts.get("facts") or {}).get(fact_name)
    return fact.get("value") if isinstance(fact, dict) else None


def _sec_source_quality(sec_facts: dict, fallback: str) -> str:
    if _sec_available(sec_facts):
        return "filing_backed"
    return fallback


def _build_fundamentals_cross_check(sec_facts: dict, yfinance_fundamentals: dict) -> dict:
    sec_status = _status_dict(sec_facts.get("source_status"))
    yf_status = _status_dict(yfinance_fundamentals.get("source_status"))
    limitations = [
        "SEC Companyfacts complements yfinance and does not replace provider-normalized MVP fundamentals.",
        "Provider normalization differences are expected; discrepancies are review signals.",
    ]
    invalid = sec_facts.get("invalid_derived_metrics") or {}
    metrics = [
        ("revenue_ttm", yfinance_fundamentals.get("revenue_ttm"), _sec_fact_value(sec_facts, "revenue"), "revenue"),
        ("gross_margin_pct", yfinance_fundamentals.get("gross_margin_pct"), _sec_metric(sec_facts, "gross_margin_pct"), "gross_margin_pct"),
        ("operating_margin_pct", yfinance_fundamentals.get("operating_margin_pct"), _sec_metric(sec_facts, "operating_margin_pct"), "operating_margin_pct"),
        ("free_cash_flow_ttm", yfinance_fundamentals.get("free_cash_flow_ttm"), _sec_metric(sec_facts, "fcf"), "fcf"),
        ("cash_and_equivalents", yfinance_fundamentals.get("cash_and_equivalents"), _sec_fact_value(sec_facts, "cash_and_equivalents"), "cash_and_equivalents"),
        ("total_debt", yfinance_fundamentals.get("total_debt"), _sec_fact_value(sec_facts, "total_debt"), "total_debt"),
        ("shares_outstanding", yfinance_fundamentals.get("shares_outstanding"), _sec_fact_value(sec_facts, "shares_outstanding"), "shares_outstanding"),
    ]
    checked = []
    for name, yf_value, sec_value, sec_metric_name in metrics:
        difference = None
        if sec_metric_name in invalid:
            status = "sec_invalid_period_alignment"
        elif _metric_available(yf_value) and _metric_available(sec_value) and yf_value != 0:
            difference = round(abs(float(sec_value) - float(yf_value)) / abs(float(yf_value)) * 100, 4)
            status = "consistent" if difference <= 5 else "moderate_difference" if difference <= 15 else "divergent"
        elif not _metric_available(sec_value) and not _metric_available(yf_value):
            status = "insufficient"
        elif not _metric_available(sec_value):
            status = "sec_missing"
        else:
            status = "yfinance_missing"
        checked.append(
            {
                "name": name,
                "yfinance_value": yf_value if _metric_available(yf_value) else None,
                "sec_value": sec_value if _metric_available(sec_value) else None,
                "difference_pct": difference,
                "status": status,
                "source_quality": "filing_backed" if status in {"consistent", "moderate_difference", "divergent"} else "provider_backed" if status in {"sec_missing", "sec_invalid_period_alignment"} and _metric_available(yf_value) else "insufficient",
            }
        )
    comparable = [item for item in checked if item["status"] in {"consistent", "moderate_difference", "divergent"}]
    divergent = [item for item in comparable if item["status"] == "divergent"]
    consistent = [item for item in comparable if item["status"] == "consistent"]
    consistent_names = {item["name"] for item in consistent}
    divergent_names = {item["name"] for item in divergent}
    parser_period_alignment_valid = not bool(invalid)
    provider_normalization_discrepancies = bool(divergent) and parser_period_alignment_valid
    revenue_and_margin_consistent = {"revenue_ttm", "gross_margin_pct"}.issubset(consistent_names)
    divergent_category = "none"
    if invalid:
        divergent_category = "invalid_sec_period_alignment"
    elif divergent_names & {"free_cash_flow_ttm"}:
        divergent_category = "cash_flow_provider_normalization"
    elif divergent_names & {"cash_and_equivalents", "total_debt"}:
        divergent_category = "balance_sheet_provider_normalization"
    elif divergent:
        divergent_category = "provider_normalization_or_classification"
    if not comparable:
        agreement = "insufficient"
        summary = "SEC/yfinance cross-check has insufficient comparable filing-backed metrics."
    elif divergent:
        agreement = "low"
        if revenue_and_margin_consistent:
            summary = "SEC and yfinance agree on revenue and gross margin; some balance-sheet or cash-flow fields differ due to provider normalization or statement classification differences."
        else:
            summary = "SEC/yfinance cross-check found material comparable metric differences that need provider-normalization review."
    elif len(consistent) >= max(1, len(comparable) - 1):
        agreement = "high"
        summary = "SEC/yfinance cross-check is directionally consistent for comparable metrics."
    else:
        agreement = "moderate"
        summary = "SEC/yfinance cross-check is partly consistent with some provider-period differences."
    if sec_status.get("source_type") in {"live", "cached_live"} and yf_status.get("source_type") in {"live", "cached_live", "derived"}:
        limitations.append("SEC latest FY values may be compared with yfinance TTM/provider-normalized values; period mismatch can create differences.")
    if invalid:
        limitations.append("SEC Companyfacts is available, but some derived metrics require period-alignment review.")
    review_metrics = []
    for item in checked:
        if item["status"] not in {"divergent", "moderate_difference", "sec_invalid_period_alignment"}:
            continue
        metric = item["name"]
        if metric in {"free_cash_flow_ttm"}:
            why = "Cash-flow definitions can differ across filings, provider normalization, and period selection."
        elif metric in {"cash_and_equivalents", "total_debt"}:
            why = "Balance-sheet classification can vary by concept mapping and provider normalization."
        elif metric in {"revenue_ttm", "gross_margin_pct", "operating_margin_pct"}:
            why = "Core operating metrics affect financial-quality validation and should be checked by period."
        else:
            why = "The metric can change validation confidence when provider values differ materially."
        review_metrics.append(
            {
                "metric": metric,
                "sec_value": item["sec_value"],
                "yfinance_value": item["yfinance_value"],
                "difference_pct": item["difference_pct"],
                "status": item["status"],
                "why_it_matters": why,
                "review_hint": "Compare the latest SEC filing period, yfinance provider-normalized period, and any concept mapping notes before increasing validation confidence.",
            }
        )
    likely_reasons = []
    if divergent or invalid:
        likely_reasons.extend([
            "SEC Companyfacts is filing-backed, but issuer concept coverage and period alignment can vary.",
            "Yfinance is a provider-normalized research reference and may use TTM or adjusted fields.",
            "Statement classification differences can affect cash, debt, and free-cash-flow comparisons.",
        ])
    elif comparable:
        likely_reasons.append("Comparable metrics are directionally aligned under available fields.")
    else:
        likely_reasons.append("Comparable metrics are missing from one or both providers.")
    manual_priority = "high" if divergent or invalid else "medium" if comparable and agreement == "moderate" else "low"
    confidence_impact = (
        "Material discrepancies cap confidence until reviewed."
        if manual_priority == "high"
        else "Cross-check is usable as preliminary validation, with normal provider-period caveats."
        if comparable
        else "Insufficient comparable metrics limit filing-backed confirmation."
    )
    source_status = build_source_status(
        {
            "source_type": "derived",
            "provider": "mixed_SEC_companyfacts_and_yfinance",
            "source_date": max([item for item in [sec_status.get("source_date"), yf_status.get("source_date")] if item], default=""),
            "fallback_used": bool(sec_status.get("fallback_used") or yf_status.get("fallback_used")),
            "fallback_reason": sec_status.get("fallback_reason") or yf_status.get("fallback_reason"),
            "limitations": limitations,
            "missing_data": sorted(set([*sec_facts.get("missing_data", []), *yfinance_fundamentals.get("missing_data", [])])),
        }
    ).model_dump(mode="json")
    return {
        "provider": "mixed_SEC_companyfacts_and_yfinance",
        "source_type": "derived",
        "summary": summary,
        "agreement_level": agreement,
        "divergence_reason": divergent_category,
        "parser_period_alignment_valid": parser_period_alignment_valid,
        "provider_normalization_discrepancies": provider_normalization_discrepancies,
        "checked_metrics": checked,
        "confidence_adjustment": {
            "boost_applied": agreement in {"high", "moderate"} and bool(comparable),
            "penalty_applied": agreement == "low",
            "reason": summary,
        },
        "explanation": {
            "agreement_level": agreement,
            "plain_language_summary": summary,
            "likely_reasons": likely_reasons,
            "metrics_requiring_review": review_metrics,
            "confidence_impact": confidence_impact,
            "manual_check_priority": manual_priority,
        },
        "source_status": source_status,
        "limitations": limitations,
        "missing_data": source_status["missing_data"],
    }


def _score_status(score: float | None) -> str:
    if score is None:
        return "insufficient"
    if score >= 65:
        return "supportive"
    if score >= 45:
        return "neutral"
    return "caution"


def _metric_available(value) -> bool:
    return isinstance(value, (int, float)) and value is not None


def _safe_ratio(numerator: float | None, denominator: float | None, missing_data: list[str], missing_label: str) -> float | None:
    if numerator is None or denominator is None:
        missing_data.append(missing_label)
        return None
    if denominator <= 0:
        missing_data.append(f"{missing_label}: denominator missing or non-positive")
        return None
    return round(numerator / denominator, 4)


def _financial_quality_score(financials: dict) -> tuple[float, str, float]:
    status = _status_dict(financials.get("source_status"))
    live_like = status.get("source_type") in {"live", "cached_live", "derived"}
    required = [
        financials.get("revenue_yoy_growth_pct"),
        financials.get("gross_margin_pct"),
        financials.get("free_cash_flow_ttm"),
        financials.get("cash_and_equivalents"),
        financials.get("total_debt"),
    ]
    available = sum(1 for item in required if _metric_available(item))
    if not live_like or available < 3:
        return 50, "neutral", 0.45 if not live_like else 0.58
    score = 50
    if (financials.get("revenue_yoy_growth_pct") or 0) >= 10:
        score += 12
    if (financials.get("gross_margin_pct") or 0) >= 40:
        score += 10
    if (financials.get("free_cash_flow_ttm") or 0) > 0:
        score += 10
    if (financials.get("net_cash_or_debt") or 0) >= 0:
        score += 8
    if (financials.get("debt_to_equity") or 0) and (financials.get("debt_to_equity") or 0) > 150:
        score -= 8
    score = round(max(0, min(100, score)), 2)
    label = "favorable_research_environment" if score >= 70 else "neutral"
    confidence = round(min(0.78, 0.52 + available * 0.05), 2)
    return score, label, confidence


def _build_financial_quality_score(financials: dict) -> ScoreObject:
    status = _status_dict(financials.get("source_status"))
    score, label, confidence = _financial_quality_score(financials)
    return ScoreObject(
        name="financial_quality_score",
        score=score,
        label=label,
        raw_data=financials,
        derived_metrics={
            "revenue_yoy_growth_pct": financials.get("revenue_yoy_growth_pct"),
            "revenue_3y_cagr_pct": financials.get("revenue_3y_cagr_pct"),
            "gross_margin_pct": financials.get("gross_margin_pct"),
            "free_cash_flow_margin_pct": financials.get("free_cash_flow_margin_pct"),
            "net_cash_or_debt": financials.get("net_cash_or_debt"),
            "available_core_metric_count": sum(
                1
                for item in [
                    financials.get("revenue_yoy_growth_pct"),
                    financials.get("gross_margin_pct"),
                    financials.get("free_cash_flow_ttm"),
                    financials.get("cash_and_equivalents"),
                    financials.get("total_debt"),
                ]
                if _metric_available(item)
            ),
        },
        benchmark={
            "revenue_growth_supportive_pct": 10,
            "gross_margin_supportive_pct": 40,
            "positive_free_cash_flow_required_for_quality_driver": True,
            "net_cash_supportive": True,
        },
        trend={
            "financial_quality": "available" if status.get("source_type") in {"live", "cached_live", "derived"} else "preliminary",
        },
        source=[status.get("provider") or financials.get("provider") or "unknown"],
        source_date=status.get("source_date") or financials.get("source_date") or "",
        confidence=confidence,
        limitations=financials.get("limitations", []),
        missing_data=financials.get("missing_data", []),
        source_status=build_source_status(financials).model_copy(update=status) if status else build_source_status(financials),
    )


def _build_valuation_context(profile: dict, financials: dict) -> ScoreObject:
    missing_data: list[str] = []
    market_cap = profile.get("market_cap")
    enterprise_value = profile.get("enterprise_value")
    revenue_ttm = financials.get("revenue_ttm")
    free_cash_flow_ttm = financials.get("free_cash_flow_ttm")
    price_to_sales = _safe_ratio(market_cap, revenue_ttm, missing_data, "market_cap or revenue_ttm unavailable for price_to_sales_ttm")
    ev_to_sales = _safe_ratio(enterprise_value, revenue_ttm, missing_data, "enterprise_value or revenue_ttm unavailable for ev_to_sales_ttm")
    price_to_fcf = _safe_ratio(market_cap, free_cash_flow_ttm, missing_data, "market_cap or free_cash_flow_ttm unavailable for price_to_free_cash_flow_ttm")
    ev_to_fcf = _safe_ratio(enterprise_value, free_cash_flow_ttm, missing_data, "enterprise_value or free_cash_flow_ttm unavailable for ev_to_free_cash_flow_ttm")
    multiples = [value for value in [price_to_sales, ev_to_sales, price_to_fcf, ev_to_fcf] if value is not None]
    if not multiples:
        label = "insufficient"
        score = 50
        summary = "Valuation context is insufficient because live market value and fundamental denominators are incomplete."
    elif (price_to_sales is not None and price_to_sales >= 15) or (ev_to_sales is not None and ev_to_sales >= 18) or (price_to_fcf is not None and price_to_fcf >= 60):
        label = "elevated"
        score = 35
        summary = "Valuation context is elevated as a research risk flag based on available live or cached inputs."
    elif (price_to_sales is not None and price_to_sales >= 8) or (ev_to_sales is not None and ev_to_sales >= 10):
        label = "moderate"
        score = 55
        summary = "Valuation context is moderate based on available live or cached inputs."
    else:
        label = "low"
        score = 70
        summary = "Valuation context is not elevated based on available live or cached inputs."
    profile_status = _status_dict(profile.get("source_status"))
    fundamentals_status = _status_dict(financials.get("source_status"))
    source_types = {profile_status.get("source_type"), fundamentals_status.get("source_type")}
    if source_types <= {"live", "cached_live"}:
        source_type = "derived"
        provider = "derived_from_yfinance"
    elif any(item in {"live", "cached_live", "derived"} for item in source_types):
        source_type = "derived"
        provider = "derived_from_yfinance"
    else:
        source_type = "mock"
        provider = "mock"
    source_date = max([item for item in [profile_status.get("source_date"), fundamentals_status.get("source_date")] if item], default="")
    limitations = sorted(set([*profile.get("limitations", []), *financials.get("limitations", []), "Valuation context is risk context only and is not an investment instruction."]))
    missing = sorted(set([*missing_data, *profile.get("missing_data", []), *financials.get("missing_data", [])]))
    source_status = build_source_status(
        {
            "source_type": source_type,
            "provider": provider,
            "source_date": source_date,
            "limitations": limitations,
            "missing_data": missing,
            "fallback_used": bool(profile_status.get("fallback_used") or fundamentals_status.get("fallback_used")),
            "fallback_reason": profile_status.get("fallback_reason") or fundamentals_status.get("fallback_reason"),
        }
    )
    threshold_context = {
        "price_to_sales_ttm": "Elevated proxy threshold >= 15; moderate context begins around 8.",
        "ev_to_sales_ttm": "Elevated proxy threshold >= 18; moderate context begins around 10.",
        "price_to_free_cash_flow_ttm": "Elevated proxy threshold >= 60 when free cash flow is positive and comparable.",
        "ev_to_free_cash_flow_ttm": "Supplemental cash-flow multiple; unavailable or negative FCF limits interpretation.",
    }
    valuation_explanation = {
        "valuation_risk_label": label if label in {"elevated", "moderate", "low"} else "unavailable",
        "plain_language_summary": (
            "Valuation risk appears elevated under available proxy metrics; this is research context only."
            if label == "elevated"
            else summary
        ),
        "metrics_used": [
            {
                "name": "price_to_sales_ttm",
                "value": price_to_sales,
                "threshold_context": threshold_context["price_to_sales_ttm"],
                "limitation": "Uses market cap and revenue TTM inputs; provider timing can differ.",
            },
            {
                "name": "ev_to_sales_ttm",
                "value": ev_to_sales,
                "threshold_context": threshold_context["ev_to_sales_ttm"],
                "limitation": "Uses enterprise value and revenue TTM inputs; debt and cash classification can differ.",
            },
            {
                "name": "price_to_free_cash_flow_ttm",
                "value": price_to_fcf,
                "threshold_context": threshold_context["price_to_free_cash_flow_ttm"],
                "limitation": "Free cash flow can vary by provider normalization and period alignment.",
            },
            {
                "name": "ev_to_free_cash_flow_ttm",
                "value": ev_to_fcf,
                "threshold_context": threshold_context["ev_to_free_cash_flow_ttm"],
                "limitation": "Supplemental context only when FCF is available and positive.",
            },
        ],
        "why_it_matters": "Valuation context helps identify whether validation confidence should be tempered by price-to-fundamental proxy risk.",
        "manual_review_hint": "Compare current valuation proxies with sector peers, growth durability, margins, and latest filing-backed fundamentals before increasing validation confidence.",
    }
    return ScoreObject(
        name="valuation_context_score",
        score=score,
        label=label,
        raw_data={
            "ticker": profile.get("ticker") or financials.get("ticker"),
            "market_cap": market_cap,
            "enterprise_value": enterprise_value,
            "price_to_sales_ttm": price_to_sales,
            "ev_to_sales_ttm": ev_to_sales,
            "price_to_free_cash_flow_ttm": price_to_fcf,
            "ev_to_free_cash_flow_ttm": ev_to_fcf,
            "gross_margin_pct": financials.get("gross_margin_pct"),
            "revenue_growth_yoy_pct": financials.get("revenue_yoy_growth_pct"),
            "valuation_risk_label": label,
            "valuation_summary": summary,
            "explanation": valuation_explanation,
            "source_status": source_status.model_dump(mode="json"),
            "limitations": limitations,
            "missing_data": missing,
        },
        derived_metrics={
            "valuation_risk_label": label,
            "available_multiple_count": len(multiples),
            "valuation_summary": summary,
        },
        benchmark={
            "price_to_sales_elevated": 15,
            "ev_to_sales_elevated": 18,
            "price_to_free_cash_flow_elevated": 60,
        },
        trend={"valuation_pressure": "elevated" if label == "elevated" else "not_elevated" if label in {"low", "moderate"} else "insufficient"},
        source=[provider],
        source_date=source_date,
        confidence=0.68 if multiples else 0.42,
        limitations=limitations,
        missing_data=missing,
        source_status=source_status,
        explanation=valuation_explanation,
    )


JANE_QUALITY_PRINCIPLES = [
    "Market Monopoly / Moat",
    "Mega Trend Fit",
    "Visionary Founder / CEO",
    "Disruptive Innovation",
    "Scalability",
    "Network Effect",
    "Continuous R&D",
]


def _metric_evidence(label: str, value) -> str:
    return f"{label}: {value if value is not None else 'unavailable'}"


def _quality_source(financial_status: dict) -> str:
    provider = str(financial_status.get("provider") or "")
    if "SEC_companyfacts" in provider or "sec_companyfacts" in provider:
        return "derived_from_mixed_sources"
    if "SEC" in provider:
        return "filing_backed"
    source_type = financial_status.get("source_type")
    if source_type == "live":
        return "derived_live"
    if source_type == "cached_live":
        return "cached_live"
    if source_type == "derived":
        return "derived_live"
    if source_type == "mock":
        return "mock_only"
    return "insufficient"


def _merge_financials_with_sec(yfinance_fundamentals: dict, sec_facts: dict, cross_check: dict) -> dict:
    merged = dict(yfinance_fundamentals)
    if not _sec_available(sec_facts):
        merged["sec_source_basis"] = "insufficient"
        return merged
    mapping = {
        "revenue_yoy_growth_pct": ("derived_metrics", "revenue_yoy_growth_pct"),
        "revenue_3y_cagr_pct": ("derived_metrics", "revenue_3y_cagr_pct"),
        "gross_margin_pct": ("derived_metrics", "gross_margin_pct"),
        "operating_margin_pct": ("derived_metrics", "operating_margin_pct"),
        "net_income_margin_pct": ("derived_metrics", "net_income_margin_pct"),
        "operating_cash_flow_ttm": ("facts", "operating_cash_flow"),
        "capex_ttm": ("facts", "capex"),
        "free_cash_flow_ttm": ("derived_metrics", "fcf"),
        "free_cash_flow_margin_pct": ("derived_metrics", "fcf_margin_pct"),
        "cash_and_equivalents": ("facts", "cash_and_equivalents"),
        "total_debt": ("facts", "total_debt"),
        "net_cash_or_debt": ("derived_metrics", "net_cash_or_debt"),
        "debt_to_equity": ("derived_metrics", "debt_to_equity"),
        "accounts_receivable": ("facts", "accounts_receivable"),
        "receivables_to_revenue_pct": ("derived_metrics", "receivables_to_revenue_pct"),
        "inventory": ("facts", "inventory"),
        "inventory_to_revenue_pct": ("derived_metrics", "inventory_to_revenue_pct"),
        "shares_outstanding": ("facts", "shares_outstanding"),
        "share_dilution_3y_pct": ("derived_metrics", "share_dilution_3y_pct"),
    }
    filing_backed_fields = []
    for target, (section, key) in mapping.items():
        value = (sec_facts.get(section) or {}).get(key)
        if section == "facts" and isinstance(value, dict):
            value = value.get("value")
        if _metric_available(value):
            merged[target] = value
            filing_backed_fields.append(target)
    sec_status = _status_dict(sec_facts.get("source_status"))
    yf_status = _status_dict(yfinance_fundamentals.get("source_status"))
    limitations = sorted(set([
        *yfinance_fundamentals.get("limitations", []),
        *sec_facts.get("limitations", []),
        *cross_check.get("limitations", []),
    ]))
    missing = sorted(set([*yfinance_fundamentals.get("missing_data", []), *sec_facts.get("missing_data", [])]))
    source_status = build_source_status(
        {
            "source_type": "derived",
            "provider": "derived_from_SEC_companyfacts_and_yfinance",
            "source_date": max([item for item in [sec_status.get("source_date"), yf_status.get("source_date")] if item], default=""),
            "limitations": limitations,
            "missing_data": missing,
            "fallback_used": bool(sec_status.get("fallback_used") or yf_status.get("fallback_used")),
            "fallback_reason": sec_status.get("fallback_reason") or yf_status.get("fallback_reason"),
        }
    ).model_dump(mode="json")
    merged.update(
        {
            "source_type": "derived",
            "provider": "derived_from_SEC_companyfacts_and_yfinance",
            "source": ["SEC EDGAR companyfacts", "yfinance"],
            "source_date": source_status.get("source_date", ""),
            "source_status": source_status,
            "sec_source_basis": "derived_from_mixed_sources",
            "filing_backed_fields": filing_backed_fields,
            "fundamentals_cross_check_agreement": cross_check.get("agreement_level"),
            "limitations": limitations,
            "missing_data": missing,
        }
    )
    return merged


def _criterion(
    name: str,
    display_name: str,
    *,
    score: float | None,
    status: str,
    source_quality: str,
    affects_score: bool,
    evidence_strength: str = "none",
    verification_level: str = "insufficient",
    evidence: list[str] | None = None,
    limitations: list[str] | None = None,
    missing_data: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "display_name": display_name,
        "score": None if score is None else round(max(0, min(100, score)), 2),
        "max_score": 10,
        "status": status,
        "source_quality": source_quality,
        "affects_score": affects_score,
        "evidence_strength": evidence_strength,
        "verification_level": verification_level,
        "evidence": evidence or [],
        "limitations": limitations or [],
        "missing_data": missing_data or [],
    }


def _financial_metric_status(score: float | None) -> str:
    if score is None:
        return "insufficient"
    if score >= 70:
        return "supportive"
    if score >= 45:
        return "neutral"
    return "caution"


def _build_jane_company_quality(financial_quality: ScoreObject, research_context: dict, qualitative_assessment: dict | None = None) -> JaneCompanyQuality:
    financials = financial_quality.raw_data
    financial_status = _status_dict(financial_quality.source_status)
    source_quality = _quality_source(financial_status)
    yfinance_limitations = list(financial_quality.limitations or [])
    financial_source_usable = source_quality in {"derived_live", "cached_live", "filing_backed", "derived_from_mixed_sources"}
    if financial_source_usable:
        yfinance_limitations = sorted(set([*yfinance_limitations, "Yfinance fundamentals may combine company-reported values with provider-normalized fields."]))

    revenue_growth = financials.get("revenue_yoy_growth_pct")
    revenue_cagr = financials.get("revenue_3y_cagr_pct")
    gross_margin = financials.get("gross_margin_pct")
    operating_margin = financials.get("operating_margin_pct")
    fcf_margin = financials.get("free_cash_flow_margin_pct")
    fcf = financials.get("free_cash_flow_ttm")
    net_cash = financials.get("net_cash_or_debt")
    debt_to_equity = financials.get("debt_to_equity")
    cash = financials.get("cash_and_equivalents")
    debt = financials.get("total_debt")
    rd_to_revenue = financials.get("rd_to_revenue_pct")
    rd_expense = financials.get("rd_expense_ttm")

    scalability_available = sum(_metric_available(item) for item in [revenue_growth, revenue_cagr, gross_margin, operating_margin, fcf_margin])
    scalability_score = None
    if financial_source_usable and scalability_available >= 3:
        scalability_score = 45
        if (revenue_growth or 0) >= 15 or (revenue_cagr or 0) >= 15:
            scalability_score += 20
        if (gross_margin or 0) >= 45:
            scalability_score += 12
        if (operating_margin or 0) >= 20:
            scalability_score += 12
        if (fcf_margin or 0) >= 10:
            scalability_score += 11
        if (revenue_growth or 0) > 10 and (operating_margin or 0) < 5:
            scalability_score -= 20
    financial_statement_score = None
    if financial_source_usable and sum(_metric_available(item) for item in [revenue_growth, revenue_cagr, gross_margin, operating_margin, fcf]) >= 3:
        financial_statement_score = 45
        if (revenue_growth or 0) > 10 or (revenue_cagr or 0) > 10:
            financial_statement_score += 20
        if (gross_margin or 0) >= 40:
            financial_statement_score += 10
        if (operating_margin or 0) >= 15:
            financial_statement_score += 10
        if (fcf or 0) > 0:
            financial_statement_score += 15
    balance_sheet_score = None
    if financial_source_usable and sum(_metric_available(item) for item in [cash, debt, net_cash, debt_to_equity]) >= 2:
        balance_sheet_score = 50
        if (net_cash or 0) >= 0:
            balance_sheet_score += 25
        if debt_to_equity is not None and debt_to_equity <= 80:
            balance_sheet_score += 15
        if debt_to_equity is not None and debt_to_equity > 150:
            balance_sheet_score -= 20
    cash_flow_score = None
    cash_flow_missing = []
    if financials.get("operating_cash_flow_ttm") is None:
        cash_flow_missing.append("operating cash flow detail")
    if financials.get("capex_ttm") is None:
        cash_flow_missing.append("capex detail")
    if financial_source_usable and _metric_available(fcf):
        cash_flow_score = 50
        if (fcf or 0) > 0:
            cash_flow_score += 25
        if (fcf_margin or 0) >= 10:
            cash_flow_score += 15
        if not cash_flow_missing:
            cash_flow_score += 10

    rd_score = None
    rd_status = "insufficient"
    rd_source_quality = "insufficient"
    if financial_source_usable and (_metric_available(rd_expense) or _metric_available(rd_to_revenue)):
        rd_source_quality = source_quality
        rd_score = 55
        if (rd_to_revenue or 0) >= 8:
            rd_score += 25
        elif (rd_to_revenue or 0) >= 3:
            rd_score += 10
        rd_status = _financial_metric_status(rd_score)

    theme = str(research_context.get("theme") or "").strip()
    qualitative_by_criterion = _qualitative_evidence_by_criterion(qualitative_assessment)
    monopoly_criterion = _build_user_qualitative_criterion(
        "monopoly_power",
        "Market Monopoly / Moat",
        qualitative_by_criterion.get("monopoly_power", []),
        default_missing=["market share evidence", "patent or moat evidence"],
    )
    founder_criterion = _build_user_qualitative_criterion(
        "visionary_founder_ceo",
        "Visionary Founder / CEO",
        qualitative_by_criterion.get("visionary_founder_ceo", []),
        default_missing=["CEO/founder live evidence", "management tenure evidence"],
    )
    disruption_criterion = _build_user_qualitative_criterion(
        "disruptive_innovation",
        "Disruptive Innovation",
        qualitative_by_criterion.get("disruptive_innovation", []),
        default_missing=["product disruption evidence", "patent evidence", "technology differentiation evidence"],
    )
    network_criterion = _build_user_qualitative_criterion(
        "network_effect",
        "Network Effect",
        qualitative_by_criterion.get("network_effect", []),
        default_missing=["network effect evidence", "ecosystem usage evidence"],
    )
    trend_criterion = _build_user_qualitative_criterion(
        "mega_trend_fit",
        "Mega Trend Fit",
        qualitative_by_criterion.get("mega_trend_fit", []),
        default_missing=["independently verified trend evidence"],
    )
    rd_user_criterion = _build_user_qualitative_criterion(
        "continuous_r_and_d",
        "Continuous R&D",
        qualitative_by_criterion.get("continuous_r_and_d", []),
        default_missing=["R&D expense", "R&D as percentage of revenue"],
    )
    criteria = [
        monopoly_criterion or _criterion(
            "monopoly_power",
            "Market Monopoly / Moat",
            score=None,
            status="insufficient",
            source_quality="insufficient",
            affects_score=False,
            evidence=([f"User context theme: {theme}"] if "moat" in theme.lower() else []),
            missing_data=["market share evidence", "patent or moat evidence"],
        ),
        trend_criterion or _criterion(
            "mega_trend_fit",
            "Mega Trend Fit",
            score=None,
            status="neutral" if theme else "insufficient",
            source_quality="user_context" if theme else "insufficient",
            affects_score=False,
            evidence=([f"User-provided theme context: {theme}"] if theme else []),
            limitations=["User-provided theme is research context and is not independently verified evidence."],
            missing_data=[] if theme else ["independently verified trend evidence"],
        ),
        founder_criterion or _criterion(
            "visionary_founder_ceo",
            "Visionary Founder / CEO",
            score=None,
            status="insufficient",
            source_quality="insufficient",
            affects_score=False,
            missing_data=["CEO/founder live evidence", "management tenure evidence"],
        ),
        disruption_criterion or _criterion(
            "disruptive_innovation",
            "Disruptive Innovation",
            score=None,
            status="insufficient",
            source_quality="insufficient",
            affects_score=False,
            missing_data=["product disruption evidence", "patent evidence", "technology differentiation evidence"],
        ),
        _criterion(
            "scalability",
            "Scalability",
            score=scalability_score,
            status=_financial_metric_status(scalability_score),
            source_quality=source_quality if scalability_score is not None else "insufficient",
            affects_score=scalability_score is not None,
            evidence_strength="strong" if scalability_score and scalability_score >= 75 else "moderate" if scalability_score is not None else "none",
            verification_level="filing_backed" if source_quality == "filing_backed" else "derived_live" if scalability_score is not None else "insufficient",
            evidence=[
                _metric_evidence("Revenue YoY growth pct", revenue_growth),
                _metric_evidence("Revenue 3Y CAGR pct", revenue_cagr),
                _metric_evidence("Gross margin pct", gross_margin),
                _metric_evidence("Operating margin pct", operating_margin),
                _metric_evidence("Free cash flow margin pct", fcf_margin),
            ],
            limitations=yfinance_limitations,
            missing_data=[] if scalability_score is not None else ["revenue growth, margin, and free cash flow margin metrics"],
        ),
        network_criterion or _criterion(
            "network_effect",
            "Network Effect",
            score=None,
            status="insufficient",
            source_quality="insufficient",
            affects_score=False,
            missing_data=["network effect evidence", "ecosystem usage evidence"],
        ),
        rd_user_criterion if rd_score is None and rd_user_criterion else _criterion(
            "continuous_r_and_d",
            "Continuous R&D",
            score=rd_score,
            status=rd_status,
            source_quality=rd_source_quality,
            affects_score=rd_score is not None,
            evidence_strength="moderate" if rd_score is not None else "none",
            verification_level="filing_backed" if rd_source_quality == "filing_backed" else "derived_live" if rd_score is not None else "insufficient",
            evidence=[_metric_evidence("R&D expense TTM", rd_expense), _metric_evidence("R&D as pct of revenue", rd_to_revenue)] if rd_score is not None else [],
            limitations=yfinance_limitations if rd_score is not None else [],
            missing_data=[] if rd_score is not None else ["R&D expense", "R&D as percentage of revenue"],
        ),
        _criterion(
            "financial_statement_quality",
            "Financial Statement Quality",
            score=financial_statement_score,
            status=_financial_metric_status(financial_statement_score),
            source_quality=source_quality if financial_statement_score is not None else "insufficient",
            affects_score=financial_statement_score is not None,
            evidence_strength="strong" if financial_statement_score and financial_statement_score >= 75 else "moderate" if financial_statement_score is not None else "none",
            verification_level="filing_backed" if source_quality == "filing_backed" else "derived_live" if financial_statement_score is not None else "insufficient",
            evidence=[
                _metric_evidence("Revenue YoY growth pct", revenue_growth),
                _metric_evidence("Revenue 3Y CAGR pct", revenue_cagr),
                _metric_evidence("Gross margin pct", gross_margin),
                _metric_evidence("Operating margin pct", operating_margin),
                _metric_evidence("Free cash flow TTM", fcf),
            ],
            limitations=yfinance_limitations,
            missing_data=[] if financial_statement_score is not None else ["revenue growth, margin, and free cash flow metrics"],
        ),
        _criterion(
            "balance_sheet_strength",
            "Balance Sheet Strength",
            score=balance_sheet_score,
            status=_financial_metric_status(balance_sheet_score),
            source_quality=source_quality if balance_sheet_score is not None else "insufficient",
            affects_score=balance_sheet_score is not None,
            evidence_strength="strong" if balance_sheet_score and balance_sheet_score >= 75 else "moderate" if balance_sheet_score is not None else "none",
            verification_level="filing_backed" if source_quality == "filing_backed" else "derived_live" if balance_sheet_score is not None else "insufficient",
            evidence=[
                _metric_evidence("Cash and equivalents", cash),
                _metric_evidence("Total debt", debt),
                _metric_evidence("Net cash or debt", net_cash),
                _metric_evidence("Debt to equity", debt_to_equity),
            ],
            limitations=yfinance_limitations,
            missing_data=[] if balance_sheet_score is not None else ["cash and debt metrics"],
        ),
        _criterion(
            "cash_flow_quality",
            "Cash Flow Quality",
            score=cash_flow_score,
            status=_financial_metric_status(cash_flow_score),
            source_quality=source_quality if cash_flow_score is not None else "insufficient",
            affects_score=cash_flow_score is not None,
            evidence_strength="strong" if cash_flow_score and cash_flow_score >= 75 else "moderate" if cash_flow_score is not None else "none",
            verification_level="filing_backed" if source_quality == "filing_backed" else "derived_live" if cash_flow_score is not None else "insufficient",
            evidence=[
                _metric_evidence("Free cash flow TTM", fcf),
                _metric_evidence("Free cash flow margin pct", fcf_margin),
                _metric_evidence("Operating cash flow TTM", financials.get("operating_cash_flow_ttm")),
                _metric_evidence("CapEx TTM", financials.get("capex_ttm")),
            ],
            limitations=sorted(set([*yfinance_limitations, "Cash-flow quality is conservative when OCF and CapEx detail is unavailable."])),
            missing_data=cash_flow_missing,
        ),
    ]
    affecting = [item for item in criteria if item["affects_score"] and item["score"] is not None]
    score = round(sum(float(item["score"]) for item in affecting) / len(criteria), 2) if affecting else 0
    evidence_count = sum(1 for item in criteria if item["source_quality"] in {"derived_live", "live_backed", "cached_live", "filing_backed", "derived_from_mixed_sources"} and item["affects_score"])
    user_evidence_count = sum(1 for item in criteria if item["source_quality"] == "user_provided" and item["affects_score"])
    insufficient_count = sum(1 for item in criteria if item["status"] == "insufficient")
    confidence = round(min(0.78, 0.25 + evidence_count * 0.08), 2)
    if user_evidence_count:
        confidence = round(min(0.75, max(confidence, 0.45 + min(user_evidence_count, 4) * 0.04)), 2)
    label = "evidence_backed" if evidence_count >= 7 and confidence >= 0.70 else "preliminary" if evidence_count else "insufficient_data"
    if user_evidence_count and evidence_count < 7:
        label = "preliminary"
    missing = sorted({missing for item in criteria for missing in item["missing_data"]})
    quality_limitations = sorted(set(["Qualitative principles require evidence and are marked insufficient when not verifiable.", *yfinance_limitations, *(USER_QUALITATIVE_LIMITATIONS if user_evidence_count else [])]))
    source_status = build_source_status(
        {
            "source_type": "derived" if evidence_count or user_evidence_count else "unknown",
            "provider": "derived_from_SEC_companyfacts_and_yfinance_company_quality" if source_quality == "derived_from_mixed_sources" else "derived_from_yfinance_company_quality" if evidence_count else "user_provided_qualitative_evidence" if user_evidence_count else "insufficient_company_quality_evidence",
            "source_date": financial_status.get("source_date", ""),
            "is_fresh": financial_status.get("is_fresh", False),
            "limitations": quality_limitations,
            "missing_data": missing,
            "fallback_used": financial_status.get("fallback_used", False),
            "fallback_reason": financial_status.get("fallback_reason"),
        }
    )
    return JaneCompanyQuality(
        score=score,
        confidence=confidence,
        label=label,
        criteria=criteria,
        source_status=source_status,
        limitations=source_status.limitations,
        missing_data=missing,
    )


def _signal(name: str, status: str, source_quality: str, evidence: list[str], limitations: list[str], missing_data: list[str]) -> dict:
    return {
        "name": name,
        "status": status,
        "source_quality": source_quality,
        "evidence": evidence,
        "limitations": limitations,
        "missing_data": missing_data,
    }


def _build_financial_statement_signals(financial_quality: ScoreObject) -> FinancialStatementSignals:
    financials = financial_quality.raw_data
    status = _status_dict(financial_quality.source_status)
    live_like = status.get("source_type") in {"live", "cached_live", "derived"}
    filing_fields = set(financials.get("filing_backed_fields") or [])
    default_source_quality = "derived_from_mixed_sources" if filing_fields else "derived_live" if live_like else "insufficient"
    limitations = list(financial_quality.limitations or [])

    def signal_source_quality(relevant_fields: set[str], *, mixed: bool = False) -> str:
        if relevant_fields & filing_fields:
            return "derived_from_mixed_sources" if mixed else "filing_backed"
        if filing_fields and live_like:
            return "yfinance_backed"
        return default_source_quality

    def available_metric(name: str):
        return financials.get(name) if _metric_available(financials.get(name)) else None

    signals = []
    revenue_growth = available_metric("revenue_yoy_growth_pct")
    revenue_cagr = available_metric("revenue_3y_cagr_pct")
    if live_like and (revenue_growth is not None or revenue_cagr is not None):
        status_name = "supportive" if (revenue_growth or 0) >= 10 or (revenue_cagr or 0) >= 10 else "neutral"
        signal_quality = signal_source_quality({"revenue_yoy_growth_pct", "revenue_3y_cagr_pct"})
        signals.append(_signal("revenue_growth_quality", status_name, signal_quality, [_metric_evidence("Revenue YoY growth pct", revenue_growth), _metric_evidence("Revenue 3Y CAGR pct", revenue_cagr)], limitations, []))
    else:
        signals.append(_signal("revenue_growth_quality", "insufficient", "insufficient", [], limitations, ["revenue_yoy_growth_pct", "revenue_3y_cagr_pct"]))

    operating_margin = available_metric("operating_margin_pct")
    if live_like and operating_margin is not None:
        signal_quality = signal_source_quality({"operating_margin_pct"})
        signals.append(_signal("operating_margin_strength", "supportive" if operating_margin >= 15 else "neutral" if operating_margin >= 5 else "caution", signal_quality, [_metric_evidence("Operating margin pct", operating_margin)], limitations, []))
    else:
        signals.append(_signal("operating_margin_strength", "insufficient", "insufficient", [], limitations, ["operating_margin_pct"]))

    net_income = available_metric("net_income_ttm")
    net_income_margin = available_metric("net_income_margin_pct")
    if live_like and (net_income is not None or net_income_margin is not None):
        ocf = available_metric("operating_cash_flow_ttm")
        if net_income is not None and ocf is not None and net_income > 0 and ocf < net_income * 0.8:
            ni_status = "caution"
        else:
            ni_status = "supportive" if (net_income or 0) > 0 and (net_income_margin or 0) >= 10 else "neutral" if (net_income or 0) > 0 else "caution"
        signal_quality = signal_source_quality({"net_income_margin_pct", "operating_cash_flow_ttm"}, mixed=True)
        signals.append(_signal("net_income_quality", ni_status, signal_quality, [_metric_evidence("Net income TTM", net_income), _metric_evidence("Net income margin pct", net_income_margin), _metric_evidence("Operating cash flow TTM", ocf)], limitations, []))
    else:
        signals.append(_signal("net_income_quality", "insufficient", "insufficient", [], limitations, ["net_income_ttm", "net_income_margin_pct"]))

    ocf = available_metric("operating_cash_flow_ttm")
    if live_like and ocf is not None:
        signal_quality = signal_source_quality({"operating_cash_flow_ttm"})
        signals.append(_signal("operating_cash_flow_quality", "supportive" if ocf > 0 else "caution", signal_quality, [_metric_evidence("Operating cash flow TTM", ocf)], limitations, []))
    else:
        signals.append(_signal("operating_cash_flow_quality", "insufficient", "insufficient", [], limitations, ["operating_cash_flow_ttm"]))

    cash = available_metric("cash_and_equivalents")
    debt = available_metric("total_debt")
    net_cash = available_metric("net_cash_or_debt")
    if live_like and (cash is not None or net_cash is not None):
        signal_quality = signal_source_quality({"cash_and_equivalents", "net_cash_or_debt"})
        signals.append(_signal("cash_safety_buffer", "supportive" if (net_cash or 0) >= 0 else "neutral", signal_quality, [_metric_evidence("Cash and equivalents", cash), _metric_evidence("Net cash or debt", net_cash)], limitations, []))
    else:
        signals.append(_signal("cash_safety_buffer", "insufficient", "insufficient", [], limitations, ["cash_and_equivalents", "net_cash_or_debt"]))

    debt_to_equity = available_metric("debt_to_equity")
    if live_like and (debt is not None or debt_to_equity is not None):
        signal_quality = signal_source_quality({"total_debt", "debt_to_equity"})
        signals.append(_signal("debt_risk", "supportive" if (net_cash or 0) >= 0 or (debt_to_equity is not None and debt_to_equity <= 0.8) else "caution" if debt_to_equity and debt_to_equity > 1.5 else "neutral", signal_quality, [_metric_evidence("Total debt", debt), _metric_evidence("Debt to equity", debt_to_equity)], limitations, []))
    else:
        signals.append(_signal("debt_risk", "insufficient", "insufficient", [], limitations, ["total_debt", "debt_to_equity"]))

    for signal_name, ratio_field, raw_field, missing in [
        ("receivables_vs_revenue_risk", "receivables_to_revenue_pct", "accounts_receivable", ["accounts_receivable", "receivables_to_revenue_pct"]),
        ("inventory_vs_revenue_risk", "inventory_to_revenue_pct", "inventory", ["inventory", "inventory_to_revenue_pct"]),
    ]:
        ratio = available_metric(ratio_field)
        raw = available_metric(raw_field)
        if live_like and ratio is not None:
            signal_quality = signal_source_quality({ratio_field, raw_field})
            signals.append(_signal(signal_name, "caution" if ratio >= 30 else "neutral", signal_quality, [_metric_evidence(raw_field.replace("_", " ").title(), raw), _metric_evidence(ratio_field, ratio)], limitations, []))
        else:
            signals.append(_signal(signal_name, "insufficient", "insufficient", [], limitations, missing))

    capex = available_metric("capex_ttm")
    if live_like and ocf is not None and capex is not None:
        capex_ratio = round(abs(capex) / ocf * 100, 2) if ocf > 0 else None
        signal_quality = signal_source_quality({"operating_cash_flow_ttm", "capex_ttm"})
        signals.append(_signal("capex_vs_ocf_risk", "caution" if capex_ratio is not None and capex_ratio >= 80 else "neutral", signal_quality, [_metric_evidence("Operating cash flow TTM", ocf), _metric_evidence("CapEx TTM", capex), _metric_evidence("CapEx as pct of OCF", capex_ratio)], limitations, []))
    else:
        signals.append(_signal("capex_vs_ocf_risk", "insufficient", "insufficient", [], limitations, ["operating_cash_flow_ttm", "capex_ttm"]))

    dilution = available_metric("share_dilution_3y_pct")
    if live_like and dilution is not None:
        signal_quality = signal_source_quality({"share_dilution_3y_pct"})
        signals.append(_signal("share_dilution_risk", "caution" if dilution >= 10 else "neutral", signal_quality, [_metric_evidence("Share dilution 3Y pct", dilution)], limitations, []))
    else:
        signals.append(_signal("share_dilution_risk", "insufficient", "insufficient", [], limitations, ["share_dilution_3y_pct"]))

    scored = [signal for signal in signals if signal["status"] != "insufficient"]
    score_by_status = {"supportive": 85, "neutral": 60, "caution": 35}
    score = round(sum(score_by_status[signal["status"]] for signal in scored) / len(signals), 2) if scored else 0
    confidence = round(min(0.78, 0.25 + len(scored) * 0.055), 2)
    label = "strong" if score >= 70 and confidence >= 0.55 else "adequate" if score >= 45 else "caution" if scored else "insufficient"
    missing = sorted({item for signal in signals for item in signal["missing_data"]})
    source_status = build_source_status(
        {
            "source_type": "derived" if scored else "unknown",
            "provider": "derived_from_SEC_companyfacts_and_yfinance_financial_statement_signals" if filing_fields else "derived_from_yfinance_financial_statement_signals" if scored else "insufficient_financial_statement_evidence",
            "source_date": status.get("source_date", ""),
            "is_fresh": status.get("is_fresh", False),
            "limitations": limitations,
            "missing_data": missing,
            "fallback_used": status.get("fallback_used", False),
            "fallback_reason": status.get("fallback_reason"),
        }
    )
    return FinancialStatementSignals(
        score=score,
        confidence=confidence,
        label=label,
        signals=signals,
        source_status=source_status,
        limitations=limitations,
        missing_data=missing,
    )


def _limited(items: list[str], fallback: str, limit: int = 3) -> list[str]:
    clean = [str(item) for item in items if item]
    return clean[:limit] or [fallback]


def _excluded_indicator_names(macro_regime) -> list[str]:
    excluded = []
    for item in macro_regime.derived_metrics.get("scoring_model", {}).get("excluded_indicators", []):
        name = str(item.get("name") or "")
        if name == "ism_manufacturing_pmi":
            excluded.append("ISM Manufacturing PMI")
        elif name == "cnn_fear_greed":
            excluded.append("CNN Fear & Greed")
        elif name:
            excluded.append(name)
    return excluded


def _status_is_fallback_evidence(status: dict) -> bool:
    return bool(status.get("fallback_used") or status.get("source_type") == "fallback")


def _macro_active_scoring_uses_fallback(macro_regime) -> bool:
    quality = getattr(macro_regime, "macro_data_quality", None)
    scoring = getattr(quality, "scoring", {}) if quality else {}
    if scoring.get("fallback_active_components") or scoring.get("cached_live_after_failure_components"):
        return True
    contributions = macro_regime.derived_metrics.get("component_contributions", [])
    for item in contributions:
        if item.get("weight", 0) and item.get("source_type") == "fallback":
            return True
    return False


def _macro_is_derived_live_quality(macro_regime) -> bool:
    quality = getattr(macro_regime, "macro_data_quality", None)
    scoring = getattr(quality, "scoring", {}) if quality else {}
    if macro_regime.derived_metrics.get("scoring_model", {}).get("version") != "macro_v12_5":
        return False
    if not quality or getattr(quality, "mock_context_score_weight_pct", None) != 0:
        return False
    if _macro_active_scoring_uses_fallback(macro_regime):
        return False
    active_available = scoring.get("active_available_weight_pct")
    if active_available is not None and float(active_available) <= 0:
        return False
    for item in macro_regime.derived_metrics.get("component_contributions", []):
        if item.get("source_type") in {"mock", "fallback"}:
            return False
    excluded = macro_regime.derived_metrics.get("scoring_model", {}).get("excluded_indicators", [])
    return all(item.get("affects_score") is False and item.get("weight", 0) == 0 for item in excluded)


def _macro_environment_source_quality(macro_regime) -> str:
    quality = getattr(macro_regime, "macro_data_quality", None)
    scoring = getattr(quality, "scoring", {}) if quality else {}
    active_available = scoring.get("active_available_weight_pct")
    if _macro_is_derived_live_quality(macro_regime):
        return "derived_live"
    if _macro_active_scoring_uses_fallback(macro_regime) or (
        active_available is not None and float(active_available) <= 0
    ):
        return "mixed_with_fallback"
    return _source_quality_from_status(_status_dict(macro_regime.source_status), category="macro_environment")


def _category_is_fallback_evidence(category: str, status: dict, response: AnalyzeStockResponse) -> bool:
    if category == "macro_environment":
        quality = getattr(response.macro_regime, "macro_data_quality", None)
        scoring = getattr(quality, "scoring", {}) if quality else {}
        active_available = scoring.get("active_available_weight_pct")
        return _macro_active_scoring_uses_fallback(response.macro_regime) or (
            active_available is not None and float(active_available) <= 0
        )
    if _status_is_fallback_evidence(status):
        return True
    if category == "legacy_leadership_score":
        return False
    matrix_quality = None
    for item in response.evidence_matrix or []:
        item_category = item.category if hasattr(item, "category") else item.get("category")
        if item_category == category:
            matrix_quality = item.source_quality if hasattr(item, "source_quality") else item.get("source_quality")
            break
    return matrix_quality == "mixed_with_fallback"


def _build_data_quality_summary(response: AnalyzeStockResponse) -> dict:
    component_statuses = {
        "macro_environment": _status_dict(response.macro_regime.source_status),
        "company_profile": _status_dict(response.company_profile.get("source_status")),
        "financial_quality": _status_dict(response.financial_quality.source_status),
        "valuation_context": _status_dict(response.valuation_context.source_status),
        "sec_financial_facts": _status_dict(response.sec_financial_facts.get("source_status")),
        "fundamentals_cross_check": _status_dict(response.fundamentals_cross_check.get("source_status")),
        "jane_company_quality": _status_dict(response.jane_company_quality.source_status),
        "financial_statement_signals": _status_dict(response.financial_statement_signals.source_status),
        "legacy_leadership_score": _status_dict(response.leadership_score.source_status),
        "smart_money": _status_dict(response.smart_money.source_status),
        "insider_activity": _status_dict(response.insider_activity.get("source_status")),
        "institutional_13f": _status_dict(response.institutional_13f.get("source_status")),
    }
    quality_criteria = response.jane_company_quality.criteria
    insufficient_evidence_categories = sorted(
        criterion.name for criterion in quality_criteria if criterion.status == "insufficient"
    )
    company_quality_breakdown = {
        "evidence_backed_criteria_count": sum(1 for criterion in quality_criteria if criterion.affects_score and criterion.source_quality in {"live_backed", "derived_live", "cached_live", "filing_backed", "derived_from_mixed_sources"}),
        "insufficient_criteria_count": sum(1 for criterion in quality_criteria if criterion.status == "insufficient"),
        "mock_criteria_count": sum(1 for criterion in quality_criteria if criterion.source_quality == "mock_only"),
        "derived_live_criteria_count": sum(1 for criterion in quality_criteria if criterion.source_quality == "derived_live"),
        "user_context_criteria_count": sum(1 for criterion in quality_criteria if criterion.source_quality == "user_context"),
        "user_provided_criteria_count": sum(1 for criterion in quality_criteria if criterion.source_quality == "user_provided"),
        "filing_backed_criteria_count": sum(1 for criterion in quality_criteria if criterion.source_quality == "filing_backed"),
        "mixed_source_criteria_count": sum(1 for criterion in quality_criteria if criterion.source_quality == "derived_from_mixed_sources"),
    }
    qualitative = response.qualitative_evidence_assessment
    comparison = response.comparison_evidence_assessment
    qualitative_summary = {
        "provided": bool(qualitative.evidence_count),
        "accepted_count": qualitative.accepted_evidence_count,
        "rejected_count": qualitative.rejected_evidence_count,
        "user_provided_count": qualitative.accepted_evidence_count,
        "independently_verified_count": 0,
        "saved_library_count": qualitative.saved_evidence_count,
        "request_scoped_count": qualitative.request_evidence_count,
        "reviewed_count": qualitative.reviewed_count,
        "unreviewed_count": qualitative.unreviewed_count,
        "reviewed_active_count": qualitative.reviewed_active_count,
        "unreviewed_active_count": qualitative.unreviewed_active_count,
        "stale_count": qualitative.stale_count,
        "review_due_count": qualitative.review_due_count,
        "quality_score_average": qualitative.quality_score_average,
        "high_quality_count": qualitative.high_quality_count,
        "medium_quality_count": qualitative.medium_quality_count,
        "low_quality_count": qualitative.low_quality_count,
        "incomplete_count": qualitative.incomplete_count,
        "archived_or_rejected_ignored_count": qualitative.archived_or_rejected_ignored_count,
        "criteria_covered": qualitative.criteria_covered,
        "criteria_still_insufficient": qualitative.criteria_still_insufficient,
    }
    comparison = response.comparison_evidence_assessment
    qualitative_summary["comparison"] = {
        "provided": bool(comparison.comparison_evidence_count),
        "accepted_count": comparison.accepted_comparison_count,
        "reviewed_count": comparison.reviewed_comparison_count,
        "stale_count": comparison.stale_comparison_count,
        "peer_company_count": len(comparison.peer_companies_mentioned),
        "criteria_supported": comparison.criteria_supported,
        "claimed_advantage_breakdown": comparison.claimed_advantage_breakdown,
    }
    fallback_categories = sorted(
        name for name, status in component_statuses.items() if _category_is_fallback_evidence(name, status, response)
    )
    fallback_category_set = set(fallback_categories)
    mock_categories = sorted(
        name for name, status in component_statuses.items() if status.get("source_type") == "mock" and name not in fallback_category_set
    )
    missing_source_date_categories = sorted(
        name for name, status in component_statuses.items() if not status.get("source_date") and status.get("source_type") != "unknown"
    )
    live_components = sum(1 for status in component_statuses.values() if status.get("source_type") in {"live", "cached_live", "derived"})
    mock_components = len(mock_categories)
    fallback_components = len(fallback_categories)
    stale_components = sum(
        1
        for status in component_statuses.values()
        if status.get("source_type") in {"live", "cached_live", "fallback", "derived"} and status.get("is_fresh") is False
    )
    legacy_only_mock = set(mock_categories) <= {"legacy_leadership_score"}
    critical_mock = {"company_profile", "financial_quality"} & set(mock_categories)
    if mock_components >= 4 or missing_source_date_categories:
        grade = "D"
    elif {"company_profile", "financial_quality"} & set(mock_categories):
        grade = "C"
    elif critical_mock and fallback_components:
        grade = "B"
    elif critical_mock or fallback_components or fallback_components:
        grade = "B"
    elif legacy_only_mock:
        grade = "B"
    else:
        grade = "A"
    if grade == "A":
        mode = "live_with_fallback" if fallback_components else "mixed_preliminary"
        summary = "Source quality is strong enough for a structured research validation view."
    elif grade == "B":
        mode = "mixed_preliminary"
        summary = "Live or derived source context is present, but some candidate-specific evidence remains preliminary."
    elif grade == "C":
        mode = "mixed_preliminary"
        summary = "Important company or fundamentals evidence remains mock-based or only partially improved."
    else:
        mode = "mostly_mock" if mock_components else "insufficient"
        summary = "Source quality is too limited for more than preliminary research triage."
    confidence_cap_applied = response.research_verdict.confidence <= MOCK_LEADERSHIP_CONFIDENCE_CAP and bool(critical_mock or fallback_components or insufficient_evidence_categories)
    cap_reason = None
    if confidence_cap_applied:
        cap_reason = "Legacy mock leadership, fallback/cached-limited evidence, or insufficient qualitative company-quality evidence caps analyze-stock confidence."
    return {
        "mode": mode,
        "confidence_cap_applied": confidence_cap_applied,
        "confidence_cap_reason": cap_reason,
        "live_components": live_components,
        "mock_components": mock_components,
        "fallback_components": fallback_components,
        "missing_source_date_components": len(missing_source_date_categories),
        "stale_components": stale_components,
        "source_quality_grade": grade,
        "source_quality_summary": summary,
        "mock_evidence_categories": mock_categories,
        "fallback_evidence_categories": fallback_categories,
        "missing_source_date_categories": missing_source_date_categories,
        "excluded_from_scoring": _excluded_indicator_names(response.macro_regime),
        "insufficient_evidence_categories": insufficient_evidence_categories,
        "company_quality": company_quality_breakdown,
        "qualitative_evidence": qualitative_summary,
        "sec_companyfacts": {
            "available": _status_dict(response.sec_financial_facts.get("source_status")).get("source_type") in {"live", "cached_live"},
            "source_type": _status_dict(response.sec_financial_facts.get("source_status")).get("source_type") or "insufficient",
            "filing_backed_metric_count": sum(1 for item in (response.sec_financial_facts.get("facts") or {}).values() if item),
            "missing_concept_count": len(response.sec_financial_facts.get("missing_data", [])),
            "latest_filing_date": response.sec_financial_facts.get("latest_filing_date"),
            "latest_report_period": response.sec_financial_facts.get("latest_report_period"),
            "agreement_level_with_yfinance": response.fundamentals_cross_check.get("agreement_level", "insufficient"),
        },
    }


def _build_insider_activity(score: ScoreObject) -> dict:
    status = _status_dict(score.source_status or score.raw_data.get("source_status"))
    metrics = score.derived_metrics
    transactions = score.raw_data.get("transactions", []) or []
    total = int(metrics.get("total_transactions_180d") or len(transactions))
    accumulation = int(metrics.get("accumulation_count_180d") or 0)
    disposition = int(metrics.get("disposition_count_180d") or 0)
    neutral_count = max(0, total - accumulation - disposition)
    source_quality = _source_quality_from_status(status, category="insider_activity")
    if source_quality == "mixed_with_fallback":
        summary = "Form 4 evidence is limited because fallback or cached-after-failure source context is present."
    elif total:
        summary = f"Form 4 review found {accumulation} code P accumulation rows and {disposition} code S disposition rows in the lookback window."
    else:
        summary = "No meaningful Form 4 transaction evidence is available in the current source snapshot."
    return {
        **score.model_dump(mode="json"),
        "summary": summary,
        "source_quality": source_quality,
        "form4_evidence": {
            "transactions": transactions,
            "transaction_row_cap": score.raw_data.get("transaction_row_cap"),
            "source_status": status,
            "not_investment_advice": True,
        },
        "accumulation_count": accumulation,
        "disposition_count": disposition,
        "neutral_or_excluded_transaction_count": neutral_count,
        "limitations": score.limitations,
        "missing_data": score.missing_data,
    }


def _build_institutional_13f(score: ScoreObject, ticker: str, sec_filings: dict) -> dict:
    raw = score.raw_data
    candidate = build_candidate_13f_evidence(
        ticker,
        sec_filings.get("institutional_13f_summary") or raw.get("portfolio_summary") or {},
        sec_filings.get("institutional_13f_target_matches") or {"target_matches": raw.get("target_matches", [])},
    )
    candidate_dict = candidate.model_dump(mode="json") if hasattr(candidate, "model_dump") else dict(candidate)
    status = _status_dict(candidate_dict.get("source_status") or score.source_status or raw.get("source_status"))
    candidate_specific = candidate_dict.get("candidate_specific_evidence") or {}
    if candidate_specific.get("matched_in_13f") is False:
        candidate_specific["score_contribution_allowed"] = False
        candidate_specific["interpretation_label"] = "no_reported_13f_position_observed"
    portfolio_context = candidate_dict.get("portfolio_context") or {}
    top_holdings = portfolio_context.get("top_holdings_by_value")
    if isinstance(top_holdings, list):
        portfolio_context["top_holdings_by_value"] = top_holdings[:5]
    return {
        **score.model_dump(mode="json"),
        "candidate_specific_evidence": candidate_specific,
        "portfolio_context": portfolio_context,
        "source_status": status,
        "limitations": sorted(set([*score.limitations, *candidate_dict.get("limitations", [])])),
        "missing_data": sorted(set([*score.missing_data, *candidate_dict.get("missing_data", [])])),
    }


def _smart_money_source_quality_breakdown(smart_money: ScoreObject, insider_activity: dict, institutional_13f: dict) -> dict:
    form4_status = _status_dict(insider_activity.get("source_status") or (smart_money.raw_data.get("form4") or {}).get("source_status"))
    thirteen_f_status = _status_dict(institutional_13f.get("source_status") or (smart_money.raw_data.get("institutional_13f") or {}).get("source_status"))
    options_component = (smart_money.derived_metrics.get("components") or {}).get("options_abnormal_activity") or {}
    options_raw = smart_money.raw_data.get("options") or {}
    form4_source_type = form4_status.get("source_type") or "unknown"
    form4_fallback = bool(form4_status.get("fallback_used") or form4_source_type in {"mock", "fallback"})
    thirteen_f_source_type = thirteen_f_status.get("source_type") or "mock"
    options_source_type = _status_dict(options_component.get("source_status")).get("source_type") or "mock"
    target_evidence = institutional_13f.get("candidate_specific_evidence") or {}
    no_candidate_match = target_evidence.get("matched_in_13f") is False
    mock_options = options_source_type == "mock" or not options_component.get("source_status")
    aggregate_limited = form4_fallback or thirteen_f_source_type in {"mock", "fallback", "unknown"} or mock_options
    return {
        "form4": {
            "source_type": form4_source_type,
            "fallback_used": form4_fallback,
            "interpretation": (
                "Form 4 evidence is fallback, mock, or cached-after-failure limited and should be treated as a constraint."
                if form4_fallback
                else "Form 4 evidence is research context based on available SEC filing rows."
            ),
            "score_impact": "Limited or neutral impact when fallback, mock, or cached-after-failure data is present." if form4_fallback else "Can affect smart-money score only under disclosed Form 4 transaction-code rules.",
        },
        "institutional_13f": {
            "source_type": thirteen_f_source_type,
            "is_delayed_quarterly": True,
            "is_real_time_signal": False,
            "interpretation": (
                "No candidate-specific 13F match is treated as context only, not support."
                if no_candidate_match
                else "13F evidence is delayed quarterly filing context and may not reflect current positioning."
            ),
            "score_impact": "Candidate-specific 13F support is allowed only for qualified filing-backed matches; portfolio context alone is not support.",
        },
        "options": {
            "source_type": options_source_type,
            "interpretation": (
                "Options component remains mock context and should not dominate smart-money interpretation."
                if mock_options
                else "Options component is supplemental research context only."
            ),
            "score_impact": "Mock options are preliminary and cap aggregate interpretation clarity." if mock_options else "Supplemental component under configured source limits.",
        },
        "aggregate_interpretation": "mixed_with_fallback_or_mock_components; smart-money output is preliminary." if aggregate_limited else "source_quality_constraints_disclosed",
        "not_investment_advice": True,
    }


def _coverage_source_quality(items: list[dict]) -> str:
    accepted = [item for item in items if item.get("accepted") is True]
    if not accepted:
        return "insufficient"
    qualities = {str(item.get("source_quality") or "user_provided") for item in accepted}
    if "filing_backed" in qualities:
        return "filing_backed"
    if "derived_live" in qualities:
        return "derived_live"
    if "user_provided" in qualities:
        return "user_provided"
    return sorted(qualities)[0]


def _accepted_jane_evidence_by_criterion(qualitative_assessment: dict) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    for item in qualitative_assessment.get("evidence_items") or []:
        if not isinstance(item, dict):
            continue
        criterion_id = item.get("criterion_id")
        if criterion_id is None:
            criterion_id = JANE_CANONICAL_ID_BY_LEGACY_SLUG.get(str(item.get("criterion") or ""))
        if criterion_id is None:
            continue
        try:
            canonical_id = int(criterion_id)
        except (TypeError, ValueError):
            continue
        if canonical_id < 1 or canonical_id > 20:
            continue
        grouped.setdefault(canonical_id, []).append(item)
    return grouped


def _build_jane_criteria_coverage(response: AnalyzeStockResponse) -> dict:
    evidence_by_id = _accepted_jane_evidence_by_criterion(response.qualitative_evidence_assessment.model_dump(mode="json"))
    rows = []
    for criterion in JANE_CRITERIA:
        criterion_id = int(criterion["criterion_id"])
        all_submetrics = list(criterion.get("submetrics") or [])
        auto_submetrics = list(criterion.get("auto_derivable_submetrics") or [])
        required_user_submetrics = list(criterion.get("requires_user_input_submetrics") or [])
        items = evidence_by_id.get(criterion_id, [])
        accepted_items = [item for item in items if item.get("accepted") is True]
        covered = sorted(
            {
                str(item.get("submetric"))
                for item in accepted_items
                if item.get("submetric") and str(item.get("submetric")) in all_submetrics
            }
        )
        missing = [submetric for submetric in all_submetrics if submetric not in covered]
        if covered and not missing:
            status = "covered"
        elif covered:
            status = "partial"
        else:
            status = "insufficient"
        source_quality = _coverage_source_quality(items)
        next_manual_check = None
        if missing:
            next_manual_check = f"Verify Jane criterion {criterion_id} missing submetrics: {', '.join(missing[:4])}."
        limitations = [
            "Coverage matrix measures evidence completeness only and does not change scoring logic.",
            "User-provided evidence still requires manual source verification.",
        ]
        if auto_submetrics:
            limitations.append("Auto-derivable submetrics are listed but Phase 28 does not deepen financial proxy calculations.")
        rows.append(
            {
                "criterion_id": criterion_id,
                "criterion_name": criterion["criterion_name"],
                "evidence_type": criterion["evidence_type"],
                "coverage_status": status,
                "source_quality": source_quality,
                "confidence": max((float(item.get("confidence") or 0) for item in accepted_items), default=0.0),
                "auto_derivable_submetrics": auto_submetrics,
                "requires_user_input_submetrics": required_user_submetrics,
                "covered_submetrics": covered,
                "missing_submetrics": missing,
                "evidence_item_count": len(items),
                "accepted_evidence_item_count": len(accepted_items),
                "financial_proxy_source": criterion.get("financial_proxy_source"),
                "requires_human_verification": bool(missing or required_user_submetrics),
                "summary": f"Jane criterion {criterion_id} coverage is {status} based on accepted canonical evidence.",
                "limitations": limitations,
                "next_manual_check": next_manual_check,
            }
        )
    covered_count = sum(1 for item in rows if item["coverage_status"] == "covered")
    partial_count = sum(1 for item in rows if item["coverage_status"] == "partial")
    insufficient_count = sum(1 for item in rows if item["coverage_status"] == "insufficient")
    return {
        "criteria": rows,
        "covered_count": covered_count,
        "partial_count": partial_count,
        "insufficient_count": insufficient_count,
        "user_input_required_count": sum(1 for item in rows if item["requires_user_input_submetrics"]),
        "financial_proxy_available_count": sum(1 for item in rows if item["financial_proxy_source"]),
        "source_quality_summary": f"Jane 20 coverage: {covered_count} covered, {partial_count} partial, {insufficient_count} insufficient. Coverage is non-scoring and for validation workflow only.",
        "not_investment_advice": True,
    }


def _build_evidence_matrix(response: AnalyzeStockResponse) -> list[dict]:
    company_status = _status_dict(response.company_profile.get("source_status"))
    financial_status = _status_dict(response.financial_quality.source_status)
    valuation_status = _status_dict(response.valuation_context.source_status)
    sec_status = _status_dict(response.sec_financial_facts.get("source_status"))
    cross_status = _status_dict(response.fundamentals_cross_check.get("source_status"))
    leadership_status = _status_dict(response.leadership_score.source_status)
    smart_status = _status_dict(response.smart_money.source_status)
    insider_status = _status_dict(response.insider_activity.get("source_status"))
    thirteen_f_status = _status_dict(response.institutional_13f.get("source_status"))
    macro_quality = response.macro_regime.macro_data_quality
    thirteen_f_candidate = response.institutional_13f.get("candidate_specific_evidence") or {}
    quality_supportive = [criterion for criterion in response.jane_company_quality.criteria if criterion.status == "supportive"]
    quality_insufficient = [criterion for criterion in response.jane_company_quality.criteria if criterion.status == "insufficient"]
    quality_user_provided = [criterion for criterion in response.jane_company_quality.criteria if criterion.source_quality == "user_provided"]
    signal_supportive = [signal for signal in response.financial_statement_signals.signals if signal.status == "supportive"]
    signal_insufficient = [signal for signal in response.financial_statement_signals.signals if signal.status == "insufficient"]
    qualitative = response.qualitative_evidence_assessment
    comparison = response.comparison_evidence_assessment
    rows = [
        {
            "category": "macro_environment",
            "status": _score_status(response.macro_regime.score),
            "score": response.macro_regime.score,
            "confidence": response.macro_regime.confidence,
            "source_quality": _macro_environment_source_quality(response.macro_regime),
            "summary": f"Macro score is {response.macro_regime.label} under macro_v12_5.",
            "key_evidence": _limited(
                [
                    f"Active macro weight total: {response.macro_regime.derived_metrics.get('scoring_model', {}).get('total_weight', 100)}",
                    f"Mock context score weight: {getattr(macro_quality, 'mock_context_score_weight_pct', 0) if macro_quality else 0}",
                    f"Excluded from scoring: {', '.join(_excluded_indicator_names(response.macro_regime))}",
                ],
                "Macro regime evidence unavailable.",
            ),
            "limitations": _limited(response.macro_regime.limitations, "No macro limitations listed."),
        },
        {
            "category": "company_profile",
            "status": "insufficient" if company_status.get("source_type") == "mock" else "neutral",
            "score": None,
            "confidence": 0.35 if company_status.get("source_type") == "mock" else 0.65,
            "source_quality": _source_quality_from_status(company_status),
            "summary": "Company profile uses live or cached yfinance context." if company_status.get("source_type") in {"live", "cached_live", "derived"} else "Company profile is mock-based preliminary context.",
            "key_evidence": _limited(
                [
                    str(response.company_profile.get("company_name", "")),
                    str(response.company_profile.get("sector", "")),
                    f"Market cap: {response.company_profile.get('market_cap')}",
                ],
                "Company profile evidence unavailable.",
            ),
            "limitations": _limited(company_status.get("limitations", []), "Company profile remains preliminary."),
        },
        {
            "category": "financial_quality",
            "status": _score_status(response.financial_quality.score),
            "score": response.financial_quality.score,
            "confidence": response.financial_quality.confidence,
            "source_quality": _source_quality_from_status(financial_status),
            "summary": "Financial quality uses live or cached yfinance fundamentals when available.",
            "key_evidence": _limited(
                [
                    f"Revenue TTM: {response.financial_quality.raw_data.get('revenue_ttm')}",
                    f"Revenue YoY growth: {response.financial_quality.raw_data.get('revenue_yoy_growth_pct')}%",
                    f"Gross margin: {response.financial_quality.raw_data.get('gross_margin_pct')}%",
                    f"Free cash flow TTM: {response.financial_quality.raw_data.get('free_cash_flow_ttm')}",
                ],
                "Financial quality evidence unavailable.",
            ),
            "limitations": _limited(response.financial_quality.limitations, "Financial quality source limitations unavailable."),
        },
        {
            "category": "valuation_context",
            "status": "caution" if response.valuation_context.label == "elevated" else "insufficient" if response.valuation_context.label == "insufficient" else "neutral",
            "score": response.valuation_context.score,
            "confidence": response.valuation_context.confidence,
            "source_quality": _source_quality_from_status(valuation_status),
            "summary": response.valuation_context.raw_data.get("valuation_summary", "Valuation context is risk context only."),
            "key_evidence": _limited(
                [
                    f"Price to sales TTM: {response.valuation_context.raw_data.get('price_to_sales_ttm')}",
                    f"EV to sales TTM: {response.valuation_context.raw_data.get('ev_to_sales_ttm')}",
                    f"Valuation risk label: {response.valuation_context.raw_data.get('valuation_risk_label')}",
                ],
                "Valuation context unavailable.",
            ),
            "limitations": _limited(response.valuation_context.limitations, "Valuation source limitations unavailable."),
        },
        {
            "category": "sec_financial_facts",
            "status": "neutral" if sec_status.get("source_type") in {"live", "cached_live"} else "insufficient",
            "score": None,
            "confidence": 0.72 if sec_status.get("source_type") in {"live", "cached_live"} else 0.25,
            "source_quality": _source_quality_from_status(sec_status, category="sec_financial_facts"),
            "summary": "SEC Companyfacts provides official filing-backed financial metric cross-checks.",
            "key_evidence": _limited(
                [
                    f"Filing-backed facts: {sum(1 for item in (response.sec_financial_facts.get('facts') or {}).values() if item)}",
                    f"Invalid derived metrics: {len(response.sec_financial_facts.get('invalid_derived_metrics') or {})}",
                    f"Aligned statement period: {response.sec_financial_facts.get('aligned_statement_period')}",
                    f"Aligned balance sheet period: {response.sec_financial_facts.get('aligned_balance_sheet_period')}",
                    f"Latest filing date: {response.sec_financial_facts.get('latest_filing_date')}",
                ],
                "SEC Companyfacts evidence unavailable.",
                limit=5,
            ),
            "limitations": _limited(response.sec_financial_facts.get("limitations", []), "SEC Companyfacts concept coverage varies by issuer."),
        },
        {
            "category": "fundamentals_cross_check",
            "status": "caution" if response.fundamentals_cross_check.get("agreement_level") == "low" else "neutral" if response.fundamentals_cross_check.get("agreement_level") in {"high", "moderate"} else "insufficient",
            "score": None,
            "confidence": 0.70 if response.fundamentals_cross_check.get("agreement_level") in {"high", "moderate"} else 0.35,
            "source_quality": _source_quality_from_status(cross_status, category="fundamentals_cross_check"),
            "summary": response.fundamentals_cross_check.get("summary", "SEC/yfinance cross-check unavailable."),
            "key_evidence": _limited(
                [
                    f"Agreement level: {response.fundamentals_cross_check.get('agreement_level')}",
                    f"Parser period alignment valid: {bool(response.fundamentals_cross_check.get('parser_period_alignment_valid'))}",
                    f"Provider normalization discrepancies: {bool(response.fundamentals_cross_check.get('provider_normalization_discrepancies'))}",
                    f"Divergence reason: {response.fundamentals_cross_check.get('divergence_reason')}",
                    f"Checked metrics: {len(response.fundamentals_cross_check.get('checked_metrics', []))}",
                    f"Divergent metrics: {sum(1 for item in response.fundamentals_cross_check.get('checked_metrics', []) if item.get('status') == 'divergent')}",
                ],
                "Cross-check evidence unavailable.",
                limit=6,
            ),
            "limitations": _limited(response.fundamentals_cross_check.get("limitations", []), "Cross-check limitations unavailable."),
        },
        {
            "category": "qualitative_evidence",
            "status": "supportive" if qualitative.accepted_evidence_count >= 2 else "neutral" if qualitative.accepted_evidence_count else "insufficient",
            "score": None,
            "confidence": min(0.7, max([item.confidence for item in qualitative.evidence_items if item.accepted], default=0.2)),
            "source_quality": "user_provided" if qualitative.accepted_evidence_count else "insufficient",
            "summary": f"User-provided qualitative evidence supports preliminary review of selected Jane criteria; saved library items: {qualitative.saved_evidence_count}, request-scoped items: {qualitative.request_evidence_count}." if qualitative.accepted_evidence_count else "No structured qualitative evidence was provided for moat/founder/network/disruption criteria.",
            "key_evidence": _limited(
                [
                    f"Saved evidence items: {qualitative.saved_evidence_count}",
                    f"Request-scoped evidence items: {qualitative.request_evidence_count}",
                    f"Accepted evidence items: {qualitative.accepted_evidence_count}",
                    f"Reviewed active evidence: {qualitative.reviewed_active_count}",
                    f"Unreviewed active evidence: {qualitative.unreviewed_active_count}",
                    f"Stale evidence: {qualitative.stale_count}",
                    f"Average quality score: {qualitative.quality_score_average if qualitative.quality_score_average is not None else 'n/a'}",
                    f"Rejected evidence items: {qualitative.rejected_evidence_count}",
                    f"Deduplicated evidence items: {qualitative.deduplicated_count}",
                    f"Archived or rejected library items ignored: {qualitative.archived_or_rejected_ignored_count}",
                    f"Criteria covered: {', '.join(qualitative.criteria_covered) if qualitative.criteria_covered else 'none'}",
                    f"Still insufficient: {', '.join(qualitative.criteria_still_insufficient) if qualitative.criteria_still_insufficient else 'none'}",
                ],
                "Qualitative evidence unavailable.",
                limit=10,
            ),
            "limitations": _limited(qualitative.limitations, "Manual verification is required for qualitative evidence."),
        },
        {
            "category": "comparison_evidence",
            "status": "supportive" if comparison.accepted_comparison_count and comparison.reviewed_comparison_count else "neutral" if comparison.accepted_comparison_count else "insufficient",
            "score": None,
            "confidence": 0.62 if comparison.reviewed_comparison_count else 0.45 if comparison.accepted_comparison_count else 0.2,
            "source_quality": comparison.source_quality,
            "summary": (
                f"User-provided comparison evidence mentions {len(comparison.peer_companies_mentioned)} peer company item(s) and supports preliminary review of {len(comparison.criteria_supported)} Jane criteria."
                if comparison.accepted_comparison_count
                else "No structured competitor or comparison evidence was provided."
            ),
            "key_evidence": _limited(
                [
                    f"Accepted comparison items: {comparison.accepted_comparison_count}",
                    f"Reviewed comparison items: {comparison.reviewed_comparison_count}",
                    f"Stale comparison items: {comparison.stale_comparison_count}",
                    f"Peer companies: {', '.join(comparison.peer_companies_mentioned) if comparison.peer_companies_mentioned else 'none'}",
                    f"Claimed advantage breakdown: {comparison.claimed_advantage_breakdown}",
                    f"Criteria supported: {', '.join(comparison.criteria_supported) if comparison.criteria_supported else 'none'}",
                ],
                "Comparison evidence unavailable.",
            ),
            "limitations": _limited(comparison.limitations, "Peer comparison requires manual validation."),
        },
        {
            "category": "jane_company_quality",
            "status": _score_status(response.jane_company_quality.score),
            "score": response.jane_company_quality.score,
            "confidence": response.jane_company_quality.confidence,
            "source_quality": _source_quality_from_status(_status_dict(response.jane_company_quality.source_status)),
            "summary": "Jane company quality replaces mock leadership as the primary company-quality model.",
            "key_evidence": _limited(
                [
                    f"Evidence-backed criteria: {len(quality_supportive)} supportive",
                    f"Filing-backed criteria: {sum(1 for criterion in response.jane_company_quality.criteria if criterion.source_quality in {'filing_backed', 'derived_from_mixed_sources'})}",
                    f"User-provided preliminary criteria: {len(quality_user_provided)}",
                    f"Saved library evidence items: {qualitative.saved_evidence_count}",
                    f"Qualitative evidence average quality score: {qualitative.quality_score_average if qualitative.quality_score_average is not None else 'n/a'}",
                    f"Stale qualitative evidence items: {qualitative.stale_count}",
                    f"Criteria supported by comparison evidence: {', '.join(comparison.criteria_supported) if comparison.criteria_supported else 'none'}",
                    f"Criteria covered by qualitative evidence: {', '.join(qualitative.criteria_covered) if qualitative.criteria_covered else 'none'}",
                    f"Insufficient criteria: {len(quality_insufficient)}",
                    f"Label: {response.jane_company_quality.label}",
                ],
                "Jane company quality evidence unavailable.",
            ),
            "limitations": _limited(response.jane_company_quality.limitations, "Jane company quality limitations unavailable."),
        },
        {
            "category": "financial_statement_signals",
            "status": _score_status(response.financial_statement_signals.score),
            "score": response.financial_statement_signals.score,
            "confidence": response.financial_statement_signals.confidence,
            "source_quality": _source_quality_from_status(_status_dict(response.financial_statement_signals.source_status)),
            "summary": "Financial statement signals derive from available yfinance fundamentals and mark unavailable filing detail as insufficient.",
            "key_evidence": _limited(
                [
                    f"Supportive signals: {len(signal_supportive)}",
                    f"Insufficient signals: {len(signal_insufficient)}",
                    f"Label: {response.financial_statement_signals.label}",
                ],
                "Financial statement signal evidence unavailable.",
            ),
            "limitations": _limited(response.financial_statement_signals.limitations, "Financial statement signal limitations unavailable."),
        },
        {
            "category": "legacy_leadership_score",
            "status": "insufficient",
            "score": response.leadership_score.score,
            "confidence": response.leadership_score.confidence,
            "source_quality": "mock_only",
            "summary": "Legacy leadership score is mock-based and replaced by jane_company_quality.",
            "key_evidence": _limited(
                [
                    f"{response.leadership_score.derived_metrics.get('full_score_criteria', 0)} full-score criteria",
                    f"{response.leadership_score.derived_metrics.get('partial_score_criteria', 0)} partial-score criteria",
                ],
                "Legacy leadership evidence unavailable.",
            ),
            "limitations": _limited(response.leadership_score.limitations, "Leadership source limitations unavailable."),
        },
        {
            "category": "smart_money",
            "status": _score_status(response.smart_money.score),
            "score": response.smart_money.score,
            "confidence": response.smart_money.confidence,
            "source_quality": _source_quality_from_status(smart_status),
            "summary": "Aggregate smart-money score combines Form 4, 13F, and mock options context.",
            "key_evidence": _limited([f"Score: {response.smart_money.score}", f"Label: {response.smart_money.label}"], "Smart-money evidence unavailable."),
            "limitations": _limited(response.smart_money.limitations, "Smart-money source limitations unavailable."),
        },
        {
            "category": "insider_activity",
            "status": _score_status(response.insider_activity.get("score")),
            "score": response.insider_activity.get("score"),
            "confidence": float(response.insider_activity.get("confidence") or 0),
            "source_quality": response.insider_activity.get("source_quality", _source_quality_from_status(insider_status)),
            "summary": response.insider_activity.get("summary", "Form 4 evidence unavailable."),
            "key_evidence": [
                f"Code P accumulation rows: {response.insider_activity.get('accumulation_count', 0)}",
                f"Code S disposition rows: {response.insider_activity.get('disposition_count', 0)}",
                f"Neutral or excluded rows: {response.insider_activity.get('neutral_or_excluded_transaction_count', 0)}",
            ],
            "limitations": _limited(response.insider_activity.get("limitations", []), "Form 4 limitations unavailable."),
        },
        {
            "category": "institutional_13f",
            "status": "neutral" if thirteen_f_candidate.get("matched_in_13f") is False else _score_status(response.institutional_13f.get("score")),
            "score": response.institutional_13f.get("score"),
            "confidence": float(response.institutional_13f.get("confidence") or 0),
            "source_quality": _source_quality_from_status(thirteen_f_status),
            "summary": thirteen_f_candidate.get("interpretation_summary") or "13F evidence is delayed quarterly candidate context.",
            "key_evidence": [
                f"Matched in configured 13F: {bool(thirteen_f_candidate.get('matched_in_13f'))}",
                f"Score contribution allowed: {bool(thirteen_f_candidate.get('score_contribution_allowed'))}",
                f"Interpretation: {thirteen_f_candidate.get('interpretation_label', 'insufficient_13f_data')}",
            ],
            "limitations": _limited(response.institutional_13f.get("limitations", []), "13F limitations unavailable."),
        },
        {
            "category": "risk_flags",
            "status": "caution" if response.risk_flags else "neutral",
            "score": None,
            "confidence": 0.65,
            "source_quality": "derived_live",
            "summary": "Risk flags summarize valuation, social heat, financial quality, and macro caution checks.",
            "key_evidence": response.risk_flags or ["No current risk flags listed by deterministic rules."],
            "limitations": ["Risk flags are deterministic research checks and require human review."],
        },
    ]
    cross_explanation = response.fundamentals_cross_check.get("explanation") or {}
    smart_breakdown = response.smart_money.source_quality_breakdown or {}
    form4_breakdown = smart_breakdown.get("form4") or {}
    for row in rows:
        if row["category"] == "smart_money" and form4_breakdown.get("fallback_used"):
            row["source_quality"] = "mixed_with_fallback"
        category = row["category"]
        row.setdefault("why_it_matters", None)
        row.setdefault("review_priority", "none")
        row.setdefault("affects_final_score", None)
        row.setdefault("is_deprecated", False)
        row.setdefault("replaced_by", None)
        if category == "legacy_leadership_score":
            row.update(
                {
                    "is_deprecated": True,
                    "replaced_by": "jane_company_quality",
                    "affects_final_score": False,
                    "review_priority": "low",
                    "why_it_matters": "This backward-compatible mock row is visible for audit only; jane_company_quality is the active company-quality model.",
                }
            )
        elif category == "fundamentals_cross_check":
            row["review_priority"] = cross_explanation.get("manual_check_priority", "low")
            row["why_it_matters"] = "Provider discrepancies can cap confidence because SEC filing-backed concepts and yfinance normalized fields may differ by period or classification."
        elif category == "smart_money":
            aggregate = str(smart_breakdown.get("aggregate_interpretation") or "")
            row["review_priority"] = "high" if "fallback" in aggregate else "medium" if "mock" in aggregate else "low"
            row["why_it_matters"] = "Smart-money evidence combines delayed 13F, Form 4 source quality, and mock options context, so source constraints affect confidence."
        elif category == "qualitative_evidence":
            row["review_priority"] = "high" if qualitative.unreviewed_active_count or qualitative.stale_count or qualitative.criteria_still_insufficient else "medium" if qualitative.accepted_evidence_count else "high"
            row["why_it_matters"] = "Jane qualitative criteria remain preliminary unless user-provided evidence is reviewed and current."
        elif category == "comparison_evidence":
            stronger_unverified = comparison.claimed_advantage_breakdown.get("stronger", 0) and comparison.reviewed_comparison_count < comparison.accepted_comparison_count
            row["review_priority"] = "high" if stronger_unverified or comparison.stale_comparison_count else "medium" if comparison.accepted_comparison_count else "low"
            row["why_it_matters"] = "Peer and claimed-advantage evidence is user-provided and requires manual validation before increasing confidence."
        elif category == "valuation_context":
            row["review_priority"] = "medium" if response.valuation_context.label == "elevated" else "low" if response.valuation_context.label in {"moderate", "low"} else "medium"
            row["why_it_matters"] = "Valuation risk is context that can limit validation confidence when proxy multiples are elevated or unavailable."
    return rows


def _build_manual_checks(response: AnalyzeStockResponse) -> list[dict]:
    dq = response.data_quality_summary
    has_mock = bool(dq.mock_evidence_categories)
    profile_live = "company_profile" not in dq.mock_evidence_categories and "company_profile" not in dq.fallback_evidence_categories
    fundamentals_live = "financial_quality" not in dq.mock_evidence_categories and "financial_quality" not in dq.fallback_evidence_categories
    checks = []
    sec_available = _status_dict(response.sec_financial_facts.get("source_status")).get("source_type") in {"live", "cached_live"}
    if sec_available:
        checks.append(
            {
                "priority": "medium",
                "area": "filings",
                "check": "Review SEC Companyfacts-derived trends against latest 10-K/10-Q narrative.",
                "reason": "Filing-backed numeric trends should be checked against management discussion and notes.",
            }
        )
    if response.sec_financial_facts.get("missing_data"):
        checks.append(
            {
                "priority": "medium",
                "area": "filings",
                "check": "Manually verify missing SEC concepts in latest filing.",
                "reason": "SEC Companyfacts concept coverage varies and missing concepts are not inferred.",
            }
        )
    cross_explanation = response.fundamentals_cross_check.get("explanation") or {}
    if cross_explanation.get("manual_check_priority") == "high":
        metrics = cross_explanation.get("metrics_requiring_review") or []
        checks.append(
            {
                "priority": "high",
                "area": "filings",
                "check": "Review material SEC/yfinance metric differences by filing period and provider normalization.",
                "reason": f"{len(metrics)} comparable metric(s) require review before increasing validation confidence.",
            }
        )
    if has_mock and not profile_live:
        checks.append(
            {
                "priority": "high",
                "area": "source_quality",
                "check": "Verify company profile and fundamentals with live company data.",
                "reason": "Mock evidence is present in score-critical candidate fields.",
            }
        )
    qualitative = response.qualitative_evidence_assessment
    comparison = response.comparison_evidence_assessment
    if qualitative.evidence_count:
        if qualitative.unreviewed_active_count:
            checks.append(
                {
                    "priority": "high",
                    "area": "qualitative_evidence",
                    "check": "Review saved manual evidence before relying on qualitative criteria.",
                    "reason": "Saved manual evidence marked unreviewed remains preliminary.",
                }
            )
        if qualitative.stale_count:
            checks.append(
                {
                    "priority": "high",
                    "area": "qualitative_evidence",
                    "check": "Refresh stale manual evidence or archive it.",
                    "reason": "Stale manual qualitative evidence is capped and needs a current source review.",
                }
            )
        if qualitative.low_quality_count or qualitative.incomplete_count:
            checks.append(
                {
                    "priority": "medium",
                    "area": "qualitative_evidence",
                    "check": "Improve evidence with source label, date, limitations, and competitive context.",
                    "reason": "Low or incomplete manual evidence has limited scoring impact.",
                }
            )
        if qualitative.reviewed_active_count:
            checks.append(
                {
                    "priority": "medium",
                    "area": "qualitative_evidence",
                    "check": "Reconfirm saved evidence is still current.",
                    "reason": "Reviewed manual evidence can become stale as company context changes.",
                }
            )
        if "source_date" in qualitative.missing_data:
            checks.append(
                {
                    "priority": "medium",
                    "area": "qualitative_evidence",
                    "check": "Add or verify source date for manual evidence.",
                    "reason": "Manual qualitative evidence without a source date has weaker audit value.",
                }
            )
        checks.extend(
            [
                {
                    "priority": "high",
                    "area": "qualitative_evidence",
                    "check": "Verify reliability of the supplied qualitative evidence sources.",
                    "reason": "User-provided qualitative evidence is preliminary until manually reviewed.",
                },
                {
                    "priority": "high",
                    "area": "filings",
                    "check": "Confirm supplied qualitative claims in the latest 10-K/10-Q or official company material.",
                    "reason": "Manual evidence should be checked against official disclosures where possible.",
                },
                {
                    "priority": "medium",
                    "area": "qualitative_evidence",
                    "check": "Compare supplied moat, innovation, or network claims against competitors.",
                    "reason": "Qualitative claims need competitive context before they can support higher confidence.",
                },
                {
                    "priority": "medium",
                    "area": "qualitative_evidence",
                    "check": "Verify the date relevance of supplied qualitative evidence.",
                    "reason": "Older qualitative claims may not reflect the current business position.",
                },
            ]
        )
    if comparison.comparison_evidence_count:
        checks.extend(
            [
                {
                    "priority": "high",
                    "area": "qualitative_evidence",
                    "check": "Verify peer list and comparison basis for manual comparison evidence.",
                    "reason": "User-provided peer comparison is not independently verified by the system.",
                },
                {
                    "priority": "medium",
                    "area": "qualitative_evidence",
                    "check": "Confirm market share, capability, or ecosystem claims from official filings or reputable sources.",
                    "reason": "Comparison evidence can only support preliminary Jane criteria until claims are manually validated.",
                },
            ]
        )
        if comparison.claimed_advantage_breakdown.get("stronger"):
            checks.append(
                {
                    "priority": "high",
                    "area": "qualitative_evidence",
                    "check": "Verify whether claimed stronger comparison evidence is measurable and current.",
                    "reason": "Claimed advantage requires current peer context and specific support.",
                }
            )
        if comparison.stale_comparison_count:
            checks.append(
                {
                    "priority": "high",
                    "area": "qualitative_evidence",
                    "check": "Refresh stale comparison evidence or archive it.",
                    "reason": "Stale comparison evidence has capped impact.",
                }
            )
        if "comparison_peer_companies" in comparison.missing_data:
            checks.append(
                {
                    "priority": "medium",
                    "area": "qualitative_evidence",
                    "check": "Add peer company list to comparison evidence.",
                    "reason": "Comparison evidence without peers has limited support for moat or network-effect criteria.",
                }
            )
    else:
        checks.extend(
            [
                {
                    "priority": "high",
                    "area": "qualitative_evidence",
                    "check": "Provide or verify market share / moat source evidence.",
                    "reason": "Monopoly and moat criteria remain insufficient without structured source-backed evidence.",
                },
                {
                    "priority": "high",
                    "area": "qualitative_evidence",
                    "check": "Provide or verify founder/CEO tenure source evidence.",
                    "reason": "Founder and management quality remain insufficient without structured evidence.",
                },
                {
                    "priority": "medium",
                    "area": "qualitative_evidence",
                    "check": "Provide or verify product disruption source evidence.",
                    "reason": "Disruptive innovation remains insufficient without specific product or adoption evidence.",
                },
                {
                    "priority": "medium",
                    "area": "qualitative_evidence",
                    "check": "Provide or verify network effect / ecosystem source evidence.",
                    "reason": "Network effect remains insufficient without platform, developer, customer, or switching-cost evidence.",
                },
                {
                    "priority": "medium",
                    "area": "qualitative_evidence",
                    "check": "Provide or verify patent or R&D source evidence.",
                    "reason": "R&D and innovation support should be tied to filings or specific manual sources.",
                },
            ]
        )
    if not comparison.comparison_evidence_count:
        checks.append(
            {
                "priority": "medium",
                "area": "qualitative_evidence",
                "check": "Provide competitor comparison evidence for monopoly, network, disruption, or trend-fit criteria.",
                "reason": "Jane qualitative criteria need structured peer context before they can gain stronger preliminary support.",
            }
        )
    checks.extend(
        [
            {
                "priority": "high",
                "area": "leadership",
                "check": "Verify moat / monopoly power through market share, patents, or ecosystem evidence.",
                "reason": "Monopoly and moat criteria are insufficient until public evidence is reviewed.",
            },
            {
                "priority": "high",
                "area": "leadership",
                "check": "Verify founder/CEO quality and management tenure from public company sources.",
                "reason": "Legacy leadership_score is mock-based and retained only for backward compatibility.",
            },
            {
                "priority": "medium" if fundamentals_live else "high",
                "area": "filings",
                "check": "Verify R&D intensity and product roadmap from latest 10-K/10-Q.",
                "reason": "Continuous R&D and product evidence require filing-level validation.",
            },
            {
                "priority": "medium",
                "area": "company_fundamentals",
                "check": "Check whether network effects are supported by customer/platform/ecosystem evidence.",
                "reason": "Network effect is insufficient without ecosystem or usage evidence.",
            },
            {
                "priority": "medium",
                "area": "filings",
                "check": "Cross-check yfinance fundamentals against SEC filings.",
                "reason": "Yfinance fundamentals are MVP research reference data and should be checked against official filings.",
            },
            {
                "priority": "medium",
                "area": "filings",
                "check": "Review receivables, inventory, OCF, and CapEx trends from official filings.",
                "reason": "Missing detailed statement fields are marked insufficient instead of inferred.",
            },
            {
                "priority": "medium",
                "area": "smart_money",
                "check": "Confirm whether SEC Form 4 evidence is cached or fallback-limited and whether recent filings exist.",
                "reason": "Form 4 source quality can materially affect smart-money interpretation.",
            },
            {
                "priority": "medium",
                "area": "filings",
                "check": "Confirm whether the configured 13F manager reports a candidate-specific position.",
                "reason": "Portfolio context alone is not candidate-specific 13F support.",
            },
            {
                "priority": "medium",
                "area": "valuation",
                "check": "Validate valuation context before raising research priority.",
                "reason": "Valuation uses preliminary proxy context in this phase.",
            },
        ]
    )
    legacy_mock_present = bool(getattr(response.leadership_score, "deprecated", False) or _status_dict(response.leadership_score.source_status).get("source_type") == "mock")
    if legacy_mock_present:
        checks.append(
            {
                "priority": "low",
                "area": "leadership",
                "check": "Treat legacy mock leadership as deprecated audit context only.",
                "reason": "jane_company_quality replaces legacy_leadership_score and the legacy row does not affect final score.",
            }
        )
    smart_breakdown = response.smart_money.source_quality_breakdown or {}
    if (smart_breakdown.get("form4") or {}).get("fallback_used"):
        checks.append(
            {
                "priority": "high",
                "area": "smart_money",
                "check": "Review Form 4 source quality before interpreting smart-money evidence.",
                "reason": "Form 4 fallback or cached-after-failure limits smart-money confidence.",
            }
        )
    if response.valuation_context.label == "elevated":
        checks.append(
            {
                "priority": "medium",
                "area": "valuation",
                "check": "Review elevated valuation proxy metrics against growth and peer context.",
                "reason": "Valuation risk appears elevated under available proxy metrics and is research context only.",
            }
        )
    priority_weight = {"high": 0, "medium": 1, "low": 2}
    area_weight = {"source_quality": 0, "filings": 1, "smart_money": 2, "qualitative_evidence": 3, "leadership": 4, "valuation": 5, "company_fundamentals": 6, "risk": 7}
    blocking_phrases = ("divergence", "fallback", "mock", "missing", "stale", "unreviewed", "source quality")
    related_by_area = {
        "source_quality": "data_quality_summary",
        "filings": "fundamentals_cross_check",
        "smart_money": "smart_money",
        "qualitative_evidence": "qualitative_evidence",
        "leadership": "jane_company_quality",
        "valuation": "valuation_context",
        "company_fundamentals": "financial_statement_signals",
        "risk": "risk_flags",
    }
    deduped = []
    seen: set[tuple[str, str]] = set()
    for check in checks:
        key = (str(check.get("area")), " ".join(str(check.get("check", "")).lower().split()))
        if key in seen:
            continue
        seen.add(key)
        text = f"{check.get('check', '')} {check.get('reason', '')}".lower()
        blocking = check.get("priority") == "high" and any(phrase in text for phrase in blocking_phrases)
        area = str(check.get("area") or "source_quality")
        enriched = {
            **check,
            "blocking": blocking,
            "category": area,
            "related_evidence_category": related_by_area.get(area),
            "reason_short": str(check.get("reason", ""))[:140],
        }
        deduped.append(enriched)
    deduped.sort(key=lambda item: (priority_weight.get(item["priority"], 9), 0 if item["blocking"] else 1, area_weight.get(item["area"], 9), item["check"]))
    for index, item in enumerate(deduped, start=1):
        item["priority_rank"] = index
    return deduped


def _build_score_driver_breakdown(response: AnalyzeStockResponse) -> dict:
    positive = []
    limiting = []
    neutral = []
    macro_quality = next(
        (
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in response.evidence_matrix
            if (item.category if hasattr(item, "category") else item.get("category")) == "macro_environment"
        ),
        {},
    )
    if response.macro_regime.score >= 56:
        positive.append(
            {
                "name": "macro_v12_5_environment",
                "category": "macro_environment",
                "effect": "positive",
                "source_quality": macro_quality.get("source_quality", "derived_live"),
                "summary": "Macro environment is neutral-to-constructive using active scored components.",
            }
        )
    sec_metric_count = sum(1 for item in (response.sec_financial_facts.get("facts") or {}).values() if item)
    agreement = response.fundamentals_cross_check.get("agreement_level")
    if sec_metric_count >= 4:
        positive.append(
            {
                "name": "sec_filing_backed_financial_quality",
                "category": "sec_financial_facts",
                "effect": "positive",
                "source_quality": "filing_backed",
                "summary": "SEC Companyfacts provides filing-backed support for multiple financial metrics.",
            }
        )
    if agreement in {"high", "moderate"}:
        positive.append(
            {
                "name": "fundamentals_cross_check_consistent",
                "category": "fundamentals_cross_check",
                "effect": "positive",
                "source_quality": "derived_from_mixed_sources",
                "summary": "Comparable SEC Companyfacts and yfinance metrics are directionally consistent.",
            }
        )
    elif agreement == "low":
        limiting.append(
            {
                "name": "fundamentals_cross_check_divergent",
                "category": "fundamentals_cross_check",
                "effect": "limiting",
                "source_quality": "derived_from_mixed_sources",
                "summary": response.fundamentals_cross_check.get("summary") or "SEC Companyfacts and yfinance show material comparable differences that need review.",
            }
        )
    qualitative = response.qualitative_evidence_assessment
    comparison = response.comparison_evidence_assessment
    if qualitative.reviewed_active_count:
        positive.append(
            {
                "name": "reviewed_manual_qualitative_evidence",
                "category": "qualitative_evidence",
                "effect": "preliminary_positive",
                "source_quality": "user_provided",
                "summary": f"Reviewed manual evidence preliminarily covers {', '.join(qualitative.criteria_covered)} and remains user-provided.",
            }
        )
    if qualitative.unreviewed_active_count:
        positive.append(
            {
                "name": "saved_manual_qualitative_evidence",
                "category": "qualitative_evidence",
                "effect": "preliminary_positive",
                "source_quality": "user_provided",
                "summary": f"Saved manual evidence preliminarily covers {', '.join(qualitative.criteria_covered)} and requires review.",
            }
        )
    if qualitative.request_evidence_count:
        positive.append(
            {
                "name": "request_scoped_qualitative_evidence",
                "category": "qualitative_evidence",
                "effect": "preliminary_positive",
                "source_quality": "user_provided",
                "summary": f"User-provided qualitative evidence preliminarily covers {', '.join(qualitative.criteria_covered)}.",
            }
        )
        positive.append(
            {
                "name": "user_provided_qualitative_evidence",
                "category": "qualitative_evidence",
                "effect": "preliminary_positive",
                "source_quality": "user_provided",
                "summary": f"Request-scoped user-provided qualitative evidence preliminarily covers {', '.join(qualitative.criteria_covered)}.",
            }
        )
    if comparison.reviewed_comparison_count:
        positive.append(
            {
                "name": "reviewed_comparison_evidence",
                "category": "comparison_evidence",
                "effect": "preliminary_positive",
                "source_quality": "user_provided",
                "summary": f"Reviewed user-provided comparison evidence preliminarily supports {', '.join(comparison.criteria_supported)} and still requires independent source review.",
            }
        )
    unreviewed_comparison_count = sum(1 for item in comparison.items if item.accepted and item.review_status != "reviewed")
    if unreviewed_comparison_count:
        positive.append(
            {
                "name": "unreviewed_comparison_evidence",
                "category": "comparison_evidence",
                "effect": "preliminary_positive",
                "source_quality": "user_provided",
                "summary": "Unreviewed user-provided comparison evidence is available for preliminary peer context.",
            }
        )
    if qualitative.rejected_evidence_count:
        limiting.append(
            {
                "name": "qualitative_evidence_rejected_or_incomplete",
                "category": "qualitative_evidence",
                "effect": "limiting",
                "source_quality": "user_provided",
                "summary": "One or more qualitative evidence items were rejected or incomplete and do not affect scoring.",
            }
        )
    if qualitative.unreviewed_active_count:
        limiting.append(
            {
                "name": "unreviewed_manual_evidence_requires_review",
                "category": "qualitative_evidence",
                "effect": "limiting",
                "source_quality": "user_provided",
                "summary": "Unreviewed manual evidence requires local validation before qualitative criteria can carry more confidence.",
            }
        )
    if qualitative.stale_count:
        limiting.append(
            {
                "name": "stale_manual_evidence_requires_refresh",
                "category": "qualitative_evidence",
                "effect": "limiting",
                "source_quality": "user_provided",
                "summary": "Stale manual evidence is capped and should be refreshed or archived.",
            }
        )
    if comparison.stale_comparison_count:
        limiting.append(
            {
                "name": "comparison_evidence_stale",
                "category": "comparison_evidence",
                "effect": "limiting",
                "source_quality": "user_provided",
                "summary": "Stale comparison evidence is capped and should be refreshed or archived.",
            }
        )
    if any(item.accepted and not item.peer_companies for item in comparison.items):
        limiting.append(
            {
                "name": "comparison_evidence_missing_peers",
                "category": "comparison_evidence",
                "effect": "limiting",
                "source_quality": "user_provided",
                "summary": "Some comparison evidence lacks peer companies, limiting moat or network-effect support.",
            }
        )
    if qualitative.incomplete_count:
        limiting.append(
            {
                "name": "incomplete_manual_evidence",
                "category": "qualitative_evidence",
                "effect": "limiting",
                "source_quality": "user_provided",
                "summary": "Incomplete manual evidence has limited impact until source details and limitations improve.",
            }
        )
    if qualitative.archived_or_rejected_ignored_count:
        limiting.append(
            {
                "name": "qualitative_evidence_rejected_or_archived",
                "category": "qualitative_evidence",
                "effect": "limiting",
                "source_quality": "user_provided",
                "summary": "Archived or rejected manual evidence is stored for audit but ignored for analyze-stock scoring.",
            }
        )
    if response.sec_financial_facts.get("missing_data"):
        limiting.append(
            {
                "name": "sec_companyfacts_missing_concepts",
                "category": "sec_financial_facts",
                "effect": "insufficient",
                "source_quality": "filing_backed" if sec_metric_count else "insufficient",
                "summary": "Some SEC Companyfacts concepts are unavailable and are listed as missing data.",
            }
        )
    else:
        neutral.append(
            {
                "name": "macro_v12_5_environment",
                "category": "macro_environment",
                "effect": "insufficient" if response.macro_regime.label == "insufficient_data" else "limiting",
                "source_quality": macro_quality.get("source_quality", "insufficient"),
                "summary": "Macro environment is not a strong positive driver in the current score.",
            }
        )
    limiting.append(
        {
            "name": "legacy_leadership_mock_replaced",
            "category": "legacy_leadership_score",
            "effect": "limiting",
            "source_quality": "mock_only",
            "summary": "Legacy leadership evidence remains mock-only and is replaced by evidence-based Jane company quality criteria.",
        }
    )
    criteria_by_name = {criterion.name: criterion for criterion in response.jane_company_quality.criteria}
    for criterion_name, driver_name in [
        ("monopoly_power", "qualitative_moat_evidence_insufficient"),
        ("visionary_founder_ceo", "founder_ceo_evidence_insufficient"),
        ("network_effect", "network_effect_evidence_insufficient"),
        ("disruptive_innovation", "disruptive_innovation_evidence_insufficient"),
    ]:
        criterion = criteria_by_name.get(criterion_name)
        if criterion and criterion.status == "insufficient":
            limiting.append(
                {
                    "name": driver_name,
                    "category": "jane_company_quality",
                    "effect": "insufficient",
                    "source_quality": criterion.source_quality,
                    "summary": f"{criterion.display_name} is marked insufficient because required qualitative evidence is unavailable.",
                }
            )
    for criterion_name, driver_name in [
        ("scalability", "scalability_from_financials"),
        ("balance_sheet_strength", "balance_sheet_strength"),
        ("cash_flow_quality", "cash_flow_quality"),
    ]:
        criterion = criteria_by_name.get(criterion_name)
        if criterion and criterion.status == "supportive":
            positive.append(
                {
                    "name": driver_name,
                    "category": "jane_company_quality",
                    "effect": "positive",
                    "source_quality": criterion.source_quality,
                    "summary": f"{criterion.display_name} is supported by available financial metrics.",
                }
            )
    thirteen_f = response.institutional_13f.get("candidate_specific_evidence") or {}
    if thirteen_f.get("matched_in_13f") and thirteen_f.get("score_contribution_allowed"):
        positive.append(
            {
                "name": "candidate_specific_13f_match",
                "category": "institutional_13f",
                "effect": "positive",
                "source_quality": _source_quality_from_status(_status_dict(response.institutional_13f.get("source_status"))),
                "summary": "Candidate-specific 13F evidence is present and allowed to contribute.",
            }
        )
    else:
        neutral.append(
            {
                "name": "candidate_specific_13f_no_match",
                "category": "institutional_13f",
                "effect": "limiting",
                "source_quality": _source_quality_from_status(_status_dict(response.institutional_13f.get("source_status"))),
                "summary": "No candidate-specific 13F match contributes to the score; portfolio context remains audit context only.",
            }
        )
    if response.insider_activity.get("source_quality") in {"mixed_with_fallback", "insufficient"}:
        limiting.append(
            {
                "name": "form4_limited_source_quality",
                "category": "insider_activity",
                "effect": "limiting",
                "source_quality": response.insider_activity.get("source_quality", "insufficient"),
                "summary": "Form 4 evidence is limited by fallback, cached-after-failure, or insufficient source context.",
            }
        )
    financial_quality = _source_quality_from_status(_status_dict(response.financial_quality.source_status))
    if financial_quality in {"live_backed", "cached_live", "derived_live"} and response.financial_quality.derived_metrics.get("available_core_metric_count", 0) >= 3:
        target = positive if response.financial_quality.score >= 65 else neutral
        target.append(
            {
                "name": "live_financial_quality",
                "category": "financial_quality",
                "effect": "positive" if response.financial_quality.score >= 65 else "limiting",
                "source_quality": financial_quality,
                "summary": "Financial quality uses live or cached company fundamentals with core metrics available.",
            }
        )
    else:
        neutral.append(
            {
                "name": "financial_quality_not_live_confirmed",
                "category": "financial_quality",
                "effect": "insufficient",
                "source_quality": financial_quality,
                "summary": "Missing or mock fundamentals do not contribute as a positive driver.",
            }
        )
    valuation_quality = _source_quality_from_status(_status_dict(response.valuation_context.source_status))
    if response.valuation_context.label == "elevated":
        limiting.append(
            {
                "name": "valuation_context_elevated",
                "category": "valuation_context",
                "effect": "limiting",
                "source_quality": valuation_quality,
                "summary": "Elevated valuation is treated as research risk context only.",
            }
        )
    if response.missing_data:
        limiting.append(
            {
                "name": "missing_data",
                "category": "source_quality",
                "effect": "insufficient",
                "source_quality": response.data_quality_summary.source_quality_grade,
                "summary": "Missing data keeps the report at preliminary validation level.",
            }
        )
    return {
        "final_score": response.research_verdict.score,
        "final_confidence": response.research_verdict.confidence,
        "positive_drivers": positive,
        "negative_or_limiting_drivers": limiting,
        "neutral_drivers": neutral,
    }


def _build_candidate_summary(response: AnalyzeStockResponse) -> dict:
    dq = response.data_quality_summary
    leadership_mock = "legacy_leadership_score" in dq.mock_evidence_categories
    company_mock = "company_profile" in dq.mock_evidence_categories
    fundamentals_mock = "financial_quality" in dq.mock_evidence_categories
    company_live = not company_mock and "company_profile" not in dq.fallback_evidence_categories
    fundamentals_live = not fundamentals_mock and "financial_quality" not in dq.fallback_evidence_categories
    sec_available = bool(dq.sec_companyfacts.get("available"))
    sec_agreement = dq.sec_companyfacts.get("agreement_level_with_yfinance", "insufficient")
    sec_invalid = bool(response.sec_financial_facts.get("invalid_derived_metrics"))
    smart_limited = "smart_money" in dq.fallback_evidence_categories or "insider_activity" in dq.fallback_evidence_categories
    qualitative = response.qualitative_evidence_assessment
    comparison = response.comparison_evidence_assessment
    strengths = []
    if response.macro_regime.score >= 56:
        strengths.append("Macro context is neutral-to-constructive under macro_v12_5.")
    if response.smart_money.score >= 50:
        strengths.append("Aggregate smart-money score is neutral or better, with source limitations disclosed.")
    if company_live:
        strengths.append("Company profile is live or cached-live instead of mock-only.")
    if fundamentals_live:
        strengths.append("Financial quality includes live or cached fundamentals context.")
    if sec_available:
        strengths.append("SEC Companyfacts filing-backed financial facts are available for cross-checking.")
    if sec_agreement in {"high", "moderate"}:
        strengths.append("SEC Companyfacts and yfinance are directionally consistent for comparable metrics.")
    supportive_quality = [criterion for criterion in response.jane_company_quality.criteria if criterion.status == "supportive"]
    if any(criterion.name == "scalability" for criterion in supportive_quality):
        strengths.append("Live financial quality supports scalability under Jane company quality criteria.")
    if any(criterion.name == "financial_statement_quality" for criterion in supportive_quality):
        strengths.append("Revenue growth, margin, or free cash flow metrics support financial statement quality.")
    if qualitative.accepted_evidence_count:
        origin_parts = []
        if qualitative.saved_evidence_count:
            origin_parts.append(f"{qualitative.saved_evidence_count} saved library item(s)")
        if qualitative.request_evidence_count:
            origin_parts.append(f"{qualitative.request_evidence_count} request-scoped item(s)")
        strengths.append(f"User-provided qualitative evidence from {' and '.join(origin_parts) or 'manual input'} preliminarily supports {', '.join(qualitative.criteria_covered)}.")
    if comparison.accepted_comparison_count:
        strengths.append(f"User-provided comparison evidence preliminarily supports {', '.join(comparison.criteria_supported)} with peer context requiring manual verification.")
    risks = []
    if leadership_mock:
        risks.append("Legacy leadership evidence is mock-based and cannot confirm live leadership quality.")
    if "monopoly_power" in dq.insufficient_evidence_categories:
        risks.append("Qualitative moat/founder/network/disruption evidence remains insufficient.")
    if qualitative.accepted_evidence_count:
        risks.append("Manual validation required for user-provided qualitative claims.")
    if comparison.accepted_comparison_count:
        risks.append("Manual validation required for user-provided comparison claims and peer lists.")
    if qualitative.rejected_evidence_count:
        risks.append("Some qualitative evidence was rejected or incomplete and does not affect scoring.")
    if company_mock:
        risks.append("Company profile remains mock-based.")
    if fundamentals_mock:
        risks.append("Financial quality remains mock-based or incomplete.")
    if sec_invalid:
        risks.append("SEC Companyfacts is available, but some derived metrics require period-alignment review.")
    if sec_agreement == "low":
        risks.append("SEC Companyfacts and yfinance show material discrepancies requiring review.")
    if smart_limited:
        risks.append("Smart-money evidence includes fallback or cached-limited components.")
    if response.risk_flags:
        risks.extend(response.risk_flags[:3])
    missing_or_mock = sorted(
        set(
            [
                *dq.fallback_evidence_categories,
                *response.missing_data[:5],
                *(["founder_ceo_evidence"] if "visionary_founder_ceo" in dq.insufficient_evidence_categories else []),
                *(["moat_or_patent_evidence"] if "monopoly_power" in dq.insufficient_evidence_categories else []),
                *(["network_effect_evidence"] if "network_effect" in dq.insufficient_evidence_categories else []),
                *(["disruptive_innovation_evidence"] if "disruptive_innovation" in dq.insufficient_evidence_categories else []),
                *(["R&D evidence"] if "continuous_r_and_d" in dq.insufficient_evidence_categories else []),
            ]
        )
    )
    env = f"Macro environment is {response.macro_regime.label} with {response.macro_regime.confidence:.2f} confidence."
    if company_live and fundamentals_live:
        company = "Live company profile and fundamentals are available; SEC filing-backed financial facts are available." if sec_available else "Live company profile and fundamentals are available; Jane company quality is partially evidence-backed by financial metrics, while qualitative moat/founder/network/disruption evidence remains insufficient."
        if sec_invalid:
            company = f"{company} SEC Companyfacts is available, but some derived metrics require period-alignment review."
        if qualitative.accepted_evidence_count:
            company = f"{company} SEC/yfinance agreement is {sec_agreement}; saved manual evidence count is {qualitative.saved_evidence_count}, request-scoped evidence count is {qualitative.request_evidence_count}, comparison evidence count is {comparison.accepted_comparison_count}, and covered qualitative criteria still require manual verification."
        else:
            company = f"{company} SEC/yfinance agreement is {sec_agreement}; qualitative moat/founder/network/disruption evidence remains insufficient."
    elif company_live:
        company = "Live company profile is available; fundamentals and qualitative Jane company quality evidence still need verification."
    else:
        company = "Company evidence remains preliminary because profile, fundamentals, or qualitative company-quality data is incomplete."
    smart = "Smart-money assessment is limited by fallback or cached components." if smart_limited else f"Smart-money assessment is {response.smart_money.label}."
    overall = (
        f"{response.ticker} qualifies as a {response.research_verdict.label} research candidate under the current validation framework. "
        f"Macro context is {response.macro_regime.label}, company profile/fundamentals evidence "
        f"{'uses live or cached sources' if company_live and fundamentals_live else 'remains partly preliminary'}, Jane company quality "
        f"{'is partially evidence-backed by financial metrics' if response.jane_company_quality.label == 'preliminary' else response.jane_company_quality.label}, and smart-money evidence "
        f"{'includes fallback or cached-limited components' if smart_limited else 'is available with disclosed limitations'}. "
        f"{'User-provided qualitative evidence is preliminary and not independently verified. ' if qualitative.accepted_evidence_count else ''}"
        f"{'User-provided comparison evidence requires peer validation. ' if comparison.accepted_comparison_count else ''}"
        "Further manual validation is required before treating the candidate as high conviction."
    )
    return {
        "ticker": response.ticker,
        "research_priority": response.research_verdict.label,
        "score": response.research_verdict.score,
        "confidence": response.research_verdict.confidence,
        "environment_assessment": env,
        "company_assessment": company,
        "smart_money_assessment": smart,
        "data_quality_assessment": f"Source quality grade {dq.source_quality_grade}: {dq.source_quality_summary}",
        "overall_summary": overall,
        "primary_strengths": strengths or ["No primary strengths are live-confirmed yet."],
        "primary_risks": risks or ["No major deterministic risk flags, but manual verification is still required."],
        "missing_or_mock_evidence": missing_or_mock,
        "next_manual_checks": [
            item.check if hasattr(item, "check") else str(item.get("check", ""))
            for item in response.next_manual_checks
        ],
    }


def _build_validation_quality_summary(response: AnalyzeStockResponse) -> dict:
    dq = response.data_quality_summary
    manual_checks = [
        item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
        for item in response.next_manual_checks
    ]
    high_priority = [item for item in manual_checks if item.get("priority") == "high"]
    blocking = [item for item in manual_checks if item.get("blocking")]
    supporting = []
    limiting = []
    if response.macro_regime.score >= 56:
        supporting.append("Macro environment has usable macro_v12_5 context.")
    if response.fundamentals_cross_check.get("agreement_level") in {"high", "moderate"}:
        supporting.append("SEC/yfinance fundamentals cross-check is usable with provider-period caveats.")
    if response.financial_statement_signals.label in {"strong", "adequate"}:
        supporting.append("Financial statement signals provide structured validation context.")
    if response.qualitative_evidence_assessment.accepted_evidence_count:
        supporting.append("User-provided qualitative evidence is available for preliminary validation.")
    if dq.fallback_evidence_categories:
        limiting.append("limited by fallback data")
    if dq.mock_evidence_categories:
        limiting.append("limited by mock or deprecated compatibility evidence")
    if dq.insufficient_evidence_categories:
        limiting.append("insufficient qualitative evidence")
    if response.fundamentals_cross_check.get("agreement_level") == "low":
        limiting.append("SEC/yfinance discrepancy requires manual review")
    if response.valuation_context.label == "elevated":
        limiting.append("valuation risk appears elevated under available proxy metrics")
    if dq.source_quality_grade == "A" and not high_priority and len(response.missing_data) <= 2:
        level = "high_quality_validation"
    elif dq.source_quality_grade == "B":
        level = "usable_preliminary_validation"
    elif dq.source_quality_grade == "C":
        level = "limited_validation"
    else:
        level = "insufficient_validation"
    if dq.fallback_evidence_categories or dq.mock_evidence_categories or response.qualitative_evidence_assessment.accepted_evidence_count:
        level = "usable_preliminary_validation" if level == "high_quality_validation" else level
    if dq.source_quality_grade == "D" or len(response.missing_data) >= 9:
        level = "insufficient_validation"
    why_by_level = {
        "high_quality_validation": "Structured evidence is broad enough for high quality validation, while remaining research-only.",
        "usable_preliminary_validation": "Usable preliminary validation is available, but source constraints or user-provided evidence require manual review.",
        "limited_validation": "Validation is limited by fallback, mock, stale, or incomplete core evidence.",
        "insufficient_validation": "Core evidence is missing or too limited for more than initial triage.",
    }
    cap_reason = dq.confidence_cap_reason
    return {
        "ticker": response.ticker,
        "overall_validation_level": level,
        "why": why_by_level[level],
        "primary_supporting_evidence": supporting[:6] or ["No primary supporting evidence is strong enough to highlight yet."],
        "primary_limiting_factors": sorted(set(limiting))[:8] or ["Manual review is still required before increasing validation confidence."],
        "manual_review_required": bool(high_priority or blocking or limiting or response.missing_data),
        "highest_priority_review_items": [item.get("check", "") for item in manual_checks[:5]],
        "data_quality_grade": dq.source_quality_grade,
        "confidence_cap_applied": dq.confidence_cap_applied,
        "confidence_cap_reason": cap_reason,
        "not_investment_advice": True,
    }


def _build_validation_os_report(response: AnalyzeStockResponse) -> dict:
    coverage = response.jane_criteria_coverage
    validation = response.validation_quality_summary
    candidate = response.candidate_validation_summary
    dq = response.data_quality_summary
    manual_checks = [item.check for item in response.next_manual_checks[:6]]
    gap_rows = [
        item
        for item in coverage.criteria
        if item.coverage_status in {"partial", "insufficient"}
    ]
    gap_rows.sort(key=lambda item: (0 if item.coverage_status == "partial" else 1, item.criterion_id))
    top_gaps = [
        {
            "criterion_id": item.criterion_id,
            "criterion_name": item.criterion_name,
            "coverage_status": item.coverage_status,
            "missing_submetrics": item.missing_submetrics[:6],
            "next_manual_check": item.next_manual_check,
        }
        for item in gap_rows[:6]
    ]
    caveats = []
    if dq.mock_evidence_categories:
        caveats.append(f"Mock or deprecated compatibility evidence remains in: {', '.join(dq.mock_evidence_categories[:5])}.")
    if dq.fallback_evidence_categories:
        caveats.append(f"Fallback evidence remains in: {', '.join(dq.fallback_evidence_categories[:5])}.")
    if dq.missing_source_date_categories:
        caveats.append(f"Missing source dates remain in: {', '.join(dq.missing_source_date_categories[:5])}.")
    if response.qualitative_evidence_assessment.accepted_evidence_count:
        caveats.append("User-provided qualitative evidence is local validation context and still requires source review.")
    if not caveats:
        caveats.append("Source quality caveats are still disclosed; manual verification remains required for research use.")
    coverage_gap_count = coverage.partial_count + coverage.insufficient_count
    report_sections = [
        "candidate_context",
        "macro_backdrop",
        "jane_quality",
        "evidence_coverage",
        "financial_signals",
        "smart_money",
        "manual_verification",
        "source_quality",
    ]
    return {
        "ticker": response.ticker,
        "research_label": response.research_verdict.label,
        "validation_level": validation.overall_validation_level,
        "data_quality_grade": dq.source_quality_grade,
        "report_sections": report_sections,
        "executive_summary": (
            f"{response.ticker} validation workflow summary: {candidate.overall_summary} "
            f"Jane criteria coverage has {coverage.covered_count} covered, {coverage.partial_count} partial, "
            f"and {coverage.insufficient_count} insufficient criteria. Manual verification remains required."
        ),
        "macro_backdrop": candidate.environment_assessment,
        "jane_quality_summary": candidate.company_assessment,
        "jane_criteria_coverage_summary": {
            "covered_count": coverage.covered_count,
            "partial_count": coverage.partial_count,
            "insufficient_count": coverage.insufficient_count,
            "coverage_gap_count": coverage_gap_count,
            "user_input_required_count": coverage.user_input_required_count,
            "financial_proxy_available_count": coverage.financial_proxy_available_count,
            "source_quality_summary": coverage.source_quality_summary,
        },
        "financial_signals_summary": f"Financial statement signals are {response.financial_statement_signals.label} with {response.financial_statement_signals.confidence:.2f} confidence.",
        "smart_money_summary": candidate.smart_money_assessment,
        "top_strengths": candidate.primary_strengths[:6],
        "top_limitations": candidate.primary_risks[:6],
        "top_evidence_gaps": top_gaps,
        "top_manual_checks": manual_checks or validation.highest_priority_review_items[:6] or response.human_verification_queue[:6],
        "source_quality_caveats": caveats,
        "manual_verification_required": bool(validation.manual_review_required or coverage_gap_count or response.human_verification_queue),
        "scoring_note": "Validation OS Report is non-scoring and does not change the final research verdict.",
        "limitations": [
            "This report organizes existing analyze-stock outputs and does not add new data providers.",
            "Coverage and user-provided evidence are research validation context only.",
            "This is not investment advice.",
        ],
        "not_investment_advice": True,
    }


def analyze_stock(request: AnalyzeStockRequest) -> AnalyzeStockResponse:
    fixture = STOCK_FIXTURES.get(request.ticker, DEFAULT_STOCK)
    market_context = read_market_data()
    macro_snapshot = read_macro_data("normal", market_context_seed=market_context)
    macro_regime = evaluate_macro_regime(macro_snapshot)
    sec_filings = read_sec_filings(request.ticker)
    company_profile = get_company_profile(request.ticker)
    yfinance_fundamentals = get_company_fundamentals(request.ticker)
    sec_financial_facts = get_sec_companyfacts(request.ticker)
    fundamentals_cross_check = _build_fundamentals_cross_check(sec_financial_facts, yfinance_fundamentals)
    company_fundamentals = _merge_financials_with_sec(yfinance_fundamentals, sec_financial_facts, fundamentals_cross_check)
    smart_money_data = {**fixture["smart_money"], **sec_filings}
    engine_context = {
        **fixture,
        **market_context,
        "user_reported_social_heat": request.user_context.social_discussion_level,
        "friends_asking_about_stock": request.user_context.friends_asking_about_stock,
    }
    missing_data = list(fixture["missing_data"])
    if company_profile.get("source_status", {}).get("source_type") not in {"live", "cached_live", "derived"}:
        missing_data.append("live yfinance company profile")
    if company_fundamentals.get("source_status", {}).get("source_type") not in {"live", "cached_live", "derived"}:
        missing_data.append("live yfinance fundamentals")
    if sec_financial_facts.get("source_status", {}).get("source_type") not in {"live", "cached_live"}:
        missing_data.append("SEC Companyfacts filing-backed fundamentals")
    missing_data.extend(company_profile.get("missing_data", []))
    missing_data.extend(company_fundamentals.get("missing_data", []))
    if market_context.get("source_type") != "live":
        missing_data.append("live price history")
    if sec_filings.get("form4_source_status", {}).get("source_type") not in {"live", "cached_live"}:
        missing_data.append("live SEC filing details")
    if sec_filings.get("institutional_13f_source_status", {}).get("source_type") not in {"live", "cached_live"}:
        missing_data.append("live SEC 13F data")
    missing_data.extend(macro_regime.missing_data)
    missing_data = sorted(set(missing_data))
    leadership_score = evaluate_leadership({"ticker": request.ticker, **fixture})
    legacy_limitation = "Legacy leadership_score is mock-based and is retained for backward compatibility only."
    if legacy_limitation not in leadership_score.limitations:
        leadership_score.limitations.append(legacy_limitation)
    leadership_score.deprecated_by = "jane_company_quality"
    leadership_score.deprecated = True
    leadership_score.replaced_by = "jane_company_quality"
    leadership_score.affects_score = False
    leadership_score.legacy_affects_score = False
    leadership_score.affects_final_score = False
    leadership_score.source_quality = "mock_only"
    market_timing_context = evaluate_market_timing(engine_context)
    overheat_risk = evaluate_overheat(engine_context)
    smart_money = evaluate_smart_money(smart_money_data)
    insider_activity = smart_money.derived_metrics["components"]["insider_form4_signal"]
    institutional_13f = smart_money.derived_metrics["components"]["institutional_support_13f"]
    if not hasattr(insider_activity, "model_dump"):
        insider_activity = ScoreObject.model_validate(insider_activity)
    if not hasattr(institutional_13f, "model_dump"):
        institutional_13f = ScoreObject.model_validate(institutional_13f)
    leadership_status = build_source_status(leadership_score.model_dump(mode="json"))
    leadership_score.source_status = leadership_status
    company_profile_status = build_source_status(company_profile)
    financial_quality = _build_financial_quality_score(company_fundamentals)
    valuation_context = _build_valuation_context(company_profile, company_fundamentals)
    research_context = request.research_context.model_dump(exclude_none=True) if request.research_context else {}
    saved_manual_evidence = load_manual_evidence_for_ticker(request.ticker)
    qualitative_evidence_assessment = _build_qualitative_evidence_assessment(request.ticker, request.qualitative_evidence, saved_manual_evidence)
    comparison_evidence_assessment = _build_comparison_evidence_assessment(request.ticker, qualitative_evidence_assessment)
    jane_company_quality = _build_jane_company_quality(financial_quality, research_context, qualitative_evidence_assessment)
    financial_statement_signals = _build_financial_statement_signals(financial_quality)
    quality_insufficient = [criterion.name for criterion in jane_company_quality.criteria if criterion.status == "insufficient"]
    missing_data.extend(
        [
            *(["founder_ceo_evidence"] if "visionary_founder_ceo" in quality_insufficient else []),
            *(["moat_or_patent_evidence"] if "monopoly_power" in quality_insufficient else []),
            *(["network_effect_evidence"] if "network_effect" in quality_insufficient else []),
            *(["disruptive_innovation_evidence"] if "disruptive_innovation" in quality_insufficient else []),
            *(["R&D evidence"] if "continuous_r_and_d" in quality_insufficient else []),
        ]
    )
    missing_data.extend(qualitative_evidence_assessment.get("missing_data", []))
    missing_data = sorted(set(missing_data))
    form4_status = sec_filings.get("form4_source_status", {})
    thirteen_f_status = sec_filings.get("institutional_13f_source_status", {})
    mock_evidence_present = (
        leadership_status.source_type == "mock"
        or company_profile_status.source_type == "mock"
        or bool(financial_quality.source_status and financial_quality.source_status.source_type == "mock")
        or market_context.get("source_type") in {"mock", "fallback"}
    )
    fallback_evidence_present = any(
        status.get("fallback_used") or status.get("source_type") == "fallback"
        for status in [
            form4_status,
            thirteen_f_status,
            _status_dict(smart_money.source_status),
            _status_dict(company_profile.get("source_status")),
            _status_dict(financial_quality.source_status),
            _status_dict(valuation_context.source_status),
        ]
        if status
    )
    macro_provider = macro_regime.source_status.provider if macro_regime.source_status else ""
    live_macro_present = macro_provider == "mixed_FRED_and_yfinance_macro" or macro_regime.source_status and macro_regime.source_status.source_type in {"live", "cached_live", "derived"}
    research_verdict = _research_verdict(
        company_quality_score=jane_company_quality.score,
        company_quality_confidence=jane_company_quality.confidence,
        key_qualitative_insufficient=any(
            name in quality_insufficient
            for name in ["monopoly_power", "visionary_founder_ceo", "network_effect", "disruptive_innovation"]
        ),
        smart_money_score=smart_money.score,
        macro_score=macro_regime.score,
        overheat_score=overheat_risk.score,
        missing_data_count=len(missing_data),
        confidence_inputs=[leadership_score.confidence, smart_money.confidence, macro_regime.confidence, overheat_risk.confidence, financial_quality.confidence],
        mock_evidence_present=mock_evidence_present,
        fallback_evidence_present=fallback_evidence_present,
        live_macro_present=bool(live_macro_present),
        user_qualitative_evidence_present=bool(qualitative_evidence_assessment.get("accepted_evidence_count")),
    )
    insider_activity_payload = _build_insider_activity(insider_activity)
    institutional_13f_payload = _build_institutional_13f(institutional_13f, request.ticker, sec_filings)
    smart_money.source_quality_breakdown = _smart_money_source_quality_breakdown(smart_money, insider_activity_payload, institutional_13f_payload)

    response = AnalyzeStockResponse(
        ticker=request.ticker,
        analysis_mode="ticker_validation",
        research_verdict=research_verdict,
        candidate_validation_summary={
            "ticker": request.ticker,
            "research_priority": research_verdict.label,
            "score": research_verdict.score,
            "confidence": research_verdict.confidence,
            "environment_assessment": "Pending evidence composition.",
            "company_assessment": "Pending evidence composition.",
            "smart_money_assessment": "Pending evidence composition.",
            "data_quality_assessment": "Pending evidence composition.",
            "overall_summary": "Pending evidence composition.",
            "primary_strengths": [],
            "primary_risks": [],
            "missing_or_mock_evidence": [],
            "next_manual_checks": [],
        },
        validation_quality_summary={
            "ticker": request.ticker,
            "overall_validation_level": "insufficient_validation",
            "why": "Pending evidence composition.",
            "primary_supporting_evidence": [],
            "primary_limiting_factors": [],
            "manual_review_required": True,
            "highest_priority_review_items": [],
            "data_quality_grade": "D",
            "confidence_cap_applied": False,
            "confidence_cap_reason": None,
            "not_investment_advice": True,
        },
        evidence_matrix=[],
        data_quality_summary={
            "mode": "insufficient",
            "confidence_cap_applied": False,
            "confidence_cap_reason": None,
            "live_components": 0,
            "mock_components": 0,
            "fallback_components": 0,
            "missing_source_date_components": 0,
            "stale_components": 0,
            "source_quality_grade": "D",
            "source_quality_summary": "Pending evidence composition.",
            "mock_evidence_categories": [],
            "fallback_evidence_categories": [],
            "missing_source_date_categories": [],
            "excluded_from_scoring": [],
        },
        score_driver_breakdown={
            "final_score": research_verdict.score,
            "final_confidence": research_verdict.confidence,
            "positive_drivers": [],
            "negative_or_limiting_drivers": [],
            "neutral_drivers": [],
        },
        next_manual_checks=[],
        qualitative_evidence_assessment=qualitative_evidence_assessment,
        comparison_evidence_assessment=comparison_evidence_assessment,
        company_profile={
            **company_profile,
            "themes": company_profile.get("themes", fixture["themes"]),
            "market_price_source_type": market_context.get("source_type", "mock"),
            "research_context": research_context,
        },
        macro_regime=macro_regime,
        leadership_score=leadership_score,
        jane_company_quality=jane_company_quality,
        financial_statement_signals=financial_statement_signals,
        sec_financial_facts=sec_financial_facts,
        fundamentals_cross_check=fundamentals_cross_check,
        market_timing_context=market_timing_context,
        overheat_risk=overheat_risk,
        smart_money=smart_money,
        insider_activity=insider_activity_payload,
        institutional_13f=institutional_13f_payload,
        financial_quality=financial_quality,
        valuation_context=valuation_context,
        risk_flags=[
            flag
            for flag, present in {
                "valuation_context_elevated": valuation_context.label == "elevated",
                "social_heat_elevated": request.user_context.social_discussion_level == "high",
                "financial_quality_mixed": financial_quality.score < 50,
                "macro_context_cautious": macro_regime.score < 45,
            }.items()
            if present
        ],
        jane_reference_conditions=_build_jane_reference_conditions(macro_snapshot),
        jane_quality_methodology_reference={
            "framework": "Jane 7-principle company quality framework",
            "principles": JANE_QUALITY_PRINCIPLES,
            "affects_score": True,
            "limitations": [
                "Qualitative principles require evidence and are marked insufficient when not verifiable.",
                "User-provided theme is context only and is not independently verified evidence.",
            ],
        },
        missing_data=missing_data,
        human_verification_queue=[
            "Verify company fundamentals with current filings.",
            "Review current news and filings before using this research output.",
        ],
    )
    statuses: list = []
    _enrich_source_status(response, statuses)
    response.source_status = build_source_status(market_context)
    statuses.append(response.source_status)
    response.data_quality = summarize_data_quality(statuses)
    if response.data_quality.mock_components and MOCK_EVIDENCE_LIMITATION not in response.data_quality.limitations:
        response.data_quality.limitations.append(MOCK_EVIDENCE_LIMITATION)
    if macro_regime.macro_data_quality:
        response.data_quality.macro = {
            "provider": macro_regime.source_status.provider if macro_regime.source_status else macro_snapshot.get("provider", "unknown"),
            "live_macro_fields_count": macro_regime.macro_data_quality.live_macro_fields_count,
            "derived_macro_fields_count": macro_regime.macro_data_quality.derived_macro_fields_count,
            "mock_macro_fields_count": macro_regime.macro_data_quality.mock_macro_fields_count,
            "yfinance_macro_fields_count": macro_regime.macro_data_quality.yfinance_macro_fields_count,
            "has_mock_macro_context": macro_regime.macro_data_quality.has_mock_macro_context,
            "mock_context_fields": macro_regime.macro_data_quality.mock_context_fields,
            "fred_backed_fields": macro_regime.macro_data_quality.fred_backed_fields,
            "derived_from_fred_fields": macro_regime.macro_data_quality.derived_from_fred_fields,
            "yfinance_backed_fields": macro_regime.macro_data_quality.yfinance_backed_fields,
            "derived_from_yfinance_fields": macro_regime.macro_data_quality.derived_from_yfinance_fields,
            "excluded_indicators": macro_regime.macro_data_quality.excluded_indicators,
            "scoring": macro_regime.macro_data_quality.scoring,
            "market_context_reused_from_daily_market_data": (macro_regime.raw_data.get("raw_market_context") or {}).get("diagnostics", {}).get("market_context_reused_from_daily_market_data"),
            "confidence_adjustment_applied": macro_regime.macro_data_quality.confidence_adjustment_applied,
        }
    if response.data_quality.fallback_components:
        response.human_verification_queue.append("Review fallback source status because one or more live data sources were unavailable.")
    if response.data_quality.stale_components:
        response.human_verification_queue.append("Review stale live or derived data source status before interpreting scores.")
    if response.data_quality.missing_source_date_components:
        response.human_verification_queue.append("Review components with missing source dates before interpreting scores.")
    response.evidence_matrix = [EvidenceMatrixItem.model_validate(item) for item in _build_evidence_matrix(response)]
    response.jane_criteria_coverage = JaneCriteriaCoverageMatrix.model_validate(_build_jane_criteria_coverage(response))
    response.data_quality_summary = AnalyzeStockDataQualitySummary.model_validate(_build_data_quality_summary(response))
    response.next_manual_checks = [NextManualCheck.model_validate(item) for item in _build_manual_checks(response)]
    response.score_driver_breakdown = ScoreDriverBreakdown.model_validate(_build_score_driver_breakdown(response))
    response.candidate_validation_summary = CandidateValidationSummary.model_validate(_build_candidate_summary(response))
    response.validation_quality_summary = ValidationQualitySummary.model_validate(_build_validation_quality_summary(response))
    response.validation_os_report = ValidationOSReport.model_validate(_build_validation_os_report(response))
    return AnalyzeStockResponse.model_validate(_sanitize_api_secret_markers(response.model_dump(mode="json")))
