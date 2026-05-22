from __future__ import annotations

import importlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import company_profile, sec_companyfacts
from backend.app.main import app
from backend.app.reports import stock_analysis
from backend.app.raw_store import company_cache

client = TestClient(app)


def _tmp_cache() -> Path:
    path = Path("backend/raw_store/cache/test_phase42") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _nok_income_statement() -> list[dict]:
    return [
        {
            "date": "2025-12-31",
            "symbol": "NOK",
            "reportedCurrency": "EUR",
            "cik": "0000924613",
            "filingDate": "2026-03-05",
            "fiscalYear": "2025",
            "period": "FY",
            "revenue": 19_889_000_000,
            "grossProfit": 8_659_000_000,
            "researchAndDevelopmentExpenses": 4_855_000_000,
            "operatingIncome": 782_000_000,
            "netIncome": 651_000_000,
            "eps": 0.11,
        },
        {
            "date": "2024-12-31",
            "symbol": "NOK",
            "reportedCurrency": "EUR",
            "cik": "0000924613",
            "filingDate": "2025-03-13",
            "fiscalYear": "2024",
            "period": "FY",
            "revenue": 19_220_000_000,
            "grossProfit": 8_864_000_000,
            "researchAndDevelopmentExpenses": 4_512_000_000,
            "operatingIncome": 1_590_000_000,
            "netIncome": 1_277_000_000,
            "eps": 0.23,
        },
        {
            "date": "2023-12-31",
            "symbol": "NOK",
            "reportedCurrency": "EUR",
            "cik": "0000924613",
            "filingDate": "2024-02-29",
            "fiscalYear": "2023",
            "period": "FY",
            "revenue": 21_138_000_000,
            "grossProfit": 8_546_000_000,
            "researchAndDevelopmentExpenses": 4_277_000_000,
            "operatingIncome": 1_470_000_000,
            "netIncome": 665_000_000,
            "eps": 0.12,
        },
    ]


def _nok_balance_sheet() -> list[dict]:
    return [
        {
            "date": "2025-12-31",
            "symbol": "NOK",
            "reportedCurrency": "EUR",
            "fiscalYear": "2025",
            "period": "FY",
            "cashAndCashEquivalents": 6_100_000_000,
            "totalDebt": 4_200_000_000,
            "totalStockholdersEquity": 21_500_000_000,
        }
    ]


def _nok_cash_flow() -> list[dict]:
    return [
        {
            "date": "2025-12-31",
            "symbol": "NOK",
            "reportedCurrency": "EUR",
            "fiscalYear": "2025",
            "period": "FY",
            "netCashProvidedByOperatingActivities": 2_000_000_000,
            "capitalExpenditure": -650_000_000,
            "freeCashFlow": 1_350_000_000,
        }
    ]


def _nok_ratios_ttm() -> list[dict]:
    return [
        {
            "symbol": "NOK",
            "date": "2026-03-05",
            "priceToEarningsRatioTTM": 28.0,
            "priceToFreeCashFlowsRatioTTM": 48.04,
            "returnOnEquityTTM": 3.1,
            "freeCashFlowPerShareTTM": 0.24,
        }
    ]


class DummyResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        return None


def _fake_fmp_get(url: str, timeout: int = 15):
    if "income-statement" in url:
        return DummyResponse(_nok_income_statement())
    if "balance-sheet-statement" in url:
        return DummyResponse(_nok_balance_sheet())
    if "cash-flow-statement" in url:
        return DummyResponse(_nok_cash_flow())
    if "ratios-ttm" in url:
        return DummyResponse(_nok_ratios_ttm())
    raise AssertionError(f"Unexpected FMP URL: {url}")


def _profile(ticker: str = "NOK") -> dict:
    return {
        "ticker": ticker,
        "company_name": "Nokia Oyj",
        "sector": "Technology",
        "market": "US",
        "country": "Finland",
        "market_cap": 76_731_932_672,
        "enterprise_value": 74_039_377_920,
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": "2026-05-20",
        "limitations": [],
        "missing_data": [],
    }


