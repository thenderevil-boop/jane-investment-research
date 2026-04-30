from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_macro import MOCK_MACRO_SOURCE, MOCK_MACRO_SOURCE_DATE
from backend.app.schemas.macro_regime import MacroIndicatorComponent
from backend.app.utils.freshness import DERIVED_FRED_FRESHNESS_WINDOW, build_source_status

LIMITATION = "Phase 5 mock macro feature; no live source connection."


def _confidence(value: Any) -> float:
    return 0.88 if value is not None else 0.45


def _component(
    name: str,
    value: Any,
    score: float,
    derived_metrics: dict[str, Any],
    benchmark: dict[str, Any],
    trend: dict[str, Any],
    source_status_payload: dict[str, Any] | None = None,
) -> MacroIndicatorComponent:
    missing = [] if value is not None else [name]
    freshness_window = source_status_payload.get("freshness_window", DERIVED_FRED_FRESHNESS_WINDOW) if source_status_payload else DERIVED_FRED_FRESHNESS_WINDOW
    status = build_source_status(source_status_payload, freshness_window=freshness_window) if source_status_payload else None
    if source_status_payload and source_status_payload.get("source_type") == "mock":
        missing = sorted(set([*missing, *source_status_payload.get("missing_data", [])]))
    source = [status.provider] if status and status.provider not in {"unknown", "derived_from_FRED"} else MOCK_MACRO_SOURCE
    if status and status.provider == "derived_from_FRED":
        source = ["derived_from_FRED"]
    source_date = status.source_date if status and status.source_date else MOCK_MACRO_SOURCE_DATE
    limitations = list(source_status_payload.get("limitations", []) if source_status_payload else [LIMITATION])
    if not limitations:
        limitations = [LIMITATION]
    return MacroIndicatorComponent(
        name=name,
        score=score if value is not None else 0,
        raw_data={name: value},
        derived_metrics=derived_metrics,
        benchmark=benchmark,
        trend=trend,
        source=source,
        source_date=source_date,
        confidence=_confidence(value),
        limitations=limitations,
        missing_data=missing,
        source_status=status,
    )


def _score_fed_funds_rate(value: Any) -> float:
    if value is None:
        return 0
    if value <= 2.5:
        return 85
    if value <= 4.0:
        return 70
    if value <= 5.5:
        return 45
    return 25


def _score_fed_policy(value: Any) -> float:
    if value == "easing":
        return 85
    if value == "neutral":
        return 70
    if value == "restrictive":
        return 45
    if value == "tightening":
        return 25
    return 0


def _score_yield_spread(value: Any) -> float:
    if value is None:
        return 0
    if value >= 75:
        return 85
    if value >= 0:
        return 70
    if value >= -50:
        return 40
    return 25


def _score_inflation(value: Any) -> float:
    if value is None:
        return 0
    if value < 2.5:
        return 85
    if value < 3.5:
        return 70
    if value < 4.5:
        return 45
    return 25


def _score_unemployment_rate(value: Any) -> float:
    if value is None:
        return 0
    if value <= 4.0:
        return 80
    if value <= 5.0:
        return 65
    if value <= 6.0:
        return 40
    return 25


def _score_unemployment_trend(value: Any) -> float:
    if value == "falling":
        return 80
    if value == "stable":
        return 65
    if value == "rising":
        return 30
    return 0


def _score_vix(value: Any) -> float:
    if value is None:
        return 0
    if value < 18:
        return 85
    if value < 25:
        return 70
    if value < 30:
        return 45
    return 20


def _score_equity_drawdown(value: Any) -> float:
    if value is None:
        return 0
    if value >= -5:
        return 80
    if value >= -10:
        return 65
    if value >= -20:
        return 45
    return 25


def _score_trend(value: Any, *, rising: float, stable: float, falling: float) -> float:
    if value == "rising":
        return rising
    if value == "stable":
        return stable
    if value == "falling":
        return falling
    return 0


def _score_trough_gain(value: Any) -> float:
    if value is None:
        return 0
    if value < 10:
        return 55
    if value < 30:
        return 70
    if value <= 50:
        return 55
    return 40


