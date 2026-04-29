from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app import config
from backend.app.data import security_map
from backend.app.data import price_reference
from backend.app.data.price_reference import PriceReference
from backend.app.data_sources import sec_edgar_13f, sec_edgar_form4
from backend.app.engines.sec_13f_aggregation import aggregate_13f_holdings, compare_13f_quarter_over_quarter, summarize_13f_portfolio
from backend.app.engines.sec_13f_target_matching import match_13f_targets, normalize_target_security_map
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.pipelines import mock_pipeline
from backend.app.raw_store import repository
from backend.app.schemas.common import DataSourceStatus
from backend.app.utils.forbidden_language import detect_forbidden_language


def workspace_tmp_dir() -> Path:
    path = Path("backend/raw_store/cache/test_phase11") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeResponse:
    def __init__(self, payload=None, text: str = "", status_code: int = 200):
        self._payload = payload
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"{self.status_code} error")
        return None

    def json(self):
        return self._payload


SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["13F-HR", "8-K", "13F-HR", "13F-HR/A"],
            "accessionNumber": ["0001067983-26-000010", "x", "0001067983-26-000005", "0001067983-26-000011"],
            "filingDate": ["2026-05-15", "2026-05-10", "2026-02-14", "2026-05-20"],
            "reportDate": ["2026-03-31", "2026-03-31", "2025-12-31", "2026-03-31"],
            "primaryDocument": ["primary.htm", "x.htm", "old.htm", "amend.htm"],
        }
    }
}

INFO_XML = """<?xml version="1.0"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>NVIDIA CORP</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>67066G104</cusip>
    <value>12345</value>
    <shrsOrPrnAmt>
      <sshPrnamt>1000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
    <votingAuthority>
      <Sole>900</Sole>
      <Shared>50</Shared>
      <None>50</None>
    </votingAuthority>
  </infoTable>
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>037833100</cusip>
    <value>20000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>2000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <putCall>CALL</putCall>
    <investmentDiscretion>DFND</investmentDiscretion>
    <otherManager>1</otherManager>
    <votingAuthority>
      <Sole>1800</Sole>
      <Shared>100</Shared>
      <None>100</None>
    </votingAuthority>
  </infoTable>
</informationTable>
"""

PRIOR_XML = INFO_XML.replace("<value>12345</value>", "<value>10000</value>").replace("<sshPrnamt>1000</sshPrnamt>", "<sshPrnamt>800</sshPrnamt>", 1)


def holding_row(
    issuer_name: str,
    cusip: str,
    value_usd: float,
    shares: float,
    *,
    report_date: str = "2026-03-31",
    filing_date: str = "2026-05-15",
    manager_cik: str = "0001067983",
    title_of_class: str = "COM",
    confidence: str = "high",
    other_manager: str = "",
) -> dict:
    return {
        "manager_cik": manager_cik,
        "accession_number": f"{manager_cik}-{report_date}",
        "filing_date": filing_date,
        "report_date": report_date,
        "issuer_name": issuer_name,
        "title_of_class": title_of_class,
        "cusip": cusip,
        "reported_value_raw": value_usd,
        "reported_value_unit": "as_reported",
        "value_usd": value_usd,
        "value_unit_confidence": confidence,
        "value_normalization_note": "fixture value",
        "shares_or_principal_amount": shares,
        "share_type": "SH",
        "put_call": "",
        "investment_discretion": "SOLE",
        "other_manager": other_manager,
        "voting_authority_sole": 10,
        "voting_authority_shared": 2,
        "voting_authority_none": 1,
        "source": ["SEC EDGAR"],
        "source_status": {
            "source_type": "live",
            "provider": "SEC EDGAR",
            "source_date": report_date,
            "fetched_at": f"{filing_date}T00:00:00+00:00",
            "is_fresh": True,
            "freshness_window": "quarterly_filing_delay",
            "fallback_used": False,
            "limitations": [],
            "missing_data": [],
        },
    }


def live_13f_payload() -> dict:
    holdings = sec_edgar_13f.parse_13f_information_table_xml(INFO_XML, "0001067983", "0001067983-26-000011", "2026-05-20", "2026-03-31")
    return {
        "manager": "0001067983",
        "manager_cik": "0001067983",
        "lookback_quarters": 4,
        "filings": [{"accession_number": "0001067983-26-000011", "filing_date": "2026-05-20", "report_date": "2026-03-31", "form": "13F-HR/A"}],
        "holdings": holdings,
        "source_type": "live",
        "provider": "SEC EDGAR",
        "source": ["SEC EDGAR"],
        "source_date": "2026-03-31",
        "fetched_at": "2026-05-20T00:00:00+00:00",
        "limitations": [],
        "missing_data": [],
    }


def test_security_map_normalizes_ticker_and_cusip():
    assert security_map.normalize_ticker(" nvda ") == "NVDA"
    assert security_map.normalize_cusip(" 037833100 ") == "037833100"


def test_security_map_resolves_ticker_cusip_and_issuer_alias():
    assert security_map.get_security_by_ticker("NVDA")["cusip"] == "67066G104"
    assert security_map.get_security_by_cusip("037833100")["ticker"] == "AAPL"
    assert security_map.find_security_by_issuer_name("NVIDIA CORPORATION")["ticker"] == "NVDA"


def test_security_map_unknown_and_ambiguous_issuer_do_not_resolve():
    assert security_map.find_security_by_issuer_name("NVIDIA INTERNATIONAL") is None
    assert security_map.find_security_by_issuer_name("ALPHABET INC") is None


def test_cik_normalization_for_manager_cik():
    assert sec_edgar_13f.get_cik_for_manager("1067983") == "0001067983"


def test_build_submissions_url_zero_pads_cik_to_10_digits():
    assert sec_edgar_13f.build_submissions_url("1067983") == "https://data.sec.gov/submissions/CIK0001067983.json"


def test_build_archives_directory_url_strips_cik_zeros_and_accession_dashes():
    assert sec_edgar_13f.build_archives_directory_url("0001067983", "0001067983-26-000011") == "https://www.sec.gov/Archives/edgar/data/1067983/000106798326000011/"


def test_build_archives_index_json_url_uses_directory_url():
    assert sec_edgar_13f.build_archives_index_json_url("0001067983", "0001067983-26-000011") == "https://www.sec.gov/Archives/edgar/data/1067983/000106798326000011/index.json"


