from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_data import MOCK_SOURCE, MOCK_SOURCE_DATE
from backend.app.engines.sec_13f_aggregation import aggregate_13f_holdings, compare_13f_quarter_over_quarter, summarize_13f_portfolio
from backend.app.engines.sec_13f_target_matching import match_13f_targets, normalize_target_security_map
from backend.app.schemas.common import ScoreObject
from backend.app.utils.freshness import build_source_status

BASE_LIMITATION = "Phase 4 deterministic mock smart money engine; no live source connection."
THIRTEEN_F_LIMITATIONS = [
    "13F may lag up to 45 days after quarter end.",
    "13F generally discloses long positions in covered securities.",
    "13F may not show shorts, derivatives, or current positions.",
    "13F alone is delayed institutional support evidence, not a real-time signal.",
]
OPTIONS_LIMITATION = "Options activity is ambiguous and may reflect hedging, speculation, or spread trades."
FORM4_TRANSACTION_ROW_CAP = 25


def _confidence(missing_data: list[str]) -> float:
    completeness = max(0.35, 1 - len(missing_data) * 0.14)
    return round(completeness * 0.40 + 0.90 * 0.30 + 0.80 * 0.30, 2)


def _aggregate_label(score: float) -> str:
    if score >= 75:
        return "smart_money_supportive"
    if score >= 60:
        return "smart_money_mixed"
    if score >= 40:
        return "smart_money_neutral"
    return "risk_warning"


def _institutional_label(score: float) -> str:
    if score >= 60:
        return "institutional_evidence_observed"
    if score >= 40:
        return "institutional_evidence_limited"
    return "insufficient_data"


def _insider_label(score: float) -> str:
    if score >= 70:
        return "insider_accumulation_observed"
    if score < 40:
        return "insider_distribution_risk"
    return "insider_activity_neutral"


def _options_label(score: float) -> str:
    if score >= 60:
        return "options_activity_elevated"
    if score >= 40:
        return "smart_money_neutral"
    return "risk_warning"


def _score_object(
    name: str,
    score: float,
    label: str,
    raw_data: dict[str, Any],
    derived_metrics: dict[str, Any],
    benchmark: dict[str, Any],
    trend: dict[str, Any],
    limitations: list[str] | None = None,
    missing_data: list[str] | None = None,
    source: list[str] | None = None,
    source_date: str | None = None,
    source_status: dict[str, Any] | None = None,
) -> ScoreObject:
    missing = missing_data or []
    result = ScoreObject(
        name=name,
        score=round(score, 2),
        label=label,
        raw_data=raw_data,
        derived_metrics=derived_metrics,
        benchmark=benchmark,
        trend=trend,
        source=source or MOCK_SOURCE,
        source_date=source_date or MOCK_SOURCE_DATE,
        confidence=_confidence(missing),
        limitations=limitations or [BASE_LIMITATION],
        missing_data=missing,
    )
    if source_status:
        result.source_status = build_source_status(source_status, freshness_window=source_status.get("freshness_window", "latest_expected_trading_day"))
    return result


