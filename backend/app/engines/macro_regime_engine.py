from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_macro import MOCK_MACRO_SOURCE, MOCK_MACRO_SOURCE_DATE
from backend.app.features.macro_features import build_macro_components
from backend.app.schemas.macro_regime import MacroRegimeOutput
from backend.app.utils.freshness import build_source_status

LIMITATION = "Phase 5 deterministic mock macro regime engine; no live source connection."
REQUIRED_FIELDS = [
    "vix",
    "ten_year_minus_two_year_spread_bps",
    "unemployment_rate",
    "unemployment_trend",
    "ism_manufacturing_pmi",
    "cpi_yoy",
    "ppi_yoy",
    "fed_policy_trend",
    "dxy_trend",
    "gold_trend",
    "oil_trend",
    "sp500_drawdown_pct",
    "nasdaq_drawdown_pct",
    "fear_greed",
]


def _missing_required(data: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if data.get(field) is None]


def _max_drawdown(data: dict[str, Any]) -> float | None:
    values = [data.get("sp500_drawdown_pct"), data.get("nasdaq_drawdown_pct")]
    values = [value for value in values if value is not None]
    return min(values) if values else None


def _max_gain_from_trough(data: dict[str, Any]) -> float | None:
    values = [data.get("sp500_gain_from_trough_pct"), data.get("nasdaq_gain_from_trough_pct")]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _classify(data: dict[str, Any]) -> tuple[str, float]:
    missing = _missing_required(data)
    if len(missing) > 5:
        return "insufficient_data", 0
    vix = data.get("vix")
    spread = data.get("ten_year_minus_two_year_spread_bps")
    unemployment_trend = data.get("unemployment_trend")
    ism = data.get("ism_manufacturing_pmi")
    cpi = data.get("cpi_yoy")
    ppi = data.get("ppi_yoy")
    fed = data.get("fed_policy_trend")
    oil = data.get("oil_trend")
    fear_greed = data.get("fear_greed")
    max_drawdown = _max_drawdown(data)
    max_gain = _max_gain_from_trough(data)
    equity_trend = data.get("equity_trend")
    vix_trend = data.get("vix_trend")
    if unemployment_trend == "rising" and ism is not None and ism < 50 and max_drawdown is not None and max_drawdown <= -20:
        return "recession_confirmed", 92
    if vix is not None and vix >= 30 and max_drawdown is not None and max_drawdown <= -10 and (fear_greed is None or fear_greed <= 25):
        return "fear_crisis", 88
    if spread is not None and spread < 0 and ((ism is not None and ism < 50) or unemployment_trend == "rising"):
        return "recession_warning", 78
    if ((cpi is not None and cpi >= 4) or (ppi is not None and ppi >= 4)) and oil == "rising":
        return "inflation_pressure", 74
    if vix_trend == "falling" and ism is not None and ism >= 50 and equity_trend == "recovering" and fed in {"easing", "neutral"}:
        return "recovery", 72
    if max_gain is not None and max_gain >= 30 and (fear_greed is None or fear_greed >= 75):
        return "overheated", 82
    return "normal", 55


def evaluate_macro_regime(data: dict[str, Any]) -> MacroRegimeOutput:
    components = build_macro_components(data)
    missing = sorted(set(_missing_required(data) + [item for component in components for item in component.missing_data]))
    label, score = _classify(data)
    confidence = 0.35 if label == "insufficient_data" else round(sum(component.confidence for component in components) / len(components), 2)
    source = data.get("source", MOCK_MACRO_SOURCE)
    if isinstance(source, str):
        source = [source]
    source_date = data.get("source_date", MOCK_MACRO_SOURCE_DATE)
    limitations = list(data.get("limitations", [LIMITATION]))
    if data.get("source_type") == "live":
        limitations = sorted(
            set(
                [
                    *limitations,
                    "FRED-backed macro fields are live; ISM, DXY, gold, oil, Fear & Greed, and equity context remain mock in Phase 9.",
                ]
            )
        )
    source_status = build_source_status(
        {
            "source_type": "derived" if data.get("source_type") == "live" else data.get("source_type", "mock"),
            "provider": "mixed_FRED_and_mock_macro" if data.get("source_type") == "live" else data.get("provider", "phase5_mock_macro_dataset"),
            "source_date": source_date,
            "fetched_at": data.get("fetched_at"),
            "is_fresh": data.get("source_status", {}).get("is_fresh") if isinstance(data.get("source_status"), dict) else None,
            "fallback_used": data.get("fallback_used"),
            "fallback_reason": data.get("fallback_reason"),
            "limitations": limitations,
            "missing_data": data.get("missing_data", []),
        },
        freshness_window=data.get("source_status", {}).get("freshness_window", "macro_release_schedule") if isinstance(data.get("source_status"), dict) else "macro_release_schedule",
    )
    return MacroRegimeOutput(
        score=score,
        label=label,
        raw_data={field: data.get(field) for field in sorted(data.keys())},
        derived_metrics={
            "max_index_drawdown_pct": _max_drawdown(data),
            "max_gain_from_recent_trough_pct": _max_gain_from_trough(data),
            "missing_required_count": len(_missing_required(data)),
            "component_count": len(components),
        },
        benchmark={
            "fear_crisis_vix": 30,
            "fear_crisis_drawdown_pct": -10,
            "recession_ism_threshold": 50,
            "inflation_pressure_yoy_pct": 4,
            "overheated_gain_from_trough_pct": 30,
        },
        trend={
            "vix": data.get("vix_trend"),
            "unemployment": data.get("unemployment_trend"),
            "fed_policy": data.get("fed_policy_trend"),
            "equities": data.get("equity_trend"),
        },
        source=source,
        source_date=source_date,
        confidence=confidence,
        components=components,
        limitations=limitations,
        missing_data=missing,
        source_status=source_status,
    )
