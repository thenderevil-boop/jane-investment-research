from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from backend.app.data_sources.external_provider_base import ExternalProviderStatus
from backend.app.data_sources.provider_registry import require_provider_enabled
from backend.app.raw_store.usaspending_contracts_cache import load_cached_usaspending_contracts, save_usaspending_contracts_snapshot
from backend.app.schemas.government_relationship import (
    GovernmentAwardingAgencySummary,
    GovernmentAwardRecord,
    GovernmentRecipientCandidate,
    GovernmentRelationshipEvidence,
)
from backend.app.schemas.jane_external_evidence import JaneCriteriaExternalEvidenceItem

USASPENDING_BASE_URL = "https://api.usaspending.gov"
GOVERNMENT_LIMITATION = "USASpending recipient matching can include subsidiaries or similarly named entities and requires manual confirmation."
GOVERNMENT_MANUAL_CHECK = "Confirm recipient candidates, subsidiaries, award descriptions, and agency context before relying on C15 government relationship evidence."


def _disabled_government_relationship(ticker: str, reason: str) -> GovernmentRelationshipEvidence:
    status = ExternalProviderStatus(
        provider="usaspending",
        source_type="fallback",
        fallback_used=True,
        fallback_reason=reason,
        missing_data=["usaspending_contract_awards"],
    ).to_data_source_status()
    item = JaneCriteriaExternalEvidenceItem(
        criterion_id=15,
        criterion_name="Regulatory / Government Relationship",
        source="usaspending_contract_awards",
        source_quality="insufficient",
        support_level="insufficient_data",
        confidence=0,
        covered_submetrics=[],
        evidence_snippets=[],
        manual_checks=[GOVERNMENT_MANUAL_CHECK],
        limitations=[GOVERNMENT_LIMITATION, reason],
        missing_data=["usaspending_contract_awards"],
    )
    return GovernmentRelationshipEvidence(
        ticker=ticker.strip().upper(),
        source_status=status,
        criteria=[item],
        criteria_count=1,
        manual_checks=[GOVERNMENT_MANUAL_CHECK],
        limitations=[GOVERNMENT_LIMITATION, reason],
    )


def _recipient_candidates(payload: Any) -> list[GovernmentRecipientCandidate]:
    if isinstance(payload, dict):
        raw = payload.get("results") or payload.get("recipient_candidates") or []
    elif isinstance(payload, list):
        raw = payload
    else:
        raw = []
    candidates = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("recipient_name") or item.get("name") or item.get("legal_business_name") or "").strip()
        if not name:
            continue
        candidates.append(
            GovernmentRecipientCandidate(
                recipient_name=name,
                recipient_hash=item.get("recipient_hash") or item.get("hash"),
                uei=item.get("uei"),
                duns=item.get("duns"),
            )
        )
    return candidates


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _award_records(payload: Any) -> list[GovernmentAwardRecord]:
    if isinstance(payload, dict):
        raw = payload.get("results") or payload.get("awards") or []
    elif isinstance(payload, list):
        raw = payload
    else:
        raw = []
    records = []
    for item in raw[:25]:
        if not isinstance(item, dict):
            continue
        records.append(
            GovernmentAwardRecord(
                award_id=str(item.get("Award ID") or item.get("award_id") or item.get("generated_unique_award_id") or ""),
                recipient_name=str(item.get("Recipient Name") or item.get("recipient_name") or ""),
                awarding_agency=str(item.get("Awarding Agency") or item.get("awarding_agency") or item.get("awarding_agency_name") or ""),
                obligated_amount=_float(item.get("Award Amount") or item.get("award_amount") or item.get("total_obligation")),
                award_date=str(item.get("Start Date") or item.get("period_of_performance_start_date") or item.get("action_date") or "")[:10],
                award_type=str(item.get("Award Type") or item.get("award_type") or item.get("type") or ""),
                description=str(item.get("Description") or item.get("description") or item.get("award_description") or "")[:220],
            )
        )
    return records


def _agency_summaries(records: list[GovernmentAwardRecord]) -> list[GovernmentAwardingAgencySummary]:
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        agency = record.awarding_agency or "Unknown agency"
        totals[agency] += record.obligated_amount
        counts[agency] += 1
    return [
        GovernmentAwardingAgencySummary(agency=agency, obligated_amount=amount, award_count=counts[agency])
        for agency, amount in sorted(totals.items(), key=lambda pair: pair[1], reverse=True)[:5]
    ]


def _source_date(records: list[GovernmentAwardRecord]) -> str:
    dates = [record.award_date for record in records if record.award_date]
    return max(dates) if dates else ""


def _coverage_submetrics(records: list[GovernmentAwardRecord]) -> list[str]:
    if not records:
        return []
    submetrics = ["government_contracts"]
    agency_text = " ".join(record.awarding_agency.lower() for record in records)
    if any(token in agency_text for token in ["defense", "army", "navy", "air force", "space force", "homeland", "nasa", "energy"]):
        submetrics.append("defense_or_infrastructure_status")
    return submetrics


