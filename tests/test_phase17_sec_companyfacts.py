from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import company_profile, sec_companyfacts
from backend.app.main import app
from backend.app.reports import stock_analysis
from backend.app.raw_store import company_cache
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def _tmp_cache() -> Path:
    path = Path("backend/raw_store/cache/test_phase17") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _fact(concept: str, val: float, end: str = "2026-01-31", fy: int = 2026, form: str = "10-K") -> dict:
    return {
        "facts": {
            "us-gaap": {
                concept: {
                    "units": {
                        "USD": [
                            {"fy": fy, "fp": "FY", "form": form, "filed": "2026-03-15", "start": f"{fy-1}-02-01", "end": end, "val": val}
                        ]
                    }
                }
            }
        }
    }


def _companyfacts_payload(primary_revenue: bool = True) -> dict:
    concepts: dict = {}

    def add(concept: str, values: list[tuple[int, float]], unit: str = "USD"):
        concepts[concept] = {
            "units": {
                unit: [
                    {"fy": fy, "fp": "FY", "form": "10-K", "filed": f"{fy}-03-15", "start": f"{fy-1}-02-01", "end": f"{fy}-01-31", "val": value}
                    for fy, value in values
                ]
            }
        }

    add("RevenueFromContractWithCustomerExcludingAssessedTax" if primary_revenue else "Revenues", [(2026, 130_000_000_000), (2025, 100_000_000_000), (2024, 80_000_000_000), (2023, 60_000_000_000)])
    add("GrossProfit", [(2026, 91_000_000_000)])
    add("OperatingIncomeLoss", [(2026, 78_000_000_000)])
    add("NetIncomeLoss", [(2026, 55_000_000_000)])
    add("NetCashProvidedByUsedInOperatingActivities", [(2026, 64_000_000_000)])
    add("PaymentsToAcquirePropertyPlantAndEquipment", [(2026, 4_000_000_000)])
    add("CashAndCashEquivalentsAtCarryingValue", [(2026, 45_000_000_000)])
    add("LongTermDebt", [(2026, 11_000_000_000)])
    add("StockholdersEquity", [(2026, 44_000_000_000)])
    add("AccountsReceivableNetCurrent", [(2026, 15_000_000_000)])
    add("InventoryNet", [(2026, 8_000_000_000)])
    add("EntityCommonStockSharesOutstanding", [(2026, 24_000_000_000), (2025, 24_100_000_000), (2024, 24_200_000_000), (2023, 24_300_000_000)], unit="shares")
    return {"cik": "1045810", "facts": {"us-gaap": concepts}}


def _misaligned_companyfacts_payload(*, fallback_revenue_2026: bool = False) -> dict:
    concepts: dict = {}

    def add(concept: str, rows: list[dict], unit: str = "USD"):
        concepts[concept] = {"units": {unit: rows}}

    add(
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        [
            {"fy": 2022, "fp": "FY", "form": "10-K", "filed": "2022-03-18", "start": "2021-02-01", "end": "2022-01-30", "val": 26_914_000_000}
        ],
    )
    if fallback_revenue_2026:
        add(
            "Revenues",
            [
                {"fy": 2026, "fp": "FY", "form": "10-K", "filed": "2026-03-15", "start": "2025-01-26", "end": "2026-01-25", "val": 130_000_000_000},
                {"fy": 2025, "fp": "FY", "form": "10-K", "filed": "2025-03-15", "start": "2024-01-26", "end": "2025-01-25", "val": 100_000_000_000},
            ],
        )
    add("GrossProfit", [{"fy": 2026, "fp": "FY", "form": "10-K", "filed": "2026-03-15", "start": "2025-01-26", "end": "2026-01-25", "val": 153_463_000_000}])
    add("OperatingIncomeLoss", [{"fy": 2026, "fp": "FY", "form": "10-K", "filed": "2026-03-15", "start": "2025-01-26", "end": "2026-01-25", "val": 130_387_000_000}])
    add("NetIncomeLoss", [{"fy": 2026, "fp": "FY", "form": "10-K", "filed": "2026-03-15", "start": "2025-01-26", "end": "2026-01-25", "val": 120_067_000_000}])
    add("NetCashProvidedByUsedInOperatingActivities", [{"fy": 2026, "fp": "FY", "form": "10-K", "filed": "2026-03-15", "start": "2025-01-26", "end": "2026-01-25", "val": 102_718_000_000}])
    add("PaymentsToAcquirePropertyPlantAndEquipment", [{"fy": 2012, "fp": "FY", "form": "10-K", "filed": "2012-03-13", "start": "2011-01-31", "end": "2012-01-29", "val": 138_735_000}])
    add("CashAndCashEquivalentsAtCarryingValue", [{"fy": 2026, "fp": "FY", "form": "10-K", "filed": "2026-03-15", "end": "2026-01-25", "val": 45_000_000_000}])
    add("AccountsReceivableNetCurrent", [{"fy": 2026, "fp": "FY", "form": "10-K", "filed": "2026-03-15", "end": "2026-01-25", "val": 20_000_000_000}])
    return {"cik": "1045810", "facts": {"us-gaap": concepts}}