def test_build_archives_index_html_url_keeps_dashes_in_filename():
    assert sec_edgar_13f.build_archives_index_html_url("0001067983", "0001067983-26-000011") == "https://www.sec.gov/Archives/edgar/data/1067983/000106798326000011/0001067983-26-000011-index.html"


def test_mocked_submissions_parsing_finds_13f_hr():
    filings = sec_edgar_13f.find_recent_13f_filings({"filings": {"recent": {**SUBMISSIONS["filings"]["recent"], "form": ["13F-HR"]}}})
    assert filings[0]["form"] == "13F-HR"


def test_mocked_submissions_parsing_handles_amendment_preference():
    filings = sec_edgar_13f.find_recent_13f_filings(SUBMISSIONS)
    assert filings[0]["form"] == "13F-HR/A"
    assert filings[0]["accession_number"] == "0001067983-26-000011"


def test_archive_url_builder_removes_dashes_and_cik_zeros():
    url = sec_edgar_13f.build_edgar_archive_url("0001067983", "0001067983-26-000011", "form13fInfoTable.xml")
    assert url == "https://www.sec.gov/Archives/edgar/data/1067983/000106798326000011/form13fInfoTable.xml"


def test_information_table_discovery_finds_xml_document(monkeypatch):
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_EDGAR_REQUEST_DELAY_SECONDS", 0)

    def fake_get(url, headers, timeout):
        assert url.endswith("index.json")
        return FakeResponse(
            {
                "directory": {
                    "item": [
                        {"name": "primary_doc.xml", "type": "XML"},
                        {"name": "infotable.xml", "type": "INFORMATION TABLE"},
                    ]
                }
            }
        )

    monkeypatch.setattr(sec_edgar_13f.httpx, "get", fake_get)
    docs = sec_edgar_13f.discover_13f_information_table_documents("0001067983", "0001067983-26-000011")
    assert docs[0].endswith("/infotable.xml")


def test_index_json_discovery_ranks_information_table_above_cover_xml(monkeypatch):
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_EDGAR_REQUEST_DELAY_SECONDS", 0)

    def fake_get(url, headers, timeout):
        return FakeResponse(
            {
                "directory": {
                    "item": [
                        {"name": "primary_doc.xml", "type": "XML"},
                        {"name": "form13f.xml", "type": "XML"},
                        {"name": "random.xml", "type": "XML"},
                        {"name": "abc-informationtable.xml", "type": "XML"},
                    ]
                }
            }
        )

    monkeypatch.setattr(sec_edgar_13f.httpx, "get", fake_get)
    docs = sec_edgar_13f.discover_13f_information_table_documents("0001067983", "0001067983-26-000011")
    assert docs[0].endswith("/abc-informationtable.xml")
    assert not any(doc.endswith("/primary_doc.xml") or doc.endswith("/form13f.xml") for doc in docs)


def test_index_json_discovery_excludes_xsl_and_html_files(monkeypatch):
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_EDGAR_REQUEST_DELAY_SECONDS", 0)

    def fake_get(url, headers, timeout):
        return FakeResponse({"directory": {"item": [{"name": "xslForm13F.xsl"}, {"name": "doc-index.html"}, {"name": "real13f.xml"}]}})

    monkeypatch.setattr(sec_edgar_13f.httpx, "get", fake_get)
    docs = sec_edgar_13f.discover_13f_information_table_documents("0001067983", "0001067983-26-000011")
    assert docs == ["https://www.sec.gov/Archives/edgar/data/1067983/000106798326000011/real13f.xml"]


def test_candidate_fetch_continues_after_first_candidate_404(monkeypatch):
    candidates = [
        "https://www.sec.gov/Archives/edgar/data/1067983/000106798326000011/missing-info.xml",
        "https://www.sec.gov/Archives/edgar/data/1067983/000106798326000011/actual-info.xml",
    ]
    monkeypatch.setattr(sec_edgar_13f, "discover_13f_information_table_documents", lambda cik, accession: candidates)

    def fake_fetch(url):
        if "missing" in url:
            raise RuntimeError("404 error")
        return INFO_XML

    monkeypatch.setattr(sec_edgar_13f, "fetch_13f_information_table_xml", fake_fetch)
    xml, url = sec_edgar_13f.fetch_first_valid_13f_information_table_xml("0001067983", "0001067983-26-000011")
    assert xml == INFO_XML
    assert url.endswith("actual-info.xml")


def test_index_html_fallback_discovers_information_table_when_json_unavailable(monkeypatch):
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_EDGAR_REQUEST_DELAY_SECONDS", 0)

    def fake_get(url, headers, timeout):
        if url.endswith("index.json"):
            return FakeResponse(status_code=404)
        return FakeResponse(
            text="""
            <table>
              <tr><td><a href="/Archives/edgar/data/1067983/000106798326000011/info_q1.xml">info_q1.xml</a></td><td>INFORMATION TABLE</td></tr>
            </table>
            """
        )

    monkeypatch.setattr(sec_edgar_13f.httpx, "get", fake_get)
    docs = sec_edgar_13f.discover_13f_information_table_documents("0001067983", "0001067983-26-000011")
    assert docs[0].endswith("/info_q1.xml")


def test_cover_page_xml_is_rejected_if_no_holdings_rows():
    cover_xml = "<edgarSubmission><formData><coverPage><reportCalendarOrQuarter>03-31-2026</reportCalendarOrQuarter></coverPage></formData></edgarSubmission>"
    assert sec_edgar_13f.contains_13f_holdings_rows(cover_xml) is False


def test_valid_information_table_xml_is_accepted():
    assert sec_edgar_13f.contains_13f_holdings_rows(INFO_XML) is True


def test_xml_parser_extracts_holdings_and_value_math():
    rows = sec_edgar_13f.parse_13f_information_table_xml(INFO_XML, "0001067983", "0001067983-26-000011", "2026-05-20", "2026-03-31")
    first = rows[0]
    assert first["issuer_name"] == "NVIDIA CORP"
    assert first["cusip"] == "67066G104"
    assert first["reported_value_raw"] == 12345
    assert first["reported_value_unit"] == "as_reported"
    assert first["value_usd"] == 12345
    assert first["value_unit_confidence"] == "low"
    assert first["shares_or_principal_amount"] == 1000
    assert first["investment_discretion"] == "SOLE"
    assert first["voting_authority_sole"] == 900
    assert first["source"] == ["SEC EDGAR"]


