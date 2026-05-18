from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import sec_edgar_form4
from backend.app.engines.smart_money_engine import evaluate_form4_insider_signal, evaluate_smart_money
from backend.app.main import app
from backend.app.pipelines import mock_pipeline
from backend.app.pipelines.mock_pipeline import build_daily_report
from backend.app.raw_store import repository
from backend.app.schemas.daily_report import DailyResearchReport
from backend.app.utils.forbidden_language import detect_forbidden_language
from backend.app.utils.freshness import is_daily_market_data_fresh

client = TestClient(app)


def workspace_tmp_dir() -> Path:
    path = Path("backend/raw_store/cache/test_phase105") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeResponse:
    def __init__(self, payload=None, text: str = ""):
        self._payload = payload
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <issuer>
    <issuerCik>1045810</issuerCik>
    <issuerName>NVIDIA CORP</issuerName>
    <issuerTradingSymbol>NVDA</issuerTradingSymbol>
  </issuer>
  <periodOfReport>2026-04-10</periodOfReport>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerName>Example CEO</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>true</isDirector>
      <isOfficer>true</isOfficer>
      <officerTitle>Chief Executive Officer</officerTitle>
      <isTenPercentOwner>false</isTenPercentOwner>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-04-09</value></transactionDate>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>100</value></transactionShares>
        <transactionPricePerShare><value>10.50</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>
    <nonDerivativeHolding>
      <securityTitle><value>Common Stock</value></securityTitle>
    </nonDerivativeHolding>
  </nonDerivativeTable>
  <derivativeTable>
    <derivativeTransaction>
      <transactionDate><value>2026-04-10</value></transactionDate>
      <securityTitle><value>Stock Option</value></securityTitle>
      <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>50</value></transactionShares>
        <transactionPricePerShare><value>0</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>I</value></directOrIndirectOwnership></ownershipNature>
    </derivativeTransaction>
  </derivativeTable>
