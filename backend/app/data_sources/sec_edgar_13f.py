from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from backend.app import config
from backend.app.utils.freshness import THIRTEEN_F_FRESHNESS_WINDOW, build_source_status

SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dash}/{document}"
PROVIDER = "SEC EDGAR"
LIMITATIONS = [
    "13F is delayed quarterly evidence and should not be interpreted as real-time institutional flow.",
    "13F may lag up to 45 days after quarter end.",
    "13F may not show shorts, many derivatives, or current positions.",
    "Manager-name discovery is limited to a small local mapping in v1.",
    "Amendments supersede original filings only for the same reporting period when the amendment filing is newer.",
]

LOCAL_MANAGER_CIKS = {
    "berkshire hathaway": "0001067983",
    "berkshire hathaway inc": "0001067983",
    "blackrock": "0001364742",
    "blackrock inc": "0001364742",
    "vanguard": "0000102909",
    "vanguard group": "0000102909",
    "the vanguard group": "0000102909",
}


class SecEdgar13FFetchError(RuntimeError):
    """Raised when official SEC EDGAR 13F data cannot be fetched or normalized."""


class FilingIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {name.lower(): value for name, value in attrs}
        href = attr_map.get("href") or ""
        if href:
            self.links.append(href)


def _headers() -> dict[str, str]:
    if not config.SEC_EDGAR_USER_AGENT:
        raise SecEdgar13FFetchError("SEC_EDGAR_USER_AGENT missing")
    return {"User-Agent": config.SEC_EDGAR_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _request_delay() -> None:
    time.sleep(max(0.0, config.SEC_EDGAR_REQUEST_DELAY_SECONDS))


def _get_json(url: str) -> dict[str, Any]:
    _request_delay()
    response = httpx.get(url, headers=_headers(), timeout=20)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise SecEdgar13FFetchError("SEC response was not a JSON object")
    return payload


def _get_text(url: str) -> str:
    _request_delay()
    response = httpx.get(url, headers=_headers(), timeout=20)
    response.raise_for_status()
    return response.text


def _cik10(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not text.isdigit():
        raise SecEdgar13FFetchError("Manager-name CIK mapping not found")
    return text.zfill(10)


def _accession_no_dash(accession_number: str) -> str:
    return accession_number.replace("-", "").strip()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element: ET.Element | None, *names: str) -> ET.Element | None:
    if element is None:
        return None
    wanted = {name.lower() for name in names}
    for child in list(element):
        if _local_name(child.tag).lower() in wanted:
            return child
    return None


def _children(element: ET.Element | None, *names: str) -> list[ET.Element]:
    if element is None:
        return []
    wanted = {name.lower() for name in names}
    return [child for child in list(element) if _local_name(child.tag).lower() in wanted]


def _text(element: ET.Element | None, path: list[str]) -> str:
    current = element
    for part in path:
        current = _child(current, part)
        if current is None:
            return ""
    return (current.text or "").strip()


def _as_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return int(number) if number is not None else None


def _filing_key(filing: dict[str, Any]) -> tuple[str, str]:
    return (str(filing.get("report_date") or filing.get("filing_date") or ""), str(filing.get("accession_number") or ""))


def get_cik_for_manager(manager_name_or_cik: str) -> str:
    text = str(manager_name_or_cik or "").strip()
    if not text:
        raise SecEdgar13FFetchError("Manager name or CIK is required")
    if text.isdigit():
        return _cik10(text)
    cik = LOCAL_MANAGER_CIKS.get(text.casefold())
    if not cik:
        raise SecEdgar13FFetchError("Manager-name discovery is limited in v1")
    return cik


def fetch_manager_submissions(cik: str) -> dict[str, Any]:
    return _get_json(SEC_SUBMISSIONS_URL.format(cik=_cik10(cik)))


def find_recent_13f_filings(submissions: dict[str, Any], lookback_quarters: int = 4) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {}) if isinstance(submissions, dict) else {}
    forms = recent.get("form", []) or []
    accessions = recent.get("accessionNumber", []) or []
    filing_dates = recent.get("filingDate", []) or []
    report_dates = recent.get("reportDate", []) or []
    primary_documents = recent.get("primaryDocument", []) or []
    by_period: dict[str, dict[str, Any]] = {}
    for index, form in enumerate(forms):
        normalized_form = str(form or "").upper()
        if normalized_form not in {"13F-HR", "13F-HR/A"}:
            continue
        filing = {
            "accession_number": str(accessions[index] if index < len(accessions) else ""),
            "accessionNumber": str(accessions[index] if index < len(accessions) else ""),
            "filing_date": str(filing_dates[index] if index < len(filing_dates) else ""),
            "filingDate": str(filing_dates[index] if index < len(filing_dates) else ""),
            "report_date": str(report_dates[index] if index < len(report_dates) else ""),
            "reportDate": str(report_dates[index] if index < len(report_dates) else ""),
            "primary_document": str(primary_documents[index] if index < len(primary_documents) else ""),
            "primaryDocument": str(primary_documents[index] if index < len(primary_documents) else ""),
            "form": normalized_form,
        }
        period = filing["report_date"] or filing["filing_date"] or filing["accession_number"]
        existing = by_period.get(period)
        if existing is None:
            by_period[period] = filing
            continue
        existing_is_amendment = existing.get("form") == "13F-HR/A"
        filing_is_amendment = filing.get("form") == "13F-HR/A"
        if filing["filing_date"] > existing.get("filing_date", "") and (filing_is_amendment or not existing_is_amendment):
            by_period[period] = filing
    filings = sorted(by_period.values(), key=_filing_key, reverse=True)
    return filings[: max(1, lookback_quarters)]


