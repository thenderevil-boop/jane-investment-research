from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from backend.app import config
from backend.app.schemas.common import DataSourceStatus
from backend.app.schemas.earnings_transcript import EarningsTranscriptAnalysis
from backend.app.schemas.jane_external_evidence import JaneCriteriaExternalEvidenceItem
from backend.app.schemas.patent_ip import PatentIPEvidence


def _tmp_cache() -> Path:
    path = Path("backend/raw_store/cache/test_phase53") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _coverage_row(payload: dict, criterion_id: int) -> dict:
    return next(item for item in payload["jane_criteria_coverage"]["criteria"] if item["criterion_id"] == criterion_id)


def _profile(ticker: str, *, country: str = "United States", source_date: str = "2026-05-01") -> dict:
    is_nok = ticker.upper() == "NOK"
    return {
        "ticker": ticker.upper(),
        "company_name": "Nokia Oyj" if is_nok else "NVIDIA Corporation",
        "longName": "Nokia Oyj" if is_nok else "NVIDIA Corporation",
        "shortName": "Nokia" if is_nok else "NVIDIA",
        "sector": "Technology",
        "industry": "Communications Equipment" if is_nok else "Semiconductors",
        "market": "US",
        "exchange": "NYSE" if is_nok else "NMS",
        "country": country,
        "currency": "USD",
        "market_cap": 20_000_000_000 if is_nok else 3_000_000_000_000,
        "enterprise_value": 21_000_000_000 if is_nok else 2_990_000_000_000,
        "shares_outstanding": 5_400_000_000 if is_nok else 24_000_000_000,
        "current_price": 4.5 if is_nok else 125,
        "quoteType": "ADR" if is_nok else "EQUITY",
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": source_date,
        "limitations": [],
        "missing_data": [],
    }


def _fundamentals(ticker: str, *, source_date: str = "2026-05-01", include_short_fields: bool = False) -> dict:
    payload = {
        "ticker": ticker.upper(),
        "period": "ttm",
        "latest_fiscal_year": "2025",
        "latest_quarter": "2026-03-31",
        "revenue_ttm": 20_000_000_000,
        "gross_margin_pct": 43.5,
        "operating_margin_pct": 8.5,
        "net_income_ttm": 650_000_000,
        "net_income_margin_pct": 3.25,
        "operating_cash_flow_ttm": 1_800_000_000,
        "capex_ttm": -700_000_000,
        "free_cash_flow_ttm": 1_100_000_000,
        "free_cash_flow_margin_pct": 5.5,
        "cash_and_equivalents": 8_000_000_000,
        "total_debt": 5_000_000_000,
        "net_cash_or_debt": 3_000_000_000,
        "debt_to_equity": 38.0,
        "shares_outstanding": 5_400_000_000,
        "reported_currency": "EUR" if ticker.upper() == "NOK" else "USD",
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": source_date,
        "limitations": [],
        "missing_data": [],
    }
    if include_short_fields:
        payload["short_ratio"] = 11.0
        payload["shortRatio"] = 11.0
        payload["short_percent_of_float"] = 15.0
        payload["shortPercentOfFloat"] = 0.15
    return payload


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


def _empty_sec_companyfacts(ticker: str) -> dict:
    return {
        "ticker": ticker.upper(),
        "source_status": {
            "source_type": "fallback",
            "provider": "sec_companyfacts",
            "source_date": "",
            "fallback_used": True,
            "fallback_reason": "No SEC Companyfacts concepts available in fixture.",
            "missing_data": ["sec_companyfacts"],
        },
        "facts": {},
        "missing_data": ["Revenue", "ResearchAndDevelopmentExpense", "FreeCashFlow"],
    }


def _analyze(monkeypatch, ticker: str, *, missing_source_dates: bool = False, patent_evidence: PatentIPEvidence | None = None) -> dict:
    import backend.app.reports.stock_analysis as stock_analysis

    source_date = "" if missing_source_dates else "2026-05-01"
    country = "Finland" if ticker.upper() == "NOK" else "United States"
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", _tmp_cache())
    monkeypatch.setattr(stock_analysis, "get_company_profile", lambda symbol: _profile(symbol, country=country, source_date=source_date))
    monkeypatch.setattr(stock_analysis, "get_company_fundamentals", lambda symbol: _fundamentals(symbol, source_date=source_date))
    monkeypatch.setattr(stock_analysis, "get_sec_companyfacts", _empty_sec_companyfacts)
    monkeypatch.setattr(stock_analysis, "get_earnings_transcript_analysis", lambda symbol: _fallback_transcript(symbol))
    monkeypatch.setattr(stock_analysis, "get_fmp_financial_proxy", lambda symbol: _fallback_fmp_financial_proxy(symbol))
    if patent_evidence is not None:
        monkeypatch.setattr(stock_analysis, "get_patent_ip_evidence", lambda symbol, company_name="": patent_evidence)
    return stock_analysis.analyze_stock(stock_analysis.AnalyzeStockRequest(ticker=ticker)).model_dump(mode="json")


