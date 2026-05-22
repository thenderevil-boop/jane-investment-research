from __future__ import annotations

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


def _analyze(monkeypatch, ticker: str):
    import backend.app.reports.stock_analysis as stock_analysis

    monkeypatch.setattr(stock_analysis, "get_earnings_transcript_analysis", lambda symbol: _fallback_transcript(symbol))
    monkeypatch.setattr(stock_analysis, "get_fmp_financial_proxy", lambda symbol: _fallback_fmp_financial_proxy(symbol))
    return stock_analysis.analyze_stock(stock_analysis.AnalyzeStockRequest(ticker=ticker)).model_dump(mode="json")


def _coverage_row(payload: dict, criterion_id: int) -> dict:
    return next(item for item in payload["jane_criteria_coverage"]["criteria"] if item["criterion_id"] == criterion_id)


def test_phase51_adr_ticker_emits_structured_foreign_filer_diagnostics(monkeypatch) -> None:
    payload = _analyze(monkeypatch, "NOK")

    diagnostics = payload["foreign_filer_coverage_diagnostics"]
    assert diagnostics["is_foreign_filer_or_adr"] is True
    assert diagnostics["affects_score"] is False
    assert diagnostics["not_investment_advice"] is True
    assert "known_adr_or_foreign_listing" in diagnostics["detected_signals"]

    limitations_by_area = {item["area"]: item for item in diagnostics["coverage_limitations"]}
    assert limitations_by_area["sec_companyfacts"]["status"] == "structural_gap"
    assert limitations_by_area["sec_form4"]["status"] == "not_expected"
    assert limitations_by_area["fmp_transcript"]["status"] == "provider_gap"
    assert 2 in limitations_by_area["sec_form4"]["affected_criteria"]
    assert 17 in limitations_by_area["fmp_transcript"]["affected_criteria"]

    checks = diagnostics["recommended_manual_checks"]
    assert any(item["criterion_id"] == 2 and "founder" in item["check"].lower() for item in checks)
    assert any(item["criterion_id"] == 17 and "annual report" in item["check"].lower() for item in checks)
    assert "foreign_filer_coverage_diagnostics" in payload["data_quality_summary"]["excluded_from_scoring"]


def test_phase51_domestic_ticker_keeps_diagnostics_inactive(monkeypatch) -> None:
    payload = _analyze(monkeypatch, "NVDA")

    diagnostics = payload["foreign_filer_coverage_diagnostics"]
    assert diagnostics["is_foreign_filer_or_adr"] is False
    assert diagnostics["detected_signals"] == []
    assert diagnostics["coverage_limitations"] == []
    assert diagnostics["recommended_manual_checks"] == []
    assert diagnostics["affects_score"] is False
    assert diagnostics["not_investment_advice"] is True


def test_phase51_adr_manual_checks_are_added_to_coverage_rows(monkeypatch) -> None:
    payload = _analyze(monkeypatch, "NOK")

    c2 = _coverage_row(payload, 2)
    c5 = _coverage_row(payload, 5)
    c10 = _coverage_row(payload, 10)
    c17 = _coverage_row(payload, 17)

    assert "ADR" in c2["next_manual_check"] or "foreign" in c2["next_manual_check"].lower()
    assert "founder" in c2["next_manual_check"].lower()
    assert "annual report" in c5["next_manual_check"].lower()
    assert "cash-flow" in c10["next_manual_check"].lower() or "cash flow" in c10["next_manual_check"].lower()
    assert "transcript" in c17["next_manual_check"].lower() or "CEO letter" in c17["next_manual_check"]


def test_phase51_foreign_filer_diagnostics_do_not_change_score_or_verdict(monkeypatch) -> None:
    nok = _analyze(monkeypatch, "NOK")
    nvda = _analyze(monkeypatch, "NVDA")

    assert nok["foreign_filer_coverage_diagnostics"]["affects_score"] is False
    assert nok["research_verdict"]["label"] in {"worth_deep_research", "watchlist_candidate", "insufficient_data", "high_risk_context"}
    assert isinstance(nok["research_verdict"]["score"], float | int)
    assert nvda["foreign_filer_coverage_diagnostics"]["affects_score"] is False