def _fundamentals(ticker: str = "NOK") -> dict:
    return {
        "ticker": ticker,
        "period": "ttm",
        "revenue_ttm": 19_889_000_000,
        "revenue_yoy_growth_pct": 3.5,
        "gross_margin_pct": 43.5,
        "operating_margin_pct": 3.9,
        "net_income_margin_pct": 3.3,
        "free_cash_flow_ttm": 1_350_000_000,
        "cash_and_equivalents": 6_100_000_000,
        "total_debt": 4_200_000_000,
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": "2026-05-20",
        "limitations": [],
        "missing_data": [],
    }


def _empty_sec_companyfacts() -> dict:
    return sec_companyfacts.parse_companyfacts("NOK", "0000924613", {"facts": {"us-gaap": {}}}, source_type="live")


def test_fmp_financial_adapter_uses_stable_symbol_query_and_normalizes_object_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("USE_LIVE_FMP_DATA", "true")
    monkeypatch.setenv("FMP_API_KEY", "dummy_fmp_key_for_test")
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", tmp_path)

    import backend.app.config as config_module
    import backend.app.data_sources.provider_registry as registry
    import backend.app.data_sources.fmp_financials as fmp_financials

    importlib.reload(config_module)
    importlib.reload(registry)
    importlib.reload(fmp_financials)
    monkeypatch.setattr(config_module, "MARKET_DATA_CACHE_DIR", tmp_path)

    requested_urls: list[str] = []

    def stable_get(url: str, timeout: int = 15):
        requested_urls.append(url)
        if "income-statement" in url:
            return DummyResponse(_nok_income_statement()[0])
        if "balance-sheet-statement" in url:
            return DummyResponse(_nok_balance_sheet()[0])
        if "cash-flow-statement" in url:
            return DummyResponse(_nok_cash_flow()[0])
        if "ratios-ttm" in url:
            return DummyResponse(_nok_ratios_ttm()[0])
        raise AssertionError(f"Unexpected FMP URL: {url}")

    proxy = fmp_financials.fetch_fmp_financial_proxy("nok", http_get=stable_get)

    paths = [urlparse(url).path for url in requested_urls]
    assert paths == [
        "/stable/income-statement",
        "/stable/balance-sheet-statement",
        "/stable/cash-flow-statement",
        "/stable/ratios-ttm",
    ]
    for url in requested_urls:
        query = parse_qs(urlparse(url).query)
        assert query["symbol"] == ["NOK"]
        assert query["apikey"] == ["dummy_fmp_key_for_test"]
    assert proxy["available"] is True
    assert proxy["latest_fiscal_year"] == "2025"
    assert proxy["reported_currency"] == "EUR"
    assert proxy["facts"]["revenue"] == 19_889_000_000
    assert proxy["derived_metrics"]["rd_to_revenue_pct"] == 24.4105
    assert proxy["ttm_ratios"]["price_to_free_cash_flow_ttm"] == 48.04
    assert "dummy_fmp_key_for_test" not in json.dumps(proxy)


