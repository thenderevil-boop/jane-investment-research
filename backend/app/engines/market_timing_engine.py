from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_data import MOCK_SOURCE, MOCK_SOURCE_DATE
from backend.app.schemas.common import ScoreObject
from backend.app.utils.confidence import source_confidence_weights

LIMITATION = "Phase 2 deterministic mock engine; no live source connection."
LIVE_LIMITATION = "Deterministic engine using repository-backed live market price features where available."


def _confidence(missing_data: list[str], source_type: str | None = "mock") -> float:
    completeness = max(0.35, 1 - len(missing_data) * 0.12)
    recency, reliability = source_confidence_weights(source_type)
    return round(completeness * 0.40 + recency * 0.30 + reliability * 0.30, 2)


def _score(
    name: str,
    score: float,
    label: str,
    raw_data: dict[str, Any],
    derived_metrics: dict[str, Any],
    benchmark: dict[str, Any],
    trend: dict[str, Any],
    missing_data: list[str] | None = None,
) -> ScoreObject:
    missing = missing_data or []
    return ScoreObject(
        name=name,
        score=round(score, 2),
        label=label,
        raw_data=raw_data,
        derived_metrics=derived_metrics,
        benchmark=benchmark,
        trend=trend,
        source=MOCK_SOURCE,
        source_date=MOCK_SOURCE_DATE,
        confidence=_confidence(missing, "mock"),
        limitations=[LIMITATION],
        missing_data=missing,
    )


def _source(data: dict[str, Any]) -> list[str]:
    value = data.get("source")
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return MOCK_SOURCE


def _source_date(data: dict[str, Any]) -> str:
    value = data.get("source_date")
    return str(value) if value else MOCK_SOURCE_DATE


def _limitations(data: dict[str, Any]) -> list[str]:
    existing = data.get("limitations")
    if isinstance(existing, list) and existing:
        return existing
    return [LIVE_LIMITATION if data.get("source_type") == "live" else LIMITATION]


def _mark_live_derived(component: ScoreObject, data: dict[str, Any]) -> ScoreObject:
    if data.get("source_type") != "live":
        return component
    component.source = _source(data)
    component.source_date = _source_date(data)
    component.limitations = _limitations(data)
    component.raw_data = {
        **component.raw_data,
        "source_type": "derived",
        "provider": "derived_from_yfinance",
        "source": _source(data),
        "source_date": _source_date(data),
    }
    return component


def fed_easing_component(data: dict[str, Any]) -> ScoreObject:
    cuts = data.get("consecutive_rate_cut_count")
    rate_trend = data.get("rate_trend") or data.get("fed_policy_state")
    missing = []
    if cuts is None:
        missing.append("consecutive_rate_cut_count")
        cuts = 0
    if cuts >= 2:
        score, label = 100, "favorable_research_environment"
    elif cuts == 1:
        score, label = 60, "watch_for_confirmation"
    elif rate_trend in {"hold_after_hikes", "steady_after_hikes"}:
        score, label = 30, "neutral"
    else:
        score, label = 0, "insufficient_data_or_unfavorable"
    return _score(
        "fed_easing_score",
        score,
        label,
        {"consecutive_rate_cut_count": cuts, "rate_trend": rate_trend},
        {"consecutive_rate_cut_count": cuts},
        {"favorable_cut_count": 2, "partial_cut_count": 1},
        {"fed_policy": "easing" if cuts else "steady"},
        missing,
    )