def build_macro_components(data: dict[str, Any]) -> list[MacroIndicatorComponent]:
    vix = data.get("vix")
    fed_funds_rate = data.get("fed_funds_rate")
    spread = data.get("ten_year_minus_two_year_spread_bps")
    unemployment = data.get("unemployment_rate")
    unemployment_trend = data.get("unemployment_trend")
    cpi = data.get("cpi_yoy")
    ppi = data.get("ppi_yoy")
    fed = data.get("fed_policy_trend")
    dxy = data.get("dxy_trend")
    gold = data.get("gold_trend")
    oil = data.get("oil_trend")
    sp500_drawdown = data.get("sp500_drawdown_pct")
    nasdaq_drawdown = data.get("nasdaq_drawdown_pct")
    component_status = data.get("component_source_status", {})
    equity_trend = data.get("equity_trend")
    max_drawdown = min(v for v in [sp500_drawdown, nasdaq_drawdown] if v is not None) if sp500_drawdown is not None or nasdaq_drawdown is not None else None
    max_gain = max(
        v
        for v in [data.get("sp500_gain_from_trough_pct"), data.get("nasdaq_gain_from_trough_pct")]
        if v is not None
    ) if data.get("sp500_gain_from_trough_pct") is not None or data.get("nasdaq_gain_from_trough_pct") is not None else None
    return [
        _component("fed_policy_trend", fed, _score_fed_policy(fed), {"fed_policy_trend": fed}, {"supportive_values": ["easing", "neutral"]}, {"fed_policy": fed}, component_status.get("fed_policy_trend")),
        _component("fed_funds_rate", fed_funds_rate, _score_fed_funds_rate(fed_funds_rate), {"fed_funds_rate": fed_funds_rate}, {"low_rate_supportive_max_pct": 2.5, "restrictive_rate_min_pct": 5.5}, {"fed_funds_rate": "restrictive" if fed_funds_rate is not None and fed_funds_rate > 5.5 else "normal"}, component_status.get("fed_funds_rate")),
        _component("ten_year_minus_two_year_spread_bps", spread, _score_yield_spread(spread), {"yield_curve_inverted": spread is not None and spread < 0}, {"inversion_threshold_bps": 0}, {"yield_curve": "inverted" if spread is not None and spread < 0 else "normal"}, component_status.get("ten_year_minus_two_year_spread_bps")),
        _component("cpi_yoy", cpi, _score_inflation(cpi), {"inflation_pressure": cpi is not None and cpi >= 4}, {"pressure_threshold_pct": 4}, {"cpi": "elevated" if cpi is not None and cpi >= 4 else "contained"}, component_status.get("cpi_yoy")),
        _component("ppi_yoy", ppi, _score_inflation(ppi), {"producer_inflation_pressure": ppi is not None and ppi >= 4}, {"pressure_threshold_pct": 4}, {"ppi": "elevated" if ppi is not None and ppi >= 4 else "contained"}, component_status.get("ppi_yoy")),
        _component("unemployment_rate", unemployment, _score_unemployment_rate(unemployment), {"unemployment_rate": unemployment}, {"resilience_threshold_pct": 4, "stress_threshold_pct": 6}, {"unemployment_rate": "low" if unemployment is not None and unemployment <= 4 else "elevated"}, component_status.get("unemployment_rate")),
        _component("unemployment_trend", unemployment_trend, _score_unemployment_trend(unemployment_trend), {"unemployment_trend": unemployment_trend}, {"resilience_values": ["falling", "stable"]}, {"unemployment": unemployment_trend}, component_status.get("unemployment_trend")),
        _component("vix", vix, _score_vix(vix), {"vix_elevated": vix is not None and vix >= 25, "vix_trend": data.get("vix_trend")}, {"elevated": 25, "high": 30}, {"vix": data.get("vix_trend")}, component_status.get("vix")),
        _component("equity_drawdown", max_drawdown, _score_equity_drawdown(max_drawdown), {"max_index_drawdown_pct": max_drawdown, "equity_trend": equity_trend}, {"correction_drawdown_pct": -10, "deep_drawdown_pct": -20}, {"equities": equity_trend}, component_status.get("equity_drawdown")),
        _component("dxy_trend", dxy, _score_trend(dxy, rising=45, stable=65, falling=75), {"dxy_trend": dxy}, {"risk_pressure_value": "rising"}, {"dxy": dxy}, component_status.get("dxy_trend")),
        _component("gold_trend", gold, _score_trend(gold, rising=50, stable=70, falling=65), {"gold_trend": gold}, {"defensive_flow_value": "rising"}, {"gold": gold}, component_status.get("gold_trend")),
        _component("oil_trend", oil, _score_trend(oil, rising=40, stable=65, falling=75), {"oil_trend": oil}, {"inflation_pressure_value": "rising"}, {"oil": oil}, component_status.get("oil_trend")),
        _component("gain_from_recent_trough", max_gain, _score_trough_gain(max_gain), {"max_gain_from_trough_pct": max_gain}, {"constructive_recovery_min_pct": 10, "extended_rebound_threshold_pct": 30}, {"trough_rebound": "extended" if max_gain is not None and max_gain >= 30 else "normal"}, component_status.get("gain_from_recent_trough")),
    ]
