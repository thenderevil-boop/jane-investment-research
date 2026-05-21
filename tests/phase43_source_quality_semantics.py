from __future__ import annotations

from backend.app.engines.smart_money_engine import evaluate_form4_insider_signal
from backend.app.schemas.common import DataSourceStatus
from backend.app.schemas.earnings_transcript import EarningsTranscriptAnalysis


def _accumulation_transactions() -> list[dict]:
    return [
        {
            "insider_name": "Officer A",
            "role": "Chief Executive Officer",
            "transaction_code": "P",
            "transaction_type": "accumulation",
            "transaction_category": "accumulation",
            "shares": 1000,
            "price": 100.0,
            "value": 100_000,
            "transaction_date": "2026-04-10",
            "filing_date": "2026-04-12",
        },
        {
            "insider_name": "Officer B",
            "role": "Chief Financial Officer",
            "transaction_code": "P",
            "transaction_type": "accumulation",
            "transaction_category": "accumulation",
            "shares": 900,
            "price": 105.0,
            "value": 94_500,
            "transaction_date": "2026-04-11",
            "filing_date": "2026-04-13",
        },
    ]


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


def test_form4_cached_live_after_failure_is_treated_as_fallback_limited() -> None:
    result = evaluate_form4_insider_signal(
        {
            "form4_transactions": _accumulation_transactions(),
            "form4_source_status": {
                "source_type": "cached_live",
                "provider": "SEC EDGAR",
                "source": ["SEC EDGAR"],
                "source_date": "2026-04-13",
                "is_fresh": True,
                "fallback_used": True,
                "fallback_reason": "Live SEC Form 4 fetch failed; using cached Form 4 snapshot.",
            },
        }
    )

    assert result.score == 40
    assert result.label == "insider_activity_neutral"
    assert result.trend["insider_activity"] == "neutral"
    assert any("fallback" in item.lower() or "cached-after-failure" in item.lower() for item in result.limitations)


def test_form4_clean_cached_live_still_allows_positive_accumulation_signal() -> None:
    result = evaluate_form4_insider_signal(
        {
            "form4_transactions": _accumulation_transactions(),
            "form4_source_status": {
                "source_type": "cached_live",
                "provider": "SEC EDGAR",
                "source": ["SEC EDGAR"],
                "source_date": "2026-04-13",
                "is_fresh": True,
                "fallback_used": False,
            },
        }
    )

    assert result.score == 100
    assert result.label == "insider_accumulation_observed"
    assert result.trend["insider_activity"] == "accumulation_observed"


def test_fmp_fallback_is_reported_as_optional_provider_not_core_penalty(monkeypatch) -> None:
    import backend.app.reports.stock_analysis as stock_analysis

    monkeypatch.setattr(stock_analysis, "get_earnings_transcript_analysis", lambda ticker: _fallback_transcript(ticker))
    monkeypatch.setattr(stock_analysis, "get_fmp_financial_proxy", lambda ticker: _fallback_fmp_financial_proxy(ticker))

    response = stock_analysis.analyze_stock(stock_analysis.AnalyzeStockRequest(ticker="NVDA"))
    summary = response.model_dump(mode="json")["data_quality_summary"]

    assert "earnings_transcript_analysis" in summary["optional_provider_fallback_categories"]
    assert "fmp_financials" in summary["optional_provider_fallback_categories"]
    assert "earnings_transcript_analysis" not in summary["fallback_evidence_categories"]
    assert "fmp_financials" not in summary["fallback_evidence_categories"]
    assert summary["fmp_financials"]["optional_enhancement"] is True
    assert "earnings_transcript_analysis" not in summary["missing_source_date_categories"]
    assert "fmp_financials" not in summary["missing_source_date_categories"]


def test_adr_foreign_filer_context_explains_structural_sec_and_13f_limits(monkeypatch) -> None:
    import backend.app.reports.stock_analysis as stock_analysis

    monkeypatch.setattr(stock_analysis, "get_earnings_transcript_analysis", lambda ticker: _fallback_transcript(ticker))
    monkeypatch.setattr(stock_analysis, "get_fmp_financial_proxy", lambda ticker: _fallback_fmp_financial_proxy(ticker))

    response = stock_analysis.analyze_stock(stock_analysis.AnalyzeStockRequest(ticker="NOK"))
    dumped = response.model_dump(mode="json")
    context = dumped["data_quality_summary"]["foreign_filer_context"]

    assert context["is_foreign_filer_or_adr"] is True
    assert context["ticker"] == "NOK"
    assert context["structural_coverage_limitation"] is True
    assert "ADR" in context["user_explanation"] or "非美國" in context["user_explanation"]
    assert dumped["data_quality_summary"]["source_quality_grade"] != "D"
    assert any("ADR" in str(item) or "非美國" in str(item) for item in dumped["human_verification_queue"])