def evaluate_13f_institutional_support(data: dict[str, Any]) -> ScoreObject:
    raw = data.get("institutional_13f", {})
    snapshots = list(data.get("institutional_13f_snapshots") or [])
    if data.get("institutional_13f_snapshot"):
        snapshots = [data["institutional_13f_snapshot"], *snapshots]
    deduped_snapshots: list[dict[str, Any]] = []
    seen_snapshot_ids: set[str] = set()
    for snapshot in snapshots:
        snapshot_id = f"{snapshot.get('manager')}|{snapshot.get('source_date')}|{snapshot.get('source_type')}"
        if snapshot_id not in seen_snapshot_ids:
            seen_snapshot_ids.add(snapshot_id)
            deduped_snapshots.append(snapshot)
    live_snapshots = [
        snapshot
        for snapshot in deduped_snapshots
        if snapshot.get("source_type") in {"live", "cached_live"}
    ]
    source_snapshot = live_snapshots[0] if live_snapshots else (deduped_snapshots[0] if deduped_snapshots else {})
    source_status = data.get("institutional_13f_source_status") or source_snapshot.get("source_status") or {}
    source_type = source_status.get("source_type") or source_snapshot.get("source_type")
    fallback_mock_13f = source_type == "fallback" and source_status.get("provider", source_snapshot.get("provider")) == "mock"
    target_cusip = str(raw.get("cusip") or "").strip().upper()
    all_holdings = [holding for snapshot in deduped_snapshots for holding in snapshot.get("holdings", []) or []]
    live_holdings = [holding for snapshot in live_snapshots for holding in snapshot.get("holdings", []) or []]
    holdings_for_metrics = live_holdings if live_holdings else all_holdings
    target_cusip_holdings = [
        holding
        for holding in holdings_for_metrics
        if target_cusip and str(holding.get("cusip") or "").strip().upper() == target_cusip
    ]
    portfolio_summary = data.get("institutional_13f_summary") or summarize_13f_portfolio(holdings_for_metrics)
    grouped_holdings = portfolio_summary.get("grouped_holdings", []) or []
    sorted_holdings = portfolio_summary.get("top_holdings_by_value") or sorted(
        holdings_for_metrics,
        key=lambda item: item.get("value_usd") or 0,
        reverse=True,
    )[:10]
    total_value = portfolio_summary.get("total_reported_value_usd")
    if total_value is None:
        total_value = sum(item.get("value_usd") or 0 for item in holdings_for_metrics)
    target_payload = data.get("institutional_13f_target_matches") or {}
    if target_payload:
        target_matches = target_payload.get("target_matches", []) or []
    elif target_cusip:
        target_matches = match_13f_targets(grouped_holdings, normalize_target_security_map({"cusip": target_cusip})).get("target_matches", [])
    else:
        target_matches = []
    component_source_status = portfolio_summary.get("source_status") or source_status
    matched_targets = [item for item in target_matches if item.get("matched")]
    high_or_medium_matches = [
        item
        for item in matched_targets
        if item.get("match_confidence") in {"high", "medium"}
    ]
    filing_dates = [filing.get("filing_date", "") for snapshot in deduped_snapshots for filing in snapshot.get("filings", []) or [] if filing.get("filing_date")]
    report_dates = [filing.get("report_date", "") for snapshot in deduped_snapshots for filing in snapshot.get("filings", []) or [] if filing.get("report_date")]
    latest_filing_date = portfolio_summary.get("latest_filing_date") or max(filing_dates, default=source_snapshot.get("source_date", ""))
    latest_report_date = portfolio_summary.get("latest_report_date") or max(report_dates, default=source_snapshot.get("source_date", ""))
    by_cusip_period: dict[str, list[dict[str, Any]]] = {}
    for holding in holdings_for_metrics:
        if not holding.get("cusip"):
            continue
        by_cusip_period.setdefault(str(holding.get("cusip")).upper(), []).append(holding)
    quarter_change = None
    if target_cusip and len(by_cusip_period.get(target_cusip, [])) >= 2:
        ordered = sorted(by_cusip_period[target_cusip], key=lambda item: (item.get("report_date") or "", item.get("filing_date") or ""), reverse=True)
        latest_value = ordered[0].get("shares_or_principal_amount") or 0
        prior_value = ordered[1].get("shares_or_principal_amount") or 0
        if prior_value:
            quarter_change = round((latest_value - prior_value) / prior_value * 100, 2)
    qoq_payload = data.get("institutional_13f_qoq_comparison") or {}
    qoq_changes = qoq_payload.get("qoq_changes", []) or []
    if not qoq_changes:
        periods = sorted({str(row.get("report_date") or "") for row in holdings_for_metrics if row.get("report_date")}, reverse=True)
        if len(periods) >= 2:
            current_grouped = aggregate_13f_holdings([row for row in holdings_for_metrics if row.get("report_date") == periods[0]]).get("grouped_holdings", [])
            prior_grouped = aggregate_13f_holdings([row for row in holdings_for_metrics if row.get("report_date") == periods[1]]).get("grouped_holdings", [])
            qoq_changes = compare_13f_quarter_over_quarter(current_grouped, prior_grouped)
    if live_holdings:
        score = 60 if high_or_medium_matches or target_cusip_holdings else 50
        if quarter_change is not None and quarter_change < -10:
            score = 40
        institutional_support_label = "institutional_target_match_observed" if high_or_medium_matches or target_cusip_holdings else "institutional_evidence_observed"
    elif fallback_mock_13f:
        score = 20
        institutional_support_label = "insufficient_data"
    elif source_type == "mock":
        score = 40
        institutional_support_label = "institutional_evidence_limited"
    else:
        score = 30
        institutional_support_label = "insufficient_data"
    if holdings_for_metrics:
        missing = []
    else:
        missing = ["13f_holdings"]
    if fallback_mock_13f:
        missing.append("live SEC 13F data")
    if live_holdings or deduped_snapshots:
        return _score_object(
            "institutional_support_13f_score",
            score,
            institutional_support_label,
            {
                "holdings": holdings_for_metrics,
                "portfolio_summary": {key: value for key, value in portfolio_summary.items() if key != "grouped_holdings"},
                "top_holdings_by_value": sorted_holdings[:10],
                "target_matches": target_matches,
                "qoq_changes": qoq_changes,
                "value_confidence_breakdown": portfolio_summary.get("value_confidence_breakdown", {}),
                "target_cusip_holdings": target_cusip_holdings,
                "target_ticker_holdings": [],
                "source_status": component_source_status,
                "delayed_institutional_support": True,
                "is_real_time_signal": False,
                "limitations": [*THIRTEEN_F_LIMITATIONS, *source_snapshot.get("limitations", [])],
                "missing_data": sorted(set([*missing, *source_snapshot.get("missing_data", []), *portfolio_summary.get("missing_data", []), *target_payload.get("missing_data", []), *qoq_payload.get("missing_data", [])])),
            },
            {
                "latest_13f_report_date": latest_report_date,
                "latest_13f_filing_date": latest_filing_date,
                "grouped_holding_count": portfolio_summary.get("holding_count_grouped", len(grouped_holdings)),
                "total_reported_value_usd": total_value,
                "holding_count": len(holdings_for_metrics),
                "top_holding_names": [item.get("issuer_name") for item in sorted_holdings[:10] if item.get("issuer_name")],
                "target_match_count": len(matched_targets),
                "high_confidence_target_match_count": len([item for item in matched_targets if item.get("match_confidence") == "high"]),
                "qoq_change_count": len(qoq_changes),
                "target_ticker_holdings": [],
                "target_cusip_holdings": target_cusip_holdings,
                "top_holdings_by_value": sorted_holdings[:10],
                "quarter_over_quarter_position_change": quarter_change,
                "manager_count_observed": len(deduped_snapshots),
                "institutional_support_label": institutional_support_label,
                "is_real_time_signal": False,
            },
            {
                "freshness_window": "quarterly_filing_delay",
                "maximum_score_from_delayed_13f_only": 60,
            },
            {"institutional_support": "observed" if live_holdings else "limited"},
            [*THIRTEEN_F_LIMITATIONS, *source_snapshot.get("limitations", [])],
            sorted(set([*missing, *source_snapshot.get("missing_data", []), *portfolio_summary.get("missing_data", []), *target_payload.get("missing_data", []), *qoq_payload.get("missing_data", [])])),
            source=source_status.get("source") or source_snapshot.get("source") or MOCK_SOURCE,
            source_date=source_status.get("source_date") or latest_report_date or latest_filing_date or MOCK_SOURCE_DATE,
            source_status=component_source_status,
        )
    missing = [field for field in ["quarter", "filing_date"] if not raw.get(field)]
    holder_count_change = raw.get("holder_count_change", 0)
    position_change_pct = raw.get("quarterly_position_change_pct", 0)
    peer_position_change_pct = raw.get("peer_average_quarterly_position_change_pct", 0)
    major_reduction = raw.get("major_holder_reduction", False)
    if position_change_pct > peer_position_change_pct and holder_count_change > 0:
        score = 100
    elif position_change_pct > 0 or holder_count_change > 0:
        score = 60
    elif major_reduction or position_change_pct <= -10:
        score = 20
    else:
        score = 40
    if score > 40:
        score = 40
    return _score_object(
        "institutional_support_13f_score",
        score,
        _institutional_label(score),
        {
            "institution_name": raw.get("institution_name"),
            "issuer_name": raw.get("issuer_name"),
            "cusip": raw.get("cusip"),
            "shares": raw.get("shares"),
            "market_value": raw.get("market_value"),
            "quarter": raw.get("quarter"),
            "filing_date": raw.get("filing_date"),
            "delayed_institutional_support": True,
        },
        {
            "holder_count": raw.get("holder_count"),
            "holder_count_change": holder_count_change,
            "top_10_holder_concentration": raw.get("top_10_holder_concentration"),
            "quarterly_position_change_pct": position_change_pct,
            "institutional_ownership_proxy": raw.get("institutional_ownership_proxy"),
            "is_real_time_signal": False,
            "institutional_support_label": _institutional_label(score),
        },
        {
            "peer_average_institutional_ownership": raw.get("peer_average_institutional_ownership"),
            "peer_average_quarterly_position_change_pct": peer_position_change_pct,
            "sector_median_institutional_ownership": raw.get("sector_median_institutional_ownership"),
        },
        {"institutional_support": "up" if score >= 60 else "down" if score == 20 else "stable"},
        [*THIRTEEN_F_LIMITATIONS, "Mock 13F fixture is not used to boost smart-money score."],
        missing,
    )