def test_normalize_13f_value_modern_xml_like_raw_usd_with_price_reference():
    normalized = sec_edgar_13f.normalize_13f_value(21929537965, shares=80664820, ticker="AAPL", price_reference=272)
    assert normalized["value_usd"] == 21929537965
    assert normalized["reported_value_unit"] == "usd"
    assert normalized["value_unit_confidence"] == "high"


def test_normalize_13f_value_legacy_thousands_style_with_price_reference():
    normalized = sec_edgar_13f.normalize_13f_value(250000, shares=1000000, ticker="MOCK", price_reference=250)
    assert normalized["value_usd"] == 250000000
    assert normalized["reported_value_unit"] == "thousands_usd"
    assert normalized["value_unit_confidence"] == "high"


def test_normalize_13f_value_without_price_reference_preserves_raw_value():
    normalized = sec_edgar_13f.normalize_13f_value(250000, shares=1000000)
    assert normalized["value_usd"] == 250000
    assert normalized["reported_value_raw"] == 250000
    assert normalized["reported_value_unit"] == "as_reported"
    assert normalized["value_unit_confidence"] != "high"
    assert normalized["value_normalization_note"]


def test_normalize_13f_value_price_reference_sets_medium_and_low_confidence():
    medium = sec_edgar_13f.normalize_13f_value(140, shares=1, price_reference=100)
    low = sec_edgar_13f.normalize_13f_value(200, shares=1, price_reference=100)
    assert medium["reported_value_unit"] == "usd"
    assert medium["value_unit_confidence"] == "medium"
    assert low["reported_value_unit"] == "usd"
    assert low["value_unit_confidence"] == "low"


def test_parser_uses_local_map_and_price_reference_for_raw_usd(monkeypatch):
    monkeypatch.setattr(sec_edgar_13f, "get_price_reference", lambda ticker, as_of_date=None: PriceReference(ticker=ticker, price=272, source_date="2025-12-31", provider="mock_price_reference", confidence="high"))
    xml = """<?xml version="1.0"?>
    <informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
      <infoTable>
        <nameOfIssuer>APPLE INC</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>037833100</cusip>
        <value>21929537965</value>
        <shrsOrPrnAmt><sshPrnamt>80664820</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
      </infoTable>
    </informationTable>
    """
    row = sec_edgar_13f.parse_13f_information_table_xml(xml, "0001067983", "a", "2026-02-16", "2025-12-31")[0]
    assert row["mapped_ticker"] == "AAPL"
    assert row["security_map_used"] is True
    assert row["price_reference_used"] is True
    assert row["reported_value_unit"] == "usd"
    assert row["value_unit_confidence"] == "high"
    assert row["value_usd"] < 1_000_000_000_000


def test_parser_uses_price_reference_for_thousands_usd(monkeypatch):
    monkeypatch.setattr(sec_edgar_13f, "get_price_reference", lambda ticker, as_of_date=None: PriceReference(ticker=ticker, price=250, source_date="2026-03-31", provider="mock_price_reference", confidence="high"))
    xml = INFO_XML.replace("<value>12345</value>", "<value>250</value>").replace("<sshPrnamt>1000</sshPrnamt>", "<sshPrnamt>1000</sshPrnamt>", 1)
    row = sec_edgar_13f.parse_13f_information_table_xml(xml, "0001067983", "a", "2026-05-20", "2026-03-31")[0]
    assert row["mapped_ticker"] == "NVDA"
    assert row["reported_value_unit"] == "thousands_usd"
    assert row["value_usd"] == 250000
    assert row["value_unit_confidence"] == "high"


def test_parser_notes_local_map_without_price_reference(monkeypatch):
    monkeypatch.setattr(sec_edgar_13f, "get_price_reference", lambda ticker, as_of_date=None: None)
    row = sec_edgar_13f.parse_13f_information_table_xml(INFO_XML, "0001067983", "a", "2026-05-20", "2026-03-31")[0]
    assert row["mapped_ticker"] == "NVDA"
    assert row["security_map_used"] is True
    assert row["price_reference_used"] is False
    assert row["reported_value_unit"] == "as_reported"
    assert "Local security mapping was available" in row["value_normalization_note"]


def test_price_reference_cache_is_used_for_mapped_holding(monkeypatch):
    cache_dir = workspace_tmp_dir()
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", True)
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", cache_dir)
    (cache_dir / "AAPL.json").write_text('{"latest_close": 272, "source_date": "2025-12-31", "provider": "yfinance_cache"}', encoding="utf-8")
    price_reference._REFERENCE_CACHE.clear()
    row = sec_edgar_13f.enrich_13f_holding_with_local_context(
        {
            "issuer_name": "APPLE INC",
            "cusip": "037833100",
            "reported_value_raw": 21929537965,
            "shares_or_principal_amount": 80664820,
            "report_date": "2025-12-31",
            "source_status": {"limitations": []},
        }
    )
    assert row["mapped_ticker"] == "AAPL"
    assert row["price_reference_used"] is True
    assert row["value_unit_confidence"] == "high"


def test_price_reference_live_adapter_is_memoized_not_per_row(monkeypatch):
    cache_dir = workspace_tmp_dir()
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", True)
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", cache_dir)
    price_reference._REFERENCE_CACHE.clear()
    calls = []

    def fake_fetch(ticker, period="5d", interval="1d"):
        calls.append(ticker)
        return {"provider": "yfinance", "source_date": "2025-12-31", "rows": [{"date": "2025-12-31", "close": 272}]}

    monkeypatch.setattr("backend.app.data_sources.live_market_prices.fetch_ohlcv", fake_fetch)
    first = price_reference.get_price_reference("AAPL", "2025-12-31")
    second = price_reference.get_price_reference("AAPL", "2025-12-31")
    assert first is not None
    assert second is first
    assert calls == ["AAPL"]


