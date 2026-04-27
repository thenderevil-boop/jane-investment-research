from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_crisis import MOCK_CRISIS_SOURCE, MOCK_CRISIS_SOURCE_DATE
from backend.app.schemas.crisis import CrisisComponent

LIMITATION = "Phase 5 mock crisis feature; no live source connection."


def _confidence(value: Any) -> float:
    return 0.88 if value is not None else 0.45


def _component(
    name: str,
    value: Any,
    score: float,
    derived_metrics: dict[str, Any],
    benchmark: dict[str, Any],
    trend: dict[str, Any],
) -> CrisisComponent:
    missing = [] if value is not None else [name]
    return CrisisComponent(
        name=name,
        score=score if value is not None else 0,
        raw_data={name: value},
        derived_metrics=derived_metrics,
        benchmark=benchmark,
        trend=trend,
        source=MOCK_CRISIS_SOURCE,
        source_date=MOCK_CRISIS_SOURCE_DATE,
        confidence=_confidence(value),
        limitations=[LIMITATION],
        missing_data=missing,
    )


def build_crisis_components(data: dict[str, Any]) -> list[CrisisComponent]:
    vix = data.get("vix")
    oil_spike = data.get("oil_price_spike_5d_pct")
    gold_spike = data.get("gold_price_spike_5d_pct")
    dxy_spike = data.get("dxy_spike_5d_pct")
    news_count = data.get("geopolitical_news_count")
    news_benchmark = data.get("geopolitical_news_count_benchmark")
    severity = data.get("geopolitical_news_severity")
    return [
        _component("vix_spike", vix, 100 if vix is not None and vix >= 40 else 80 if vix is not None and vix >= 30 else 60 if vix is not None and vix >= 25 else 10, {"vix": vix, "vix_spike_pct": data.get("vix_spike_pct")}, {"elevated": 25, "high": 30, "severe": 40}, {"vix": "rising" if data.get("vix_spike_pct", 0) and data.get("vix_spike_pct", 0) > 10 else "stable"}),
        _component("oil_price_spike_5d_pct", oil_spike, 100 if oil_spike is not None and oil_spike >= 10 else 70 if oil_spike is not None and oil_spike >= 5 else 10, {"oil_price_spike_5d_pct": oil_spike}, {"elevated_spike_pct": 5, "severe_spike_pct": 10}, {"oil": "spiking" if oil_spike is not None and oil_spike >= 5 else "stable"}),
        _component("gold_price_spike_5d_pct", gold_spike, 75 if gold_spike is not None and gold_spike >= 3 else 20, {"gold_price_spike_5d_pct": gold_spike}, {"strong_rise_pct": 3}, {"gold": "rising_strongly" if gold_spike is not None and gold_spike >= 3 else "stable"}),
        _component("dxy_spike_5d_pct", dxy_spike, 75 if dxy_spike is not None and dxy_spike >= 3 else 20, {"dxy_spike_5d_pct": dxy_spike}, {"strong_rise_pct": 3}, {"dxy": "rising_strongly" if dxy_spike is not None and dxy_spike >= 3 else "stable"}),
        _component("treasury_yield_movement", data.get("treasury_yield_movement"), 60 if data.get("treasury_yield_movement") == "falling" else 20, {"treasury_yield_movement": data.get("treasury_yield_movement")}, {"defensive_flow_value": "falling"}, {"treasury": data.get("treasury_yield_movement")}),
        _component("geopolitical_news_count", news_count, 80 if news_count is not None and news_benchmark is not None and news_count > news_benchmark else 20, {"geopolitical_news_count": news_count, "benchmark": news_benchmark}, {"above_benchmark": news_benchmark}, {"geopolitical_news": "above_benchmark" if news_count is not None and news_benchmark is not None and news_count > news_benchmark else "normal"}),
        _component("geopolitical_news_severity", severity, 100 if severity == "high" else 75 if severity == "medium" else 20 if severity == "low" else 0, {"geopolitical_news_severity": severity}, {"high_values": ["medium", "high"]}, {"severity": severity}),
        _component("defense_energy_relative_strength", data.get("defense_energy_relative_strength"), 70 if data.get("defense_energy_relative_strength") in {"firm", "strong"} else 20, {"defense_energy_relative_strength": data.get("defense_energy_relative_strength")}, {"watch_values": ["firm", "strong"]}, {"defense_energy": data.get("defense_energy_relative_strength")}),
        _component("global_equity_volatility", data.get("global_equity_volatility"), 85 if data.get("global_equity_volatility") in {"high", "severe"} else 55 if data.get("global_equity_volatility") == "elevated" else 15, {"global_equity_volatility": data.get("global_equity_volatility")}, {"high_values": ["high", "severe"]}, {"global_equity_volatility": data.get("global_equity_volatility")}),
    ]