def _sec_snapshot(primary_revenue: bool = True) -> dict:
    return sec_companyfacts.parse_companyfacts("NVDA", "1045810", _companyfacts_payload(primary_revenue), source_type="live")


def _provider_normalization_diff_sec_snapshot() -> dict:
    payload = _companyfacts_payload()
    rows = payload["facts"]["us-gaap"]["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"]
    rows[0]["val"] = 34_000_000_000
    payload["facts"]["us-gaap"]["CashAndCashEquivalentsAtCarryingValue"]["units"]["USD"][0]["val"] = 30_000_000_000
    payload["facts"]["us-gaap"]["LongTermDebt"]["units"]["USD"][0]["val"] = 25_000_000_000
    return sec_companyfacts.parse_companyfacts("NVDA", "1045810", payload, source_type="live")


def _profile(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "company_name": "NVIDIA Corporation",
        "sector": "Technology",
        "market": "US",
        "market_cap": 3_000_000_000_000,
        "enterprise_value": 2_990_000_000_000,
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": "2026-05-01",
        "limitations": [],
        "missing_data": [],
    }


def _fundamentals(ticker: str = "NVDA", revenue: float = 130_000_000_000) -> dict:
    return {
        "ticker": ticker,
        "period": "ttm",
        "revenue_ttm": revenue,
        "revenue_yoy_growth_pct": 28.0,
        "revenue_3y_cagr_pct": 29.0,
        "gross_margin_pct": 70.0,
        "operating_margin_pct": 60.0,
        "net_income_ttm": 55_000_000_000,
        "net_income_margin_pct": 42.0,
        "operating_cash_flow_ttm": 64_000_000_000,
        "capex_ttm": -4_000_000_000,
        "free_cash_flow_ttm": 60_000_000_000,
        "free_cash_flow_margin_pct": 46.0,
        "cash_and_equivalents": 45_000_000_000,
        "total_debt": 11_000_000_000,
        "net_cash_or_debt": 34_000_000_000,
        "debt_to_equity": 25.0,
        "shares_outstanding": 24_000_000_000,
        "share_dilution_3y_pct": None,
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": "2026-05-01",
        "limitations": [],
        "missing_data": [],
    }


def _analyze(monkeypatch, sec_snapshot: dict | None = None, revenue: float = 130_000_000_000) -> dict:
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "USE_LIVE_COMPANY_DATA", True)
    monkeypatch.setattr(company_profile, "fetch_company_profile", _profile)
    monkeypatch.setattr(company_profile, "fetch_company_fundamentals", lambda ticker: _fundamentals(ticker, revenue))
    monkeypatch.setattr(stock_analysis, "get_sec_companyfacts", lambda ticker: sec_snapshot or _sec_snapshot())
    response = client.post(
        "/api/analyze-stock",
        json={"ticker": "NVDA", "market": "US", "research_context": {"theme": "AI infrastructure", "user_reason": "External trend research"}},
    )
    assert response.status_code == 200
    return response.json()


def test_companyfacts_endpoint_uses_padded_cik():
    assert sec_companyfacts.companyfacts_endpoint("1045810").endswith("CIK0001045810.json")


def test_companyfacts_client_sends_user_agent_without_exposing(monkeypatch):
    seen_headers = {}

    class Response:
        def raise_for_status(self): ...
        def json(self): return _companyfacts_payload()

    def fake_get(url, headers, timeout):
        seen_headers.update(headers)
        return Response()

    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Jane Research jane@example.com")
    monkeypatch.setattr(sec_companyfacts.httpx, "get", fake_get)
    parsed = sec_companyfacts.fetch_companyfacts("1045810")
    assert seen_headers["User-Agent"] == "Jane Research jane@example.com"
    assert "Jane Research" not in json.dumps(sec_companyfacts.parse_companyfacts("NVDA", "1045810", parsed))


