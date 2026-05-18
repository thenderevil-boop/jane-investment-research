from __future__ import annotations

import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import httpx

from backend.app import config
from backend.app.data.price_reference import get_price_reference
from backend.app.data.security_map import resolve_security_identifier
from backend.app.utils.freshness import THIRTEEN_F_FRESHNESS_WINDOW, build_source_status

SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_DIRECTORY_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dash}/"
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
    "state street": "0000093751",
    "state street corp": "0000093751",
    "geode capital": "0001214717",
    "geode capital management": "0001214717",
    "geode capital management llc": "0001214717",
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
        self.documents: list[dict[str, str]] = []
        self._current_href = ""
        self._current_cells: list[str] = []
        self._in_td = False
        self._cell_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower_tag = tag.lower()
        if lower_tag == "tr":
            self._current_href = ""
            self._current_cells = []
        if lower_tag == "td":
            self._in_td = True
            self._cell_text = []
        if lower_tag != "a":
            return
        attr_map = {name.lower(): value for name, value in attrs}
        href = attr_map.get("href") or ""
        if href:
            self.links.append(href)
            self._current_href = href

    def handle_data(self, data: str) -> None:
        if self._in_td:
            text = data.strip()
            if text:
                self._cell_text.append(text)

    def handle_endtag(self, tag: str) -> None:
        lower_tag = tag.lower()
        if lower_tag == "td" and self._in_td:
            self._current_cells.append(" ".join(self._cell_text).strip())
            self._in_td = False
            self._cell_text = []
        if lower_tag == "tr" and self._current_href:
            filename = self._current_href.rsplit("/", 1)[-1]
            self.documents.append(
                {
                    "name": filename,
                    "href": self._current_href,
                    "type": " ".join(self._current_cells),
                    "description": " ".join(self._current_cells),
                }
            )


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


def _cik_no_leading_zeros(cik: str) -> str:
    cik10 = _cik10(cik)
    if not cik10:
        raise SecEdgar13FFetchError("CIK is required")
    return str(int(cik10))


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


def normalize_13f_value(
    raw_value: float | int | None,
    shares: float | int | None = None,
    ticker: str | None = None,
    price_reference: float | int | None = None,
    security_map_used: bool = False,
) -> dict[str, Any]:
    if raw_value is None:
        return {
            "reported_value_raw": None,
            "reported_value_unit": "unknown",
            "value_usd": None,
            "value_unit_confidence": "low",
            "value_normalization_note": "13F XML value was missing.",
        }
    raw = float(raw_value)
    if price_reference is not None and shares is not None and shares > 0 and price_reference > 0:
        expected_value = float(shares) * float(price_reference)
        raw_delta = abs(raw - expected_value)
        thousands_delta = abs(raw * 1000 - expected_value)
        chosen_delta = min(raw_delta, thousands_delta)
        tolerance = chosen_delta / expected_value if expected_value else 1
        confidence = "high" if tolerance <= 0.25 else "medium" if tolerance <= 0.50 else "low"
        note_suffix = " Local security map and price reference were used. Price reference may not match the 13F report date exactly."
        if thousands_delta < raw_delta:
            return {
                "reported_value_raw": raw,
                "reported_value_unit": "thousands_usd",
                "value_usd": raw * 1000,
                "value_unit_confidence": confidence,
                "value_normalization_note": f"13F XML value interpreted as thousands of USD because that is closer to shares times the available price reference.{note_suffix}",
            }
        return {
            "reported_value_raw": raw,
            "reported_value_unit": "usd",
            "value_usd": raw,
            "value_unit_confidence": confidence,
            "value_normalization_note": f"13F XML value interpreted as USD because that is closer to shares times the available price reference.{note_suffix}",
        }
    if config.SEC_13F_ASSUME_VALUE_THOUSANDS:
        return {
            "reported_value_raw": raw,
            "reported_value_unit": "thousands_usd",
            "value_usd": raw * 1000,
            "value_unit_confidence": "medium",
            "value_normalization_note": "13F XML value interpreted as thousands of USD because SEC_13F_ASSUME_VALUE_THOUSANDS=true.",
        }
    return {
        "reported_value_raw": raw,
        "reported_value_unit": "as_reported",
        "value_usd": raw,
        "value_unit_confidence": "low",
        "value_normalization_note": "Local security mapping was available, but no reliable price reference was available." if security_map_used else "13F XML value preserved as reported because no reliable unit disambiguation reference was available.",
    }


