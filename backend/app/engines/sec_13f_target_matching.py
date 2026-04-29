from __future__ import annotations

from typing import Any

from backend.app import config
from backend.app.data.manager_map import MANAGER_MAP_LIMITATION, get_manager_metadata_by_cik
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
CANDIDATE_13F_LIMITATIONS = [
    "13F is delayed quarterly evidence and should not be interpreted as real-time institutional flow.",
    "13F may lag up to 45 days after quarter end.",
    "13F may not show shorts, many derivatives, or current positions.",
    "Local security mapping is bounded and not authoritative.",
]
NO_REPORTED_POSITION_LIMITATION = "No reported 13F position was observed for this candidate in the configured manager portfolio."
NO_REPORTED_POSITION_SUMMARY = NO_REPORTED_POSITION_LIMITATION
NOT_NEGATIVE_SIGNAL_LIMITATION = "This is not a negative trading signal; it only means the configured 13F manager did not report this security for the latest available report period."
REPORTED_POSITION_SUMMARY = "A reported 13F position was observed for this candidate in the configured manager portfolio."
DELAYED_POSITION_LIMITATION = "13F reflects a delayed quarterly report and may not represent the manager's current position."


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


def _compact_top_holding(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "issuer_name": item.get("issuer_name"),
        "cusip": item.get("cusip"),
        "mapped_ticker": item.get("mapped_ticker"),
        "total_value_usd": item.get("total_value_usd"),
        "total_shares_or_principal_amount": item.get("total_shares_or_principal_amount"),
        "portfolio_weight_pct": item.get("portfolio_weight_pct"),
        "value_unit_confidence_summary": item.get("value_unit_confidence_summary"),
        "report_date": item.get("report_date"),
    }


