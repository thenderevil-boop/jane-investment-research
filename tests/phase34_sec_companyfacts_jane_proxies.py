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

client = TestClient(app)


def _tmp_cache() -> Path:
    path = Path("backend/raw_store/cache/test_phase34") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _companyfacts_payload_with_rd(*, misaligned_rd: bool = False) -> dict:
    concepts: dict = {}

    def add(concept: str, values: list[tuple[int, float]], unit: str = "USD"):
        concepts[concept] = {
            "units": {
                unit: [
                    {
                        "fy": fy,
                        "fp": "FY",
                        "form": "10-K",
                        "filed": f"{fy}-03-15",
                        "start": f"{fy - 1}-02-01",
                        "end": f"{fy}-01-31",
                        "val": value,
                    }
                    for fy, value in values
                ]
            }
        }

    add("RevenueFromContractWithCustomerExcludingAssessedTax", [(2026, 130_000_000_000), (2025, 100_000_000_000), (2024, 80_000_000_000), (2023, 60_000_000_000)])
    add("GrossProfit", [(2026, 91_000_000_000), (2025, 62_000_000_000), (2024, 44_000_000_000), (2023, 30_000_000_000)])
    add("OperatingIncomeLoss", [(2026, 78_000_000_000), (2025, 50_000_000_000), (2024, 32_000_000_000), (2023, 18_000_000_000)])
    add("NetIncomeLoss", [(2026, 55_000_000_000), (2025, 40_000_000_000), (2024, 25_000_000_000), (2023, 12_000_000_000)])
    add("NetCashProvidedByUsedInOperatingActivities", [(2026, 64_000_000_000), (2025, 48_000_000_000), (2024, 34_000_000_000), (2023, 22_000_000_000)])
    add("PaymentsToAcquirePropertyPlantAndEquipment", [(2026, 4_000_000_000), (2025, 3_500_000_000), (2024, 3_000_000_000), (2023, 2_000_000_000)])
    rd_rows = [(2026, 12_000_000_000), (2025, 9_000_000_000), (2024, 6_000_000_000), (2023, 3_000_000_000)]
    if misaligned_rd:
        concepts["ResearchAndDevelopmentExpense"] = {
            "units": {
                "USD": [
                    {"fy": 2025, "fp": "FY", "form": "10-K", "filed": "2025-03-15", "start": "2024-02-01", "end": "2025-01-31", "val": 9_000_000_000}
                ]
            }
        }
    else:
        add("ResearchAndDevelopmentExpense", rd_rows)
    add("CashAndCashEquivalentsAtCarryingValue", [(2026, 45_000_000_000)])
    add("LongTermDebt", [(2026, 11_000_000_000)])
    add("StockholdersEquity", [(2026, 44_000_000_000)])
    add("AccountsReceivableNetCurrent", [(2026, 15_000_000_000)])
    add("InventoryNet", [(2026, 8_000_000_000)])
    add("EntityCommonStockSharesOutstanding", [(2026, 24_000_000_000), (2025, 24_100_000_000), (2024, 24_200_000_000), (2023, 24_300_000_000)], unit="shares")
    return {"cik": "1045810", "facts": {"us-gaap": concepts}}


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


def _fundamentals(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "period": "ttm",
        "revenue_ttm": 130_000_000_000,
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
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": "2026-05-01",
        "limitations": [],
        "missing_data": [],
    }


def _analyze(monkeypatch, *, sec_snapshot: dict | None = None) -> dict:
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "USE_LIVE_COMPANY_DATA", True)
    monkeypatch.setattr(config, "USE_LIVE_SEC_COMPANYFACTS", True)
    monkeypatch.setattr(company_profile, "fetch_company_profile", _profile)
    monkeypatch.setattr(company_profile, "fetch_company_fundamentals", _fundamentals)
    monkeypatch.setattr(company_cache, "get_sec_companyfacts", lambda ticker: sec_snapshot or sec_companyfacts.parse_companyfacts(ticker, "1045810", _companyfacts_payload_with_rd(), source_type="live"))
    monkeypatch.setattr(stock_analysis, "get_sec_companyfacts", lambda ticker: sec_snapshot or sec_companyfacts.parse_companyfacts(ticker, "1045810", _companyfacts_payload_with_rd(), source_type="live"))
    response = client.post(
        "/api/analyze-stock",
        json={"ticker": "NVDA", "market": "US", "research_context": {"theme": "AI infrastructure", "user_reason": "Phase 34 regression test"}},
    )
    assert response.status_code == 200
    return response.json()


