from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import requests

from backend.app.data_sources.external_provider_base import ExternalProviderStatus
from backend.app.data_sources.provider_registry import require_provider_enabled
from backend.app.raw_store.uspto_patents_cache import load_cached_uspto_patents, save_uspto_patents_snapshot
from backend.app.schemas.jane_external_evidence import JaneCriteriaExternalEvidenceItem
from backend.app.schemas.patent_ip import PatentIPEvidence, PatentRecord

PATENTSVIEW_BASE_URL = "https://search.patentsview.org/api/v1/patent/"
PATENT_LIMITATION = "Patent count is an auto-derived proxy and does not prove patent quality, relevance, or defensibility."
PATENT_MANUAL_CHECK = "Confirm assignee/entity matching, subsidiaries, acquired entities, and patent relevance before relying on C18 IP evidence."


def _disabled_patent_ip(ticker: str, reason: str) -> PatentIPEvidence:
    status = ExternalProviderStatus(
        provider="uspto_patentsview",
        source_type="fallback",
        fallback_used=True,
        fallback_reason=reason,
        missing_data=["uspto_patentsview_patent_count"],
    ).to_data_source_status()
    item = JaneCriteriaExternalEvidenceItem(
        criterion_id=18,
        criterion_name="Patents and IP",
        source="uspto_patentsview",
        source_quality="insufficient",
        support_level="insufficient_data",
        confidence=0,
        covered_submetrics=[],
        evidence_snippets=[],
        manual_checks=[PATENT_MANUAL_CHECK],
        limitations=[PATENT_LIMITATION, reason],
        missing_data=["uspto_patentsview_patent_count"],
    )
    return PatentIPEvidence(
        ticker=ticker.strip().upper(),
        source_status=status,
        criteria=[item],
        criteria_count=1,
        manual_checks=[PATENT_MANUAL_CHECK],
        limitations=[PATENT_LIMITATION, reason],
    )


