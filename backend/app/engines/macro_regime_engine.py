from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_macro import MOCK_MACRO_SOURCE, MOCK_MACRO_SOURCE_DATE
from backend.app.features.macro_features import build_macro_components
from backend.app.schemas.macro_regime import MacroDataQuality, MacroRegimeOutput
from backend.app.utils.freshness import build_source_status

LIMITATION = "Phase 5 deterministic mock macro regime engine; no live source connection."
FRED_BACKED_FIELDS = [
    "fed_funds_rate",
    "ten_year_yield",
    "two_year_yield",
    "unemployment_rate",
]
DERIVED_FROM_FRED_FIELDS = [
    "cpi_yoy",
    "ppi_yoy",
    "ten_year_minus_two_year_spread_bps",
    "fed_policy_trend",
    "unemployment_trend",
]
MOCK_CONTEXT_FIELDS = [
    "vix",
    "ism_manufacturing_pmi",
    "dxy_trend",
    "gold_trend",
    "oil_trend",
    "fear_greed",
    "equity_drawdown",
    "gain_from_recent_trough",
]
YFINANCE_BACKED_FIELDS = ["vix"]
DERIVED_FROM_YFINANCE_FIELDS = [
    "vix_trend",
    "dxy_trend",
    "gold_trend",
    "oil_trend",
    "equity_drawdown",
    "gain_from_recent_trough",
]
MOCK_CONTEXT_LIMITATION = "This field remains mock context in Phase 9 and is not live market evidence."
MOCK_CONTEXT_UNAVAILABLE_LIMITATION = "This field remains mock context because live market context was unavailable."
FRED_CLARITY_LIMITATIONS = [
    "FRED-backed macro fields are live or derived from live/cached FRED data.",
    "Fear & Greed and ISM Manufacturing PMI remain mock context until live providers are added.",
    "Macro confidence is adjusted when mock context fields contribute to the score.",
]
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


def _component_names_by_source(components: list[Any]) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    fred_backed: list[str] = []
    fred_derived: list[str] = []
    yfinance_backed: list[str] = []
    yfinance_derived: list[str] = []
    mock_context: list[str] = []
    for component in components:
        status = component.source_status
        name = component.name
        if name in FRED_BACKED_FIELDS and status and status.source_type in {"live", "cached_live"} and status.provider == "FRED":
            fred_backed.append(name)
        elif name in DERIVED_FROM_FRED_FIELDS and status and status.provider == "derived_from_FRED":
            fred_derived.append(name)
        elif name in YFINANCE_BACKED_FIELDS and status and status.source_type in {"live", "cached_live", "derived"} and status.provider in {"yfinance", "derived_from_yfinance"}:
            yfinance_backed.append(name)
        elif name in DERIVED_FROM_YFINANCE_FIELDS and status and status.provider == "derived_from_yfinance":
            yfinance_derived.append(name)
        elif name in MOCK_CONTEXT_FIELDS or (status and status.source_type == "mock"):
            mock_context.append(name)
    return sorted(set(fred_backed)), sorted(set(fred_derived)), sorted(set(yfinance_backed)), sorted(set(yfinance_derived)), sorted(set(mock_context))


def _score_weight_pct(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total * 100, 2)


def _build_macro_data_quality(data: dict[str, Any], components: list[Any], limitations: list[str]) -> MacroDataQuality:
    fred_backed, fred_derived, yfinance_backed, yfinance_derived, mock_context = _component_names_by_source(components)
    component_status = data.get("component_source_status", {}) if isinstance(data.get("component_source_status"), dict) else {}
    for field in FRED_BACKED_FIELDS:
        status = component_status.get(field, {}) if isinstance(component_status.get(field), dict) else {}
        if data.get(field) is not None and (status.get("source_type") in {"live", "cached_live"} or status.get("provider") == "FRED"):
            fred_backed.append(field)
    for field in DERIVED_FROM_FRED_FIELDS:
        status = component_status.get(field, {}) if isinstance(component_status.get(field), dict) else {}
        if data.get(field) is not None and (status.get("source_type") == "derived" or status.get("provider") == "derived_from_FRED"):
            fred_derived.append(field)
    for field in YFINANCE_BACKED_FIELDS:
        status = component_status.get(field, {}) if isinstance(component_status.get(field), dict) else {}
        if data.get(field) is not None and status.get("provider") in {"yfinance", "derived_from_yfinance"}:
            yfinance_backed.append(field)
    for field in DERIVED_FROM_YFINANCE_FIELDS:
        status = component_status.get(field, {}) if isinstance(component_status.get(field), dict) else {}
        value_present = field in {"equity_drawdown", "gain_from_recent_trough"} or data.get(field) is not None
        if value_present and status.get("provider") == "derived_from_yfinance":
            yfinance_derived.append(field)
    fred_backed = sorted(set(fred_backed))
    fred_derived = sorted(set(fred_derived))
    yfinance_backed = sorted(set(yfinance_backed))
    yfinance_derived = sorted(set(yfinance_derived))
    mock_context = sorted(set(mock_context))
    total = len(set([*fred_backed, *fred_derived, *yfinance_backed, *yfinance_derived, *mock_context]))
    mock_pct = _score_weight_pct(len(mock_context), total)
    fred_pct = _score_weight_pct(len(fred_backed) + len(fred_derived), total)
    live_context_pct = _score_weight_pct(len(fred_backed) + len(fred_derived) + len(yfinance_backed) + len(yfinance_derived), total)
    return MacroDataQuality(
        fred_backed_fields=fred_backed,
        mock_context_fields=mock_context,
        derived_from_fred_fields=fred_derived,
        yfinance_backed_fields=yfinance_backed,
        derived_from_yfinance_fields=yfinance_derived,
        live_macro_fields_count=len(fred_backed) + len(yfinance_backed),
        mock_macro_fields_count=len(mock_context),
        derived_macro_fields_count=len(fred_derived) + len(yfinance_derived),
        yfinance_macro_fields_count=len(yfinance_backed) + len(yfinance_derived),
        has_mock_macro_context=bool(mock_context),
        mock_context_score_weight_pct=mock_pct,
        fred_backed_score_weight_pct=fred_pct,
        live_or_cached_context_score_weight_pct=live_context_pct,
        confidence_adjustment_applied=mock_pct >= 40,
        limitations=sorted(set(limitations)),
    )