def evaluate_form4_insider_signal(data: dict[str, Any]) -> ScoreObject:
    transactions = data.get("form4_transactions", [])
    source_status = data.get("form4_source_status") or data.get("source_status") or {}
    source = source_status.get("source") or (["SEC EDGAR"] if source_status.get("provider") == "SEC EDGAR" else MOCK_SOURCE)
    source_date = source_status.get("source_date") or max((item.get("filing_date", "") for item in transactions), default=MOCK_SOURCE_DATE)
    fallback_mock_form4 = source_status.get("source_type") == "fallback" and source_status.get("provider") == "mock"

    def category(item: dict[str, Any]) -> str:
        return str(item.get("transaction_category") or item.get("transaction_type") or "other")

    def code(item: dict[str, Any]) -> str:
        return str(item.get("transaction_code") or "").strip().upper()

    accumulation_items = [item for item in transactions if category(item) == "accumulation" and code(item) == "P"]
    disposition_items = [item for item in transactions if category(item) == "disposition" and code(item) == "S"]
    accumulation_count = len(accumulation_items)
    disposition_count = len(disposition_items)
    accumulation_value = sum(item.get("value", 0) or 0 for item in accumulation_items)
    disposition_value = sum(item.get("value", 0) or 0 for item in disposition_items)
    net_value = accumulation_value - disposition_value
    officer_accumulation_count = sum(1 for item in accumulation_items if item.get("is_officer") or "officer" in str(item.get("role", "")).lower())
    director_accumulation_count = sum(1 for item in accumulation_items if item.get("is_director") or "director" in str(item.get("role", "")).lower())
    founder_or_ceo_accumulation = any(
        "founder" in f"{item.get('role', '')} {item.get('officer_title', '')}".lower()
        or "ceo" in f"{item.get('role', '')} {item.get('officer_title', '')}".lower()
        for item in accumulation_items
    )
    largest_accumulation_value = max((item.get("value", 0) or 0 for item in accumulation_items), default=0)
    latest_transaction_date = max((item.get("transaction_date", "") for item in transactions), default="")
    latest_filing_date = max((item.get("filing_date", "") for item in transactions), default="")
    missing = [] if transactions else ["form4_transactions"]
    all_transaction_codes_missing = bool(transactions) and all(not code(item) for item in transactions)
    if all_transaction_codes_missing:
        missing.append("transaction_code")
    if fallback_mock_form4:
        score = 50
    elif all_transaction_codes_missing:
        score = 50
    elif accumulation_count >= 2 and disposition_count == 0:
        score = 100
    elif founder_or_ceo_accumulation and net_value > 0:
        score = 90
    elif net_value > 0:
        score = 70
    elif disposition_count >= 2 or net_value < 0:
        score = 20
    else:
        score = 50
    limitations = [
        "Form 4 interpretation is limited by transaction-code context, compensation plans, indirect ownership, and reporting timing.",
        "Only code P is counted as insider accumulation; code S is counted as disposition.",
        "Codes M, A, F, G, D, V, J, and unknown codes are not counted as accumulation by default.",
    ]
    if all_transaction_codes_missing:
        limitations.append("All live Form 4 rows are missing transaction codes, so Form 4 does not boost the smart-money score.")
    if fallback_mock_form4:
        limitations.append("Mock fallback Form 4 data is not used to boost smart-money score.")
    for item in transactions:
        for limitation in item.get("limitations", []) or []:
            if limitation not in limitations:
                limitations.append(limitation)
    if source_status.get("source_type") in {"mock", "fallback"} and BASE_LIMITATION not in limitations:
        limitations.append(BASE_LIMITATION)
    return _score_object(
        "insider_form4_signal_score",
        score,
        "insufficient_data" if not transactions else "insider_activity_neutral" if (all_transaction_codes_missing or fallback_mock_form4) else _insider_label(score),
        {
            "transactions": sorted(
                transactions,
                key=lambda item: (str(item.get("filing_date") or ""), str(item.get("transaction_date") or "")),
                reverse=True,
            )[:FORM4_TRANSACTION_ROW_CAP],
            "transaction_row_cap": FORM4_TRANSACTION_ROW_CAP,
            "provider": source_status.get("provider", "phase1_mock_dataset"),
            "source_status": source_status,
        },
        {
            "net_insider_accumulation_value_180d": net_value,
            "total_transactions_180d": len(transactions),
            "accumulation_count_180d": accumulation_count,
            "disposition_count_180d": disposition_count,
            "officer_accumulation_count": officer_accumulation_count,
            "director_accumulation_count": director_accumulation_count,
            "founder_or_ceo_accumulation": founder_or_ceo_accumulation,
            "largest_accumulation_value": largest_accumulation_value,
            "latest_transaction_date": latest_transaction_date,
            "latest_filing_date": latest_filing_date,
        },
        {
            "multiple_officer_activity_count": 2,
            "positive_net_value": 0,
            "accumulation_code": "P",
            "disposition_code": "S",
        },
        {"insider_activity": "neutral" if fallback_mock_form4 else "accumulation_observed" if score >= 70 else "distribution_risk" if score == 20 else "neutral"},
        limitations,
        missing,
        source=source if isinstance(source, list) else [str(source)],
        source_date=source_date,
        source_status=source_status,
    )