</ownershipDocument>
"""


def live_form4_payload(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "cik": "0001045810",
        "lookback_days": 180,
        "transactions": [
            {
                "ticker": ticker,
                "cik": "0001045810",
                "accession_number": "0001045810-26-000001",
                "filing_date": "2026-04-11",
                "transaction_date": "2026-04-10",
                "insider_name": "Example CEO",
                "role": "Chief Executive Officer",
                "is_director": True,
                "is_officer": True,
                "officer_title": "Chief Executive Officer",
                "transaction_code": "P",
                "transaction_category": "accumulation",
                "transaction_type": "accumulation",
                "security_title": "Common Stock",
                "shares": 100,
                "price": 10,
                "value": 1000,
                "ownership_type": "direct",
                "acquired_disposed_code": "A",
                "source": ["SEC EDGAR"],
                "source_date": "2026-04-11",
            }
        ],
        "source_type": "live",
        "provider": "SEC EDGAR",
        "source": ["SEC EDGAR"],
        "source_date": "2026-04-11",
        "fetched_at": "2026-04-11T00:00:00+00:00",
        "limitations": ["Form 4 transaction code interpretation is context-limited."],
        "missing_data": [],
    }


def test_get_cik_for_ticker_maps_nvda_and_aapl_from_mocked_company_tickers(monkeypatch):
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_EDGAR_REQUEST_DELAY_SECONDS", 0)
    monkeypatch.setattr(sec_edgar_form4, "_TICKER_CIK_CACHE", None)

    def fake_get(url, headers, timeout):
        assert "company_tickers.json" in url
        assert "User-Agent" in headers
        return FakeResponse({0: {"ticker": "NVDA", "cik_str": 1045810}, 1: {"ticker": "AAPL", "cik_str": 320193}})

    monkeypatch.setattr(sec_edgar_form4.httpx, "get", fake_get)

    assert sec_edgar_form4.get_cik_for_ticker("nvda") == "0001045810"
    assert sec_edgar_form4.get_cik_for_ticker("AAPL") == "0000320193"


def test_fetch_company_submissions_parses_mocked_json(monkeypatch):
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_EDGAR_REQUEST_DELAY_SECONDS", 0)

    def fake_get(url, headers, timeout):
        assert "CIK0001045810.json" in url
        return FakeResponse({"filings": {"recent": {"form": ["4"]}}})

    monkeypatch.setattr(sec_edgar_form4.httpx, "get", fake_get)

    assert sec_edgar_form4.fetch_company_submissions("1045810")["filings"]["recent"]["form"] == ["4"]


def test_find_recent_form4_filings_extracts_fields(monkeypatch):
    monkeypatch.setattr(sec_edgar_form4, "date", type("FakeDate", (), {"today": staticmethod(lambda: datetime(2026, 4, 28).date()), "fromisoformat": staticmethod(lambda value: datetime.fromisoformat(value).date())}))
    submissions = {
        "filings": {
            "recent": {
                "form": ["4", "8-K", "4"],
                "accessionNumber": ["0001", "0002", "0003"],
                "filingDate": ["2026-04-20", "2026-04-20", "2025-01-01"],
                "reportDate": ["2026-04-19", "2026-04-19", "2024-12-31"],
                "primaryDocument": ["doc.xml", "doc.htm", "old.xml"],
            }
        }
    }

    filings = sec_edgar_form4.find_recent_form4_filings(submissions, lookback_days=180)

    assert filings == [
        {
            "accession_number": "0001",
            "accessionNumber": "0001",
            "filing_date": "2026-04-20",
            "filingDate": "2026-04-20",
            "report_date": "2026-04-19",
            "reportDate": "2026-04-19",
            "primary_document": "doc.xml",
            "primaryDocument": "doc.xml",
        }
    ]


def test_build_edgar_archive_url_removes_dashes_and_cik_zeros():
    url = sec_edgar_form4.build_edgar_archive_url("0001045810", "0001045810-26-000001", "xslF345X05/doc.xml")

    assert url == "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000001/xslF345X05/doc.xml"


def test_parse_form4_xml_extracts_code_p_shares_price_and_value():
    rows = sec_edgar_form4.parse_form4_xml(FORM4_XML, "NVDA", "0001045810", "0001045810-26-000001", "2026-04-11")

    purchase = rows[0]
    assert purchase["insider_name"] == "Example CEO"
    assert purchase["transaction_code"] == "P"
    assert purchase["transaction_category"] == "accumulation"
    assert purchase["shares"] == 100
    assert purchase["price"] == 10.5
    assert purchase["value"] == 1050
    assert purchase["acquired_disposed_code"] == "A"
    assert purchase["source"] == ["SEC EDGAR"]


def test_parse_form4_xml_extracts_code_s():
    xml = FORM4_XML.replace("<transactionCode>P</transactionCode>", "<transactionCode>S</transactionCode>", 1)
    rows = sec_edgar_form4.parse_form4_xml(xml, "NVDA", "0001045810", "0001045810-26-000001", "2026-04-11")

    assert rows[0]["transaction_code"] == "S"
    assert rows[0]["transaction_category"] == "disposition"


def test_parse_form4_xml_handles_m_a_f_without_accumulation():
    for code in ["M", "A", "F"]:
        category, _limitations = sec_edgar_form4.classify_transaction_code(code)
        assert category != "accumulation"


def test_parse_form4_xml_ignores_holdings_only_rows():
    rows = sec_edgar_form4.parse_form4_xml(FORM4_XML, "NVDA", "0001045810", "0001045810-26-000001", "2026-04-11")

    assert len(rows) == 2
    assert all(row["security_title"] != "" for row in rows)


def test_deduplication_removes_duplicate_transactions():
    row = sec_edgar_form4.parse_form4_xml(FORM4_XML, "NVDA", "0001045810", "0001045810-26-000001", "2026-04-11")[0]

    assert len(sec_edgar_form4.dedupe_transactions([row, dict(row)])) == 1


def test_missing_sec_edgar_user_agent_returns_fallback_not_crash(monkeypatch):
    monkeypatch.setattr(config, "USE_LIVE_SEC_FORM4", True)
    monkeypatch.setattr(config, "SEC_FORM4_PROVIDER", "sec_edgar")
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "")
    monkeypatch.setattr(config, "SEC_FORM4_CACHE_DIR", workspace_tmp_dir())

    payload = repository.get_sec_form4_transactions("NVDA")

    assert payload["source_type"] == "fallback"
    assert payload["source_status"]["fallback_reason"] == "SEC_EDGAR_USER_AGENT missing"


def test_edgar_fetch_failure_uses_cached_live_if_available(monkeypatch):
    cache_dir = workspace_tmp_dir()
    monkeypatch.setattr(config, "USE_LIVE_SEC_FORM4", True)
    monkeypatch.setattr(config, "SEC_FORM4_PROVIDER", "sec_edgar")
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_FORM4_CACHE_DIR", cache_dir)
    repository.write_sec_form4_data("NVDA", live_form4_payload("NVDA"))

    def fail_fetch(_ticker, lookback_days=180):
        raise RuntimeError("sec unavailable")

    monkeypatch.setattr(sec_edgar_form4, "fetch_insider_transactions", fail_fetch)
    payload = repository.get_sec_form4_transactions("NVDA")

    assert payload["source_type"] == "cached_live"
    assert payload["provider"] == "SEC EDGAR"


def test_edgar_fetch_failure_with_no_cache_returns_fallback_mock(monkeypatch):
    monkeypatch.setattr(config, "USE_LIVE_SEC_FORM4", True)
    monkeypatch.setattr(config, "SEC_FORM4_PROVIDER", "sec_edgar")
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_FORM4_CACHE_DIR", workspace_tmp_dir())

    def fail_fetch(_ticker, lookback_days=180):
        raise RuntimeError("sec unavailable")

    monkeypatch.setattr(sec_edgar_form4, "fetch_insider_transactions", fail_fetch)
    payload = repository.get_sec_form4_transactions("NVDA")

    assert payload["source_type"] == "fallback"
    assert payload["provider"] == "mock"
    assert "sec unavailable" in payload["source_status"]["fallback_reason"]


def test_fallback_mock_form4_does_not_boost_smart_money_score():
    fallback = repository._mock_form4_snapshot("NVDA", "SEC unavailable")
    result = evaluate_form4_insider_signal(
        {
            "form4_transactions": fallback["transactions"],
            "form4_source_status": fallback["source_status"],
        }
    )

    assert result.score == 40
    assert result.label == "insider_activity_neutral"
    assert "Live SEC Form 4 fetch failed; fallback data used. Disposition count from fallback data is not scored." in result.limitations
    assert "Mock fallback Form 4 data is not used to boost smart-money score." in result.limitations


def test_candidate_source_status_is_not_live_mock_inconsistent(monkeypatch):
    monkeypatch.setattr(
        mock_pipeline,
        "read_sec_filings",
        lambda ticker: {
            "institutional_13f": {},
            "form4_transactions": live_form4_payload(ticker)["transactions"],
            "form4_source_status": {**live_form4_payload(ticker), "source_status": None}.get("source_status") or {
                "source_type": "live",
                "provider": "SEC EDGAR",
                "source": ["SEC EDGAR"],
                "source_date": "2026-04-11",
                "is_fresh": True,
                "freshness_window": "form4_recent_180_days",
                "fallback_used": False,
                "fallback_reason": None,
                "limitations": [],
                "missing_data": [],
            },
            "form4_snapshot": live_form4_payload(ticker),
        },
    )

    report = build_daily_report()
    status = report.stock_candidates[0].source_status

    assert status is not None
    assert status.source_type == "derived"
    assert status.provider == "mixed_sources"


def test_previous_us_trading_day_yfinance_data_is_fresh_before_next_close():
    assert is_daily_market_data_fresh("2026-04-27", as_of=datetime(2026, 4, 28, 1, 34, 32, tzinfo=timezone.utc)) is True


def test_data_health_endpoint_does_not_expose_sec_user_agent(monkeypatch):
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Secret Name secret@example.com")
    payload = client.get("/api/data-health").json()

    assert payload["providers"]["SEC EDGAR"]["user_agent_configured"] is True
    assert "Secret Name" not in str(payload)


def test_smart_money_score_not_boosted_when_all_form4_codes_missing():
    result = evaluate_smart_money(
        {
            "institutional_13f": {},
            "form4_transactions": [{"transaction_code": "", "transaction_category": "other", "value": 1000, "filing_date": "2026-04-11"}],
            "form4_source_status": {"source_type": "live", "provider": "SEC EDGAR", "source_date": "2026-04-11"},
            "options_activity": {},
        }
    )

    insider = result.derived_metrics["components"]["insider_form4_signal"]
    assert insider["score"] == 50
    assert insider["label"] == "insider_activity_neutral"
    assert "transaction_code" in result.missing_data


def test_phase105_forbidden_language_guard_still_passes():
    payload = client.get("/api/daily-report/latest").json()
    assert detect_forbidden_language(payload) == []


def test_phase105_api_schema_remains_stable():
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    report = DailyResearchReport.model_validate(response.json())
    assert set(report.model_dump()) == set(build_daily_report().model_dump())