def test_current_price_reference_for_old_report_date_caps_confidence_at_medium(monkeypatch):
    monkeypatch.setattr(sec_edgar_13f, "get_price_reference", lambda ticker, as_of_date=None: PriceReference(ticker=ticker, price=240, source_date="2026-04-29", provider="mock_price_reference", confidence="medium"))
    xml = """<?xml version="1.0"?>
    <informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
      <infoTable>
        <nameOfIssuer>APPLE INC</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>037833100</cusip>
        <value>21929537965</value>
        <shrsOrPrnAmt><sshPrnamt>80664820</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
      </infoTable>
    </informationTable>
    """
    row = sec_edgar_13f.parse_13f_information_table_xml(xml, "0001067983", "a", "2026-02-16", "2025-12-31")[0]
    assert row["price_reference_used"] is True
    assert row["value_unit_confidence"] == "medium"
    assert "Confidence capped at medium" in row["value_normalization_note"]


def test_berkshire_apple_style_holding_does_not_exceed_one_trillion():
    xml = """<?xml version="1.0"?>
    <informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
      <infoTable>
        <nameOfIssuer>APPLE INC</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>037833100</cusip>
        <value>21929537965</value>
        <shrsOrPrnAmt>
          <sshPrnamt>80664820</sshPrnamt>
          <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
      </infoTable>
    </informationTable>
    """
    row = sec_edgar_13f.parse_13f_information_table_xml(xml, "0001067983", "0001193125-26-054580", "2026-02-16", "2025-12-31")[0]
    assert row["issuer_name"] == "APPLE INC"
    assert row["shares_or_principal_amount"] == 80664820
    assert row["reported_value_raw"] == 21929537965
    assert row["value_usd"] < 1_000_000_000_000


def test_aggregate_13f_holdings_groups_by_cusip_and_sums_values_and_shares():
    rows = [
        holding_row("NVIDIA CORP", "67066G104", 100, 10, other_manager="1"),
        holding_row("NVIDIA CORP", "67066G104", 150, 15, other_manager="2"),
    ]
    grouped = aggregate_13f_holdings(rows)["grouped_holdings"]
    assert len(grouped) == 1
    assert grouped[0]["cusip"] == "67066G104"
    assert grouped[0]["total_value_usd"] == 250
    assert grouped[0]["total_shares_or_principal_amount"] == 25
    assert grouped[0]["manager_count_observed"] == 1


def test_aggregation_does_not_merge_different_cusips_for_similar_issuer_names():
    rows = [
        holding_row("ALPHABET INC", "02079K305", 100, 10, title_of_class="CL A"),
        holding_row("ALPHABET INC", "02079K107", 200, 20, title_of_class="CL C"),
    ]
    grouped = aggregate_13f_holdings(rows)["grouped_holdings"]
    assert len(grouped) == 2
    assert {item["cusip"] for item in grouped} == {"02079K305", "02079K107"}


def test_aggregation_preserves_low_confidence_and_dedupes_identical_rows():
    low = holding_row("APPLE INC", "037833100", 300, 30, confidence="low")
    high = holding_row("APPLE INC", "037833100", 100, 10, confidence="high", other_manager="1")
    grouped = aggregate_13f_holdings([low, low.copy(), high])["grouped_holdings"]
    assert len(grouped) == 1
    assert grouped[0]["row_count"] == 2
    assert grouped[0]["total_value_usd"] == 400
    assert grouped[0]["value_unit_confidence_summary"] == "low"


def test_portfolio_summary_totals_top_holdings_and_weights():
    rows = [
        {**holding_row("NVIDIA CORP", "67066G104", 300, 30), "value_unit_confidence": "high", "price_reference_used": True},
        {**holding_row("APPLE INC", "037833100", 100, 10), "value_unit_confidence": "medium"},
        holding_row("UNKNOWN CORP", "999999999", 50, 5, confidence="low"),
    ]
    summary = summarize_13f_portfolio(rows)
    assert summary["total_reported_value_usd"] == 450
    assert summary["top_holdings_by_value"][0]["issuer_name"] == "NVIDIA CORP"
    assert summary["top_holdings_by_value"][0]["mapped_ticker"] == "NVDA"
    assert summary["top_holdings_by_value"][0]["portfolio_weight_pct"] == 66.6667
    assert summary["value_confidence_breakdown"] == {"high": 1, "medium": 1, "low": 1}
    assert summary["mapped_holding_count"] == 2
    assert summary["unmapped_holding_count"] == 1
    assert summary["price_reference_used_count"] == 1
    assert summary["source_status"]["source_type"] == "derived"
    assert summary["source_status"]["provider"] == "derived_from_SEC_EDGAR_13F"


def test_target_cusip_exact_match_returns_high_confidence():
    summary = summarize_13f_portfolio([holding_row("NVIDIA CORP", "67066G104", 300, 30)])
    target_map = normalize_target_security_map({"cusips": "67066G104"})
    matches = match_13f_targets(summary["grouped_holdings"], target_map)["target_matches"]
    assert matches[0]["matched"] is True
    assert matches[0]["match_confidence"] == "high"
    assert matches[0]["match_method"] == "cusip_exact"
    assert matches[0]["matched_cusip"] == "67066G104"


def test_target_ticker_resolves_to_local_cusip_and_high_confidence_match():
    summary = summarize_13f_portfolio([holding_row("NVIDIA CORP", "67066G104", 300, 30)])
    target_map = normalize_target_security_map({"tickers": "NVDA"})
    matches = match_13f_targets(summary["grouped_holdings"], target_map)["target_matches"]
    assert matches[0]["matched"] is True
    assert matches[0]["match_confidence"] == "high"
    assert matches[0]["match_method"] == "ticker_to_local_cusip"
    assert matches[0]["resolved_cusip"] == "67066G104"
    assert matches[0]["resolved_ticker"] == "NVDA"
    assert matches[0]["local_security_map_used"] is True


def test_target_issuer_alias_resolves_to_local_cusip_with_medium_confidence():
    summary = summarize_13f_portfolio([holding_row("NVIDIA CORP", "67066G104", 300, 30)])
    target_map = normalize_target_security_map({"issuers": "NVIDIA CORPORATION"})
    matches = match_13f_targets(summary["grouped_holdings"], target_map)["target_matches"]
    assert matches[0]["matched"] is True
    assert matches[0]["match_confidence"] == "medium"
    assert matches[0]["match_method"] == "issuer_alias_to_local_cusip"
    assert matches[0]["resolved_cusip"] == "67066G104"


