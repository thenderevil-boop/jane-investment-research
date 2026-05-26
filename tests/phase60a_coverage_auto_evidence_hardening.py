from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import company_profile
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.main import app
from backend.app.reports import stock_analysis
from backend.app.schemas.common import DataSourceStatus, ScoreObject

client = TestClient(app)


def _tmp_cache() -> Path:
    path = Path("backend/raw_store/cache/test_phase60a") / uuid4().hex
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


def _live_fundamentals(ticker: str = "NVDA", *, short_ratio: float | None = None, short_percent_of_float: float | None = None) -> dict:
    payload = {
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
    if short_ratio is not None:
        payload["short_ratio"] = short_ratio
    if short_percent_of_float is not None:
        payload["short_percent_of_float"] = short_percent_of_float
    return payload


def _smart_money_with_13f(label: str = "institutional_target_match_observed") -> ScoreObject:
    institutional = ScoreObject(
        name="institutional_support_13f",
        score=60 if label == "institutional_target_match_observed" else 40,
        label=label,
        raw_data={
            "target_matches": [{"ticker": "NVDA", "manager": "Berkshire Hathaway", "match_confidence": "high", "matched": True}],
            "source_status": {"source_type": "live", "provider": "SEC EDGAR", "source_date": "2026-03-31"},
        },
        derived_metrics={"target_match_count": 1, "grouped_holding_count": 1},
        benchmark={},
        trend={},
        source=["SEC EDGAR 13F"],
        source_date="2026-03-31",
        confidence=0.62,
        limitations=["13F is delayed quarterly evidence and does not reflect current positions."],
        missing_data=[],
        source_status=DataSourceStatus(source_type="live", provider="SEC EDGAR", source_date="2026-03-31"),
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
        source_status=DataSourceStatus(source_type="fallback", provider="SEC EDGAR", fallback_used=True),
    )
    return ScoreObject(
        name="smart_money",
        score=60,
        label="positive_signal",
        raw_data={},
        derived_metrics={"components": {"institutional_support_13f": institutional, "insider_form4_signal": insider}},
        benchmark={},
        trend={},
        source=["SEC EDGAR 13F"],
        source_date="2026-03-31",
        confidence=0.55,
        limitations=[],
        missing_data=[],
        source_status=DataSourceStatus(source_type="live", provider="SEC EDGAR", source_date="2026-03-31"),
    )


def _analyze(monkeypatch, *, short_ratio: float | None = None, short_percent_of_float: float | None = None, qualitative_evidence: list[dict] | None = None, theme: str = "AI infrastructure") -> dict:
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "USE_LIVE_COMPANY_DATA", True)
    monkeypatch.setattr(company_profile, "fetch_company_profile", _live_profile)
    monkeypatch.setattr(company_profile, "fetch_company_fundamentals", lambda ticker: _live_fundamentals(ticker, short_ratio=short_ratio, short_percent_of_float=short_percent_of_float))
    monkeypatch.setattr(stock_analysis, "evaluate_smart_money", lambda data: _smart_money_with_13f())
    response = client.post(
        "/api/analyze-stock",
        json={
            "ticker": "NVDA",
            "market": "US",
            "research_context": {"theme": theme, "user_reason": "Phase 60A coverage hardening"},
            "qualitative_evidence": qualitative_evidence or [],
        },
    )
    assert response.status_code == 200
    return response.json()


def _coverage_row(payload: dict, criterion_id: int) -> dict:
    return next(item for item in payload["jane_criteria_coverage"]["criteria"] if item["criterion_id"] == criterion_id)


def test_c3_yfinance_short_interest_proxy_covers_canonical_skepticism_submetric(monkeypatch) -> None:
    payload = _analyze(monkeypatch, short_ratio=6.2, short_percent_of_float=9.5)

    row = _coverage_row(payload, 3)
    assert row["coverage_status"] == "partial"
    assert "short_interest_proxy" in row["covered_submetrics"]
    assert "short_interest_proxy" not in row["missing_submetrics"]
    assert row["source_quality"] == "derived_live"
    assert "short interest" in row["summary"].lower()
    assert row["requires_human_verification"] is True


def test_c3_missing_yfinance_short_interest_keeps_manual_gap_explainable(monkeypatch) -> None:
    payload = _analyze(monkeypatch)

    row = _coverage_row(payload, 3)
    assert row["coverage_status"] == "insufficient"
    assert "short_interest_proxy" in row["missing_submetrics"]
    assert "short interest" in row["next_manual_check"].lower()
    assert row["requires_human_verification"] is True


def test_c19_warns_when_13f_manager_override_drops_default_core_managers(monkeypatch) -> None:
    monkeypatch.setattr(config, "SEC_13F_TARGET_MANAGERS", "0001067983")
    payload = _analyze(monkeypatch, short_ratio=6.2)

    warning_text = " ".join(payload["institutional_13f"]["limitations"])
    assert "SEC_13F_TARGET_MANAGERS override is missing default managers" in warning_text
    assert "0000102909" in warning_text
    assert "0001364742" in warning_text
    assert "0000093751" in warning_text

    row = _coverage_row(payload, 19)
    assert row["coverage_status"] == "partial"
    assert "institutional_support" in row["covered_submetrics"]
    assert "SEC_13F_TARGET_MANAGERS override is missing default managers" in " ".join(row["limitations"])


def test_c11_user_theme_text_alone_does_not_cover_but_explicit_evidence_can_cover_submetric(monkeypatch) -> None:
    theme_only = _analyze(monkeypatch, theme="AI infrastructure")
    theme_only_row = _coverage_row(theme_only, 11)
    assert theme_only_row["coverage_status"] == "insufficient"
    assert "jane_theme_alignment" not in theme_only_row["covered_submetrics"]

    explicit = _analyze(
        monkeypatch,
        theme="AI infrastructure",
        qualitative_evidence=[
            {
                "criterion": "mega_trend_fit",
                "criterion_id": 11,
                "criterion_name": "Mega Trend Alignment",
                "submetric": "industry_cagr",
                "evidence_type": "filing_reference",
                "summary": "Independent industry research estimates AI infrastructure demand is compounding above 20% annually.",
                "source_label": "User supplied industry report excerpt",
                "source_date": "2026-05-01",
                "confidence": 0.7,
            }
        ],
    )
    explicit_row = _coverage_row(explicit, 11)
    assert explicit_row["coverage_status"] == "partial"
    assert "industry_cagr" in explicit_row["covered_submetrics"]
    assert "jane_theme_alignment" in explicit_row["missing_submetrics"]
    assert explicit_row["source_quality"] == "user_provided"
    assert explicit_row["requires_human_verification"] is True