def evaluate_options_abnormal_activity(data: dict[str, Any]) -> ScoreObject:
    raw = data.get("options_activity", {})
    option_volume = raw.get("option_volume")
    open_interest = raw.get("open_interest")
    missing = [field for field in ["option_volume", "open_interest"] if raw.get(field) is None]
    volume_to_open_interest = (
        round(option_volume / open_interest, 2)
        if isinstance(option_volume, (int, float)) and isinstance(open_interest, (int, float)) and open_interest
        else None
    )
    abnormal_ratio = raw.get("abnormal_volume_ratio", 0)
    direction_consistent = bool(raw.get("direction_consistent_with_price_action", False))
    if abnormal_ratio >= 3 and direction_consistent:
        score = 80
    elif abnormal_ratio >= 2:
        score = 60
    else:
        score = 40
    return _score_object(
        "options_abnormal_activity_score",
        score,
        _options_label(score),
        {
            "option_volume": option_volume,
            "open_interest": open_interest,
            "call_put_ratio": raw.get("call_put_ratio"),
            "implied_volatility": raw.get("implied_volatility"),
            "expiration_date": raw.get("expiration_date"),
        },
        {
            "volume_to_open_interest": volume_to_open_interest,
            "call_put_ratio": raw.get("call_put_ratio"),
            "abnormal_volume_ratio": abnormal_ratio,
            "direction_consistent_with_price_action": direction_consistent,
        },
        {"abnormal_volume_ratio_high": 3, "abnormal_volume_ratio_watch": 2},
        {"options_attention": "up" if score >= 60 else "stable"},
        [BASE_LIMITATION, OPTIONS_LIMITATION],
        missing,
    )