def test_target_raw_issuer_name_only_match_returns_low_confidence_and_limitation():
    row = holding_row("PRIVATE FIXTURE SECURITY", "", 300, 30)
    summary = summarize_13f_portfolio([row])
    target_map = normalize_target_security_map({"issuers": "PRIVATE FIXTURE SECURITY"})
    matches = match_13f_targets(summary["grouped_holdings"], target_map)["target_matches"]
    assert matches[0]["matched"] is True
    assert matches[0]["match_confidence"] == "low"
    assert matches[0]["match_method"] == "issuer_name_string_match"
    assert matches[0]["limitations"]


def test_no_target_config_returns_empty_matches_and_missing_data(monkeypatch):
    monkeypatch.setattr(config, "SEC_13F_TARGET_CUSIPS", "")
    monkeypatch.setattr(config, "SEC_13F_TARGET_TICKERS", "")
    monkeypatch.setattr(config, "SEC_13F_TARGET_ISSUERS", "")
    target_map = normalize_target_security_map({})
    matches = match_13f_targets([], target_map)
    assert matches["target_matches"] == []
    assert "SEC 13F target map is not configured." in matches["missing_data"]


def test_qoq_comparison_detects_increased_decreased_and_new_reported_positions():
    current = aggregate_13f_holdings(
        [
            holding_row("NVIDIA CORP", "67066G104", 300, 30, report_date="2026-03-31"),
            holding_row("APPLE INC", "037833100", 50, 5, report_date="2026-03-31"),
            holding_row("TESLA INC", "88160R101", 20, 2, report_date="2026-03-31"),
        ]
    )["grouped_holdings"]
    prior = aggregate_13f_holdings(
        [
            holding_row("NVIDIA CORP", "67066G104", 100, 10, report_date="2025-12-31"),
            holding_row("APPLE INC", "037833100", 100, 10, report_date="2025-12-31"),
        ]
    )["grouped_holdings"]
    changes = {item["cusip"]: item for item in compare_13f_quarter_over_quarter(current, prior)}
    assert changes["67066G104"]["change_label"] == "institutional_position_increased"
    assert changes["037833100"]["change_label"] == "institutional_position_decreased"
    assert changes["88160R101"]["change_label"] == "new_13f_reported_position"


def test_qoq_comparison_missing_prior_quarter_repository_result(monkeypatch):
    cache_dir = workspace_tmp_dir()
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", True)
    monkeypatch.setattr(config, "SEC_13F_CACHE_DIR", cache_dir)
    repository.write_sec_13f_data("0001067983", {**live_13f_payload(), "holdings": [holding_row("NVIDIA CORP", "67066G104", 300, 30)]})
    result = repository.get_sec_13f_qoq_comparison("0001067983", allow_live_fetch=False)
    assert result["qoq_changes"] == []
    assert "prior SEC 13F quarter unavailable" in result["missing_data"]


def test_repository_13f_summary_and_target_matches_are_derived(monkeypatch):
    cache_dir = workspace_tmp_dir()
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", True)
    monkeypatch.setattr(config, "SEC_13F_CACHE_DIR", cache_dir)
    repository.write_sec_13f_data("0001067983", {**live_13f_payload(), "holdings": [holding_row("NVIDIA CORP", "67066G104", 300, 30)]})
    summary = repository.get_sec_13f_summary("0001067983", allow_live_fetch=False)
    matches = repository.get_sec_13f_target_matches("0001067983", {"cusips": "67066G104"}, allow_live_fetch=False)
    assert summary["source_status"]["source_type"] == "derived"
    assert summary["source_status"]["provider"] == "derived_from_SEC_EDGAR_13F"
    assert matches["target_matches"][0]["matched"] is True


def test_smart_money_uses_aggregated_13f_summary_and_target_match():
    snapshot = {**live_13f_payload(), "holdings": [holding_row("NVIDIA CORP", "67066G104", 300, 30)]}
    snapshot["source_status"] = repository.build_source_status(snapshot, freshness_window="quarterly_filing_delay").model_dump(mode="json")
    summary = summarize_13f_portfolio(snapshot["holdings"])
    target_matches = match_13f_targets(summary["grouped_holdings"], normalize_target_security_map({"cusips": "67066G104"}))
    result = evaluate_smart_money(
        {
            "institutional_13f": {"cusip": "67066G104"},
            "institutional_13f_snapshot": snapshot,
            "institutional_13f_source_status": snapshot["source_status"],
            "institutional_13f_summary": summary,
            "institutional_13f_target_matches": target_matches,
            "form4_transactions": [],
            "options_activity": {},
        }
    )
    institutional = result.derived_metrics["components"]["institutional_support_13f"]
    assert institutional["score"] <= 60
    assert institutional["label"] == "institutional_target_match_observed"
    assert institutional["derived_metrics"]["grouped_holding_count"] == 1
    assert institutional["derived_metrics"]["target_match_count"] == 1
    assert result.raw_data["institutional_13f"]["portfolio_summary"]
    assert result.raw_data["institutional_13f"]["target_matches"]


def test_nvda_and_tsla_target_matching_high_confidence_when_cusip_exists():
    summary = summarize_13f_portfolio(
        [
            holding_row("NVIDIA CORP", "67066G104", 300, 30),
            holding_row("TESLA INC", "88160R101", 200, 20),
        ]
    )
    matches = match_13f_targets(summary["grouped_holdings"], normalize_target_security_map({"tickers": "NVDA,TSLA"}))["target_matches"]
    by_ticker = {item["target_value"]: item for item in matches}
    assert by_ticker["NVDA"]["matched"] is True
    assert by_ticker["NVDA"]["match_method"] == "ticker_to_local_cusip"
    assert by_ticker["NVDA"]["match_confidence"] == "high"
    assert by_ticker["TSLA"]["matched"] is True
    assert by_ticker["TSLA"]["resolved_cusip"] == "88160R101"


