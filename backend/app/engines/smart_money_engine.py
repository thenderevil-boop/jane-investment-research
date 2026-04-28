from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_data import MOCK_SOURCE, MOCK_SOURCE_DATE
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
        return "institutional_supportive"
    if score >= 40:
        return "smart_money_neutral"
    return "risk_warning"


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
        },
        {
            "peer_average_institutional_ownership": raw.get("peer_average_institutional_ownership"),
            "peer_average_quarterly_position_change_pct": peer_position_change_pct,
            "sector_median_institutional_ownership": raw.get("sector_median_institutional_ownership"),
        },
        {"institutional_support": "up" if score >= 60 else "down" if score == 20 else "stable"},
        THIRTEEN_F_LIMITATIONS,
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
    source_status = data.get("form4_source_status") or insider.raw_data.get("source_status")
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
        result.source_status = build_source_status(
            {
                "source_type": "derived",
                "provider": "mixed_smart_money_sources",
                "source_date": source_status.get("source_date", result.source_date),
                "fetched_at": source_status.get("fetched_at"),
                "is_fresh": source_status.get("is_fresh", True),
                "limitations": result.limitations,
                "missing_data": result.missing_data,
            }
        )
    return result