def test_fmp_financial_adapter_normalizes_nok_statements_and_ttm_ratios(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("USE_LIVE_FMP_DATA", "true")
    monkeypatch.setenv("FMP_API_KEY", "dummy_fmp_key_for_test")
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", tmp_path)

    import backend.app.config as config_module
    import backend.app.data_sources.provider_registry as registry
    import backend.app.data_sources.fmp_financials as fmp_financials

    importlib.reload(config_module)
    importlib.reload(registry)
    importlib.reload(fmp_financials)
    monkeypatch.setattr(config_module, "MARKET_DATA_CACHE_DIR", tmp_path)

    requested_urls: list[str] = []

    def tracking_get(url: str, timeout: int = 15):
        requested_urls.append(url)
        return _fake_fmp_get(url, timeout=timeout)

    proxy = fmp_financials.fetch_fmp_financial_proxy("nok", http_get=tracking_get)

    assert proxy["ticker"] == "NOK"
    assert proxy["available"] is True
    assert proxy["source_status"]["provider"] == "fmp_financials"
    assert proxy["source_status"]["source_type"] == "live"
    assert proxy["latest_fiscal_year"] == "2025"
    assert proxy["reported_currency"] == "EUR"
    assert proxy["filing_date"] == "2026-03-05"
    assert proxy["derived_metrics"]["revenue_yoy_growth_pct"] == 3.4807
    assert proxy["derived_metrics"]["gross_margin_pct"] == 43.5366
    assert proxy["derived_metrics"]["operating_margin_pct"] == 3.9318
    assert proxy["derived_metrics"]["rd_to_revenue_pct"] == 24.4105
    assert proxy["derived_metrics"]["free_cash_flow_ttm"] == 1_350_000_000
    assert proxy["ttm_ratios"]["price_to_free_cash_flow_ttm"] == 48.04
    dumped = json.dumps(proxy)
    assert "dummy_fmp_key_for_test" not in dumped
    assert all("dummy_fmp_key_for_test" in url for url in requested_urls)


def test_analyze_stock_uses_fmp_financial_proxy_when_sec_companyfacts_has_zero_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "USE_LIVE_FMP_DATA", True)
    monkeypatch.setattr(config, "FMP_API_KEY", "dummy_fmp_key_for_test")
    monkeypatch.setattr(config, "USE_LIVE_COMPANY_DATA", True)
    monkeypatch.setattr(config, "USE_LIVE_SEC_COMPANYFACTS", True)
    monkeypatch.setattr(company_profile, "fetch_company_profile", _profile)
    monkeypatch.setattr(company_profile, "fetch_company_fundamentals", _fundamentals)
    monkeypatch.setattr(company_cache, "get_sec_companyfacts", lambda ticker: _empty_sec_companyfacts())
    monkeypatch.setattr(stock_analysis, "get_sec_companyfacts", lambda ticker: _empty_sec_companyfacts())

    from backend.app.features.earnings_transcript_analysis import analyze_earnings_transcripts
    import backend.app.data_sources.fmp_financials as fmp_financials

    monkeypatch.setattr(stock_analysis, "get_earnings_transcript_analysis", lambda ticker: analyze_earnings_transcripts(ticker, []))
    monkeypatch.setattr(stock_analysis, "get_fmp_financial_proxy", lambda ticker: fmp_financials.fetch_fmp_financial_proxy(ticker, http_get=_fake_fmp_get))

    response = client.post("/api/analyze-stock", json={"ticker": "NOK", "market": "US"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["earnings_transcript_analysis"]["quarters_analyzed"] == 0
    assert payload["fmp_financial_proxy"]["available"] is True
    assert payload["fmp_financial_proxy"]["latest_fiscal_year"] == "2025"
    assert payload["data_quality_summary"]["fmp_financials"]["available"] is True
    assert payload["data_quality_summary"]["fmp_financials"]["reported_currency"] == "EUR"
    assert payload["financial_quality"]["raw_data"]["fmp_financial_proxy_used"] is True
    assert payload["financial_quality"]["raw_data"]["reported_currency"] == "EUR"
    assert payload["financial_quality"]["raw_data"]["rd_to_revenue_pct"] == 24.4105
    assert payload["fundamentals_cross_check"]["fmp_ttm_ratio_context"]["available"] is True
    assert payload["fundamentals_cross_check"]["provider"] == "mixed_SEC_companyfacts_yfinance_and_FMP_financials"
    assert "SEC Companyfacts filing-backed financial facts are available" not in json.dumps(payload["candidate_validation_summary"])
    assert any("FMP financial" in item for item in payload["candidate_validation_summary"]["primary_strengths"])
    assert "dummy_fmp_key_for_test" not in json.dumps(payload)


def test_fmp_financial_proxy_does_not_override_valid_sec_companyfacts(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.app.data_sources.fmp_financials as fmp_financials

    yfinance = {"revenue_ttm": 100, "source_status": {"source_type": "live", "provider": "yfinance", "source_date": "2026-05-20"}, "missing_data": [], "limitations": []}
    sec = {
        "facts": {"revenue": {"value": 100}},
        "derived_metrics": {"gross_margin_pct": 70.0},
        "source_status": {"source_type": "live", "provider": "SEC_companyfacts", "source_date": "2026-03-01"},
        "missing_data": [],
        "limitations": [],
    }
    cross_check = {"agreement_level": "high", "limitations": []}
    proxy = fmp_financials.disabled_fmp_financial_proxy("NVDA", "External provider 'fmp' is disabled.")

    merged = stock_analysis._merge_financials_with_sec_and_fmp(yfinance, sec, cross_check, proxy)

    assert merged["provider"] == "derived_from_SEC_companyfacts_and_yfinance"
    assert merged["sec_source_basis"] == "derived_from_mixed_sources"
    assert merged.get("fmp_financial_proxy_used") is not True