def index_drawdown_stabilization_component(data: dict[str, Any]) -> ScoreObject:
    sp500_drawdown = data.get("sp500_drawdown_pct")
    nasdaq_drawdown = data.get("nasdaq_drawdown_pct")
    range_20d = data.get("index_range_20d_pct")
    vol_20d = data.get("realized_vol_20d")
    prev_vol_20d = data.get("previous_realized_vol_20d")
    days_since_low = data.get("days_since_low")
    missing = [
        field
        for field, value in {
            "sp500_drawdown_pct": sp500_drawdown,
            "nasdaq_drawdown_pct": nasdaq_drawdown,
            "index_range_20d_pct": range_20d,
            "realized_vol_20d": vol_20d,
            "previous_realized_vol_20d": prev_vol_20d,
        }.items()
        if value is None
    ]
    drawdown = min(v for v in [sp500_drawdown, nasdaq_drawdown] if v is not None) if len(missing) < 2 else 0
    is_deep_drawdown = drawdown <= -20
    is_in_range = range_20d is not None and range_20d <= 8
    is_vol_falling = vol_20d is not None and prev_vol_20d is not None and vol_20d < prev_vol_20d
    if is_deep_drawdown and is_in_range and is_vol_falling:
        score, label = 100, "favorable_research_environment"
    elif is_deep_drawdown and (is_in_range or is_vol_falling):
        score, label = 70, "watch_for_confirmation"
    elif is_deep_drawdown:
        score, label = 50, "neutral"
    else:
        score, label = 0, "insufficient_data_or_unfavorable"
    return _score(
        "index_drawdown_stabilization_score",
        score,
        label,
        {
            "sp500_drawdown_pct": sp500_drawdown,
            "nasdaq_drawdown_pct": nasdaq_drawdown,
            "index_range_20d_pct": range_20d,
            "realized_vol_20d": vol_20d,
            "previous_realized_vol_20d": prev_vol_20d,
            "days_since_low": days_since_low,
        },
        {
            "deep_drawdown": is_deep_drawdown,
            "within_8pct_range": is_in_range,
            "volatility_falling": is_vol_falling,
        },
        {"drawdown_threshold_pct": -20, "range_threshold_pct": 8},
        {"index_stabilization": "up" if is_in_range and is_vol_falling else "mixed"},
        missing,
    )


def vix_confirmation_component(data: dict[str, Any]) -> ScoreObject:
    vix = data.get("vix")
    recent_spike = bool(data.get("vix_recent_spike", False))
    vix_trend = data.get("vix_trend")
    falling_from_spike = bool(data.get("vix_falling_from_spike", vix_trend == "falling"))
    range_20d = data.get("index_range_20d_pct")
    vol_20d = data.get("realized_vol_20d")
    prev_vol_20d = data.get("previous_realized_vol_20d")
    index_stabilization_exists = data.get("stabilization_status") == "stabilizing" or (
        range_20d is not None
        and range_20d <= 8
        and vol_20d is not None
        and prev_vol_20d is not None
        and vol_20d < prev_vol_20d
    )
    missing = [
        field
        for field, value in {
            "vix": vix,
            "vix_trend": vix_trend,
            "index_range_20d_pct": range_20d,
            "realized_vol_20d": vol_20d,
            "previous_realized_vol_20d": prev_vol_20d,
        }.items()
        if value is None
    ]
    if vix is None:
        vix = 0
    if vix > 30 and recent_spike and falling_from_spike and index_stabilization_exists:
        score, label = 100, "favorable_research_environment"
    elif vix > 25 and recent_spike and (falling_from_spike or index_stabilization_exists):
        score, label = 60, "watch_for_confirmation"
    elif vix > 20:
        score, label = 30, "neutral"
    else:
        score, label = 0, "insufficient_data_or_unfavorable"
    return _score(
        "vix_confirmation_score",
        score,
        label,
        {
            "vix": vix,
            "vix_recent_spike": recent_spike,
            "vix_trend": vix_trend,
            "vix_falling_from_spike": falling_from_spike,
            "index_range_20d_pct": range_20d,
            "realized_vol_20d": vol_20d,
            "previous_realized_vol_20d": prev_vol_20d,
        },
        {
            "elevated_vix": vix > 25,
            "vix_falling_from_spike": falling_from_spike,
            "index_stabilization_exists": index_stabilization_exists,
            "full_confirmation": vix > 30 and recent_spike and falling_from_spike and index_stabilization_exists,
        },
        {"high_vix": 30, "elevated_vix": 25, "stabilized_range_pct": 8},
        {"vix": "falling_from_spike" if falling_from_spike else vix_trend or "unknown"},
        missing,
    )


def company_cash_component(data: dict[str, Any]) -> ScoreObject:
    value = data.get("cash_to_market_cap_pct")
    if value is None:
        return _score(
            "company_cash_score",
            0,
            "insufficient_data_or_unfavorable",
            {"cash_to_market_cap_pct": None},
            {"cash_to_market_cap_pct": None},
            {"strong_cash_reference_pct": 10},
            {"company_cash": "unknown"},
            ["cash_to_market_cap_pct"],
        )
    score = 100 if value >= 10 else 50 if value >= 5 else 0
    label = "favorable_research_environment" if score == 100 else "neutral" if score == 50 else "insufficient_data_or_unfavorable"
    return _score(
        "company_cash_score",
        score,
        label,
        {"cash_to_market_cap_pct": value},
        {"cash_to_market_cap_pct": value},
        {"strong_cash_reference_pct": 10, "partial_cash_reference_pct": 5},
        {"company_cash": "strong" if value >= 10 else "partial" if value >= 5 else "low"},
    )


