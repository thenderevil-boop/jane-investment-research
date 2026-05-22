from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import company_profile
from backend.app.main import app

client = TestClient(app)


class _MockResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _tmp_cache() -> Path:
    path = Path("backend/raw_store/cache/test_phase47") / uuid4().hex
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


def _coverage_row(payload: dict, criterion_id: int) -> dict:
    return next(item for item in payload["jane_criteria_coverage"]["criteria"] if item["criterion_id"] == criterion_id)


def test_c18_patents_api_returns_count_and_criteria_evidence(monkeypatch) -> None:
    from backend.app.data_sources.uspto_patents import fetch_patent_ip_evidence

    calls: list[dict] = []

    def fake_get(url: str, *, params: dict, timeout: int) -> _MockResponse:
        calls.append({"url": url, "params": params, "timeout": timeout})
        return _MockResponse({"total_hits": 64, "patents": [{"patent_id": "US123", "patent_date": "2025-02-03", "patent_title": "GPU fabric"}]})

    monkeypatch.setattr(config, "USE_LIVE_USPTO_PATENTS_DATA", True)
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())

    evidence = fetch_patent_ip_evidence("NVDA", "NVIDIA Corporation", http_get=fake_get)

    assert evidence.provider == "uspto_patentsview"
    assert evidence.patent_count == 64
    assert evidence.ip_signal == "supportive"
    assert evidence.source_status.source_type == "live"
    assert evidence.criteria_count == 1
    criterion = evidence.criteria[0]
    assert criterion.criterion_id == 18
    assert criterion.criterion_name == "Patents and IP"
    assert criterion.source == "uspto_patentsview"
    assert criterion.source_quality == "provider_backed"
    assert criterion.support_level == "supportive"
    assert "patent_count" in criterion.covered_submetrics
    assert criterion.manual_checks
    assert evidence.affects_score is False
    assert evidence.not_investment_advice is True
    assert calls[0]["url"] == "https://search.patentsview.org/api/v1/patent/"
    assert "NVIDIA Corporation" in str(calls[0]["params"])
    assert "patent_date" in str(calls[0]["params"])


def test_c18_patents_cached_30_days(monkeypatch) -> None:
    from backend.app.data_sources.uspto_patents import fetch_patent_ip_evidence

    cache_dir = _tmp_cache()
    monkeypatch.setattr(config, "USE_LIVE_USPTO_PATENTS_DATA", True)
    monkeypatch.setattr(config, "USPTO_PATENTS_CACHE_TTL_DAYS", 30)
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", cache_dir)

    live = fetch_patent_ip_evidence(
        "NVDA",
        "NVIDIA Corporation",
        http_get=lambda *args, **kwargs: _MockResponse({"total_hits": 17, "patents": []}),
    )
    assert live.source_status.source_type == "live"

    def failing_get(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("network unavailable")

    cached = fetch_patent_ip_evidence("NVDA", "NVIDIA Corporation", http_get=failing_get)

    assert cached.patent_count == 17
    assert cached.source_status.source_type == "cached_live"
    assert cached.source_status.fallback_used is True
    assert any("cache hit" in limitation.lower() for limitation in cached.source_status.limitations)


def test_c18_patents_cache_expires_after_30_days(monkeypatch) -> None:
    from backend.app.raw_store.uspto_patents_cache import load_cached_uspto_patents, save_uspto_patents_snapshot

    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())
    save_uspto_patents_snapshot(
        "NVDA",
        {"company_name": "NVIDIA Corporation", "patent_count": 3},
        fetched_at=datetime.now(timezone.utc) - timedelta(days=31),
    )

    assert load_cached_uspto_patents("NVDA", ttl_days=30) is None


def test_analyze_stock_adds_c18_patent_proxy_to_coverage_matrix(monkeypatch) -> None:
    from backend.app.reports import stock_analysis
    from backend.app.schemas.common import DataSourceStatus
    from backend.app.schemas.jane_external_evidence import JaneCriteriaExternalEvidenceItem
    from backend.app.schemas.patent_ip import PatentIPEvidence

    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", _tmp_cache())
    monkeypatch.setattr(config, "USE_LIVE_COMPANY_DATA", True)
    monkeypatch.setattr(company_profile, "fetch_company_profile", _live_profile)
    monkeypatch.setattr(company_profile, "fetch_company_fundamentals", _live_fundamentals)
    monkeypatch.setattr(
        stock_analysis,
        "get_patent_ip_evidence",
        lambda ticker, company_name="": PatentIPEvidence(
            ticker=ticker,
            query_name=company_name,
            patent_count=64,
            source_status=DataSourceStatus(provider="uspto_patentsview", source_type="live", source_date="2026-05-01"),
            criteria=[
                JaneCriteriaExternalEvidenceItem(
                    criterion_id=18,
                    criterion_name="Patents and IP",
                    source="uspto_patentsview",
                    source_quality="provider_backed",
                    support_level="supportive",
                    confidence=0.74,
                    covered_submetrics=["patent_count"],
                    evidence_snippets=["PatentsView found 64 patents in the last 3 years."],
                    manual_checks=["Confirm assignee/entity matching before relying on C18 IP evidence."],
                    limitations=["Patent count is an auto-derived proxy and does not prove defensibility."],
                )
            ],
            criteria_count=1,
            ip_signal="supportive",
            manual_checks=["Confirm assignee/entity matching before relying on C18 IP evidence."],
            limitations=["Patent count is an auto-derived proxy and does not prove defensibility."],
        ),
    )

    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["patent_ip_evidence"]["patent_count"] == 64
    assert payload["patent_ip_evidence"]["affects_score"] is False
    row = _coverage_row(payload, 18)
    assert row["criterion_name"] == "Patents and IP"
    assert row["coverage_status"] == "partial"
    assert row["source_quality"] == "provider_backed"
    assert "patent_count" in row["covered_submetrics"]
    assert row["accepted_evidence_item_count"] >= 1
    assert "patent count" in " ".join(row["limitations"]).lower()