def build_edgar_archive_url(cik: str, accession_number: str, document_name: str) -> str:
    return SEC_ARCHIVES_URL.format(
        cik_int=str(int(_cik10(cik))),
        accession_no_dash=_accession_no_dash(accession_number),
        document=document_name,
    )


def _index_url(cik: str, accession_number: str) -> str:
    return build_edgar_archive_url(cik, accession_number, "index.html")


def _candidate_document_names(primary_document: str) -> list[str]:
    names = [
        "form13fInfoTable.xml",
        "form13fInfoTable.XML",
        "infotable.xml",
        "infoTable.xml",
        "primary_doc.xml",
        primary_document,
    ]
    return [name for index, name in enumerate(names) if name and name not in names[:index]]


def discover_13f_information_table_documents(cik: str, accession_number: str, primary_document: str) -> list[str]:
    candidates = _candidate_document_names(primary_document)
    try:
        index_text = _get_text(_index_url(cik, accession_number))
    except Exception:
        index_text = ""
    if index_text:
        parser = FilingIndexParser()
        parser.feed(index_text)
        for href in parser.links[:100]:
            document = href.rsplit("/", 1)[-1]
            normalized = document.lower()
            if normalized.endswith(".xml") and (
                "infotable" in normalized
                or "form13f" in normalized
                or re.search(r"(^|[-_])info", normalized)
            ):
                candidates.insert(0, document)
            elif normalized.endswith(".xml"):
                candidates.append(document)
    documents: list[str] = []
    for name in candidates:
        document = name.rsplit("/", 1)[-1]
        if document and document not in documents and document.lower() != str(primary_document).lower():
            documents.append(document)
    return documents[:10]


def fetch_13f_information_table_xml(url: str) -> str:
    return _get_text(url)


