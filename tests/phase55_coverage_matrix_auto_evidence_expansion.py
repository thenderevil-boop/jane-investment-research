from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import company_profile, uspto_patents
from backend.app.main import app
from backend.app.reports import stock_analysis
from backend.app.schemas.common import DataSourceStatus, ScoreObject

client = TestClient(app)


class _MockResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _tmp_cache() -> Path:
    path = Path("backend/raw_store/cache/test_phase55") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _live_profile(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "company_name": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors",
        "market": "US",
        "exchange": "NMS",
        "currency": "USD",
        "market_cap": 3_000_000_000_000,
        "enterprise_value": 2_990_000_000_000,
        "shares_outstanding": 24_000_000_000,
        "current_price": 125,
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": "2026-05-01",
        "limitations": [],
        "missing_data": [],
    }


def _live_fundamentals(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "period": "ttm",
        "latest_fiscal_year": "2026-01-31",
        "latest_quarter": "2026-04-30",
        "revenue_ttm": 130_000_000_000,
        "revenue_yoy_growth_pct": 80.2,
        "revenue_3y_cagr_pct": 54.4,
        "gross_margin_pct": 71.5,
        "operating_margin_pct": 60.1,
        "net_income_ttm": 55_000_000_000,
        "net_income_margin_pct": 42.3,
        "operating_cash_flow_ttm": 64_000_000_000,
        "capex_ttm": -4_000_000_000,
        "free_cash_flow_ttm": 60_000_000_000,
        "free_cash_flow_margin_pct": 46.15,
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


def _smart_money_with_13f(label: str) -> ScoreObject:
    institutional = ScoreObject(
        name="institutional_support_13f",
        score=60 if label == "institutional_target_match_observed" else 25,
        label=label,
        raw_data={
            "target_matches": [{"ticker": "NVDA", "manager": "Berkshire Hathaway", "value": 1_200_000_000}],
            "source_status": {"source_type": "live", "provider": "sec_edgar_13f", "source_date": "2026-03-31"},
        },
        derived_metrics={"target_match_count": 1, "grouped_holding_count": 1},
        benchmark={},
        trend={},
        source=["SEC EDGAR 13F"],
        source_date="2026-03-31",
        confidence=0.62,
        limitations=["13F is delayed quarterly evidence and does not reflect current positions."],
        missing_data=[],
        source_status=DataSourceStatus(source_type="live", provider="sec_edgar_13f", source_date="2026-03-31"),
    )
    insider = ScoreObject(
        name="insider_form4_signal",
        score=0,
        label="insider_evidence_limited",
        raw_data={},
        derived_metrics={},
        benchmark={},
        trend={},
        source=["SEC EDGAR Form 4"],
        source_date="",
        confidence=0.2,
        limitations=[],
        missing_data=[],
        source_status=DataSourceStatus(source_type="fallback", provider="sec_edgar_form4", fallback_used=True),
    )
    return ScoreObject(
        name="smart_money",
        score=60,
        label="positive_signal",
        raw_data={},
        derived_metrics={
            "components": {
                "institutional_support_13f": institutional,
                "insider_form4_signal": insider,
            }
        },
        benchmark={},
        trend={},
        source=["SEC EDGAR 13F"],
        source_date="2026-03-31",
        confidence=0.55,
        limitations=[],
        missing_data=[],
        source_status=DataSourceStatus(source_type="live", provider="sec_edgar_13f", source_date="2026-03-31"),
    )


def _analyze(monkeypatch, *, theme: str = "AI infrastructure", smart_money_label: str | None = None) -> dict:
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "USE_LIVE_COMPANY_DATA", True)
    monkeypatch.setattr(company_profile, "fetch_company_profile", _live_profile)
    monkeypatch.setattr(company_profile, "fetch_company_fundamentals", _live_fundamentals)
    if smart_money_label:
        monkeypatch.setattr(stock_analysis, "evaluate_smart_money", lambda data: _smart_money_with_13f(smart_money_label))
    response = client.post(
        "/api/analyze-stock",
        json={"ticker": "NVDA", "market": "US", "research_context": {"theme": theme, "user_reason": "Phase 55 coverage expansion"}},
    )
    assert response.status_code == 200
    return response.json()


def _coverage_row(payload: dict, criterion_id: int) -> dict:
    return next(item for item in payload["jane_criteria_coverage"]["criteria"] if item["criterion_id"] == criterion_id)


def test_c18_uspto_patentsview_is_connected_by_default_and_derives_patent_count(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_get(url: str, *, params: dict, timeout: int) -> _MockResponse:
        calls.append({"url": url, "params": params, "timeout": timeout})
        return _MockResponse({"total_hits": 237, "patents": [{"patent_id": "US123", "patent_date": "2026-01-15", "patent_title": "GPU interconnect fabric"}]})

    monkeypatch.setattr(uspto_patents.requests, "get", fake_get)

    payload = _analyze(monkeypatch)

    row = _coverage_row(payload, 18)
    assert payload["patent_ip_evidence"]["source_status"]["source_type"] == "live"
    assert payload["patent_ip_evidence"]["patent_count"] == 237
    assert row["coverage_status"] == "partial"
    assert "patent_count" in row["covered_submetrics"]
    assert row["source_quality"] == "provider_backed"
    assert "Patent count" in " ".join(row["limitations"])
    assert calls and calls[0]["url"] == "https://search.patentsview.org/api/v1/patent/"
    assert "NVIDIA Corporation" in str(calls[0]["params"])


def test_c19_links_existing_13f_target_match_to_coverage_matrix(monkeypatch) -> None:
    payload = _analyze(monkeypatch, smart_money_label="institutional_target_match_observed")

    row = _coverage_row(payload, 19)
    assert row["coverage_status"] == "partial"
    assert row["financial_proxy_source"] == "sec_13f"
    assert "institutional_support" in row["covered_submetrics"]
    assert "fund_support" in row["covered_submetrics"]
    assert row["source_quality"] == "filing_backed"
    assert "13F" in row["summary"]
    assert "delayed quarterly evidence" in " ".join(row["limitations"])
    assert row["requires_human_verification"] is True


def test_c11_keeps_user_theme_as_validation_target_not_auto_coverage(monkeypatch) -> None:
    payload = _analyze(monkeypatch, theme="AI infrastructure")

    row = _coverage_row(payload, 11)
    assert row["coverage_status"] == "insufficient"
    assert row["financial_proxy_source"] is None
    assert "jane_theme_alignment" not in row["covered_submetrics"]
    assert "jane_theme_alignment" in row["requires_user_input_submetrics"]
    assert row["source_quality"] == "insufficient"
    assert "User-supplied theme is a validation target" in row["next_manual_check"]
    assert row["requires_human_verification"] is True


def test_c11_unmapped_theme_remains_insufficient(monkeypatch) -> None:
    payload = _analyze(monkeypatch, theme="miscellaneous watchlist idea")

    row = _coverage_row(payload, 11)
    assert row["coverage_status"] == "insufficient"
    assert "jane_theme_alignment" not in row["covered_submetrics"]