def _int(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _patent_records(payload: Any) -> list[PatentRecord]:
    if isinstance(payload, dict):
        raw = payload.get("patents") or payload.get("results") or payload.get("data") or []
    elif isinstance(payload, list):
        raw = payload
    else:
        raw = []
    records: list[PatentRecord] = []
    for item in raw[:10]:
        if not isinstance(item, dict):
            continue
        records.append(
            PatentRecord(
                patent_id=str(item.get("patent_id") or item.get("patent_number") or item.get("id") or ""),
                patent_date=str(item.get("patent_date") or item.get("date") or "")[:10],
                patent_title=str(item.get("patent_title") or item.get("title") or "")[:220],
                assignee_organization=str(item.get("assignees.assignee_organization") or item.get("assignee_organization") or item.get("assignee") or "")[:220],
            )
        )
    return records


def _source_date(records: list[PatentRecord]) -> str:
    dates = [record.patent_date for record in records if record.patent_date]
    return max(dates) if dates else ""


def _support_level(count: int) -> str:
    if count >= 50:
        return "supportive"
    if count >= 1:
        return "partial"
    return "insufficient_data"


def _ip_signal(support_level: str) -> str:
    return "supportive" if support_level == "supportive" else "limited" if support_level == "partial" else "insufficient_data"


def _build_evidence(ticker: str, query_name: str, patent_count: int, records: list[PatentRecord], status: Any) -> PatentIPEvidence:
    support_level = _support_level(patent_count)
    source_quality = "provider_backed" if status.source_type == "live" and patent_count > 0 else "cached_live" if status.source_type == "cached_live" and patent_count > 0 else "insufficient"
    snippets = [f"PatentsView found {patent_count} patent(s) assigned to names matching {query_name} in the last 3 years."] if patent_count > 0 else []
    item = JaneCriteriaExternalEvidenceItem(
        criterion_id=18,
        criterion_name="Patents and IP",
        source="uspto_patentsview",
        source_quality=source_quality,
        support_level=support_level,
        confidence=0.74 if support_level == "supportive" else 0.55 if support_level == "partial" else 0,
        covered_submetrics=["patent_count"] if patent_count > 0 else [],
        evidence_snippets=snippets,
        manual_checks=[PATENT_MANUAL_CHECK],
        limitations=[PATENT_LIMITATION, "PatentsView organization-name matching can miss subsidiaries or include similarly named assignees."],
        missing_data=[] if patent_count > 0 else ["uspto_patentsview_patent_count"],
    )
    return PatentIPEvidence(
        ticker=ticker.strip().upper(),
        source_status=status,
        query_name=query_name,
        patent_count=patent_count,
        patent_records=records,
        criteria=[item],
        criteria_count=1,
        ip_signal=_ip_signal(support_level),
        manual_checks=[PATENT_MANUAL_CHECK],
        limitations=[PATENT_LIMITATION, "PatentsView organization-name matching can miss subsidiaries or include similarly named assignees."],
    )


def _query_params(company_name: str) -> dict[str, str]:
    start_date = (datetime.now(timezone.utc) - timedelta(days=365 * 3)).date().isoformat()
    query = {
        "_and": [
            {"assignees.assignee_organization": {"_text_any": company_name}},
            {"patent_date": {"_gte": start_date}},
        ]
    }
    fields = ["patent_id", "patent_date", "patent_title", "assignees.assignee_organization"]
    return {"q": json.dumps(query, separators=(",", ":")), "f": json.dumps(fields), "o": json.dumps({"per_page": 10})}


def _from_cached(ticker: str, query_name: str, reason: str, ttl_days: int) -> PatentIPEvidence | None:
    cached = load_cached_uspto_patents(ticker, ttl_days=ttl_days)
    if not cached:
        return None
    patent_count = _int(cached.get("patent_count") or cached.get("payload", {}).get("patent_count"))
    records = _patent_records(cached.get("patent_records") or cached.get("payload", {}).get("patent_records") or [])
    cached_query = str(cached.get("company_name") or cached.get("query_name") or cached.get("payload", {}).get("company_name") or query_name)
    status = ExternalProviderStatus(
        provider="uspto_patentsview",
        source_type="cached_live",
        source_date=_source_date(records),
        fetched_at=cached.get("fetched_at"),
        cache_hit=True,
        fallback_used=True,
        fallback_reason="PatentsView live fetch failed; using cached patent snapshot.",
        limitations=[reason[:180]],
    ).to_data_source_status()
    return _build_evidence(ticker, cached_query, patent_count, records, status)


def fetch_patent_ip_evidence(ticker: str, company_name: str = "", http_get: Callable[..., Any] | None = None) -> PatentIPEvidence:
    normalized_ticker = ticker.strip().upper()
    query_name = (company_name or normalized_ticker).strip()
    try:
        provider_config = require_provider_enabled("uspto_patentsview")
    except RuntimeError as exc:
        return _disabled_patent_ip(normalized_ticker, str(exc))

    getter = http_get or requests.get
    try:
        response = getter(PATENTSVIEW_BASE_URL, params=_query_params(query_name), timeout=20)
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        payload = response.json()
        patent_count = _int(payload.get("total_hits") if isinstance(payload, dict) else 0)
        records = _patent_records(payload)
    except Exception as exc:  # noqa: BLE001 - provider boundary must degrade safely.
        cached = _from_cached(normalized_ticker, query_name, str(exc), provider_config.cache_ttl_days)
        if cached:
            return cached
        return _disabled_patent_ip(normalized_ticker, "PatentsView live patent fetch failed.")

    save_uspto_patents_snapshot(
        normalized_ticker,
        {
            "company_name": query_name,
            "patent_count": patent_count,
            "patent_records": [record.model_dump(mode="json") for record in records],
        },
        fetched_at=datetime.now(timezone.utc),
    )
    status = ExternalProviderStatus(
        provider="uspto_patentsview",
        source_type="live",
        source_date=_source_date(records),
        fetched_at=datetime.now(timezone.utc),
        limitations=[PATENT_LIMITATION],
        missing_data=[] if patent_count > 0 else ["uspto_patentsview_patent_count"],
    ).to_data_source_status()
    return _build_evidence(normalized_ticker, query_name, patent_count, records, status)


def get_patent_ip_evidence(ticker: str, company_name: str = "") -> PatentIPEvidence:
    return fetch_patent_ip_evidence(ticker, company_name)
