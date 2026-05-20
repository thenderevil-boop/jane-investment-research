from __future__ import annotations

from backend.app.schemas.earnings_transcript import EarningsTranscriptAnalysis
from backend.app.schemas.jane_external_evidence import JaneCriteriaExternalEvidence, JaneCriteriaExternalEvidenceItem

TRANSCRIPT_LIMITATION = "Transcript criteria evidence is management-provided context only and requires independent verification."
TRANSCRIPT_MANUAL_CHECK = "Confirm transcript themes against filings, customer evidence, management history, and independent sources before relying on C2/C17 evidence."


def _snippets(*groups: list[str], limit: int = 4) -> list[str]:
    seen: list[str] = []
    for group in groups:
        for item in group or []:
            text = " ".join(str(item).split())
            if not text:
                continue
            if len(text) > 220:
                text = text[:217].rstrip() + "..."
            if text not in seen:
                seen.append(text)
            if len(seen) >= limit:
                return seen
    return seen


def _source_quality(analysis: EarningsTranscriptAnalysis) -> str:
    source_type = analysis.source_status.source_type
    if source_type == "live":
        return "provider_backed"
    if source_type == "cached_live":
        return "cached_live"
    return "insufficient"


def _support_level(confidence: float, snippets: list[str], quarters: int) -> str:
    if not snippets or quarters <= 0:
        return "insufficient_data"
    if confidence >= 0.66 and quarters >= 2:
        return "supportive"
    return "partial"


def _base_missing(analysis: EarningsTranscriptAnalysis) -> list[str]:
    if analysis.quarters_analyzed <= 0:
        return ["fmp_earnings_transcripts"]
    return []


def map_transcript_to_jane_criteria_evidence(analysis: EarningsTranscriptAnalysis) -> JaneCriteriaExternalEvidence:
    source_quality = _source_quality(analysis)
    provider_available = analysis.quarters_analyzed > 0 and source_quality in {"provider_backed", "cached_live"}

    c2_snippets = _snippets(
        analysis.management_consistency.evidence_snippets,
        analysis.strategy_clarity.evidence_snippets,
        analysis.capital_allocation_focus.evidence_snippets,
        limit=4,
    ) if provider_available else []
    c17_snippets = _snippets(
        analysis.strategy_clarity.evidence_snippets,
        analysis.management_consistency.evidence_snippets,
        [snippet for theme in analysis.positive_themes for snippet in theme.evidence_snippets],
        limit=4,
    ) if provider_available else []

    c2_confidence = round(max(analysis.management_consistency.confidence, analysis.strategy_clarity.confidence, analysis.capital_allocation_focus.confidence) * 0.9, 2) if c2_snippets else 0
    c17_confidence = round(max(analysis.strategy_clarity.confidence, analysis.management_consistency.confidence) * 0.92, 2) if c17_snippets else 0

    c2_covered = []
    if c2_snippets:
        if analysis.management_consistency.label in {"consistent"}:
            c2_covered.append("long_term_vision_consistency")
        if analysis.strategy_clarity.label in {"clear", "mixed"}:
            c2_covered.append("milestone_execution_record")
    c17_covered = []
    if c17_snippets:
        if analysis.strategy_clarity.label in {"clear", "mixed"}:
            c17_covered.append("clear_long_term_mission")
        if analysis.management_consistency.label == "consistent":
            c17_covered.append("founder_narrative_consistency")
        if analysis.positive_themes:
            c17_covered.append("investor_narrative_durability")

    common_checks = sorted(set([TRANSCRIPT_MANUAL_CHECK, *analysis.manual_checks]))
    common_limitations = sorted(set([TRANSCRIPT_LIMITATION, *analysis.limitations]))
    missing = _base_missing(analysis)

    criteria = [
        JaneCriteriaExternalEvidenceItem(
            criterion_id=2,
            criterion_name="Visionary Founder / CEO",
            source_quality=source_quality if c2_snippets else "insufficient",
            support_level=_support_level(c2_confidence, c2_snippets, analysis.quarters_analyzed),
            confidence=c2_confidence,
            covered_submetrics=c2_covered,
            evidence_snippets=c2_snippets,
            manual_checks=common_checks,
            limitations=common_limitations,
            missing_data=missing or (["CEO/founder transcript evidence"] if not c2_snippets else []),
        ),
        JaneCriteriaExternalEvidenceItem(
            criterion_id=17,
            criterion_name="Mission and Narrative Power",
            source_quality=source_quality if c17_snippets else "insufficient",
            support_level=_support_level(c17_confidence, c17_snippets, analysis.quarters_analyzed),
            confidence=c17_confidence,
            covered_submetrics=c17_covered,
            evidence_snippets=c17_snippets,
            manual_checks=common_checks,
            limitations=common_limitations,
            missing_data=missing or (["mission and narrative transcript evidence"] if not c17_snippets else []),
        ),
    ]
    return JaneCriteriaExternalEvidence(
        ticker=analysis.ticker,
        provider=analysis.provider,
        source_status=analysis.source_status,
        criteria=criteria,
        criteria_count=len(criteria),
        manual_checks=common_checks,
        limitations=common_limitations,
    )
