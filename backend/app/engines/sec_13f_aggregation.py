from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from backend.app import config
from backend.app.data.security_map import resolve_security_identifier
from backend.app.utils.freshness import THIRTEEN_F_FRESHNESS_WINDOW, build_source_status

THIRTEEN_F_LIMITATIONS = [
    "13F is delayed quarterly evidence and should not be interpreted as real-time institutional flow.",
    "13F may lag up to 45 days after quarter end.",
    "13F may not show shorts, many derivatives, or current positions.",
    "Same issuer names may appear under multiple CUSIPs or classes and are not merged unless the security key matches.",
]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _upper(value: Any) -> str:
    return _text(value).upper()


def _normalized_name(value: Any) -> str:
    return " ".join(_text(value).casefold().split())


def _num(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _date_like(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return ""


def _security_key(row: dict[str, Any]) -> tuple[str, str]:
    cusip = _upper(row.get("cusip"))
    if cusip:
        return ("cusip", cusip)
    issuer_name = _normalized_name(row.get("issuer_name"))
    title_of_class = _normalized_name(row.get("title_of_class"))
    return ("issuer_class", f"{issuer_name}|{title_of_class}")


def _dedupe_holdings(holdings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for row in holdings:
        key = (
            _upper(row.get("manager_cik")),
            _text(row.get("accession_number")),
            _upper(row.get("cusip")),
            _normalized_name(row.get("issuer_name")),
            _normalized_name(row.get("title_of_class")),
            _text(row.get("report_date")),
            _text(row.get("filing_date")),
            row.get("value_usd"),
            row.get("reported_value_raw"),
            row.get("shares_or_principal_amount"),
            _text(row.get("investment_discretion")),
            _text(row.get("other_manager")),
            row.get("voting_authority_sole"),
            row.get("voting_authority_shared"),
            row.get("voting_authority_none"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _confidence_summary(values: list[str]) -> str:
    normalized = {_text(value).lower() for value in values if _text(value)}
    if "low" in normalized or not normalized:
        return "low"
    if "medium" in normalized:
        return "medium"
    return "high"


def _source_status_for_rows(rows: list[dict[str, Any]], *, provider: str) -> dict[str, Any]:
    statuses = [row.get("source_status") for row in rows if isinstance(row.get("source_status"), dict)]
    source_dates = [_date_like(status.get("source_date")) for status in statuses if _date_like(status.get("source_date"))]
    row_dates = [
        _date_like(row.get("report_date")) or _date_like(row.get("filing_date"))
        for row in rows
        if _date_like(row.get("report_date")) or _date_like(row.get("filing_date"))
    ]
    fetched_dates = [status.get("fetched_at") for status in statuses if status.get("fetched_at")]
    fallback_used = any(status.get("fallback_used") or status.get("source_type") == "fallback" for status in statuses)
    limitations = sorted({item for status in statuses for item in status.get("limitations", []) or []})
    missing_data = sorted({item for status in statuses for item in status.get("missing_data", []) or []})
    return build_source_status(
        {
            "source_type": "derived",
            "provider": provider,
            "source_date": max(source_dates, default=max(row_dates, default="")),
            "fetched_at": max(fetched_dates, default=None),
            "fallback_used": fallback_used,
            "limitations": [*THIRTEEN_F_LIMITATIONS, *limitations],
            "missing_data": missing_data,
        },
        freshness_window=THIRTEEN_F_FRESHNESS_WINDOW,
    ).model_dump(mode="json")


def aggregate_13f_holdings(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _dedupe_holdings(list(holdings or []))
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_security_key(row), []).append(row)

    grouped_holdings: list[dict[str, Any]] = []
    for key, group_rows in grouped.items():
        sorted_rows = sorted(group_rows, key=lambda item: (_text(item.get("report_date")), _text(item.get("filing_date"))), reverse=True)
        first = sorted_rows[0]
        resolved_rows = [
            {
                "ticker": row.get("mapped_ticker") or (resolve_security_identifier(cusip=row.get("cusip"), issuer_name=row.get("issuer_name")).get("security") or {}).get("ticker", ""),
                "cusip": row.get("resolved_cusip") or (resolve_security_identifier(cusip=row.get("cusip"), issuer_name=row.get("issuer_name")).get("security") or {}).get("cusip", ""),
                "security_map_used": bool(row.get("security_map_used")) or bool(resolve_security_identifier(cusip=row.get("cusip"), issuer_name=row.get("issuer_name")).get("security")),
            }
            for row in group_rows
        ]
        mapped_tickers = {item["ticker"] for item in resolved_rows if item["ticker"]}
        resolved_cusips = {item["cusip"] for item in resolved_rows if item["cusip"]}
        price_reference_rows = [row for row in group_rows if row.get("price_reference_used")]
        price_reference_tickers = {
            _upper((row.get("price_reference") or {}).get("ticker") or row.get("mapped_ticker"))
            for row in price_reference_rows
            if _upper((row.get("price_reference") or {}).get("ticker") or row.get("mapped_ticker"))
        }
        value_notes = sorted({_text(row.get("value_normalization_note")) for row in group_rows if _text(row.get("value_normalization_note"))})
        source_values = sorted({source for row in group_rows for source in row.get("source", []) or []}) or ["SEC EDGAR"]
        provider = "derived_from_SEC_EDGAR_13F" if any("SEC EDGAR" in source for source in source_values) else "derived_from_mock_13f"
        grouped_holdings.append(
            {
                "security_key_type": key[0],
                "security_key": key[1],
                "cusip": _upper(first.get("cusip")),
                "issuer_name": first.get("issuer_name"),
                "title_of_class": first.get("title_of_class"),
                "mapped_ticker": next(iter(mapped_tickers)) if len(mapped_tickers) == 1 else "",
                "resolved_cusip": next(iter(resolved_cusips)) if len(resolved_cusips) == 1 else _upper(first.get("cusip")),
                "security_map_used": any(item["security_map_used"] for item in resolved_rows),
                "report_date": max((_text(row.get("report_date")) for row in group_rows), default=""),
                "latest_filing_date": max((_text(row.get("filing_date")) for row in group_rows), default=""),
                "manager_cik": first.get("manager_cik"),
                "manager_count_observed": len({_upper(row.get("manager_cik")) for row in group_rows if _upper(row.get("manager_cik"))}),
                "row_count": len(group_rows),
                "total_value_usd": sum(_num(row.get("value_usd") if row.get("value_usd") is not None else row.get("reported_value_raw")) for row in group_rows),
                "total_shares_or_principal_amount": sum(_num(row.get("shares_or_principal_amount")) for row in group_rows),
                "value_unit_confidence_summary": _confidence_summary([_text(row.get("value_unit_confidence")) for row in group_rows]),
                "value_normalization_notes": value_notes,
                "price_reference_used_count": 1 if price_reference_rows else 0,
                "price_reference_grouped_holding_count": 1 if price_reference_rows else 0,
                "price_reference_row_count": len(price_reference_rows),
                "price_reference_ticker_count": len(price_reference_tickers),
                "price_reference_cache_hit_count": sum(1 for row in price_reference_rows if "cache" in _text((row.get("price_reference") or {}).get("provider")).casefold()),
                "price_reference_live_fetch_count": sum(1 for row in price_reference_rows if "cache" not in _text((row.get("price_reference") or {}).get("provider")).casefold()),
                "investment_discretion_values": sorted({_text(row.get("investment_discretion")) for row in group_rows if _text(row.get("investment_discretion"))}),
                "other_manager_values": sorted({_text(row.get("other_manager")) for row in group_rows if _text(row.get("other_manager"))}),
                "voting_authority_sole": sum(_num(row.get("voting_authority_sole")) for row in group_rows),
                "voting_authority_shared": sum(_num(row.get("voting_authority_shared")) for row in group_rows),
                "voting_authority_none": sum(_num(row.get("voting_authority_none")) for row in group_rows),
                "source": source_values,
                "source_status": _source_status_for_rows(group_rows, provider=provider),
                "rows": deepcopy(group_rows),
            }
        )
    grouped_holdings.sort(key=lambda item: item.get("total_value_usd") or 0, reverse=True)
    return {
        "grouped_holdings": grouped_holdings,
        "holding_count_raw": len(rows),
        "holding_count_grouped": len(grouped_holdings),
        "limitations": THIRTEEN_F_LIMITATIONS,
        "missing_data": [] if grouped_holdings else ["13f_holdings"],
    }


def summarize_13f_portfolio(holdings: list[dict[str, Any]], top_holdings_limit: int = 10) -> dict[str, Any]:
    rows = list(holdings or [])
    latest_report_date = max((_date_like(row.get("report_date")) for row in rows if _date_like(row.get("report_date"))), default="")
    latest_rows = [row for row in rows if not latest_report_date or _text(row.get("report_date")) == latest_report_date]
    if latest_report_date:
        latest_rows = [row for row in rows if _date_like(row.get("report_date")) == latest_report_date]
    elif rows:
        latest_filing_period = max((_date_like(row.get("filing_date")) for row in rows if _date_like(row.get("filing_date"))), default="")
        latest_rows = [row for row in rows if _date_like(row.get("filing_date")) == latest_filing_period] if latest_filing_period else rows
    aggregate = aggregate_13f_holdings(latest_rows)
    grouped_holdings = aggregate["grouped_holdings"]
    total_value = sum(item.get("total_value_usd") or 0 for item in grouped_holdings)
    latest_filing_date = max((_text(row.get("filing_date")) for row in latest_rows if _text(row.get("filing_date"))), default="")
    confidence_values = [_text(item.get("value_unit_confidence_summary")) for item in grouped_holdings]
    confidence_breakdown = {
        "high": confidence_values.count("high"),
        "medium": confidence_values.count("medium"),
        "low": confidence_values.count("low"),
    }
    mapped_holding_count = sum(1 for item in grouped_holdings if item.get("security_map_used"))
    price_reference_grouped_holding_count = sum(int(item.get("price_reference_grouped_holding_count") or item.get("price_reference_used_count") or 0) for item in grouped_holdings)
    price_reference_row_count = sum(int(item.get("price_reference_row_count") or 0) for item in grouped_holdings)
    price_reference_tickers = {
        _upper(item.get("mapped_ticker"))
        for item in grouped_holdings
        if item.get("price_reference_grouped_holding_count") and _upper(item.get("mapped_ticker"))
    }
    price_reference_ticker_count = len(price_reference_tickers)
    price_reference_cache_hit_count = sum(int(item.get("price_reference_cache_hit_count") or 0) for item in grouped_holdings)
    price_reference_live_fetch_count = sum(int(item.get("price_reference_live_fetch_count") or 0) for item in grouped_holdings)
    mapped_tickers = sorted({_upper(item.get("mapped_ticker")) for item in grouped_holdings if item.get("security_map_used") and _upper(item.get("mapped_ticker"))})
    price_reference_unavailable_tickers = sorted(set(mapped_tickers) - set(price_reference_tickers))
    if config.ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST:
        price_reference_mode = "live_allowed"
    elif config.PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT:
        price_reference_mode = "cache_with_bounded_warmup"
    else:
        price_reference_mode = "cache_only"
    missing_data = list(aggregate.get("missing_data", []))
    if mapped_holding_count and price_reference_grouped_holding_count == 0:
        missing_data.append("price reference unavailable for mapped 13F holdings")
    top_holdings: list[dict[str, Any]] = []
    for item in grouped_holdings:
        value = item.get("total_value_usd") or 0
        item["portfolio_weight_pct"] = round(value / total_value * 100, 4) if total_value else None
    for item in grouped_holdings[:top_holdings_limit]:
        value = item.get("total_value_usd") or 0
        top_holdings.append(
            {
                "issuer_name": item.get("issuer_name"),
                "cusip": item.get("cusip"),
                "title_of_class": item.get("title_of_class"),
                "mapped_ticker": item.get("mapped_ticker"),
                "resolved_cusip": item.get("resolved_cusip"),
                "security_map_used": item.get("security_map_used"),
                "price_reference_used_count": item.get("price_reference_used_count"),
                "price_reference_grouped_holding_count": item.get("price_reference_grouped_holding_count"),
                "price_reference_ticker_count": item.get("price_reference_ticker_count"),
                "price_reference_row_count": item.get("price_reference_row_count"),
                "price_reference_cache_hit_count": item.get("price_reference_cache_hit_count"),
                "price_reference_live_fetch_count": item.get("price_reference_live_fetch_count"),
                "total_value_usd": value,
                "total_shares_or_principal_amount": item.get("total_shares_or_principal_amount"),
                "portfolio_weight_pct": round(value / total_value * 100, 4) if total_value else None,
                "value_unit_confidence_summary": item.get("value_unit_confidence_summary"),
                "report_date": item.get("report_date"),
                "source_status": item.get("source_status"),
            }
        )
    source_status = _source_status_for_rows(latest_rows, provider="derived_from_SEC_EDGAR_13F") if latest_rows else build_source_status(
        {
            "source_type": "derived",
            "provider": "derived_from_SEC_EDGAR_13F",
            "source_date": "",
            "limitations": THIRTEEN_F_LIMITATIONS,
            "missing_data": ["13f_holdings", "source_date"],
        },
        freshness_window=THIRTEEN_F_FRESHNESS_WINDOW,
    ).model_dump(mode="json")
    return {
        "manager_cik": next((_upper(row.get("manager_cik")) for row in latest_rows if _upper(row.get("manager_cik"))), ""),
        "latest_report_date": latest_report_date,
        "latest_filing_date": latest_filing_date,
        "holding_count_raw": len(_dedupe_holdings(latest_rows)),
        "holding_count_grouped": len(grouped_holdings),
        "total_reported_value_usd": total_value,
        "top_holdings_by_value": top_holdings,
        "top_holdings_limit": top_holdings_limit,
        "value_confidence_breakdown": confidence_breakdown,
        "mapped_holding_count": mapped_holding_count,
        "unmapped_holding_count": len(grouped_holdings) - mapped_holding_count,
        "price_reference_used_count": price_reference_grouped_holding_count,
        "price_reference_grouped_holding_count": price_reference_grouped_holding_count,
        "price_reference_ticker_count": price_reference_ticker_count,
        "price_reference_row_count": price_reference_row_count,
        "price_reference_cache_hit_count": price_reference_cache_hit_count,
        "price_reference_live_fetch_count": price_reference_live_fetch_count,
        "price_reference_unavailable_tickers": price_reference_unavailable_tickers,
        "price_reference_mode": price_reference_mode,
        "source_status": source_status,
        "limitations": THIRTEEN_F_LIMITATIONS,
        "missing_data": sorted(set(missing_data)),
        "grouped_holdings": grouped_holdings,
    }


def compare_13f_quarter_over_quarter(current_grouped: list[dict[str, Any]], prior_grouped: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current_by_cusip = {_upper(item.get("cusip")): item for item in current_grouped if _upper(item.get("cusip"))}
    prior_by_cusip = {_upper(item.get("cusip")): item for item in prior_grouped if _upper(item.get("cusip"))}
    changes: list[dict[str, Any]] = []
    for cusip in sorted(set(current_by_cusip) | set(prior_by_cusip)):
        current = current_by_cusip.get(cusip)
        prior = prior_by_cusip.get(cusip)
        current_value = _num(current.get("total_value_usd")) if current else 0.0
        prior_value = _num(prior.get("total_value_usd")) if prior else 0.0
        current_shares = _num(current.get("total_shares_or_principal_amount")) if current else 0.0
        prior_shares = _num(prior.get("total_shares_or_principal_amount")) if prior else 0.0
        value_change = current_value - prior_value
        share_change = current_shares - prior_shares
        if current and not prior:
            label = "new_13f_reported_position"
        elif prior and not current:
            label = "removed_13f_reported_position"
        elif abs(share_change) < 0.000001 and abs(value_change) < 0.000001:
            label = "institutional_position_unchanged"
        elif share_change > 0 or value_change > 0:
            label = "institutional_position_increased"
        elif share_change < 0 or value_change < 0:
            label = "institutional_position_decreased"
        else:
            label = "insufficient_prior_data"
        basis = current or prior or {}
        changes.append(
            {
                "cusip": cusip,
                "issuer_name": basis.get("issuer_name"),
                "current_report_date": current.get("report_date") if current else "",
                "prior_report_date": prior.get("report_date") if prior else "",
                "current_value_usd": current_value,
                "prior_value_usd": prior_value,
                "value_change_usd": value_change,
                "value_change_pct": round(value_change / prior_value * 100, 4) if prior_value else None,
                "current_shares": current_shares,
                "prior_shares": prior_shares,
                "share_change": share_change,
                "share_change_pct": round(share_change / prior_shares * 100, 4) if prior_shares else None,
                "change_label": label,
                "limitations": ["QoQ 13F comparison reflects reported quarterly change only and is not real-time activity."],
            }
        )
    return changes