def test_unmatched_ticker_targets_keep_resolved_cusip_from_local_map():
    summary = summarize_13f_portfolio([holding_row("APPLE INC", "037833100", 300, 30)])
    matches = match_13f_targets(summary["grouped_holdings"], normalize_target_security_map({"tickers": "NVDA,TSLA"}))["target_matches"]
    by_ticker = {item["target_value"]: item for item in matches}
    assert by_ticker["NVDA"]["matched"] is False
    assert by_ticker["NVDA"]["resolved_cusip"] == "67066G104"
    assert by_ticker["TSLA"]["matched"] is False
    assert by_ticker["TSLA"]["resolved_cusip"] == "88160R101"


def test_daily_report_13f_raw_data_excludes_full_holdings_by_default(monkeypatch):
    monkeypatch.setattr(config, "INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT", False)
    snapshot = {**live_13f_payload(), "holdings": [holding_row("NVIDIA CORP", "67066G104", 300, 30)]}
    snapshot["source_status"] = repository.build_source_status(snapshot, freshness_window="quarterly_filing_delay").model_dump(mode="json")
    summary = summarize_13f_portfolio(snapshot["holdings"])
    target_matches = match_13f_targets(summary["grouped_holdings"], normalize_target_security_map({"cusips": "67066G104"}))
    result = evaluate_smart_money(
        {
            "institutional_13f": {"cusip": "67066G104"},
            "institutional_13f_snapshot": snapshot,
            "institutional_13f_source_status": snapshot["source_status"],
            "institutional_13f_summary": summary,
            "institutional_13f_target_matches": target_matches,
            "form4_transactions": [],
            "options_activity": {},
        }
    )
    institutional = result.raw_data["institutional_13f"]
    assert "holdings" not in institutional
    assert "raw_data_full" not in institutional
    assert institutional["portfolio_summary"]
    assert institutional["top_holdings_by_value"]
    assert "target_matches" in institutional
    assert "qoq_changes" in institutional


def test_full_13f_holdings_are_included_only_when_config_enabled(monkeypatch):
    monkeypatch.setattr(config, "INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT", True)
    snapshot = {**live_13f_payload(), "holdings": [holding_row("NVIDIA CORP", "67066G104", 300, 30)]}
    snapshot["source_status"] = repository.build_source_status(snapshot, freshness_window="quarterly_filing_delay").model_dump(mode="json")
    result = evaluate_smart_money(
        {
            "institutional_13f": {"cusip": "67066G104"},
            "institutional_13f_snapshot": snapshot,
            "institutional_13f_source_status": snapshot["source_status"],
            "form4_transactions": [],
            "options_activity": {},
        }
    )
    institutional = result.raw_data["institutional_13f"]
    assert "holdings" not in institutional
    assert institutional["raw_data_full"]["holdings"]


def test_qoq_changes_are_capped_and_report_total_count(monkeypatch):
    monkeypatch.setattr(config, "INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT", False)
    snapshot = {**live_13f_payload(), "holdings": [holding_row("NVIDIA CORP", "67066G104", 300, 30)]}
    snapshot["source_status"] = repository.build_source_status(snapshot, freshness_window="quarterly_filing_delay").model_dump(mode="json")
    qoq_changes = [
        {
            "cusip": f"000000{i:03d}",
            "issuer_name": f"Fixture {i}",
            "current_report_date": "2026-03-31",
            "prior_report_date": "2025-12-31",
            "value_change_usd": i,
            "change_label": "institutional_position_increased",
        }
        for i in range(25)
    ]
    result = evaluate_smart_money(
        {
            "institutional_13f_snapshot": snapshot,
            "institutional_13f_source_status": snapshot["source_status"],
            "institutional_13f_qoq_comparison": {"qoq_changes": qoq_changes},
            "form4_transactions": [],
            "options_activity": {},
        }
    )
    institutional = result.raw_data["institutional_13f"]
    assert len(institutional["qoq_changes"]) == 20
    assert institutional["qoq_changes_count_total"] == 25
    assert institutional["qoq_changes_limit"] == 20
    assert institutional["qoq_changes"][0]["value_change_usd"] == 24


def test_stale_phase4_smart_money_limitation_text_is_not_present_with_sec_sources():
    snapshot = {**live_13f_payload(), "holdings": [holding_row("NVIDIA CORP", "67066G104", 300, 30)]}
    snapshot["source_status"] = repository.build_source_status(snapshot, freshness_window="quarterly_filing_delay").model_dump(mode="json")
    result = evaluate_smart_money(
        {
            "institutional_13f_snapshot": snapshot,
            "institutional_13f_source_status": snapshot["source_status"],
            "form4_transactions": [],
            "form4_source_status": {"source_type": "cached_live", "provider": "SEC EDGAR", "source_date": "2026-04-10", "is_fresh": True, "fallback_used": False},
            "options_activity": {},
        }
    )
    text = str(result.model_dump(mode="json"))
    assert "Phase 4 deterministic mock smart money engine; no live source connection." not in text
    assert result.source_status is not None
    assert result.source_status.fallback_used is False
    assert result.source_status.source_type == "derived"
    assert result.source_status.provider == "mixed_smart_money_sources"


def test_daily_report_keeps_compact_13f_summary_fields(monkeypatch):
    monkeypatch.setattr(config, "INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT", False)
    snapshot = {**live_13f_payload(), "holdings": [holding_row("NVIDIA CORP", "67066G104", 300, 30)]}
    snapshot["source_status"] = repository.build_source_status(snapshot, freshness_window="quarterly_filing_delay").model_dump(mode="json")
    summary = summarize_13f_portfolio(snapshot["holdings"])
    target_matches = match_13f_targets(summary["grouped_holdings"], normalize_target_security_map({"cusips": "67066G104"}))
    sec_filings = {
        "institutional_13f": {"cusip": "67066G104"},
        "institutional_13f_snapshot": snapshot,
        "institutional_13f_snapshots": [snapshot],
        "institutional_13f_source_status": snapshot["source_status"],
        "institutional_13f_summary": summary,
        "institutional_13f_target_matches": target_matches,
        "institutional_13f_qoq_comparison": {"qoq_changes": []},
        "form4_transactions": [],
        "form4_source_status": {"source_type": "cached_live", "provider": "SEC EDGAR", "source_date": "2026-04-10", "is_fresh": True, "fallback_used": False},
        "form4_snapshot": {"limitations": []},
        "crisis_scenarios": {},
    }
    monkeypatch.setattr(mock_pipeline, "read_sec_filings", lambda ticker="NVDA": sec_filings)
    report = mock_pipeline.build_daily_report()
    institutional = report.smart_money.raw_data["institutional_13f"]
    assert "holdings" not in institutional
    assert "raw_data_full" not in institutional
    assert institutional["portfolio_summary"]
    assert institutional["top_holdings_by_value"]
    assert "target_matches" in institutional
    assert "qoq_changes" in institutional


