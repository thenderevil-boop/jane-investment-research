from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlencode

import requests

from backend.app.data_sources.external_provider_base import ExternalProviderStatus
from backend.app.data_sources.provider_registry import require_provider_enabled
from backend.app.features.earnings_transcript_analysis import analyze_earnings_transcripts
from backend.app.raw_store.fmp_transcripts_cache import load_cached_fmp_transcripts, save_fmp_transcripts_snapshot
from backend.app.schemas.earnings_transcript import EarningsTranscriptAnalysis, disabled_earnings_transcript_analysis

FMP_TRANSCRIPT_BASE_URL = "https://financialmodelingprep.com/api/v4"


def _normalize_record(ticker: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(item.get("symbol") or item.get("ticker") or ticker).strip().upper(),
        "quarter": item.get("quarter"),
        "year": item.get("year"),
        "date": str(item.get("date") or item.get("fillingDate") or item.get("acceptedDate") or "")[:10],
        "transcript": str(item.get("transcript") or item.get("content") or item.get("text") or ""),
    }


def _records_from_payload(ticker: str, payload: Any, limit: int) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        raw_records = payload.get("records") or payload.get("transcripts") or payload.get("data") or []
    else:
        raw_records = payload
    if not isinstance(raw_records, list):
        return []
    return [_normalize_record(ticker, item) for item in raw_records[:limit] if isinstance(item, dict)]


def _source_date(records: list[dict[str, Any]]) -> str:
    dates = [str(record.get("date") or "")[:10] for record in records if str(record.get("date") or "").strip()]
    return max(dates) if dates else ""


def _fallback_from_cache(ticker: str, limit: int, reason: str, ttl_days: int) -> EarningsTranscriptAnalysis | None:
    cached = load_cached_fmp_transcripts(ticker, ttl_days=ttl_days)
    if not cached:
        return None
    records = _records_from_payload(ticker, cached.get("payload", cached), limit)
    status = ExternalProviderStatus(
        provider="fmp",
        source_type="cached_live",
        source_date=_source_date(records),
        fetched_at=cached.get("fetched_at"),
        cache_hit=True,
        fallback_used=True,
        fallback_reason="FMP live transcript fetch failed; using cached transcript snapshot.",
        limitations=[reason[:180]],
    ).to_data_source_status()
    return analyze_earnings_transcripts(ticker, records, source_status=status)


def fetch_fmp_earnings_transcripts(ticker: str, limit: int = 4, http_get: Callable[..., Any] | None = None) -> EarningsTranscriptAnalysis:
    normalized_ticker = ticker.strip().upper()
    try:
        provider_config = require_provider_enabled("fmp")
    except RuntimeError as exc:
        return disabled_earnings_transcript_analysis(normalized_ticker, str(exc))

    getter = http_get or requests.get
    current_year = datetime.now(timezone.utc).year
    years = [current_year, current_year - 1]
    payload: list[dict[str, Any]] = []
    try:
        for year in years:
            query = urlencode({"year": year, "apikey": provider_config.api_key})
            # FMP legacy docs expose batch transcripts by symbol/year under api/v4.
            # Keep endpoint isolated in the adapter so FMP raw shape can change without leaking into app contracts.
            url = f"{FMP_TRANSCRIPT_BASE_URL}/batch_earning_call_transcript/{normalized_ticker}?{query}"
            response = getter(url, timeout=15)
            status_code = int(getattr(response, "status_code", 200) or 200)
            if status_code == 429:
                cached = _fallback_from_cache(normalized_ticker, limit, "FMP transcript provider was rate limited.", provider_config.cache_ttl_days)
                if cached:
                    return cached
                status = ExternalProviderStatus(provider="fmp", source_type="fallback", rate_limited=True, fallback_used=True, fallback_reason="FMP transcript provider was rate limited.", missing_data=["fmp_earnings_transcripts"]).to_data_source_status()
                return analyze_earnings_transcripts(normalized_ticker, [], source_status=status)
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            year_payload = response.json()
            year_records = _records_from_payload(normalized_ticker, year_payload, limit)
            payload.extend(year_records)
            if len(payload) >= limit:
                break
    except Exception as exc:  # noqa: BLE001 - provider boundary must degrade safely.
        safe_reason = str(exc).replace(provider_config.api_key, "[REDACTED]")[:180]
        cached = _fallback_from_cache(normalized_ticker, limit, safe_reason, provider_config.cache_ttl_days)
        if cached:
            return cached
        status = ExternalProviderStatus(provider="fmp", source_type="fallback", fallback_used=True, fallback_reason="FMP live transcript fetch failed.", limitations=[safe_reason], missing_data=["fmp_earnings_transcripts"]).to_data_source_status()
        return analyze_earnings_transcripts(normalized_ticker, [], source_status=status)

    records = _records_from_payload(normalized_ticker, payload, limit)
    if not records:
        status = ExternalProviderStatus(provider="fmp", source_type="fallback", fallback_used=True, fallback_reason="FMP transcript payload did not include usable records.", missing_data=["fmp_earnings_transcripts"]).to_data_source_status()
        return analyze_earnings_transcripts(normalized_ticker, [], source_status=status)

    save_fmp_transcripts_snapshot(normalized_ticker, {"records": records}, fetched_at=datetime.now(timezone.utc))
    status = ExternalProviderStatus(provider="fmp", source_type="live", source_date=_source_date(records), fetched_at=datetime.now(timezone.utc), limitations=["FMP earnings transcript data is management-provided call text and requires review."]).to_data_source_status()
    return analyze_earnings_transcripts(normalized_ticker, records, source_status=status)


def get_earnings_transcript_analysis(ticker: str) -> EarningsTranscriptAnalysis:
    return fetch_fmp_earnings_transcripts(ticker)