def _build_evidence(ticker: str, query_name: str, candidates: list[GovernmentRecipientCandidate], records: list[GovernmentAwardRecord], status: Any) -> GovernmentRelationshipEvidence:
    total = round(sum(record.obligated_amount for record in records), 2)
    submetrics = _coverage_submetrics(records)
    source_quality = "provider_backed" if status.source_type == "live" and records else "cached_live" if status.source_type == "cached_live" and records else "insufficient"
    support_level = "supportive" if total >= 10_000_000 and records else "partial" if records else "insufficient_data"
    snippets = [
        f"{summary.agency}: ${summary.obligated_amount:,.0f} across {summary.award_count} award(s)."
        for summary in _agency_summaries(records)[:3]
    ]
    missing = [] if records else ["usaspending_contract_awards"]
    item = JaneCriteriaExternalEvidenceItem(
        criterion_id=15,
        criterion_name="Regulatory / Government Relationship",
        source="usaspending_contract_awards",
        source_quality=source_quality,
        support_level=support_level,
        confidence=0.74 if support_level == "supportive" else 0.55 if support_level == "partial" else 0,
        covered_submetrics=submetrics,
        evidence_snippets=snippets,
        manual_checks=[GOVERNMENT_MANUAL_CHECK],
        limitations=[GOVERNMENT_LIMITATION, "Government contract amounts are research context only and do not imply durable moat or policy advantage."],
        missing_data=missing,
    )
    return GovernmentRelationshipEvidence(
        ticker=ticker.strip().upper(),
        source_status=status,
        query_name=query_name,
        recipient_candidates=candidates,
        award_records=records,
        total_obligated_amount=total,
        award_count=len(records),
        top_awarding_agencies=_agency_summaries(records),
        criteria=[item],
        criteria_count=1,
        relationship_signal=support_level if support_level in {"supportive", "insufficient_data"} else "limited",
        manual_checks=[GOVERNMENT_MANUAL_CHECK],
        limitations=[GOVERNMENT_LIMITATION, "Government contract amounts are research context only and do not imply durable moat or policy advantage."],
    )


def _from_cached(ticker: str, reason: str, ttl_days: int) -> GovernmentRelationshipEvidence | None:
    cached = load_cached_usaspending_contracts(ticker, ttl_days=ttl_days)
    if not cached:
        return None
    records = _award_records(cached.get("awards") or cached.get("payload", {}).get("awards") or [])
    candidates = _recipient_candidates(cached.get("recipient_candidates") or cached.get("payload", {}).get("recipient_candidates") or [])
    status = ExternalProviderStatus(
        provider="usaspending",
        source_type="cached_live",
        source_date=_source_date(records),
        fetched_at=cached.get("fetched_at"),
        cache_hit=True,
        fallback_used=True,
        fallback_reason="USASpending live fetch failed; using cached contract snapshot.",
        limitations=[reason[:180]],
    ).to_data_source_status()
    return _build_evidence(ticker, str(cached.get("query_name") or ticker), candidates, records, status)


def fetch_usaspending_contracts(ticker: str, company_name: str = "", http_post: Callable[..., Any] | None = None) -> GovernmentRelationshipEvidence:
    normalized_ticker = ticker.strip().upper()
    query_name = (company_name or normalized_ticker).strip()
    try:
        provider_config = require_provider_enabled("usaspending")
    except RuntimeError as exc:
        return _disabled_government_relationship(normalized_ticker, str(exc))

    poster = http_post or requests.post
    try:
        autocomplete_response = poster(
            f"{USASPENDING_BASE_URL}/api/v2/autocomplete/recipient/",
            json={"search_text": query_name},
            timeout=15,
        )
        if hasattr(autocomplete_response, "raise_for_status"):
            autocomplete_response.raise_for_status()
        candidates = _recipient_candidates(autocomplete_response.json())
        recipient_names = [candidates[0].recipient_name] if candidates else [query_name]
        award_response = poster(
            f"{USASPENDING_BASE_URL}/api/v2/search/spending_by_award/",
            json={
                "filters": {"recipient_search_text": recipient_names},
                "fields": ["Award ID", "Recipient Name", "Awarding Agency", "Award Amount", "Start Date", "Award Type", "Description"],
                "page": 1,
                "limit": 25,
                "sort": "Award Amount",
                "order": "desc",
            },
            timeout=20,
        )
        if hasattr(award_response, "raise_for_status"):
            award_response.raise_for_status()
        records = _award_records(award_response.json())
    except Exception as exc:  # noqa: BLE001 - provider boundary must degrade safely.
        cached = _from_cached(normalized_ticker, str(exc), provider_config.cache_ttl_days)
        if cached:
            return cached
        return _disabled_government_relationship(normalized_ticker, "USASpending live contract fetch failed.")

    save_usaspending_contracts_snapshot(
        normalized_ticker,
        {
            "query_name": query_name,
            "recipient_candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            "awards": [record.model_dump(mode="json") for record in records],
        },
        fetched_at=datetime.now(timezone.utc),
    )
    status = ExternalProviderStatus(
        provider="usaspending",
        source_type="live",
        source_date=_source_date(records),
        fetched_at=datetime.now(timezone.utc),
        limitations=[GOVERNMENT_LIMITATION],
        missing_data=[] if records else ["usaspending_contract_awards"],
    ).to_data_source_status()
    return _build_evidence(normalized_ticker, query_name, candidates, records, status)


def get_government_relationship_evidence(ticker: str, company_name: str = "") -> GovernmentRelationshipEvidence:
    return fetch_usaspending_contracts(ticker, company_name=company_name)