def company_revenue_growth_component(data: dict[str, Any]) -> ScoreObject:
    yearly_growth = data.get("revenue_growth_yoy_pct")
    cagr = data.get("revenue_cagr_3y_pct")
    latest = yearly_growth[-1] if yearly_growth else data.get("latest_revenue_growth_pct")
    missing = []
    if yearly_growth is None:
        missing.append("revenue_growth_yoy_pct")
    if cagr is None:
        missing.append("revenue_cagr_3y_pct")
        cagr = 0
    each_year_double_digit = bool(yearly_growth) and all(value >= 10 for value in yearly_growth[-3:])
    if each_year_double_digit:
        score, label = 100, "favorable_research_environment"
    elif cagr >= 10:
        score, label = 70, "watch_for_confirmation"
    elif latest is not None and latest >= 10:
        score, label = 40, "neutral"
    else:
        score, label = 0, "insufficient_data_or_unfavorable"
    return _score(
        "company_revenue_growth_score",
        score,
        label,
        {"revenue_growth_yoy_pct": yearly_growth, "revenue_cagr_3y_pct": cagr},
        {"each_year_double_digit": each_year_double_digit, "latest_revenue_growth_pct": latest},
        {"double_digit_growth_reference_pct": 10},
        {"company_growth": "up" if score >= 70 else "mixed" if score else "weak"},
        missing,
    )


def founder_ceo_insider_component(data: dict[str, Any]) -> ScoreObject:
    founder_is_ceo = bool(data.get("founder_is_ceo", False))
    net_value = data.get("net_insider_buy_value_180d", 0) or 0
    count = data.get("insider_buy_count_180d", 0) or 0
    if founder_is_ceo and net_value > 0 and count >= 2:
        score, label = 100, "favorable_research_environment"
    elif founder_is_ceo and net_value > 0:
        score, label = 70, "watch_for_confirmation"
    elif founder_is_ceo:
        score, label = 40, "neutral"
    else:
        score, label = 0, "insufficient_data_or_unfavorable"
    return _score(
        "founder_ceo_insider_buying_score",
        score,
        label,
        {
            "founder_is_ceo": founder_is_ceo,
            "net_insider_buy_value_180d": net_value,
            "insider_buy_count_180d": count,
        },
        {"founder_with_positive_insider_activity": founder_is_ceo and net_value > 0},
        {"multiple_insider_activity_count": 2},
        {"founder_alignment": "up" if score >= 70 else "stable" if score == 40 else "unknown"},
    )


def market_timing_label(score: float) -> str:
    if score >= 80:
        return "favorable_research_environment"
    if score >= 60:
        return "watch_for_confirmation"
    if score >= 40:
        return "neutral"
    return "insufficient_data_or_unfavorable"


def _format_pct(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.1f}%"


