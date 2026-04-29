from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from backend.app import config
from backend.app.utils.freshness import FORM4_FRESHNESS_WINDOW, build_source_status

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dash}/{document}"
SEC_ARCHIVES_DIRECTORY_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dash}/"
PROVIDER = "SEC EDGAR"
LIMITATION = "Form 4 transaction codes require context; only code P is counted as accumulation and only code S is counted as disposition."
PAGINATION_LIMITATION = "SEC submissions recent filings pagination is not followed in this MVP unless already present in the recent filings payload."

_TICKER_CIK_CACHE: dict[str, str] | None = None


class SecEdgarForm4FetchError(RuntimeError):
    """Raised when official SEC EDGAR Form 4 data cannot be fetched or normalized."""


def _headers() -> dict[str, str]:
    if not config.SEC_EDGAR_USER_AGENT:
        raise SecEdgarForm4FetchError("SEC_EDGAR_USER_AGENT missing")
    return {"User-Agent": config.SEC_EDGAR_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _request_delay() -> None:
    time.sleep(max(0.0, config.SEC_EDGAR_REQUEST_DELAY_SECONDS))


def _get_json(url: str) -> dict[str, Any]:
    _request_delay()
    response = httpx.get(url, headers=_headers(), timeout=20)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise SecEdgarForm4FetchError("SEC response was not a JSON object")
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
    return text.zfill(10)


def _accession_no_dash(accession_number: str) -> str:
    return accession_number.replace("-", "").strip()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element | None, name: str) -> list[ET.Element]:
    if element is None:
        return []
    return [child for child in list(element) if _local_name(child.tag) == name]


def _child(element: ET.Element | None, name: str) -> ET.Element | None:
    matches = _children(element, name)
    return matches[0] if matches else None


def _text(element: ET.Element | None, path: list[str]) -> str:
    current = element
    for part in path:
        current = _child(current, part)
        if current is None:
            return ""
    return (current.text or "").strip()


def _first_text(element: ET.Element | None, paths: list[list[str]]) -> str:
    for path in paths:
        value = _text(element, path)
        if value:
            return value
    return ""