def build_candidate_13f_evidence(
    candidate_ticker: str,
    portfolio_summary: dict[str, Any] | None,
    target_matches: dict[str, Any] | list[dict[str, Any]] | None,
    security_map: dict[str, Any] | None = None,
    *,
    top_holdings_limit: int | None = None,
) -> dict[str, Any]:
    summary = portfolio_summary or {}
    grouped_holdings = list(summary.get("grouped_holdings") or [])
    matches = target_matches.get("target_matches", []) if isinstance(target_matches, dict) else list(target_matches or [])
    top_limit = max(0, top_holdings_limit if top_holdings_limit is not None else config.SEC_13F_CANDIDATE_CONTEXT_TOP_HOLDINGS_LIMIT)
    ticker = normalize_ticker(candidate_ticker)
    provided_security = security_map or {}
    security = provided_security if provided_security.get("ticker") else get_security_by_ticker(ticker)
    limitations = list(CANDIDATE_13F_LIMITATIONS)
    missing_data = list(summary.get("missing_data", []) or [])
    source_status = summary.get("source_status") or {}
    manager_cik = _upper(summary.get("manager_cik") or summary.get("manager") or "")
    manager_metadata = get_manager_metadata_by_cik(manager_cik)
    manager_name = str(summary.get("manager_name") or "")
    if not manager_name or manager_name == manager_cik:
        manager_name = str(manager_metadata.get("manager_name") or manager_cik)
    manager_metadata_source = str(summary.get("manager_metadata_source") or manager_metadata.get("confidence_source") or "")
    if manager_metadata_source == "local_static_map":
        limitations.append(MANAGER_MAP_LIMITATION)
    resolved_ticker = ticker
    resolved_cusip = ""
    resolved_issuer_name = ""
    local_security_map_used = False
    interpretation_label = "insufficient_identifier_mapping"
    match_confidence = "unknown"
    match_method = "unresolved_ticker"
    matched_in_13f = False
    matched_holding: dict[str, Any] | None = None

    if security:
        resolved_ticker = security.get("ticker") or ticker
        resolved_cusip = normalize_cusip(security.get("cusip") or "")
        resolved_issuer_name = str(security.get("issuer_name") or "")
        local_security_map_used = True
        match_method = "ticker_to_local_cusip"
        match_confidence = "none"
        interpretation_label = "no_reported_13f_position_observed"
        matched_holding = next((item for item in grouped_holdings if resolved_cusip and _upper(item.get("cusip")) == resolved_cusip), None)
        if matched_holding:
            matched_in_13f = True
            match_confidence = "high"
            match_method = "ticker_to_local_cusip"
            interpretation_label = "reported_13f_position_observed"
            limitations.append(DELAYED_POSITION_LIMITATION)
        else:
            limitations.append(NO_REPORTED_POSITION_LIMITATION)
            limitations.append(NOT_NEGATIVE_SIGNAL_LIMITATION)
    else:
        missing_data.append("local security mapping unavailable for candidate ticker")

    if security and not matched_holding and resolved_cusip:
        matched_target = next(
            (
                item
                for item in matches
                if item.get("matched")
                and normalize_cusip(item.get("matched_cusip") or item.get("resolved_cusip")) == resolved_cusip
                and item.get("match_confidence") in {"high", "medium"}
            ),
            None,
        )
        if matched_target:
            matched_holding = {
                "cusip": matched_target.get("matched_cusip") or resolved_cusip,
                "issuer_name": matched_target.get("matched_issuer_name") or resolved_issuer_name,
                "total_value_usd": matched_target.get("total_value_usd"),
                "total_shares_or_principal_amount": matched_target.get("total_shares_or_principal_amount"),
                "portfolio_weight_pct": matched_target.get("portfolio_weight_pct"),
                "report_date": matched_target.get("report_date"),
                "latest_filing_date": matched_target.get("filing_date"),
                "source_status": matched_target.get("source_status"),
            }
            matched_in_13f = True
            match_confidence = str(matched_target.get("match_confidence") or "medium")
            match_method = str(matched_target.get("match_method") or "cusip_exact")
            interpretation_label = "reported_13f_position_observed"
            limitations.append(DELAYED_POSITION_LIMITATION)
            if NO_REPORTED_POSITION_LIMITATION in limitations:
                limitations.remove(NO_REPORTED_POSITION_LIMITATION)
            if NOT_NEGATIVE_SIGNAL_LIMITATION in limitations:
                limitations.remove(NOT_NEGATIVE_SIGNAL_LIMITATION)

    if not matched_holding and resolved_issuer_name:
        normalized_resolved_name = normalize_issuer_name(resolved_issuer_name)
        issuer_holding = next(
            (
                item
                for item in grouped_holdings
                if normalized_resolved_name and normalize_issuer_name(item.get("issuer_name")) == normalized_resolved_name
            ),
            None,
        )
        if issuer_holding:
            matched_holding = issuer_holding
            matched_in_13f = True
            match_confidence = "low"
            match_method = "issuer_name_string_match"
            interpretation_label = "low_confidence_issuer_name_match"
            limitations.append(DELAYED_POSITION_LIMITATION)
            if ISSUER_ONLY_LIMITATION not in limitations:
                limitations.append(ISSUER_ONLY_LIMITATION)
            if NO_REPORTED_POSITION_LIMITATION in limitations:
                limitations.remove(NO_REPORTED_POSITION_LIMITATION)
            if NOT_NEGATIVE_SIGNAL_LIMITATION in limitations:
                limitations.remove(NOT_NEGATIVE_SIGNAL_LIMITATION)

    relevant_matches = [
        item
        for item in matches
        if (
            normalize_ticker(item.get("target_value")) == ticker
            or normalize_ticker(item.get("resolved_ticker")) == ticker
            or (resolved_cusip and normalize_cusip(item.get("resolved_cusip") or item.get("matched_cusip")) == resolved_cusip)
        )
    ]
    if matched_holding and not relevant_matches:
        relevant_matches = [
            {
                "target_type": "ticker",
                "target_value": ticker,
                "matched": True,
                "match_confidence": match_confidence,
                "match_method": match_method,
                "matched_cusip": matched_holding.get("cusip"),
                "matched_issuer_name": matched_holding.get("issuer_name"),
                "resolved_ticker": resolved_ticker,
                "resolved_cusip": resolved_cusip,
                "resolved_issuer_name": resolved_issuer_name,
                "local_security_map_used": local_security_map_used,
                "total_value_usd": matched_holding.get("total_value_usd"),
                "total_shares_or_principal_amount": matched_holding.get("total_shares_or_principal_amount"),
                "portfolio_weight_pct": matched_holding.get("portfolio_weight_pct"),
                "report_date": matched_holding.get("report_date"),
                "filing_date": matched_holding.get("latest_filing_date"),
                "source_status": matched_holding.get("source_status"),
                "limitations": limitations,
            }
        ]

    latest_report_date = summary.get("latest_report_date") or (matched_holding or {}).get("report_date") or ""
    latest_filing_date = summary.get("latest_filing_date") or (matched_holding or {}).get("latest_filing_date") or ""
    final_label = interpretation_label if grouped_holdings or source_status else "insufficient_13f_data"
    score_contribution_allowed = bool(
        matched_in_13f
        and match_confidence in {"high", "medium"}
        and (source_status.get("provider") in {"SEC EDGAR", "derived_from_SEC_EDGAR_13F"} or summary.get("provider") == "derived_from_SEC_EDGAR_13F")
        and (source_status.get("source_type") in {"live", "cached_live", "derived"} or summary.get("underlying_source_type") in {"live", "cached_live"})
        and source_status.get("freshness_window", "quarterly_filing_delay") == "quarterly_filing_delay"
        and source_status.get("is_fresh", True) is not False
    )
    interpretation_summary = (
        REPORTED_POSITION_SUMMARY
        if final_label == "reported_13f_position_observed"
        else NO_REPORTED_POSITION_SUMMARY
        if final_label == "no_reported_13f_position_observed"
        else "Issuer-name-only 13F match is low confidence without CUSIP confirmation."
        if final_label == "low_confidence_issuer_name_match"
        else "Candidate-specific 13F evidence is limited because identifier mapping is incomplete."
        if final_label == "insufficient_identifier_mapping"
        else "Candidate-specific 13F evidence is unavailable."
    )
    candidate_specific_evidence = {
        "ticker": ticker,
        "resolved_ticker": resolved_ticker,
        "resolved_cusip": resolved_cusip,
        "resolved_issuer_name": resolved_issuer_name,
        "local_security_map_used": local_security_map_used,
        "matched_in_13f": matched_in_13f,
        "match_confidence": match_confidence,
        "match_method": match_method,
        "position_value_usd": (matched_holding or {}).get("total_value_usd"),
        "position_shares_or_principal_amount": (matched_holding or {}).get("total_shares_or_principal_amount"),
        "portfolio_weight_pct": (matched_holding or {}).get("portfolio_weight_pct"),
        "source_date": source_status.get("source_date") or latest_report_date or latest_filing_date,
        "report_date": latest_report_date,
        "filing_date": latest_filing_date,
        "latest_report_date": latest_report_date,
        "latest_filing_date": latest_filing_date,
        "manager_cik": manager_cik,
        "manager_name": manager_name,
        "manager_metadata_source": manager_metadata_source,
        "value_unit_confidence_summary": (matched_holding or {}).get("value_unit_confidence_summary"),
        "interpretation_label": final_label,
        "interpretation_summary": interpretation_summary,
        "score_contribution_allowed": score_contribution_allowed,
    }
    portfolio_context = {
        "manager_cik": manager_cik,
        "manager_name": manager_name,
        "manager_metadata_source": manager_metadata_source,
        "latest_report_date": latest_report_date,
        "latest_filing_date": latest_filing_date,
        "holding_count_grouped": summary.get("holding_count_grouped"),
        "mapped_holding_count": summary.get("mapped_holding_count"),
        "top_holdings_by_value": [_compact_top_holding(item) for item in (summary.get("top_holdings_by_value") or [])[:top_limit]],
        "source_status": source_status,
    }
    return {
        "source_status": source_status,
        "candidate_specific_evidence": candidate_specific_evidence,
        "target_matches": relevant_matches,
        "portfolio_context": portfolio_context,
        "limitations": sorted(set(limitations)),
        "missing_data": sorted(set(missing_data)),
    }
