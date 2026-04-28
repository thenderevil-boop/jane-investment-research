from __future__ import annotations

from typing import Any

from backend.app import config

LOCAL_TICKER_CUSIP_MAP = {
    "AAPL": {"cusip": "037833100", "confidence": "medium", "source": "local_fixture"},
    "NVDA": {"cusip": "67066G104", "confidence": "medium", "source": "local_fixture"},
    "TSLA": {"cusip": "88160R101", "confidence": "medium", "source": "local_fixture"},
}

ISSUER_MATCH_LIMITATION = "Issuer-name matching is low confidence unless CUSIP or local ticker mapping confirms the security."
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
    for cusip in sorted({_upper(item) for item in cusips if _upper(item)}):
        targets.append({"target_type": "cusip", "target_value": cusip, "cusip": cusip, "match_confidence": "high"})
    for ticker in sorted({_upper(item) for item in tickers if _upper(item)}):
        mapping = LOCAL_TICKER_CUSIP_MAP.get(ticker)
        targets.append(
            {
                "target_type": "ticker",
                "target_value": ticker,
                "ticker": ticker,
                "cusip": mapping.get("cusip") if mapping else "",
                "match_confidence": mapping.get("confidence", "low") if mapping else "low",
                "mapping_source": mapping.get("source") if mapping else "unmapped_local_fixture",
                "limitations": [] if mapping else ["Ticker target has no local CUSIP mapping in Phase 11.3."],
            }
        )
    for issuer in sorted({_name(item) for item in issuers if _name(item)}):
        targets.append(
            {
                "target_type": "issuer_name",
                "target_value": issuer,
                "issuer_name": issuer,
                "match_confidence": "low",
                "limitations": [ISSUER_MATCH_LIMITATION],
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
        if target_type == "cusip":
            target_cusip = _upper(target.get("cusip") or target.get("target_value"))
            candidate = next((item for item in holdings if _upper(item.get("cusip")) == target_cusip), None)
            confidence = "high"
        elif target_type == "ticker":
            target_cusip = _upper(target.get("cusip"))
            candidate = next((item for item in holdings if target_cusip and _upper(item.get("cusip")) == target_cusip), None)
            confidence = confidence if target_cusip else "low"
        elif target_type == "issuer_name":
            target_name = _name(target.get("issuer_name") or target.get("target_value"))
            candidate = next((item for item in holdings if target_name and target_name in _name(item.get("issuer_name"))), None)
            confidence = "low"
            if ISSUER_MATCH_LIMITATION not in limitations:
                limitations.append(ISSUER_MATCH_LIMITATION)
        matched = candidate is not None
        matches.append(
            {
                "target_type": target_type,
                "target_value": target.get("target_value"),
                "matched": matched,
                "match_confidence": confidence if matched else "low",
                "matched_cusip": candidate.get("cusip") if candidate else "",
                "matched_issuer_name": candidate.get("issuer_name") if candidate else "",
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
