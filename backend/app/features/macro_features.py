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


def build_macro_components(data: dict[str, Any]) -> list[MacroIndicatorComponent]:
    vix = data.get("vix")
    spread = data.get("ten_year_minus_two_year_spread_bps")
    unemployment = data.get("unemployment_rate")
    unemployment_trend = data.get("unemployment_trend")
    ism = data.get("ism_manufacturing_pmi")
    cpi = data.get("cpi_yoy")
    ppi = data.get("ppi_yoy")
    fed = data.get("fed_policy_trend")
    dxy = data.get("dxy_trend")
    gold = data.get("gold_trend")
    oil = data.get("oil_trend")
    sp500_drawdown = data.get("sp500_drawdown_pct")
    nasdaq_drawdown = data.get("nasdaq_drawdown_pct")
    fear_greed = data.get("fear_greed")
    component_status = data.get("component_source_status", {})
    equity_trend = data.get("equity_trend")
    max_drawdown = min(v for v in [sp500_drawdown, nasdaq_drawdown] if v is not None) if sp500_drawdown is not None or nasdaq_drawdown is not None else None
    max_gain = max(
        v
        for v in [data.get("sp500_gain_from_trough_pct"), data.get("nasdaq_gain_from_trough_pct")]
        if v is not None
    ) if data.get("sp500_gain_from_trough_pct") is not None or data.get("nasdaq_gain_from_trough_pct") is not None else None
    return [
        _component("vix", vix, 100 if vix is not None and vix >= 40 else 80 if vix is not None and vix >= 30 else 50 if vix is not None and vix >= 25 else 10, {"vix_elevated": vix is not None and vix >= 25, "vix_trend": data.get("vix_trend")}, {"elevated": 25, "high": 30, "severe": 40}, {"vix": data.get("vix_trend")}, component_status.get("vix")),
        _component("ten_year_minus_two_year_spread_bps", spread, 80 if spread is not None and spread < 0 else 10, {"yield_curve_inverted": spread is not None and spread < 0}, {"inversion_threshold_bps": 0}, {"yield_curve": "inverted" if spread is not None and spread < 0 else "normal"}, component_status.get("ten_year_minus_two_year_spread_bps")),
        _component("unemployment_rate", unemployment, 70 if unemployment_trend == "rising" else 20, {"unemployment_trend": unemployment_trend}, {"rising_trend_flag": "rising"}, {"unemployment": unemployment_trend}, component_status.get("unemployment_rate")),
        _component("ism_manufacturing_pmi", ism, 75 if ism is not None and ism < 50 else 15, {"below_50": ism is not None and ism < 50}, {"contraction_threshold": 50}, {"manufacturing": "contracting" if ism is not None and ism < 50 else "expanding"}, component_status.get("ism_manufacturing_pmi")),
        _component("cpi_yoy", cpi, 80 if cpi is not None and cpi >= 4 else 20, {"inflation_pressure": cpi is not None and cpi >= 4}, {"pressure_threshold_pct": 4}, {"cpi": "elevated" if cpi is not None and cpi >= 4 else "contained"}, component_status.get("cpi_yoy")),
        _component("ppi_yoy", ppi, 80 if ppi is not None and ppi >= 4 else 20, {"producer_inflation_pressure": ppi is not None and ppi >= 4}, {"pressure_threshold_pct": 4}, {"ppi": "elevated" if ppi is not None and ppi >= 4 else "contained"}, component_status.get("ppi_yoy")),
        _component("fed_policy_trend", fed, 70 if fed == "easing" else 35 if fed == "neutral" else 60 if fed in {"restrictive", "tightening"} else 0, {"fed_policy_trend": fed}, {"supportive_values": ["easing", "neutral"]}, {"fed_policy": fed}, component_status.get("fed_policy_trend")),
        _component("dxy_trend", dxy, 60 if dxy == "rising" else 20, {"dxy_trend": dxy}, {"risk_pressure_value": "rising"}, {"dxy": dxy}, component_status.get("dxy_trend")),
        _component("gold_trend", gold, 50 if gold == "rising" else 20, {"gold_trend": gold}, {"defensive_flow_value": "rising"}, {"gold": gold}, component_status.get("gold_trend")),
        _component("oil_trend", oil, 70 if oil == "rising" else 20, {"oil_trend": oil}, {"inflation_pressure_value": "rising"}, {"oil": oil}, component_status.get("oil_trend")),
        _component("equity_drawdown", max_drawdown, 90 if max_drawdown is not None and max_drawdown <= -20 else 60 if max_drawdown is not None and max_drawdown <= -10 else 10, {"max_index_drawdown_pct": max_drawdown, "equity_trend": equity_trend}, {"stress_drawdown_pct": -10, "deep_drawdown_pct": -20}, {"equities": equity_trend}, component_status.get("equity_drawdown")),
        _component("gain_from_recent_trough", max_gain, 80 if max_gain is not None and max_gain >= 30 else 20, {"max_gain_from_trough_pct": max_gain}, {"overheated_gain_threshold_pct": 30}, {"trough_rebound": "extended" if max_gain is not None and max_gain >= 30 else "normal"}, component_status.get("gain_from_recent_trough")),
        _component("fear_greed", fear_greed, 80 if fear_greed is not None and fear_greed <= 25 else 80 if fear_greed is not None and fear_greed >= 75 else 20, {"extreme_fear": fear_greed is not None and fear_greed <= 25, "greed_elevated": fear_greed is not None and fear_greed >= 75}, {"fear_threshold": 25, "greed_threshold": 75}, {"sentiment": "fear" if fear_greed is not None and fear_greed <= 25 else "greed" if fear_greed is not None and fear_greed >= 75 else "neutral"}, component_status.get("fear_greed")),
    ]