def enrich_13f_holding_with_local_context(holding: dict[str, Any]) -> dict[str, Any]:
    row = dict(holding)
    resolved = resolve_security_identifier(cusip=row.get("cusip"), issuer_name=row.get("issuer_name"))
    security = resolved.get("security") or {}
    mapped_ticker = security.get("ticker", "")
    price_reference = get_price_reference(mapped_ticker, as_of_date=row.get("report_date")) if mapped_ticker else None
    raw_value = row.get("reported_value_raw")
    shares = row.get("shares_or_principal_amount")
    price = price_reference.price if price_reference else None
    value_fields = normalize_13f_value(raw_value, shares=shares, ticker=mapped_ticker, price_reference=price, security_map_used=bool(security))
    if price_reference and value_fields.get("value_unit_confidence") == "high":
        expected_value = float(shares or 0) * float(price_reference.price)
        chosen_value = float(value_fields.get("value_usd") or 0)
        tolerance = abs(chosen_value - expected_value) / expected_value if expected_value else 1
        if price_reference.source_date and row.get("report_date") and price_reference.source_date != row.get("report_date") and tolerance > 0.01:
            value_fields["value_unit_confidence"] = "medium"
            value_fields["value_normalization_note"] = f"{value_fields.get('value_normalization_note')} Confidence capped at medium because the price reference date differs from the 13F report date."
    row.update(
        {
            "mapped_ticker": mapped_ticker,
            "resolved_cusip": security.get("cusip", ""),
            "resolved_issuer_name": security.get("issuer_name", ""),
            "security_map_used": bool(security),
            "price_reference_used": price_reference is not None,
            "price_reference": price_reference.model_dump() if price_reference else None,
            **value_fields,
        }
    )
    if price_reference and isinstance(row.get("source_status"), dict):
        limitations = list(row["source_status"].get("limitations", []) or [])
        if "Price reference may not match the 13F report date exactly." not in limitations:
            limitations.append("Price reference may not match the 13F report date exactly.")
        row["source_status"]["limitations"] = limitations
    return row


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
    return _get_json(build_submissions_url(cik))


def build_submissions_url(cik: str) -> str:
    return SEC_SUBMISSIONS_URL.format(cik=_cik10(cik))


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


def build_archives_directory_url(cik: str, accession_number: str) -> str:
    return SEC_ARCHIVES_DIRECTORY_URL.format(
        cik_int=_cik_no_leading_zeros(cik),
        accession_no_dash=_accession_no_dash(accession_number),
    )


def build_archives_index_json_url(cik: str, accession_number: str) -> str:
    return f"{build_archives_directory_url(cik, accession_number)}index.json"


def build_archives_index_html_url(cik: str, accession_number: str) -> str:
    return f"{build_archives_directory_url(cik, accession_number)}{accession_number}-index.html"


def build_edgar_archive_url(cik: str, accession_number: str, document_name: str) -> str:
    return urljoin(build_archives_directory_url(cik, accession_number), document_name)


def _document_name(document: dict[str, Any]) -> str:
    return str(document.get("name") or document.get("href") or "").rsplit("/", 1)[-1]


def _is_excluded_document(document: dict[str, Any]) -> bool:
    name = _document_name(document).lower()
    if not name:
        return True
    if name.endswith((".htm", ".html", ".xsl")):
        return True
    if name in {"primary_doc.xml", "form13f.xml"}:
        return True
    if name.endswith(".txt"):
        return True
    return False


def _candidate_rank(document: dict[str, Any]) -> int | None:
    if _is_excluded_document(document):
        return None
    name = _document_name(document).lower()
    doc_type = str(document.get("type") or "").lower()
    description = str(document.get("description") or "").lower()
    combined = f"{name} {doc_type} {description}"
    if not name.endswith(".xml"):
        return None
    if "infotable" in name or "informationtable" in name or "form13finfotable" in name:
        return 0
    if "information table" in combined:
        return 1
    if "13f" in name:
        return 2
    if "primary_doc" not in name and "form13f" not in name:
        return 5
    return None


def _ordered_candidate_urls(cik: str, accession_number: str, documents: list[dict[str, Any]]) -> list[str]:
    ranked: list[tuple[int, int, str]] = []
    directory_url = build_archives_directory_url(cik, accession_number)
    for index, document in enumerate(documents):
        rank = _candidate_rank(document)
        if rank is None:
            continue
        href = str(document.get("href") or document.get("name") or "")
        url = href if href.startswith("http") else urljoin(directory_url, href.rsplit("/", 1)[-1])
        ranked.append((rank, index, url))
    urls: list[str] = []
    for _rank, _index, url in sorted(ranked, key=lambda item: (item[0], item[1])):
        if url not in urls:
            urls.append(url)
    return urls[:5]


def _documents_from_index_json(payload: dict[str, Any]) -> list[dict[str, Any]]:
    directory = payload.get("directory", {}) if isinstance(payload, dict) else {}
    items = directory.get("item") or payload.get("item") or []
    documents: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        documents.append(
            {
                "name": str(item.get("name") or ""),
                "href": str(item.get("href") or item.get("name") or ""),
                "type": str(item.get("type") or ""),
                "description": str(item.get("description") or ""),
            }
        )
    return documents