def test_companyfacts_cache_read_write(monkeypatch):
    monkeypatch.setattr(config, "SEC_COMPANYFACTS_CACHE_DIR", _tmp_cache())
    written = company_cache.write_sec_companyfacts_data("NVDA", _sec_snapshot())
    read = company_cache.read_sec_companyfacts_data("NVDA")
    assert read["ticker"] == written["ticker"] == "NVDA"
    assert "headers" not in read


def test_companyfacts_parser_extracts_primary_and_fallback_revenue():
    primary = _sec_snapshot(primary_revenue=True)
    fallback = _sec_snapshot(primary_revenue=False)
    assert primary["facts"]["revenue"]["concept"] == "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
    assert fallback["facts"]["revenue"]["concept"] == "us-gaap:Revenues"
    for key in ["gross_profit", "operating_income", "net_income", "operating_cash_flow", "capex", "cash_and_equivalents", "total_debt", "accounts_receivable", "inventory"]:
        assert primary["facts"][key]["value"] is not None


def test_companyfacts_missing_concepts_and_no_fabricated_dilution():
    parsed = sec_companyfacts.parse_companyfacts("NVDA", "1045810", _fact("Revenues", 10_000_000), source_type="live")
    assert parsed["facts"]["gross_profit"] is None
    assert parsed["derived_metrics"]["share_dilution_3y_pct"] is None
    assert any("share dilution not inferred" in item for item in parsed["missing_data"])


def test_analyze_stock_phase17_contract(monkeypatch):
    payload = _analyze(monkeypatch)
    signals = {item["name"]: item for item in payload["financial_statement_signals"]["signals"]}
    criteria = {item["name"]: item for item in payload["jane_company_quality"]["criteria"]}
    matrix = {item["category"]: item for item in payload["evidence_matrix"]}

    assert payload["not_investment_advice"] is True
    assert payload["sec_financial_facts"]["facts"]["revenue"]["value"] == 130_000_000_000
    assert payload["fundamentals_cross_check"]["agreement_level"] == "high"
    assert signals["revenue_growth_quality"]["source_quality"] == "filing_backed"
    assert criteria["financial_statement_quality"]["source_quality"] == "derived_from_mixed_sources"
    assert criteria["monopoly_power"]["status"] == "insufficient"
    assert "sec_companyfacts" in payload["data_quality_summary"]
    assert matrix["sec_financial_facts"]["source_quality"] == "filing_backed"
    assert matrix["fundamentals_cross_check"]["source_quality"] == "derived_from_mixed_sources"
    assert detect_forbidden_language(payload) == []
    assert "SEC_EDGAR_USER_AGENT" not in json.dumps(payload)
    assert "data.sec.gov/api/xbrl/companyfacts" not in json.dumps(payload)


def test_cross_check_marks_divergent(monkeypatch):
    payload = _analyze(monkeypatch, revenue=80_000_000_000)
    revenue = next(item for item in payload["fundamentals_cross_check"]["checked_metrics"] if item["name"] == "revenue_ttm")
    assert revenue["status"] == "divergent"
    assert payload["fundamentals_cross_check"]["agreement_level"] == "low"
    assert "fundamentals_cross_check_divergent" in json.dumps(payload["score_driver_breakdown"])


def test_phase17a_parser_does_not_mix_old_revenue_with_current_profit():
    parsed = sec_companyfacts.parse_companyfacts("NVDA", "1045810", _misaligned_companyfacts_payload(), source_type="live")
    assert parsed["aligned_statement_period"] == "2026-01-25"
    assert parsed["facts"]["revenue"] is None
    assert parsed["facts"]["gross_profit"]["period"] == "2026-01-25"
    assert parsed["derived_metrics"]["gross_margin_pct"] is None
    assert parsed["derived_metrics"]["operating_margin_pct"] is None
    assert parsed["derived_metrics"]["net_income_margin_pct"] is None
    assert parsed["invalid_derived_metrics"]["gross_margin_pct"] == "invalid_period_alignment"


def test_phase17a_parser_does_not_use_stale_capex_with_current_ocf():
    parsed = sec_companyfacts.parse_companyfacts("NVDA", "1045810", _misaligned_companyfacts_payload(), source_type="live")
    assert parsed["facts"]["operating_cash_flow"]["period"] == "2026-01-25"
    assert parsed["facts"]["capex"] is None
    assert parsed["derived_metrics"]["fcf"] is None
    assert parsed["derived_metrics"]["capex_as_pct_of_ocf"] is None
    assert "capex for latest aligned fiscal year" in parsed["missing_data"]