def test_phase34_parser_extracts_rd_and_multiyear_financial_proxy_metrics():
    parsed = sec_companyfacts.parse_companyfacts("NVDA", "1045810", _companyfacts_payload_with_rd(), source_type="live")

    assert parsed["facts"]["research_and_development_expense"]["value"] == 12_000_000_000
    assert parsed["facts"]["research_and_development_expense"]["concept"] == "us-gaap:ResearchAndDevelopmentExpense"
    assert parsed["derived_metrics"]["rd_to_revenue_pct"] == 9.2308
    assert parsed["derived_metrics"]["rd_to_revenue_trend_pct"] == 4.2308
    assert parsed["derived_metrics"]["gross_margin_trend_pct"] == 20.0
    assert parsed["derived_metrics"]["operating_margin_trend_pct"] == 30.0
    assert parsed["derived_metrics"]["fcf_margin_trend_pct"] == 12.8205
    assert parsed["invalid_derived_metrics"].get("rd_to_revenue_pct") is None


def test_phase34_parser_invalidates_rd_proxy_when_periods_do_not_align():
    parsed = sec_companyfacts.parse_companyfacts("NVDA", "1045810", _companyfacts_payload_with_rd(misaligned_rd=True), source_type="live")

    assert parsed["facts"]["research_and_development_expense"] is None
    assert parsed["derived_metrics"]["rd_to_revenue_pct"] is None
    assert parsed["invalid_derived_metrics"]["rd_to_revenue_pct"] == "invalid_period_alignment"
    assert "research_and_development_expense for latest aligned fiscal year" in parsed["missing_data"]


def test_phase34_sec_rd_and_margin_proxies_flow_into_jane_quality_and_coverage(monkeypatch):
    payload = _analyze(monkeypatch)
    criteria = {item["name"]: item for item in payload["jane_company_quality"]["criteria"]}
    coverage = {item["criterion_id"]: item for item in payload["jane_criteria_coverage"]["criteria"]}
    financials = payload["financial_quality"]["raw_data"]

    assert financials["rd_expense_ttm"] == 12_000_000_000
    assert financials["rd_to_revenue_pct"] == 9.2308
    assert "rd_expense_ttm" in financials["filing_backed_fields"]
    assert "rd_to_revenue_pct" in financials["filing_backed_fields"]
    assert criteria["continuous_r_and_d"]["status"] == "supportive"
    assert criteria["continuous_r_and_d"]["source_quality"] == "derived_from_mixed_sources"

    assert coverage[5]["coverage_status"] == "partial"
    assert coverage[5]["source_quality"] == "filing_backed"
    assert "rd_percent_of_revenue" in coverage[5]["covered_submetrics"]
    assert coverage[6]["source_quality"] == "filing_backed"
    assert {"gross_margin_expansion", "operating_leverage"}.issubset(set(coverage[6]["covered_submetrics"]))
    assert coverage[10]["coverage_status"] == "covered"
    assert set(coverage[10]["covered_submetrics"]) == {"positive_fcf", "fcf_margin", "fcf_growth_trend", "cash_conversion_quality"}
    assert "SEC Companyfacts" in json.dumps(coverage[5])


def test_phase34_misaligned_sec_rd_does_not_create_rd_coverage(monkeypatch):
    sec_snapshot = sec_companyfacts.parse_companyfacts("NVDA", "1045810", _companyfacts_payload_with_rd(misaligned_rd=True), source_type="live")
    payload = _analyze(monkeypatch, sec_snapshot=sec_snapshot)
    criteria = {item["name"]: item for item in payload["jane_company_quality"]["criteria"]}
    coverage = {item["criterion_id"]: item for item in payload["jane_criteria_coverage"]["criteria"]}

    assert criteria["continuous_r_and_d"]["status"] == "insufficient"
    assert "rd_percent_of_revenue" not in coverage[5]["covered_submetrics"]
    assert coverage[5]["coverage_status"] == "insufficient"
    assert coverage[5]["source_quality"] == "insufficient"