def parse_13f_information_table_xml(
    xml_text: str,
    manager_cik: str,
    accession_number: str,
    filing_date: str,
    report_date: str,
) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SecEdgar13FFetchError("Malformed 13F information table XML") from exc
    fetched_source_date = report_date or filing_date
    rows: list[dict[str, Any]] = []
    for info_table in root.iter():
        if _local_name(info_table.tag).lower() != "infotable":
            continue
        issuer_name = _text(info_table, ["nameOfIssuer"])
        cusip = _text(info_table, ["cusip"])
        if not issuer_name and not cusip:
            continue
        raw_value = _as_float(_text(info_table, ["value"]))
        shares = _as_float(_text(info_table, ["shrsOrPrnAmt", "sshPrnamt"]))
        row = {
            "manager_cik": _cik10(manager_cik),
            "accession_number": accession_number,
            "filing_date": filing_date,
            "report_date": report_date,
            "issuer_name": issuer_name,
            "title_of_class": _text(info_table, ["titleOfClass"]),
            "cusip": cusip,
            "value_usd_thousands_raw": raw_value,
            "value_usd": raw_value * 1000 if raw_value is not None else None,
            "shares_or_principal_amount": shares,
            "share_type": _text(info_table, ["shrsOrPrnAmt", "sshPrnamtType"]),
            "put_call": _text(info_table, ["putCall"]),
            "investment_discretion": _text(info_table, ["investmentDiscretion"]),
            "other_manager": _text(info_table, ["otherManager"]),
            "voting_authority_sole": _as_int(_text(info_table, ["votingAuthority", "Sole"])),
            "voting_authority_shared": _as_int(_text(info_table, ["votingAuthority", "Shared"])),
            "voting_authority_none": _as_int(_text(info_table, ["votingAuthority", "None"])),
            "source": [PROVIDER],
            "source_status": {
                "source_type": "live",
                "provider": PROVIDER,
                "source_date": fetched_source_date,
                "freshness_window": THIRTEEN_F_FRESHNESS_WINDOW,
                "fallback_used": False,
                "fallback_reason": None,
                "limitations": LIMITATIONS,
                "missing_data": [],
            },
        }
        rows.append(row)
    return rows


def dedupe_holdings(holdings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for item in holdings:
        key = (
            item.get("manager_cik"),
            item.get("accession_number"),
            str(item.get("cusip") or "").upper(),
            str(item.get("issuer_name") or "").casefold(),
            item.get("value_usd"),
            item.get("shares_or_principal_amount"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def fetch_13f_holdings_for_manager(manager_name_or_cik: str, lookback_quarters: int = 4) -> dict[str, Any]:
    manager_cik = get_cik_for_manager(manager_name_or_cik)
    submissions = fetch_manager_submissions(manager_cik)
    filings = find_recent_13f_filings(submissions, lookback_quarters=lookback_quarters)
    fetched_at = datetime.now(timezone.utc).isoformat()
    holdings: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    missing_data: list[str] = []
    limitations = list(LIMITATIONS)
    for filing in filings:
        documents = discover_13f_information_table_documents(manager_cik, filing["accession_number"], filing.get("primary_document", ""))
        if not documents:
            missing_data.append(f"13F information table XML for {filing['accession_number']}")
            continue
        parsed_for_filing = False
        for document in documents:
            url = build_edgar_archive_url(manager_cik, filing["accession_number"], document)
            try:
                rows = parse_13f_information_table_xml(
                    fetch_13f_information_table_xml(url),
                    manager_cik,
                    filing["accession_number"],
                    filing.get("filing_date", ""),
                    filing.get("report_date", ""),
                )
            except SecEdgar13FFetchError:
                continue
            for row in rows:
                row["source_status"] = build_source_status(
                    {**row["source_status"], "fetched_at": fetched_at},
                    freshness_window=THIRTEEN_F_FRESHNESS_WINDOW,
                ).model_dump(mode="json")
            holdings.extend(rows)
            parsed_for_filing = True
            metadata.append({**filing, "information_table_document": document})
            break
        if not parsed_for_filing:
            missing_data.append(f"parseable 13F information table XML for {filing['accession_number']}")
    holdings = dedupe_holdings(holdings)
    source_date = max((item.get("report_date") or item.get("filing_date") or "" for item in metadata), default="")
    payload = {
        "manager": manager_name_or_cik,
        "manager_cik": manager_cik,
        "lookback_quarters": lookback_quarters,
        "filings": metadata,
        "holdings": holdings,
        "source_type": "live",
        "provider": PROVIDER,
        "source": [PROVIDER],
        "source_date": source_date,
        "fetched_at": fetched_at,
        "limitations": limitations,
        "missing_data": missing_data if filings else ["recent SEC 13F filings"],
    }
    payload["source_status"] = build_source_status(payload, freshness_window=THIRTEEN_F_FRESHNESS_WINDOW).model_dump(mode="json")
    return payload