def test_phase17a_revenue_fallback_uses_same_fiscal_period_before_old_revenue():
    parsed = sec_companyfacts.parse_companyfacts("NVDA", "1045810", _misaligned_companyfacts_payload(fallback_revenue_2026=True), source_type="live")
    assert parsed["facts"]["revenue"]["concept"] == "us-gaap:Revenues"
    assert parsed["facts"]["revenue"]["period"] == "2026-01-25"
    assert parsed["derived_metrics"]["gross_margin_pct"] is None
    assert parsed["invalid_derived_metrics"]["gross_margin_pct"] == "invalid_period_alignment"


def test_phase17a_cross_check_ignores_invalid_sec_alignment(monkeypatch):
    sec_snapshot = sec_companyfacts.parse_companyfacts("NVDA", "1045810", _misaligned_companyfacts_payload(), source_type="live")
    payload = _analyze(monkeypatch, sec_snapshot=sec_snapshot)
    margin = next(item for item in payload["fundamentals_cross_check"]["checked_metrics"] if item["name"] == "gross_margin_pct")
    assert margin["status"] == "sec_invalid_period_alignment"
    assert margin["difference_pct"] is None
    assert payload["fundamentals_cross_check"]["agreement_level"] != "low"
    assert "fundamentals_cross_check_divergent" not in json.dumps(payload["score_driver_breakdown"])


def test_phase17a_signals_and_quality_fallback_to_yfinance_for_invalid_sec_ratios(monkeypatch):
    sec_snapshot = sec_companyfacts.parse_companyfacts("NVDA", "1045810", _misaligned_companyfacts_payload(), source_type="live")
    payload = _analyze(monkeypatch, sec_snapshot=sec_snapshot)
    signals = {item["name"]: item for item in payload["financial_statement_signals"]["signals"]}
    criteria = {item["name"]: item for item in payload["jane_company_quality"]["criteria"]}
    assert signals["operating_margin_strength"]["status"] == "supportive"
    assert signals["operating_margin_strength"]["source_quality"] != "filing_backed"
    assert criteria["financial_statement_quality"]["status"] in {"supportive", "neutral"}
    assert criteria["financial_statement_quality"]["source_quality"] != "filing_backed"
    assert "period-alignment review" in payload["candidate_validation_summary"]["company_assessment"]


def test_phase17a_guardrails_for_misaligned_sec_payload(monkeypatch):
    sec_snapshot = sec_companyfacts.parse_companyfacts("NVDA", "1045810", _misaligned_companyfacts_payload(), source_type="live")
    payload = _analyze(monkeypatch, sec_snapshot=sec_snapshot)
    text = json.dumps(payload)
    assert '"source_type": "mixed"' not in text
    assert "SEC_EDGAR_USER_AGENT" not in text
    assert "data.sec.gov/api/xbrl/companyfacts" not in text
    report = client.get("/api/daily-report/latest")
    assert report.status_code in {200, 503}
    if report.status_code == 200:
        assert report.json().get("daily_report_metadata", {}).get("read_mode") == "snapshot_first"


