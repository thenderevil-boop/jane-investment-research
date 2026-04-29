from __future__ import annotations

from typing import Any

from backend.app import config
from backend.app.data.security_map import (
    find_security_by_issuer_name,
    get_security_by_ticker,
    normalize_cusip,
    normalize_issuer_name,
    normalize_ticker,
)

ISSUER_MATCH_LIMITATION = "Issuer-name matching is low confidence unless CUSIP or local ticker mapping confirms the security."
ISSUER_ONLY_LIMITATION = "Issuer-name-only 13F match is low confidence without CUSIP confirmation."
TARGET_CONFIG_MISSING = "SEC 13F target map is not configured."


def _csv(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _name(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def normalize_target_security_map(config_or_fixture: dict[str, Any] | None = None) -> dict[str, Any]:
    source = config_or_fixture or {}
    cusips = _csv(source.get("cusips") or source.get("SEC_13F_TARGET_CUSIPS") or getattr(config, "SEC_13F_TARGET_CUSIPS", ""))
    tickers = _csv(source.get("tickers") or source.get("SEC_13F_TARGET_TICKERS") or getattr(config, "SEC_13F_TARGET_TICKERS", ""))
    issuers = _csv(source.get("issuers") or source.get("SEC_13F_TARGET_ISSUERS") or getattr(config, "SEC_13F_TARGET_ISSUERS", ""))
    if source.get("cusip"):
        cusips.append(str(source["cusip"]))
    if source.get("ticker"):
        tickers.append(str(source["ticker"]))
    if source.get("issuer_name"):
        issuers.append(str(source["issuer_name"]))

    targets: list[dict[str, Any]] = []
    for cusip in sorted({normalize_cusip(item) for item in cusips if normalize_cusip(item)}):
        targets.append({"target_type": "cusip", "target_value": cusip, "cusip": cusip, "match_confidence": "high"})
    for ticker in sorted({normalize_ticker(item) for item in tickers if normalize_ticker(item)}):
        security = get_security_by_ticker(ticker)
        targets.append(
            {
                "target_type": "ticker",
                "target_value": ticker,
                "ticker": ticker,
                "cusip": security.get("cusip") if security else "",
                "resolved_ticker": security.get("ticker") if security else ticker,
                "resolved_cusip": security.get("cusip") if security else "",
                "resolved_issuer_name": security.get("issuer_name") if security else "",
                "match_confidence": "high" if security else "low",
                "mapping_source": security.get("confidence_source") if security else "unmapped_local_static_map",
                "local_security_map_used": security is not None,
                "limitations": ["Local security mapping is bounded and not authoritative."] if security else ["Ticker target has no local CUSIP mapping in Phase 11.4."],
            }
        )
    for issuer in sorted({item.strip() for item in issuers if item.strip()}):
        security = find_security_by_issuer_name(issuer)
        targets.append(
            {
                "target_type": "issuer_name",
                "target_value": normalize_issuer_name(issuer),
                "issuer_name": issuer,
                "cusip": security.get("cusip") if security else "",
                "resolved_ticker": security.get("ticker") if security else "",
                "resolved_cusip": security.get("cusip") if security else "",
                "resolved_issuer_name": security.get("issuer_name") if security else "",
                "match_confidence": "medium" if security else "low",
                "local_security_map_used": security is not None,
                "limitations": ["Local security mapping is bounded and not authoritative."] if security else [ISSUER_MATCH_LIMITATION],
            }
        )
    return {
        "targets": targets,
        "missing_data": [] if targets else [TARGET_CONFIG_MISSING],
    }


def match_13f_targets(aggregated_holdings: dict[str, Any] | list[dict[str, Any]], targets: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    holdings = aggregated_holdings.get("grouped_holdings", []) if isinstance(aggregated_holdings, dict) else list(aggregated_holdings or [])
    target_items = targets.get("targets", []) if isinstance(targets, dict) else list(targets or [])
    if not target_items:
        return {"target_matches": [], "missing_data": [TARGET_CONFIG_MISSING], "limitations": []}

    matches: list[dict[str, Any]] = []
    for target in target_items:
        target_type = str(target.get("target_type") or "")
        candidate = None
        confidence = str(target.get("match_confidence") or "low")
        limitations = list(target.get("limitations", []) or [])
        match_method = "none"
        resolved_ticker = str(target.get("resolved_ticker") or target.get("ticker") or "")
        resolved_cusip = normalize_cusip(target.get("resolved_cusip") or target.get("cusip") or "")
        resolved_issuer_name = str(target.get("resolved_issuer_name") or "")
        local_map_used = bool(target.get("local_security_map_used"))
        if target_type == "cusip":
            target_cusip = _upper(target.get("cusip") or target.get("target_value"))
            candidate = next((item for item in holdings if _upper(item.get("cusip")) == target_cusip), None)
            confidence = "high"
            match_method = "cusip_exact" if candidate else "none"
            resolved_cusip = target_cusip
        elif target_type == "ticker":
            target_cusip = resolved_cusip
            candidate = next((item for item in holdings if target_cusip and _upper(item.get("cusip")) == target_cusip), None)
            confidence = "high" if candidate and target_cusip else "low"
            match_method = "ticker_to_local_cusip" if candidate and target_cusip else "none"
        elif target_type == "issuer_name":
            if resolved_cusip:
                candidate = next((item for item in holdings if _upper(item.get("cusip")) == resolved_cusip), None)
                confidence = "medium" if candidate else "low"
                match_method = "issuer_alias_to_local_cusip" if candidate else "none"
            if candidate is None:
                target_name = _name(target.get("issuer_name") or target.get("target_value"))
                candidate = next((item for item in holdings if target_name and target_name == _name(item.get("issuer_name"))), None)
                if candidate:
                    confidence = "low"
                    match_method = "issuer_name_string_match"
                    if ISSUER_ONLY_LIMITATION not in limitations:
                        limitations.append(ISSUER_ONLY_LIMITATION)
                elif ISSUER_MATCH_LIMITATION not in limitations:
                    limitations.append(ISSUER_MATCH_LIMITATION)
        matched = candidate is not None
        matches.append(
            {
                "target_type": target_type,
                "target_value": target.get("target_value"),
                "matched": matched,
                "match_confidence": confidence if matched else "low",
                "match_method": match_method if matched else "none",
                "matched_cusip": candidate.get("cusip") if candidate else "",
                "matched_issuer_name": candidate.get("issuer_name") if candidate else "",
                "resolved_ticker": resolved_ticker,
                "resolved_cusip": resolved_cusip,
                "resolved_issuer_name": resolved_issuer_name,
                "local_security_map_used": local_map_used,
                "total_value_usd": candidate.get("total_value_usd") if candidate else None,
                "total_shares_or_principal_amount": candidate.get("total_shares_or_principal_amount") if candidate else None,
                "portfolio_weight_pct": candidate.get("portfolio_weight_pct") if candidate else None,
                "report_date": candidate.get("report_date") if candidate else "",
                "filing_date": candidate.get("latest_filing_date") if candidate else "",
                "source_status": candidate.get("source_status") if candidate else {},
                "limitations": limitations,
            }
        )
    return {"target_matches": matches, "missing_data": [], "limitations": sorted({limitation for item in matches for limitation in item.get("limitations", [])})}