def test_portfolio_summary_missing_price_reference_for_mapped_holdings(monkeypatch):
    monkeypatch.setattr(sec_edgar_13f, "get_price_reference", lambda ticker, as_of_date=None: None)
    rows = sec_edgar_13f.parse_13f_information_table_xml(INFO_XML, "0001067983", "a", "2026-05-20", "2026-03-31")
    summary = summarize_13f_portfolio(rows)
    assert summary["mapped_holding_count"] > 0
    assert summary["price_reference_used_count"] == 0
    assert "price reference unavailable for mapped 13F holdings" in summary["missing_data"]


def test_form4_parser_rejects_html_before_xml_parse():
    html = "<html><body><table><tr><td>not xml</td></tr></table></body></html>"
    with pytest.raises(sec_edgar_form4.SecEdgarForm4FetchError):
        sec_edgar_form4.parse_form4_xml(html, "NVDA", "0000000000", "a", "2026-04-01")


def test_form4_fetch_discovers_actual_xml_after_html_primary(monkeypatch):
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_EDGAR_REQUEST_DELAY_SECONDS", 0)
    valid_xml = """<ownershipDocument><issuer><issuerCik>0000000000</issuerCik><issuerName>NVIDIA</issuerName><issuerTradingSymbol>NVDA</issuerTradingSymbol></issuer><reportingOwner><reportingOwnerId><rptOwnerName>Owner</rptOwnerName></reportingOwnerId><reportingOwnerRelationship><isDirector>1</isDirector></reportingOwnerRelationship></reportingOwner></ownershipDocument>"""

    def fake_get(url, headers, timeout):
        if url.endswith("index.json"):
            return FakeResponse({"directory": {"item": [{"name": "primary.html"}, {"name": "form4.xml"}]}})
        if url.endswith("primary.html"):
            return FakeResponse(text="<html><body>index</body></html>")
        return FakeResponse(text=valid_xml)

    monkeypatch.setattr(sec_edgar_form4.httpx, "get", fake_get)
    assert sec_edgar_form4.fetch_form4_xml("0000000001", "0000000001-26-000001", "primary.html") == valid_xml


def test_form4_live_fetch_failure_with_cache_returns_cached_live_reason(monkeypatch):
    cache_dir = workspace_tmp_dir()
    monkeypatch.setattr(config, "USE_LIVE_SEC_FORM4", True)
    monkeypatch.setattr(config, "SEC_FORM4_CACHE_DIR", cache_dir)
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_FORM4_CACHE_TTL_HOURS", -1)
    repository.write_sec_form4_data(
        "NVDA",
        {
            "ticker": "NVDA",
            "transactions": [],
            "source_type": "live",
            "provider": "SEC EDGAR",
            "source": ["SEC EDGAR"],
            "source_date": "2026-04-01",
            "limitations": [],
            "missing_data": [],
        },
    )
    monkeypatch.setattr(sec_edgar_form4, "fetch_insider_transactions", lambda ticker, lookback_days=180: (_ for _ in ()).throw(RuntimeError("mismatched tag: line 29, column 16")))
    payload = repository.get_sec_form4_transactions("NVDA")
    assert payload["source_type"] == "cached_live"
    assert payload["provider"] == "SEC EDGAR"
    assert payload["source_status"]["fallback_reason"] == "Live SEC EDGAR Form 4 fetch failed; cached live data used."


def test_candidate_cached_live_form4_warning_not_candidate_fallback(monkeypatch):
    sec_filings = {
        "institutional_13f": {},
        "institutional_13f_snapshot": {},
        "institutional_13f_snapshots": [],
        "institutional_13f_source_status": {"source_type": "cached_live", "provider": "SEC EDGAR", "source_date": "2026-03-31", "is_fresh": True, "fallback_used": False},
        "form4_transactions": [],
        "form4_source_status": {"source_type": "cached_live", "provider": "SEC EDGAR", "source_date": "2026-04-01", "is_fresh": True, "fallback_used": True, "fallback_reason": "Live SEC EDGAR Form 4 fetch failed; cached live data used."},
        "form4_snapshot": {"limitations": []},
        "crisis_scenarios": {},
    }
    monkeypatch.setattr(mock_pipeline, "read_sec_filings", lambda ticker="NVDA": sec_filings)
    candidate = mock_pipeline._candidate("NVDA", "AI energy infrastructure", {"source_type": "live", "source": ["yfinance"], "source_date": "2026-04-29", "source_status": {"is_fresh": True}})
    assert candidate.source_status is not None
    assert candidate.source_status.source_type == "derived"
    assert candidate.source_status.fallback_used is False


def test_xml_parser_handles_namespaces():
    rows = sec_edgar_13f.parse_13f_information_table_xml(INFO_XML, "1067983", "a", "2026-05-20", "2026-03-31")
    assert len(rows) == 2


def test_missing_or_malformed_xml_returns_insufficient_data_not_crash(monkeypatch):
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", True)
    monkeypatch.setattr(config, "SEC_13F_PROVIDER", "sec_edgar")
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_13F_CACHE_DIR", workspace_tmp_dir())

    def fail_fetch(_manager, lookback_quarters=4):
        raise sec_edgar_13f.SecEdgar13FFetchError("Malformed 13F information table XML")

    monkeypatch.setattr(sec_edgar_13f, "fetch_13f_holdings_for_manager", fail_fetch)
    payload = repository.get_sec_13f_holdings("0001067983")
    result = evaluate_smart_money({"institutional_13f_snapshot": payload, "institutional_13f_source_status": payload["source_status"], "form4_transactions": [], "options_activity": {}})
    assert payload["source_type"] == "fallback"
    assert result.derived_metrics["components"]["institutional_support_13f"]["label"] in {"insufficient_data", "institutional_evidence_limited"}


