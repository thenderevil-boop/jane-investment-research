from __future__ import annotations

import re
from collections import Counter
from typing import Any

from backend.app.schemas.common import DataSourceStatus
from backend.app.schemas.earnings_transcript import EarningsTranscriptAnalysis, EarningsTranscriptDimension, TranscriptTheme

POSITIVE_THEME_KEYWORDS = {
    "customer_demand": ["customer demand", "demand", "bookings", "backlog", "pipeline", "retention", "usage", "adoption"],
    "strategy_clarity": ["strategy", "platform", "roadmap", "priorities", "growth driver", "product suite"],
    "capital_allocation": ["reinvestment", "r&d", "research and development", "capex", "free cash flow", "operating leverage"],
}
RISK_THEME_KEYWORDS = {
    "margin_pressure": ["margin pressure", "gross margin", "cost inflation", "compute cost", "pricing", "depreciation"],
    "macro_risk": ["macro uncertainty", "slowdown", "competition", "regulation", "supply chain"],
}


def _record_text(record: dict[str, Any]) -> str:
    return str(record.get("transcript") or record.get("content") or record.get("text") or "")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _snippets(records: list[dict[str, Any]], keywords: list[str], limit: int = 3) -> list[str]:
    found: list[str] = []
    lowered_keywords = [keyword.lower() for keyword in keywords]
    for record in records:
        for sentence in _sentences(_record_text(record)):
            lower = sentence.lower()
            if any(keyword in lower for keyword in lowered_keywords):
                found.append(sentence[:220])
            if len(found) >= limit:
                return found
    return found


def _keyword_hits(records: list[dict[str, Any]], keywords: list[str]) -> int:
    text = "\n".join(_record_text(record).lower() for record in records)
    return sum(1 for keyword in keywords if keyword.lower() in text)


def _dimension(label: str, confidence: float, snippets: list[str], limitation: str | None = None) -> EarningsTranscriptDimension:
    limitations = ["Transcript evidence reflects management statements and requires human review."]
    if limitation:
        limitations.append(limitation)
    return EarningsTranscriptDimension(label=label, confidence=round(min(max(confidence, 0), 1), 2), evidence_snippets=snippets, limitations=limitations)


def _theme(theme: str, label: str, snippets: list[str], confidence: float) -> TranscriptTheme:
    return TranscriptTheme(theme=theme, label=label, evidence_snippets=snippets, confidence=round(confidence, 2), limitations=["Theme is extracted from transcript language and is not independently verified."])


def _source_date(records: list[dict[str, Any]]) -> str:
    dates = [str(record.get("date") or record.get("source_date") or "")[:10] for record in records if str(record.get("date") or record.get("source_date") or "").strip()]
    return max(dates) if dates else ""


def analyze_earnings_transcripts(ticker: str, records: list[dict[str, Any]], source_status: DataSourceStatus | None = None) -> EarningsTranscriptAnalysis:
    normalized_ticker = ticker.strip().upper()
    usable_records = [record for record in records if _record_text(record).strip()]
    if not usable_records:
        status = source_status or DataSourceStatus(source_type="fallback", provider="fmp", freshness_window="external_provider_cache", fallback_used=True, missing_data=["fmp_earnings_transcripts"])
        return EarningsTranscriptAnalysis(ticker=normalized_ticker, source_status=status, limitations=["No usable FMP earnings transcripts were available.", "Earnings transcript analysis is research context only."])

    all_text = "\n".join(_record_text(record).lower() for record in usable_records)
    strategy_terms = ["strategy", "cloud", "ai", "platform", "roadmap", "priority", "product"]
    demand_terms = POSITIVE_THEME_KEYWORDS["customer_demand"]
    risk_terms = RISK_THEME_KEYWORDS["margin_pressure"] + RISK_THEME_KEYWORDS["macro_risk"]
    capital_terms = POSITIVE_THEME_KEYWORDS["capital_allocation"] + ["shareholder return", "dividend", "acquisition"]

    repeated_terms = [term for term, count in Counter(term for term in strategy_terms if term in all_text).items() if count]
    strategy_hits = _keyword_hits(usable_records, strategy_terms)
    demand_hits = _keyword_hits(usable_records, demand_terms)
    risk_hits = _keyword_hits(usable_records, risk_terms)
    capital_hits = _keyword_hits(usable_records, capital_terms)

    management_label = "consistent" if len(repeated_terms) >= 2 and len(usable_records) >= 2 else "mixed" if strategy_hits else "insufficient_data"
    strategy_label = "clear" if strategy_hits >= 3 else "mixed" if strategy_hits else "insufficient_data"
    risk_label = "transparent" if risk_hits >= 3 else "partial" if risk_hits else "insufficient_data"
    demand_label = "strong_positive" if demand_hits >= 4 else "mixed" if demand_hits else "insufficient_data"
    margin_label = "manageable_pressure" if risk_hits and ("pricing" in all_text or "operating leverage" in all_text) else "elevated_pressure" if risk_hits else "insufficient_data"
    capital_label = "reinvestment_focused" if ("reinvestment" in all_text or "r&d" in all_text or "capex" in all_text) else "mixed" if capital_hits else "insufficient_data"

    positive_themes = [
        _theme(theme, "supportive_context", snippets, min(0.5 + 0.08 * len(snippets), 0.85))
        for theme, keywords in POSITIVE_THEME_KEYWORDS.items()
        if (snippets := _snippets(usable_records, keywords, limit=2))
    ]
    risk_themes = [
        _theme(theme, "review_context", snippets, min(0.5 + 0.08 * len(snippets), 0.85))
        for theme, keywords in RISK_THEME_KEYWORDS.items()
        if (snippets := _snippets(usable_records, keywords, limit=2))
    ]
    status = source_status or DataSourceStatus(source_type="derived", provider="derived_from_fmp_transcripts", source_date=_source_date(usable_records), freshness_window="external_provider_cache", is_fresh=True)

    return EarningsTranscriptAnalysis(
        ticker=normalized_ticker,
        source_status=status,
        quarters_analyzed=len(usable_records),
        management_consistency=_dimension(management_label, 0.45 + 0.1 * min(strategy_hits, 4), _snippets(usable_records, strategy_terms)),
        strategy_clarity=_dimension(strategy_label, 0.4 + 0.1 * min(strategy_hits, 4), _snippets(usable_records, strategy_terms)),
        risk_acknowledgement=_dimension(risk_label, 0.4 + 0.1 * min(risk_hits, 4), _snippets(usable_records, risk_terms)),
        customer_demand_signal=_dimension(demand_label, 0.4 + 0.1 * min(demand_hits, 4), _snippets(usable_records, demand_terms)),
        margin_pressure_signal=_dimension(margin_label, 0.4 + 0.1 * min(risk_hits, 4), _snippets(usable_records, RISK_THEME_KEYWORDS["margin_pressure"])),
        capital_allocation_focus=_dimension(capital_label, 0.4 + 0.1 * min(capital_hits, 4), _snippets(usable_records, capital_terms)),
        positive_themes=positive_themes,
        risk_themes=risk_themes,
        manual_checks=[
            "Review full transcript context before interpreting management claims.",
            "Confirm transcript themes against filings, fundamentals, and subsequent reported results.",
        ],
        limitations=[
            "Earnings transcript analysis is deterministic research context only.",
            "Management statements are not independently verified by this analysis.",
        ],
    )
