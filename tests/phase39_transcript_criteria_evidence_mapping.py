from __future__ import annotations

import json
import re

from backend.app.schemas.common import DataSourceStatus

FORBIDDEN_PATTERNS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"target price",
    r"must invest",
    r"liquidate",
    r"position size",
]


def assert_no_forbidden_language(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False).lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert not re.search(pattern, text), pattern


def sample_transcript_analysis():
    from backend.app.schemas.earnings_transcript import EarningsTranscriptAnalysis, EarningsTranscriptDimension, TranscriptTheme

    status = DataSourceStatus(source_type="live", provider="fmp", source_date="2026-04-24", is_fresh=True)
    return EarningsTranscriptAnalysis(
        ticker="NVDA",
        source_status=status,
        quarters_analyzed=2,
        management_consistency=EarningsTranscriptDimension(
            label="consistent",
            confidence=0.72,
            evidence_snippets=["Management repeatedly emphasized AI platform strategy and data center execution."],
            limitations=["Transcript language is management-provided and requires filing/customer validation."],
        ),
        strategy_clarity=EarningsTranscriptDimension(
            label="clear",
            confidence=0.7,
            evidence_snippets=["Management described AI factories, accelerated computing, and software ecosystem priorities."],
        ),
        risk_acknowledgement=EarningsTranscriptDimension(
            label="transparent",
            confidence=0.64,
            evidence_snippets=["Management discussed supply constraints, competition, regulation, and margin pressure."],
        ),
        customer_demand_signal=EarningsTranscriptDimension(
            label="strong_positive",
            confidence=0.66,
            evidence_snippets=["Management cited strong customer demand and expanding pipeline."],
        ),
        margin_pressure_signal=EarningsTranscriptDimension(
            label="manageable_pressure",
            confidence=0.58,
            evidence_snippets=["Management discussed pricing and operating leverage against compute cost pressure."],
        ),
        capital_allocation_focus=EarningsTranscriptDimension(
            label="reinvestment_focused",
            confidence=0.61,
            evidence_snippets=["Management emphasized R&D, capex, and ecosystem investment."],
        ),
        positive_themes=[
            TranscriptTheme(theme="ai_platform_strategy", label="supportive_context", evidence_snippets=["AI platform strategy remained consistent across calls."], confidence=0.7),
            TranscriptTheme(theme="customer_demand", label="supportive_context", evidence_snippets=["Customer demand and pipeline were repeatedly discussed."], confidence=0.64),
        ],
        risk_themes=[
            TranscriptTheme(theme="competition", label="review_context", evidence_snippets=["Competition and regulation require follow-up review."], confidence=0.55)
        ],
        manual_checks=["Confirm management claims against filings, customer adoption, and independent evidence."],
        limitations=["Transcript evidence reflects management statements and is not independently verified."],
    )


def test_transcript_criteria_mapper_outputs_c2_c17_non_scoring_evidence() -> None:
    from backend.app.features.transcript_criteria_evidence import map_transcript_to_jane_criteria_evidence

    result = map_transcript_to_jane_criteria_evidence(sample_transcript_analysis())
    dumped = result.model_dump(mode="json")

    assert dumped["ticker"] == "NVDA"
    assert dumped["provider"] == "fmp"
    assert dumped["source"] == "fmp_earnings_transcript"
    assert dumped["affects_score"] is False
    assert dumped["not_investment_advice"] is True
    assert dumped["criteria_count"] == 2
    criteria = {item["criterion_id"]: item for item in dumped["criteria"]}
    assert set(criteria) == {2, 17}

    c2 = criteria[2]
    assert c2["criterion_name"] == "Visionary Founder / CEO"
    assert c2["support_level"] in {"supportive", "partial"}
    assert c2["source_quality"] == "provider_backed"
    assert c2["affects_score"] is False
    assert c2["requires_manual_review"] is True
    assert "long_term_vision_consistency" in c2["covered_submetrics"]
    assert c2["evidence_snippets"]

    c17 = criteria[17]
    assert c17["criterion_name"] == "Mission and Narrative Power"
    assert c17["support_level"] in {"supportive", "partial"}
    assert c17["source_quality"] == "provider_backed"
    assert "clear_long_term_mission" in c17["covered_submetrics"]
    assert "founder_narrative_consistency" in c17["covered_submetrics"]
    assert c17["manual_checks"]
    assert_no_forbidden_language(dumped)


def test_transcript_criteria_mapper_handles_disabled_or_missing_transcript_as_insufficient() -> None:
    from backend.app.features.transcript_criteria_evidence import map_transcript_to_jane_criteria_evidence
    from backend.app.schemas.earnings_transcript import disabled_earnings_transcript_analysis

    result = map_transcript_to_jane_criteria_evidence(disabled_earnings_transcript_analysis("NVDA"))
    dumped = result.model_dump(mode="json")

    assert dumped["criteria_count"] == 2
    assert dumped["affects_score"] is False
    assert all(item["support_level"] == "insufficient_data" for item in dumped["criteria"])
    assert all(item["evidence_snippets"] == [] for item in dumped["criteria"])
    assert all(item["requires_manual_review"] is True for item in dumped["criteria"])
    assert "fmp_earnings_transcripts" in dumped["source_status"]["missing_data"]
    assert_no_forbidden_language(dumped)


def test_analyze_stock_exposes_transcript_criteria_evidence_and_coverage_without_scoring_change(monkeypatch) -> None:
    from backend.app.reports import stock_analysis
    from backend.app.schemas.stock_analysis import AnalyzeStockRequest

    analysis = sample_transcript_analysis()
    monkeypatch.setattr(stock_analysis, "get_earnings_transcript_analysis", lambda ticker: analysis)

    response = stock_analysis.analyze_stock(AnalyzeStockRequest(ticker="NVDA"))
    dumped = response.model_dump(mode="json")

    external = dumped["jane_criteria_external_evidence"]
    assert external["affects_score"] is False
    assert external["criteria_count"] == 2
    assert {item["criterion_id"] for item in external["criteria"]} == {2, 17}
    assert "jane_criteria_external_evidence" in dumped["data_quality_summary"]["excluded_from_scoring"]

    criteria = {item["criterion_id"]: item for item in dumped["jane_criteria_coverage"]["criteria"]}
    assert criteria[2]["coverage_status"] in {"partial", "covered"}
    assert criteria[2]["source_quality"] == "provider_backed"
    assert "long_term_vision_consistency" in criteria[2]["covered_submetrics"]
    assert criteria[17]["coverage_status"] in {"partial", "covered"}
    assert criteria[17]["source_quality"] == "provider_backed"
    assert criteria[17]["accepted_evidence_item_count"] >= 1
    assert dumped["jane_company_quality"]["score"] >= 0
    assert all(item["affects_score"] is False for item in external["criteria"])
    assert_no_forbidden_language(external)