def test_cache_first_repository_returns_cached_live_when_valid(monkeypatch):
    cache_dir = workspace_tmp_dir()
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", True)
    monkeypatch.setattr(config, "SEC_13F_CACHE_DIR", cache_dir)
    repository.write_sec_13f_data("0001067983", live_13f_payload())
    payload = repository.get_sec_13f_holdings("0001067983", allow_live_fetch=False)
    assert payload["source_type"] == "cached_live"
    assert payload["provider"] == "SEC EDGAR"


def test_missing_sec_edgar_user_agent_returns_fallback(monkeypatch):
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", True)
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "")
    monkeypatch.setattr(config, "SEC_13F_CACHE_DIR", workspace_tmp_dir())
    payload = repository.get_sec_13f_holdings("0001067983")
    assert payload["source_type"] == "fallback"
    assert payload["source_status"]["fallback_reason"] == "SEC_EDGAR_USER_AGENT missing"


def test_edgar_fetch_failure_uses_cached_live_if_available(monkeypatch):
    cache_dir = workspace_tmp_dir()
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", True)
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_13F_CACHE_DIR", cache_dir)
    repository.write_sec_13f_data("0001067983", live_13f_payload())

    def fail_fetch(_manager, lookback_quarters=4):
        raise RuntimeError("sec unavailable")

    monkeypatch.setattr(sec_edgar_13f, "fetch_13f_holdings_for_manager", fail_fetch)
    payload = repository.get_sec_13f_holdings("0001067983")
    assert payload["source_type"] == "cached_live"


def test_edgar_fetch_failure_with_no_cache_returns_fallback_mock(monkeypatch):
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", True)
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(config, "SEC_13F_CACHE_DIR", workspace_tmp_dir())

    def fail_fetch(_manager, lookback_quarters=4):
        raise RuntimeError("sec unavailable")

    monkeypatch.setattr(sec_edgar_13f, "fetch_13f_holdings_for_manager", fail_fetch)
    payload = repository.get_sec_13f_holdings("0001067983")
    assert payload["source_type"] == "fallback"
    assert payload["provider"] == "mock"


def test_fallback_mock_13f_does_not_boost_smart_money_score():
    fallback = repository._mock_13f_snapshot("0001067983", "NVDA", "SEC unavailable")
    result = evaluate_smart_money({"institutional_13f_snapshot": fallback, "institutional_13f_source_status": fallback["source_status"], "form4_transactions": [], "options_activity": {}})
    institutional = result.derived_metrics["components"]["institutional_support_13f"]
    assert institutional["score"] <= 20
    assert institutional["label"] == "insufficient_data"
    assert result.score < 50


def test_mock_13f_filing_date_is_not_future_relative_to_report_date():
    fallback = repository._mock_13f_snapshot("0001067983", "NVDA", "SEC unavailable")
    today = date.today().isoformat()
    assert fallback["source_date"] <= today
    assert fallback["filings"][0]["filing_date"] <= today
    assert fallback["holdings"][0]["filing_date"] <= today


def test_smart_money_source_date_not_pulled_forward_by_fallback_mock_13f():
    fallback = repository._mock_13f_snapshot("0001067983", "NVDA", "SEC unavailable")
    form4_status = {
        "source_type": "live",
        "provider": "SEC EDGAR",
        "source": ["SEC EDGAR"],
        "source_date": "2026-04-11",
        "is_fresh": True,
        "fallback_used": False,
        "limitations": [],
        "missing_data": [],
    }
    result = evaluate_smart_money(
        {
            "institutional_13f_snapshot": fallback,
            "institutional_13f_source_status": fallback["source_status"],
            "form4_transactions": [],
            "form4_source_status": form4_status,
            "options_activity": {},
        }
    )
    assert result.source_status is not None
    assert result.source_status.source_date == "2026-04-11"
    assert result.source_status.fallback_used is True
    assert "live SEC 13F data" in result.source_status.missing_data


def test_13f_source_status_uses_quarterly_filing_delay():
    payload = live_13f_payload()
    payload["source_status"] = repository.build_source_status(payload, freshness_window="quarterly_filing_delay").model_dump(mode="json")
    assert payload["source_status"]["freshness_window"] == "quarterly_filing_delay"
    assert payload["source_status"]["freshness_window"] != "latest_expected_trading_day"


def test_qoq_comparison_when_prior_quarter_same_cusip_exists():
    latest = sec_edgar_13f.parse_13f_information_table_xml(INFO_XML, "0001067983", "new", "2026-05-20", "2026-03-31")
    prior = sec_edgar_13f.parse_13f_information_table_xml(PRIOR_XML, "0001067983", "old", "2026-02-14", "2025-12-31")
    snapshot = {**live_13f_payload(), "holdings": [*latest, *prior], "source_status": {"source_type": "live", "provider": "SEC EDGAR", "source_date": "2026-03-31"}}
    result = evaluate_smart_money({"institutional_13f": {"cusip": "67066G104"}, "institutional_13f_snapshot": snapshot, "institutional_13f_source_status": snapshot["source_status"], "form4_transactions": [], "options_activity": {}})
    institutional = result.derived_metrics["components"]["institutional_support_13f"]
    assert institutional["derived_metrics"]["quarter_over_quarter_position_change"] == 25.0


def test_mixed_smart_money_sources_with_13f_form4_options():
    payload = live_13f_payload()
    payload["source_status"] = {"source_type": "live", "provider": "SEC EDGAR", "source_date": "2026-03-31", "is_fresh": True}
    result = evaluate_smart_money({"institutional_13f_snapshot": payload, "institutional_13f_source_status": payload["source_status"], "form4_transactions": [], "options_activity": {}})
    assert result.source_status is not None
    assert result.source_status.source_type == "derived"
    assert result.source_status.provider == "mixed_smart_money_sources"


def test_source_type_enum_rejects_unexpected_values():
    with pytest.raises(Exception):
        DataSourceStatus(source_type="mixed")


def test_phase11_forbidden_language_guard_still_passes():
    payload = live_13f_payload()
    result = evaluate_smart_money({"institutional_13f_snapshot": payload, "institutional_13f_source_status": {"source_type": "live", "provider": "SEC EDGAR", "source_date": "2026-03-31"}, "form4_transactions": [], "options_activity": {}})
    assert detect_forbidden_language(result.model_dump(mode="json")) == []