def _as_float(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return 0.0


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def _ownership_type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized == "D":
        return "direct"
    if normalized == "I":
        return "indirect"
    return "unknown"


def classify_transaction_code(code: str) -> tuple[str, list[str]]:
    normalized = code.strip().upper()
    if normalized == "P":
        return "accumulation", []
    if normalized == "S":
        return "disposition", []
    if normalized == "M":
        return "option_exercise", ["Code M is option exercise activity and is not counted as accumulation by default."]
    if normalized == "A":
        return "award", ["Code A is grant or award activity and is not counted as accumulation by default."]
    if normalized == "F":
        return "tax_withholding", ["Code F is tax withholding activity and is not counted as accumulation by default."]
    if normalized == "G":
        return "gift", ["Code G is gift activity and is not counted as accumulation or disposition by default."]
    if normalized == "D":
        return "disposition_to_issuer_or_other", ["Code D is not treated as normal open-market disposition by default."]
    if normalized == "J":
        return "other", ["Code J is not counted as accumulation or disposition by default."]
    if normalized:
        return "other", [f"Unknown Form 4 transaction code {normalized}; classified as other."]
    return "other", ["Missing Form 4 transaction code; classified as other."]


def dedupe_transactions(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for item in transactions:
        key = (
            str(item.get("ticker") or "").upper(),
            _cik10(item.get("cik")),
            str(item.get("accession_number") or ""),
            str(item.get("insider_name") or "").casefold(),
            str(item.get("transaction_date") or ""),
            str(item.get("transaction_code") or "").upper(),
            str(item.get("security_title") or "").casefold(),
            item.get("shares"),
            item.get("price"),
            str(item.get("ownership_type") or "").casefold(),
            str(item.get("acquired_disposed_code") or "").upper(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def fetch_company_tickers() -> dict[str, str]:
    global _TICKER_CIK_CACHE
    if _TICKER_CIK_CACHE is not None:
        return dict(_TICKER_CIK_CACHE)
    payload = _get_json(SEC_COMPANY_TICKERS_URL)
    mapping: dict[str, str] = {}
    for item in payload.values():
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip().upper()
        cik = _cik10(item.get("cik_str"))
        if ticker and cik:
            mapping[ticker] = cik
    _TICKER_CIK_CACHE = mapping
    return dict(mapping)


def get_cik_for_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not normalized:
        raise SecEdgarForm4FetchError("Ticker is required")
    cik = fetch_company_tickers().get(normalized)
    if not cik:
        raise SecEdgarForm4FetchError(f"No SEC CIK mapping found for {normalized}")
    return cik


def fetch_company_submissions(cik: str) -> dict[str, Any]:
    cik10 = _cik10(cik)
    if not cik10:
        raise SecEdgarForm4FetchError("CIK is required")
    return _get_json(SEC_SUBMISSIONS_URL.format(cik=cik10))


def find_recent_form4_filings(submissions: dict[str, Any], lookback_days: int = 180) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {}) if isinstance(submissions, dict) else {}
    forms = recent.get("form", []) or []
    accession_numbers = recent.get("accessionNumber", []) or []
    filing_dates = recent.get("filingDate", []) or []
    report_dates = recent.get("reportDate", []) or []
    primary_documents = recent.get("primaryDocument", []) or []
    cutoff = date.today() - timedelta(days=lookback_days)
    filings: list[dict[str, Any]] = []
    for index, form in enumerate(forms):
        if str(form).upper() != "4":
            continue
        filing_date = str(filing_dates[index] if index < len(filing_dates) else "")
        try:
            parsed_date = date.fromisoformat(filing_date)
        except ValueError:
            parsed_date = date.today()
        if parsed_date < cutoff:
            continue
        filings.append(
            {
                "accession_number": str(accession_numbers[index] if index < len(accession_numbers) else ""),
                "accessionNumber": str(accession_numbers[index] if index < len(accession_numbers) else ""),
                "filing_date": filing_date,
                "filingDate": filing_date,
                "report_date": str(report_dates[index] if index < len(report_dates) else ""),
                "reportDate": str(report_dates[index] if index < len(report_dates) else ""),
                "primary_document": str(primary_documents[index] if index < len(primary_documents) else ""),
                "primaryDocument": str(primary_documents[index] if index < len(primary_documents) else ""),
            }
        )
    return filings


def build_edgar_archive_url(cik: str, accession_number: str, primary_document: str) -> str:
    cik_int = str(int(_cik10(cik)))
    return SEC_ARCHIVES_URL.format(
        cik_int=cik_int,
        accession_no_dash=_accession_no_dash(accession_number),
        document=primary_document,
    )


def build_archives_directory_url(cik: str, accession_number: str) -> str:
    cik_int = str(int(_cik10(cik)))
    return SEC_ARCHIVES_DIRECTORY_URL.format(cik_int=cik_int, accession_no_dash=_accession_no_dash(accession_number))


def build_archives_index_json_url(cik: str, accession_number: str) -> str:
    return f"{build_archives_directory_url(cik, accession_number)}index.json"


def _looks_like_html(text: str) -> bool:
    sample = text[:500].lower()
    return "<html" in sample or "<!doctype html" in sample or "<table" in sample


def _is_form4_xml(text: str) -> bool:
    if _looks_like_html(text):
        return False
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return False
    return _local_name(root.tag) == "ownershipDocument"


def _discover_form4_xml_documents(cik: str, accession_number: str) -> list[str]:
    try:
        payload = _get_json(build_archives_index_json_url(cik, accession_number))
    except Exception:
        return []
    items = payload.get("directory", {}).get("item") or []
    candidates: list[str] = []
    directory_url = build_archives_directory_url(cik, accession_number)
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        lower = name.lower()
        if not lower.endswith(".xml") or lower.endswith(".xsl"):
            continue
        if lower in {"primary_doc.xml"}:
            continue
        candidates.append(f"{directory_url}{name}")
    return candidates[:5]


def fetch_form4_xml(cik: str, accession_number: str, primary_document: str) -> str:
    if not primary_document:
        raise SecEdgarForm4FetchError("Form 4 primary document is missing")
    failures: list[str] = []
    primary_url = build_edgar_archive_url(cik, accession_number, primary_document)
    try:
        text = _get_text(primary_url)
        if _is_form4_xml(text):
            return text
        failures.append(f"{primary_document}: not Form 4 XML")
    except Exception as exc:
        failures.append(f"{primary_document}: {str(exc).splitlines()[0][:80]}")
    for url in _discover_form4_xml_documents(cik, accession_number):
        document = url.rsplit("/", 1)[-1]
        try:
            text = _get_text(url)
            if _is_form4_xml(text):
                return text
            failures.append(f"{document}: not Form 4 XML")
        except Exception as exc:
            failures.append(f"{document}: {str(exc).splitlines()[0][:80]}")
    raise SecEdgarForm4FetchError(f"No valid Form 4 XML document found: {'; '.join(failures)}")


def parse_form4_xml(xml_text: str, ticker: str, cik: str, accession_number: str, filing_date: str) -> list[dict[str, Any]]:
    if not _is_form4_xml(xml_text):
        raise SecEdgarForm4FetchError("Fetched document is not a valid Form 4 ownershipDocument XML")
    root = ET.fromstring(xml_text)
    issuer = _child(root, "issuer")
    owner = _child(root, "reportingOwner")
    owner_id = _child(owner, "reportingOwnerId")
    relationship = _child(owner, "reportingOwnerRelationship")
    insider_name = _text(owner_id, ["rptOwnerName"])
    is_director = _as_bool(_text(relationship, ["isDirector"]))
    is_officer = _as_bool(_text(relationship, ["isOfficer"]))
    ten_percent_owner = _as_bool(_text(relationship, ["isTenPercentOwner"]))
    other_relationship = _text(relationship, ["otherText"])
    officer_title = _text(relationship, ["officerTitle"])
    role_parts: list[str] = []
    if is_director:
        role_parts.append("Director")
    if is_officer:
        role_parts.append(officer_title or "Officer")
    if ten_percent_owner:
        role_parts.append("10% Owner")
    if other_relationship:
        role_parts.append(other_relationship)
    role = ", ".join(role_parts) or officer_title or "unknown"
    issuer_name = _text(issuer, ["issuerName"])
    issuer_trading_symbol = _text(issuer, ["issuerTradingSymbol"])
    normalized_ticker = ticker.strip().upper() or issuer_trading_symbol.strip().upper()
    normalized_cik = _cik10(cik or _text(issuer, ["issuerCik"]))
    fetched_source_date = filing_date or _text(root, ["periodOfReport"])
    transactions: list[dict[str, Any]] = []
    table_specs = [
        ("nonDerivativeTable", "nonDerivativeTransaction"),
        ("derivativeTable", "derivativeTransaction"),
    ]
    for table_name, row_name in table_specs:
        for transaction in _children(_child(root, table_name), row_name):
            code = _text(transaction, ["transactionCoding", "transactionCode"])
            category, code_limitations = classify_transaction_code(code)
            shares_text = _text(transaction, ["transactionAmounts", "transactionShares", "value"])
            price_text = _text(transaction, ["transactionAmounts", "transactionPricePerShare", "value"])
            shares = _as_float(shares_text)
            price = _as_float(price_text)
            value = _as_float(
                _first_text(
                    transaction,
                    [
                        ["transactionAmounts", "transactionTotalValue", "value"],
                        ["transactionAmounts", "totalTransactionValue", "value"],
                        ["transactionTotalValue", "value"],
                    ],
                )
            )
            if not value and shares and price:
                value = round(shares * price, 2)
            ownership_code = _text(transaction, ["ownershipNature", "directOrIndirectOwnership", "value"])
            acquired_disposed_code = _text(transaction, ["transactionAmounts", "transactionAcquiredDisposedCode", "value"]).upper()
            transaction_date = _text(transaction, ["transactionDate", "value"])
            limitations = [LIMITATION, *code_limitations]
            missing_data = [
                field
                for field, field_value in {
                    "transaction_code": code,
                    "transaction_date": transaction_date,
                    "shares": shares_text,
                    "price": price_text,
                }.items()
                if not field_value
            ]
            transactions.append(
                {
                    "ticker": normalized_ticker,
                    "cik": normalized_cik,
                    "accession_number": accession_number,
                    "filing_date": filing_date,
                    "transaction_date": transaction_date,
                    "security_title": _text(transaction, ["securityTitle", "value"])
                    or _text(transaction, ["underlyingSecurity", "underlyingSecurityTitle", "value"]),
                    "insider_name": insider_name,
                    "role": role,
                    "is_director": is_director,
                    "is_officer": is_officer,
                    "officer_title": officer_title,
                    "ten_percent_owner": ten_percent_owner,
                    "other_relationship": other_relationship,
                    "issuer_name": issuer_name,
                    "issuer_trading_symbol": issuer_trading_symbol,
                    "transaction_code": code,
                    "transaction_category": category,
                    "transaction_type": category,
                    "shares": shares,
                    "price": price,
                    "value": value,
                    "acquired_disposed_code": acquired_disposed_code,
                    "ownership_type": _ownership_type(ownership_code),
                    "direct_or_indirect_ownership": ownership_code.strip().upper() or "unknown",
                    "source": [PROVIDER],
                    "source_date": fetched_source_date,
                    "source_status": {
                        "source_type": "live",
                        "provider": PROVIDER,
                        "source_date": fetched_source_date,
                        "freshness_window": FORM4_FRESHNESS_WINDOW,
                        "fallback_used": False,
                        "fallback_reason": None,
                        "limitations": limitations,
                        "missing_data": missing_data,
                    },
                    "limitations": limitations,
                    "missing_data": missing_data,
                }
            )
    return dedupe_transactions(transactions)


def fetch_insider_transactions(ticker: str, lookback_days: int = 180) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    cik = get_cik_for_ticker(normalized_ticker)
    submissions = fetch_company_submissions(cik)
    filings = find_recent_form4_filings(submissions, lookback_days=lookback_days)
    fetched_at = datetime.now(timezone.utc).isoformat()
    transactions: list[dict[str, Any]] = []
    filing_dates: list[str] = []
    limitations = [LIMITATION, PAGINATION_LIMITATION]
    for filing in filings:
        accession_number = filing.get("accession_number", "")
        filing_date = filing.get("filing_date", "")
        primary_document = filing.get("primary_document", "")
        xml_text = fetch_form4_xml(cik, accession_number, primary_document)
        filing_dates.append(filing_date)
        for transaction in parse_form4_xml(xml_text, normalized_ticker, cik, accession_number, filing_date):
            status_payload = {
                **transaction.get("source_status", {}),
                "fetched_at": fetched_at,
                "source_date": filing_date or transaction.get("source_date", ""),
            }
            transaction["source_status"] = build_source_status(
                status_payload,
                freshness_window=FORM4_FRESHNESS_WINDOW,
            ).model_dump(mode="json")
            transactions.append(transaction)
    transactions = dedupe_transactions(transactions)
    source_date = max(filing_dates, default="")
    payload = {
        "ticker": normalized_ticker,
        "cik": cik,
        "lookback_days": lookback_days,
        "transactions": transactions,
        "source_type": "live",
        "provider": PROVIDER,
        "source": [PROVIDER],
        "source_date": source_date,
        "fetched_at": fetched_at,
        "limitations": limitations,
        "missing_data": [] if filings else ["recent SEC Form 4 filings"],
    }
    payload["source_status"] = build_source_status(payload, freshness_window=FORM4_FRESHNESS_WINDOW).model_dump(mode="json")
    return payload