def _adjust_macro_confidence(confidence: float, macro_data_quality: MacroDataQuality) -> float:
    if not macro_data_quality.confidence_adjustment_applied:
        return confidence
    cap = 0.78
    if macro_data_quality.mock_context_score_weight_pct >= 60:
        cap = 0.70
    return round(min(confidence, cap), 2)


def _source_contribution(components: list[Any], macro_data_quality: MacroDataQuality, total_score: float) -> dict[str, Any]:
    by_name = {component.name: component for component in components}

    def score_sum(names: list[str]) -> float:
        return round(sum(float(by_name[name].score) for name in names if name in by_name), 2)

    return {
        "fred_backed_score": score_sum(macro_data_quality.fred_backed_fields),
        "fred_derived_score": score_sum(macro_data_quality.derived_from_fred_fields),
        "yfinance_backed_score": score_sum(macro_data_quality.yfinance_backed_fields),
        "yfinance_derived_score": score_sum(macro_data_quality.derived_from_yfinance_fields),
        "mock_context_score": score_sum(macro_data_quality.mock_context_fields),
        "total_score": round(total_score, 2),
        "mock_context_component_names": macro_data_quality.mock_context_fields,
        "fred_component_names": macro_data_quality.fred_backed_fields,
        "derived_from_fred_component_names": macro_data_quality.derived_from_fred_fields,
        "yfinance_component_names": macro_data_quality.yfinance_backed_fields,
        "derived_from_yfinance_component_names": macro_data_quality.derived_from_yfinance_fields,
    }


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
    incoming_source_status = data.get("source_status", {}) if isinstance(data.get("source_status"), dict) else {}
    is_mixed_fred_macro = str(data.get("provider") or "").startswith("mixed_")
    if is_mixed_fred_macro:
        limitations = sorted(
            set(
                [
                    *limitations,
                    *FRED_CLARITY_LIMITATIONS,
                ]
            )
        )
    macro_data_quality = _build_macro_data_quality(data, components, limitations if is_mixed_fred_macro else data.get("limitations", [LIMITATION]))
    if macro_data_quality.has_mock_macro_context:
        if is_mixed_fred_macro:
            limitations = sorted(set([*limitations, *FRED_CLARITY_LIMITATIONS]))
        for component in components:
            if component.name in macro_data_quality.mock_context_fields:
                component.limitations = sorted(set([*component.limitations, MOCK_CONTEXT_LIMITATION]))
                if component.source_status:
                    component.source_status.fallback_used = False
                    component.source_status.limitations = sorted(set([*component.source_status.limitations, MOCK_CONTEXT_LIMITATION]))
        macro_data_quality = _build_macro_data_quality(data, components, limitations)
    confidence = _adjust_macro_confidence(confidence, macro_data_quality)
    source_status = build_source_status(
        {
            "source_type": "derived" if is_mixed_fred_macro else data.get("source_type", "mock"),
            "provider": data.get("provider", "mixed_FRED_and_mock_macro") if is_mixed_fred_macro else data.get("provider", "phase5_mock_macro_dataset"),
            "source_date": source_date,
            "fetched_at": data.get("fetched_at"),
            "is_fresh": incoming_source_status.get("is_fresh"),
            "fallback_used": data.get("fallback_used") or incoming_source_status.get("fallback_used"),
            "fallback_reason": data.get("fallback_reason") or incoming_source_status.get("fallback_reason"),
            "limitations": limitations,
            "missing_data": data.get("missing_data", []),
        },
        freshness_window=incoming_source_status.get("freshness_window", "macro_release_schedule"),
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
            "source_contribution": _source_contribution(components, macro_data_quality, score),
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
        macro_data_quality=macro_data_quality,
    )