def test_phase53_c18_disabled_uspto_explains_activation_flag(monkeypatch) -> None:
    monkeypatch.setattr(config, "USE_LIVE_USPTO_PATENTS_DATA", False)

    payload = _analyze(monkeypatch, "NVDA")

    patent = payload["patent_ip_evidence"]
    c18 = _coverage_row(payload, 18)
    joined = " ".join([*patent["limitations"], *c18["limitations"], str(c18["next_manual_check"])])
    assert patent["source_status"]["fallback_used"] is True
    assert c18["coverage_status"] == "insufficient"
    assert "USE_LIVE_USPTO_PATENTS_DATA=true" in joined
    assert "provider disabled" in joined.lower() or "currently disabled" in joined.lower()
    assert "patent_count" not in c18["covered_submetrics"]
    assert patent["affects_score"] is False


def test_phase53_c18_enabled_uspto_patent_count_still_non_scoring(monkeypatch) -> None:
    evidence = PatentIPEvidence(
        ticker="NVDA",
        query_name="NVIDIA Corporation",
        patent_count=42,
        source_status=DataSourceStatus(provider="uspto_patentsview", source_type="live", source_date="2026-05-01"),
        criteria=[
            JaneCriteriaExternalEvidenceItem(
                criterion_id=18,
                criterion_name="Patents and IP",
                source="uspto_patentsview",
                source_quality="provider_backed",
                support_level="partial",
                confidence=0.55,
                covered_submetrics=["patent_count"],
                evidence_snippets=["PatentsView found 42 patent(s) assigned to names matching NVIDIA Corporation in the last 3 years."],
                manual_checks=["Confirm assignee/entity matching before relying on C18 IP evidence."],
                limitations=["Patent count is an auto-derived proxy and does not prove patent quality, relevance, or defensibility."],
            )
        ],
        criteria_count=1,
        ip_signal="limited",
        manual_checks=["Confirm assignee/entity matching before relying on C18 IP evidence."],
        limitations=["Patent count is an auto-derived proxy and does not prove patent quality, relevance, or defensibility."],
    )

    payload = _analyze(monkeypatch, "NVDA", patent_evidence=evidence)

    c18 = _coverage_row(payload, 18)
    assert payload["patent_ip_evidence"]["patent_count"] == 42
    assert payload["patent_ip_evidence"]["affects_score"] is False
    assert payload["patent_ip_evidence"]["not_investment_advice"] is True
    assert c18["coverage_status"] == "partial"
    assert c18["source_quality"] == "provider_backed"
    assert c18["covered_submetrics"] == ["patent_count"]


def test_phase53_nok_c3_missing_short_interest_is_explained_as_adr_source_gap(monkeypatch) -> None:
    payload = _analyze(monkeypatch, "NOK")

    c3 = _coverage_row(payload, 3)
    diagnostics = payload["foreign_filer_coverage_diagnostics"]
    joined = " ".join([*c3["limitations"], str(c3["next_manual_check"]), *(item["reason"] for item in diagnostics["coverage_limitations"])])
    assert diagnostics["is_foreign_filer_or_adr"] is True
    assert c3["coverage_status"] == "insufficient"
    assert "short_interest_proxy" not in c3["covered_submetrics"]
    assert "yfinance" in joined.lower()
    assert "short-interest" in joined.lower() or "short interest" in joined.lower()
    assert "ADR" in joined or "foreign-filer" in joined
    assert "not company" in joined.lower() or "not a company-quality weakness" in joined.lower()


def test_phase53_adr_source_gap_summary_names_data_structure_not_company_quality(monkeypatch) -> None:
    payload = _analyze(monkeypatch, "NOK", missing_source_dates=True)

    summary = payload["data_quality_summary"]
    assert summary["source_quality_grade"] != "D"
    assert summary["source_quality_grade"] in {"A", "B", "C"}
    text = " ".join([summary["source_quality_summary"], summary["foreign_filer_context"]["user_explanation"], *summary["foreign_filer_context"]["limitations"]])
    assert "ADR" in text or "foreign" in text.lower()
    assert "data-structure" in text.lower() or "source coverage" in text.lower() or "data source" in text.lower()
    assert "not company" in text.lower() or "should not be read as company-specific weakness" in text.lower()
    assert payload["foreign_filer_coverage_diagnostics"]["affects_score"] is False