def discover_13f_information_table_documents(cik: str, accession_number: str) -> list[str]:
    json_error = ""
    try:
        documents = _documents_from_index_json(_get_json(build_archives_index_json_url(cik, accession_number)))
        candidates = _ordered_candidate_urls(cik, accession_number, documents)
        if candidates:
            return candidates
    except Exception as exc:
        json_error = str(exc).splitlines()[0][:120]
    try:
        index_text = _get_text(build_archives_index_html_url(cik, accession_number))
        parser = FilingIndexParser()
        parser.feed(index_text)
        candidates = _ordered_candidate_urls(cik, accession_number, parser.documents)
        if candidates:
            return candidates
    except Exception as exc:
        html_error = str(exc).splitlines()[0][:120]
        reason = "; ".join(item for item in [json_error, html_error] if item)
        raise SecEdgar13FFetchError(f"No 13F information table candidates found: {reason or 'Archives indexes unavailable'}") from exc
    raise SecEdgar13FFetchError(f"No 13F information table candidates found: {json_error or 'Archives index had no XML candidates'}")


def fetch_13f_information_table_xml(url: str) -> str:
    return _get_text(url)


def _holding_row_has_required_evidence(row: ET.Element) -> bool:
    issuer_name = _text(row, ["nameOfIssuer"]) or _text(row, ["issuer_name"])
    cusip = _text(row, ["cusip"]) or _text(row, ["CUSIP"])
    value = _text(row, ["value"]) or _text(row, ["value_usd_thousands_raw"])
    shares = _text(row, ["shrsOrPrnAmt", "sshPrnamt"]) or _text(row, ["shares_or_principal_amount"])
    return bool((issuer_name or cusip) and value and shares)


def contains_13f_holdings_rows(xml_text: str) -> bool:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SecEdgar13FFetchError("Malformed 13F information table XML") from exc
    for element in root.iter():
        if _local_name(element.tag).lower() in {"infotable", "informationtable"} and _holding_row_has_required_evidence(element):
            return True
    return False


def fetch_first_valid_13f_information_table_xml(cik: str, accession_number: str) -> tuple[str, str]:
    candidates = discover_13f_information_table_documents(cik, accession_number)
    failures: list[str] = []
    for url in candidates:
        try:
            xml_text = fetch_13f_information_table_xml(url)
        except Exception as exc:
            failures.append(f"{url.rsplit('/', 1)[-1]}: {str(exc).splitlines()[0][:80]}")
            continue
        try:
            if contains_13f_holdings_rows(xml_text):
                return xml_text, url
            failures.append(f"{url.rsplit('/', 1)[-1]}: cover page XML")
        except SecEdgar13FFetchError as exc:
            failures.append(f"{url.rsplit('/', 1)[-1]}: {str(exc)}")
    raise SecEdgar13FFetchError(f"No valid 13F information table XML found after trying candidates: {'; '.join(failures)}")


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
        if not _holding_row_has_required_evidence(info_table):
            continue
        issuer_name = _text(info_table, ["nameOfIssuer"])
        cusip = _text(info_table, ["cusip"])
        raw_value = _as_float(_text(info_table, ["value"]))
        shares = _as_float(_text(info_table, ["shrsOrPrnAmt", "sshPrnamt"]))
        value_fields = normalize_13f_value(raw_value, shares=shares)
        row = {
            "manager_cik": _cik10(manager_cik),
            "accession_number": accession_number,
            "filing_date": filing_date,
            "report_date": report_date,
            "issuer_name": issuer_name,
            "title_of_class": _text(info_table, ["titleOfClass"]),
            "cusip": cusip,
            **value_fields,
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
        rows.append(enrich_13f_holding_with_local_context(row))
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
        try:
            xml_text, url = fetch_first_valid_13f_information_table_xml(manager_cik, filing["accession_number"])
            rows = parse_13f_information_table_xml(
                xml_text,
                manager_cik,
                filing["accession_number"],
                filing.get("filing_date", ""),
                filing.get("report_date", ""),
            )
        except SecEdgar13FFetchError as exc:
            missing_data.append(f"parseable 13F information table XML for {filing['accession_number']}: {str(exc)}")
            continue
        for row in rows:
            row["source_status"] = build_source_status(
                {**row["source_status"], "fetched_at": fetched_at},
                freshness_window=THIRTEEN_F_FRESHNESS_WINDOW,
            ).model_dump(mode="json")
        holdings.extend(rows)
        metadata.append({**filing, "information_table_document": url.rsplit("/", 1)[-1], "information_table_url": url})
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
