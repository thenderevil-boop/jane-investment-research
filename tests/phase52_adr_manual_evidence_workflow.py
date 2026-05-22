from __future__ import annotations

import json

from backend.app.schemas.common import DataSourceStatus
from backend.app.schemas.earnings_transcript import EarningsTranscriptAnalysis


def _fallback_transcript(ticker: str) -> EarningsTranscriptAnalysis:
    return EarningsTranscriptAnalysis(
        ticker=ticker,
        source_status=DataSourceStatus(
            source_type="fallback",
            provider="fmp",
            source_date="",
            is_fresh=False,
            fallback_used=True,
            fallback_reason="FMP transcript unavailable for this ticker.",
            limitations=["FMP transcript unavailable for this ticker."],
            missing_data=["fmp_earnings_transcripts"],
        ),
    )


def _fallback_fmp_financial_proxy(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "provider": "fmp_financials",
        "source_type": "fallback",
        "source_status": {
            "source_type": "fallback",
            "provider": "fmp_financials",
            "source_date": "",
            "is_fresh": False,
            "fallback_used": True,
            "fallback_reason": "FMP financial statements unavailable for this ticker.",
            "limitations": ["FMP financial statements unavailable for this ticker."],
            "missing_data": ["fmp_financial_statements", "fmp_ttm_ratios"],
        },
        "latest_fiscal_year": None,
        "reported_currency": None,
        "filing_date": None,
        "facts": {},
        "derived_metrics": {},
        "ttm_ratios": {},
        "missing_data": ["fmp_financial_statements", "fmp_ttm_ratios"],
    }


def _adr_manual_evidence(**overrides) -> dict:
    row = {
        "criterion": "visionary_founder_ceo",
        "criterion_id": 2,
        "criterion_name": "Visionary Founder / CEO",
        "submetric": "founder_ownership",
        "evidence_type": "filing_reference",
        "summary": "Annual report governance disclosure describes long-term insider and board alignment that requires local filing verification.",
        "source_label": "Nokia Annual Report FY2025",
        "source_url": "https://example.com/nokia-annual-report-2025.pdf",
        "source_date": None,
        "document_title": "Nokia Annual Report 2025",
        "document_date": "2026-03-05",
        "filing_period": "FY2025",
        "quoted_text": "The annual report governance section describes board ownership and long-term incentive alignment for Nokia leadership.",
        "adr_evidence_type": "annual_report",
        "local_market": "NASDAQ Helsinki",
        "local_ticker": "NOKIA",
        "translation_note": "English annual report; no translation required.",
        "confidence": 0.72,
        "limitations": ["Manual ADR filing evidence still requires human verification."],
    }
    row.update(overrides)
    return row


def _analyze(monkeypatch, ticker: str = "NOK", qualitative_evidence: list[dict] | None = None) -> dict:
    import backend.app.reports.stock_analysis as stock_analysis

    monkeypatch.setattr(stock_analysis, "get_earnings_transcript_analysis", lambda symbol: _fallback_transcript(symbol))
    monkeypatch.setattr(stock_analysis, "get_fmp_financial_proxy", lambda symbol: _fallback_fmp_financial_proxy(symbol))
    request = stock_analysis.AnalyzeStockRequest(ticker=ticker, qualitative_evidence=qualitative_evidence or [])
    return stock_analysis.analyze_stock(request).model_dump(mode="json")


def _coverage_row(payload: dict, criterion_id: int) -> dict:
    return next(item for item in payload["jane_criteria_coverage"]["criteria"] if item["criterion_id"] == criterion_id)


def test_phase52_adr_manual_filing_metadata_is_preserved_and_filing_backed(monkeypatch) -> None:
    payload = _analyze(monkeypatch, qualitative_evidence=[_adr_manual_evidence()])

    assessment = payload["qualitative_evidence_assessment"]
    assert assessment["accepted_evidence_count"] == 1
    item = assessment["evidence_items"][0]
    assert item["accepted"] is True
    assert item["adr_evidence_type"] == "annual_report"
    assert item["document_title"] == "Nokia Annual Report 2025"
    assert item["document_date"] == "2026-03-05"
    assert item["source_date"] == "2026-03-05"
    assert item["filing_period"] == "FY2025"
    assert item["quoted_text"].startswith("The annual report governance section")
    assert item["source_url"].startswith("https://example.com/")
    assert item["local_market"] == "NASDAQ Helsinki"
    assert item["local_ticker"] == "NOKIA"
    assert item["translation_note"] == "English annual report; no translation required."
    assert item["source_quality"] == "filing_backed"
    assert item["verification_level"] == "filing_backed"
    assert item["not_investment_advice"] is True
    assert item["affects_score"] is False

    c2 = _coverage_row(payload, 2)
    assert c2["coverage_status"] == "partial"
    assert "founder_ownership" in c2["covered_submetrics"]
    assert c2["source_quality"] == "filing_backed"
    assert c2["accepted_evidence_item_count"] >= 1
    assert payload["foreign_filer_coverage_diagnostics"]["is_foreign_filer_or_adr"] is True


def test_phase52_adr_manual_filing_missing_document_date_stays_lower_confidence_and_reviewable(monkeypatch) -> None:
    evidence = _adr_manual_evidence(document_date=None, source_date=None)
    payload = _analyze(monkeypatch, qualitative_evidence=[evidence])

    item = payload["qualitative_evidence_assessment"]["evidence_items"][0]
    assert item["accepted"] is True
    assert item["adr_evidence_type"] == "annual_report"
    assert item["source_quality"] == "user_provided"
    assert item["verification_level"] == "user_provided"
    assert "document_date" in item["missing_data"]
    assert "source_date" in item["missing_data"]
    assert any("document date" in reason.lower() for reason in item["evidence_quality_reasons"])

    queue_blob = json.dumps(payload["stale_review_queue"].get("items", []))
    assert "missing_source_date" in queue_blob or "source_date" in queue_blob


def test_phase52_rejected_or_unmapped_adr_evidence_does_not_cover_submetric(monkeypatch) -> None:
    rejected = _adr_manual_evidence(
        summary="",
        source_url="https://example.com/nokia-annual-report-2025.pdf",
        document_date="2026-03-05",
    )
    payload = _analyze(monkeypatch, qualitative_evidence=[rejected])

    item = payload["qualitative_evidence_assessment"]["evidence_items"][0]
    assert item["accepted"] is False
    assert item["source_quality"] == "rejected"

    c2 = _coverage_row(payload, 2)
    assert "founder_ownership" not in c2["covered_submetrics"]


def test_phase52_domestic_ticker_accepts_existing_manual_evidence_without_adr_helper_requirement(monkeypatch) -> None:
    evidence = _adr_manual_evidence(adr_evidence_type=None, document_date=None, source_date="2026-03-05")
    payload = _analyze(monkeypatch, ticker="NVDA", qualitative_evidence=[evidence])

    assert payload["foreign_filer_coverage_diagnostics"]["is_foreign_filer_or_adr"] is False
    item = payload["qualitative_evidence_assessment"]["evidence_items"][0]
    assert item["accepted"] is True
    assert item["adr_evidence_type"] is None
    assert item["source_quality"] == "user_provided"
    assert _coverage_row(payload, 2)["accepted_evidence_item_count"] >= 1