def evaluate_smart_money(data: dict[str, Any]) -> ScoreObject:
    institutional = evaluate_13f_institutional_support(data)
    insider = evaluate_form4_insider_signal(data)
    options = evaluate_options_abnormal_activity(data)
    weights = {
        "institutional_support_13f_score": 0.30,
        "insider_form4_signal_score": 0.45,
        "options_abnormal_activity_score": 0.25,
    }
    final_score = (
        institutional.score * weights["institutional_support_13f_score"]
        + insider.score * weights["insider_form4_signal_score"]
        + options.score * weights["options_abnormal_activity_score"]
    )
    missing = sorted(set(institutional.missing_data + insider.missing_data + options.missing_data))
    source_status = data.get("form4_source_status") or insider.raw_data.get("source_status") or data.get("institutional_13f_source_status")
    result = ScoreObject(
        name="smart_money_score",
        score=round(final_score, 2),
        max_score=100,
        label=_aggregate_label(final_score),
        raw_data={
            "institutional_13f": institutional.raw_data,
            "form4": insider.raw_data,
            "options": options.raw_data,
        },
        derived_metrics={
            "components": {
                "institutional_support_13f": institutional.model_dump(),
                "insider_form4_signal": insider.model_dump(),
                "options_abnormal_activity": options.model_dump(),
            },
            "weights": weights,
        },
        benchmark={"smart_money_supportive_minimum": 75, "smart_money_mixed_minimum": 60},
        trend={
            "institutional_support": institutional.trend.get("institutional_support"),
            "insider_activity": insider.trend.get("insider_activity"),
            "options_attention": options.trend.get("options_attention"),
        },
        source=MOCK_SOURCE,
        source_date=MOCK_SOURCE_DATE,
        confidence=round((institutional.confidence + insider.confidence + options.confidence) / 3, 2),
        limitations=sorted(set([BASE_LIMITATION, *THIRTEEN_F_LIMITATIONS, OPTIONS_LIMITATION, *insider.limitations])),
        missing_data=missing,
    )
    if source_status:
        institutional_status = data.get("institutional_13f_source_status") or institutional.raw_data.get("source_status") or {}
        form4_status = data.get("form4_source_status") or insider.raw_data.get("source_status") or {}
        source_dates = [
            item.get("source_date")
            for item in [institutional_status, form4_status]
            if item.get("source_date") and item.get("source_type") in {"live", "cached_live"}
        ]
        fallback_used = any(
            item.get("fallback_used") or item.get("source_type") == "fallback"
            for item in [institutional_status, form4_status]
            if item
        )
        fallback_reasons = [
            str(item.get("fallback_reason"))
            for item in [institutional_status, form4_status]
            if item.get("fallback_reason")
        ]
        result.source_status = build_source_status(
            {
                "source_type": "derived",
                "provider": "mixed_smart_money_sources",
                "source_date": max(source_dates, default=result.source_date),
                "fetched_at": source_status.get("fetched_at"),
                "is_fresh": all(item.get("is_fresh", True) for item in [institutional_status, form4_status] if item),
                "fallback_used": fallback_used,
                "fallback_reason": "; ".join(fallback_reasons) if fallback_reasons else None,
                "limitations": result.limitations,
                "missing_data": result.missing_data,
            }
        )
    return result