def _phase36_market_timing_condition_checklist(data: dict[str, Any]) -> list[dict[str, Any]]:
    cuts = data.get("consecutive_rate_cut_count") or 0
    sp500_drawdown = data.get("sp500_drawdown_pct")
    nasdaq_drawdown = data.get("nasdaq_drawdown_pct")
    drawdowns = [value for value in [sp500_drawdown, nasdaq_drawdown] if value is not None]
    deepest_drawdown = min(drawdowns) if drawdowns else None
    range_20d = data.get("index_range_20d_pct")
    vol_20d = data.get("realized_vol_20d")
    previous_vol_20d = data.get("previous_realized_vol_20d")
    deep_drawdown = deepest_drawdown is not None and deepest_drawdown <= -20
    stabilizing = bool(
        range_20d is not None
        and range_20d <= 8
        and vol_20d is not None
        and previous_vol_20d is not None
        and vol_20d < previous_vol_20d
    )
    vix = data.get("vix")
    vix_recent_spike = bool(data.get("vix_recent_spike", False))
    vix_falling = bool(data.get("vix_falling_from_spike", data.get("vix_trend") == "falling"))
    vix_full_confirmation = bool(vix is not None and vix > 30 and vix_recent_spike and vix_falling and stabilizing)
    vix_partial_confirmation = bool(vix is not None and vix > 25 and vix_recent_spike and (vix_falling or stabilizing))
    if deep_drawdown and stabilizing and (vix_falling or vix_full_confirmation):
        market_state = "fear_recovery"
        state_explanation = "Deep drawdown is present and volatility is recovering."
    elif vix is not None and vix >= 30 and not vix_falling:
        market_state = "overheat"
        state_explanation = "Volatility is elevated without recovery confirmation."
    elif deep_drawdown:
        market_state = "fear"
        state_explanation = "Deep drawdown is present but recovery confirmation is incomplete."
    else:
        market_state = "normal"
        state_explanation = "Normal market context often means entry timing score remains low."
    return [
        {
            "id": "fed_consecutive_cuts",
            "label": "Fed consecutive cuts",
            "status": "met" if cuts >= 2 else "partial" if cuts == 1 else "not_met",
            "observed_value": f"{cuts} consecutive cut(s)",
            "explanation": "The timing framework looks for at least two consecutive cuts.",
            "affects_score": False,
        },
        {
            "id": "market_drawdown_stabilization",
            "label": "Market drawdown and stabilization",
            "status": "met" if deep_drawdown and stabilizing else "partial" if deep_drawdown else "not_met",
            "observed_value": f"SPY {_format_pct(sp500_drawdown)}, QQQ {_format_pct(nasdaq_drawdown)} drawdown",
            "explanation": "The timing framework looks for a deep drawdown plus stabilization.",
            "affects_score": False,
        },
        {
            "id": "vix_spike_recovery",
            "label": "VIX spike and recovery",
            "status": "met" if vix_full_confirmation else "partial" if vix_partial_confirmation else "not_met",
            "observed_value": f"VIX {vix if vix is not None else 'N/A'}; spike {'yes' if vix_recent_spike else 'no'}; falling {'yes' if vix_falling else 'no'}",
            "explanation": "The timing framework looks for volatility spike confirmation and recovery.",
            "affects_score": False,
        },
        {
            "id": "overheat_state",
            "label": "Overheat / normal / fear state",
            "status": market_state,
            "observed_value": f"VIX {vix if vix is not None else 'N/A'}; drawdown {_format_pct(deepest_drawdown)}",
            "explanation": state_explanation,
            "affects_score": False,
        },
    ]


def _phase36_entry_timing_summary(score: float) -> str:
    if score >= 80:
        return "Timing conditions are broadly met for research context."
    if score >= 60:
        return "Some timing conditions are present but still need confirmation."
    return "Entry timing conditions are not met yet; this is expected near market highs or calm markets."


def evaluate_market_timing(data: dict[str, Any]) -> ScoreObject:
    components = [
        fed_easing_component(data),
        index_drawdown_stabilization_component(data),
        vix_confirmation_component(data),
        company_cash_component(data),
        company_revenue_growth_component(data),
        founder_ceo_insider_component(data),
    ]
    for component in components:
        if component.name in {"index_drawdown_stabilization_score", "vix_confirmation_score"}:
            _mark_live_derived(component, data)
    weights = {
        "fed_easing_score": 0.32,
        "index_drawdown_stabilization_score": 0.32,
        "vix_confirmation_score": 0.14,
        "company_cash_score": 0.08,
        "company_revenue_growth_score": 0.08,
        "founder_ceo_insider_buying_score": 0.06,
    }
    total = sum(component.score * weights[component.name] for component in components)
    missing = sorted({item for component in components for item in component.missing_data})
    component_payload = {component.name: component.model_dump() for component in components}
    return ScoreObject(
        name="entry_environment_score",
        score=round(total, 2),
        label=market_timing_label(total),
        raw_data={key: data.get(key) for key in sorted(data.keys()) if key != "fear_greed"},
        derived_metrics={
            "components": component_payload,
            "weights": weights,
            "phase36_explanation_version": "market_timing_condition_explanation_v2",
            "scoring_unchanged": True,
            "score_zero_interpretation": "Score 0 means entry timing conditions are not met; this is expected near market highs.",
            "entry_timing_summary": _phase36_entry_timing_summary(total),
            "condition_checklist": _phase36_market_timing_condition_checklist(data),
        },
        benchmark={
            "favorable_research_environment_minimum": 80,
            "watch_for_confirmation_minimum": 60,
            "neutral_minimum": 40,
        },
        trend={
            "market_environment": "steady",
            "component_count": len(components),
        },
        source=_source(data),
        source_date=_source_date(data),
        confidence=_confidence(missing, data.get("source_type") or "mock"),
        limitations=_limitations(data),
        missing_data=missing,
    )