def test_phase17a_old_parsed_companyfacts_cache_is_not_served(monkeypatch):
    cache_dir = _tmp_cache()
    monkeypatch.setattr(config, "SEC_COMPANYFACTS_CACHE_DIR", cache_dir)
    monkeypatch.setattr(config, "USE_LIVE_SEC_COMPANYFACTS", True)
    bad_cached = {
        "ticker": "NVDA",
        "cik": "0001045810",
        "parser_version": "old_phase17_parser",
        "cached_at": "2026-05-06T00:00:00+00:00",
        "source_type": "live",
        "provider": "SEC EDGAR companyfacts",
        "facts": {
            "revenue": {"value": 26_914_000_000, "unit": "USD", "period": "2022-01-30", "form": "10-K", "filed": "2022-03-18", "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"},
            "gross_profit": {"value": 153_463_000_000, "unit": "USD", "period": "2026-01-25", "form": "10-K", "filed": "2026-03-15", "concept": "us-gaap:GrossProfit"},
            "operating_cash_flow": {"value": 102_718_000_000, "unit": "USD", "period": "2026-01-25", "form": "10-K", "filed": "2026-03-15", "concept": "us-gaap:NetCashProvidedByUsedInOperatingActivities"},
            "capex": {"value": 138_735_000, "unit": "USD", "period": "2012-01-29", "form": "10-K", "filed": "2012-03-13", "concept": "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"},
        },
        "derived_metrics": {
            "gross_margin_pct": 570.1977,
            "operating_margin_pct": 484.4579,
            "net_income_margin_pct": 446.1135,
            "capex_as_pct_of_ocf": 0.1351,
        },
        "source_status": {"source_type": "live", "provider": "SEC EDGAR companyfacts", "source_date": "2026-03-15", "is_fresh": True, "freshness_window": "latest_company_filing", "fallback_used": False, "limitations": [], "missing_data": []},
        "limitations": [],
        "missing_data": [],
    }
    (cache_dir / "NVDA_companyfacts.json").write_text(json.dumps(bad_cached), encoding="utf-8")
    (cache_dir / "NVDA_companyfacts_raw.json").write_text(
        json.dumps(
            {
                "ticker": "NVDA",
                "cik": "0001045810",
                "cached_at": "2026-05-06T00:00:00+00:00",
                "provider": "SEC EDGAR companyfacts",
                "raw_payload": _misaligned_companyfacts_payload(),
            }
        ),
        encoding="utf-8",
    )
    parsed = company_cache.get_sec_companyfacts("NVDA")
    assert parsed["parser_version"] == sec_companyfacts.PARSER_VERSION
    assert parsed["facts"]["revenue"] is None
    assert parsed["facts"]["capex"] is None
    assert parsed["derived_metrics"]["gross_margin_pct"] is None
    assert parsed["derived_metrics"]["capex_as_pct_of_ocf"] is None
    assert parsed["invalid_derived_metrics"]["gross_margin_pct"] == "invalid_period_alignment"


def test_phase17b_companyfacts_latest_filing_is_not_stale():
    parsed = _sec_snapshot()
    status = parsed["source_status"]
    assert status["freshness_window"] == "latest_company_filing"
    assert status["is_fresh"] is True


def test_phase17b_cached_latest_companyfacts_uses_filing_freshness(monkeypatch):
    cache_dir = _tmp_cache()
    monkeypatch.setattr(config, "SEC_COMPANYFACTS_CACHE_DIR", cache_dir)
    monkeypatch.setattr(config, "USE_LIVE_SEC_COMPANYFACTS", True)
    company_cache.write_sec_companyfacts_data("NVDA", _sec_snapshot())
    cached = company_cache.get_sec_companyfacts("NVDA")
    assert cached["source_status"]["source_type"] == "cached_live"
    assert cached["source_status"]["freshness_window"] == "latest_company_filing"
    assert cached["source_status"]["is_fresh"] is True


def test_phase17b_cross_check_summary_distinguishes_provider_normalization(monkeypatch):
    payload = _analyze(monkeypatch, sec_snapshot=_provider_normalization_diff_sec_snapshot(), revenue=130_000_000_000)
    cross = payload["fundamentals_cross_check"]
    assert cross["parser_period_alignment_valid"] is True
    assert cross["agreement_level"] == "low"
    assert cross["provider_normalization_discrepancies"] is True
    assert "agree on revenue and gross margin" in cross["summary"]
    assert "period-alignment review" not in cross["summary"]


def test_phase17b_evidence_matrix_alignment_and_no_invalid_wording(monkeypatch):
    payload = _analyze(monkeypatch, sec_snapshot=_provider_normalization_diff_sec_snapshot(), revenue=130_000_000_000)
    matrix = {item["category"]: item for item in payload["evidence_matrix"]}
    sec_row_text = " ".join(matrix["sec_financial_facts"]["key_evidence"])
    cross_row_text = " ".join(matrix["fundamentals_cross_check"]["key_evidence"])
    assert "Filing-backed facts: 12" in sec_row_text
    assert "Invalid derived metrics: 0" in sec_row_text
    assert "Aligned statement period: 2026-01-31" in sec_row_text
    assert "Aligned balance sheet period: 2026-01-31" in sec_row_text
    assert "Parser period alignment valid: True" in cross_row_text
    assert "Provider normalization discrepancies: True" in cross_row_text
    assert "period-alignment review" not in json.dumps(matrix["fundamentals_cross_check"])


def test_phase17b_aligned_facts_produce_sane_margins_and_current_capex():
    parsed = _sec_snapshot()
    assert 69 <= parsed["derived_metrics"]["gross_margin_pct"] <= 72
    assert parsed["derived_metrics"]["gross_margin_pct"] != 570.1977
    assert parsed["facts"]["capex"]["period"] == "2026-01-31"
    assert parsed["derived_metrics"]["capex_as_pct_of_ocf"] is not None
