from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_macro import MOCK_MACRO_SOURCE, MOCK_MACRO_SOURCE_DATE
from backend.app.features.macro_features import build_macro_components
from backend.app.schemas.macro_regime import MacroDataQuality, MacroRegimeOutput
from backend.app.utils.freshness import build_source_status

LIMITATION = "Phase 5 deterministic mock macro regime engine; no live source connection."
ISM_PMI_EXCLUSION_NOTE = "ISM Manufacturing PMI is excluded from scoring because no valid licensed/live source is configured."
SCORING_MODEL_VERSION = "macro_v12_5"
MACRO_SCORING_GROUPS = [
    {
        "name": "rates_and_policy",
        "weight": 25,
        "components": [
            {"name": "fed_policy_trend", "weight": 10},
            {"name": "fed_funds_rate", "weight": 5},
            {"name": "ten_year_minus_two_year_spread_bps", "weight": 10},
        ],
    },
    {
        "name": "inflation_pressure",
        "weight": 20,
        "components": [
            {"name": "cpi_yoy", "weight": 10},
            {"name": "ppi_yoy", "weight": 10},
        ],
    },
    {
        "name": "labor_recession_resilience",
        "weight": 15,
        "components": [
            {"name": "unemployment_rate", "weight": 8},
            {"name": "unemployment_trend", "weight": 7},
        ],
    },
    {
        "name": "market_stress_volatility",
        "weight": 15,
        "components": [
            {"name": "vix", "weight": 10},
            {"name": "equity_drawdown", "weight": 5},
        ],
    },
    {
        "name": "cross_asset_risk_context",
        "weight": 15,
        "components": [
            {"name": "dxy_trend", "weight": 5},
            {"name": "gold_trend", "weight": 5},
            {"name": "oil_trend", "weight": 5},
        ],
    },
    {
        "name": "rebound_market_recovery",
        "weight": 10,
        "components": [
            {"name": "gain_from_recent_trough", "weight": 10},
        ],
    },
]
ACTIVE_COMPONENT_WEIGHTS = {
    component["name"]: (group["name"], component["weight"])
    for group in MACRO_SCORING_GROUPS
    for component in group["components"]
}
ACTIVE_COMPONENT_NAMES = list(ACTIVE_COMPONENT_WEIGHTS.keys())
EXCLUDED_INDICATORS = [
    {
        "name": "ism_manufacturing_pmi",
        "reason": "Excluded because no valid licensed/live source is configured. NAPM is invalid and IPMAN is not PMI.",
        "affects_score": False,
    },
    {
        "name": "cnn_fear_greed",
        "reason": "Excluded because no licensed/stable source is configured.",
        "affects_score": False,
    },
]
GROUP_DISPLAY_NAMES = {
    "rates_and_policy": "Rates and policy environment",
    "inflation_pressure": "Inflation pressure",
    "labor_recession_resilience": "Labor / recession resilience",
    "market_stress_volatility": "Market stress / volatility context",
    "cross_asset_risk_context": "Cross-asset risk context",
    "rebound_market_recovery": "Rebound / market recovery context",
}
COMPONENT_DISPLAY_NAMES = {
    "fed_policy_trend": "Fed policy trend",
    "fed_funds_rate": "Fed funds rate",
    "ten_year_minus_two_year_spread_bps": "10Y-2Y spread",
    "cpi_yoy": "CPI YoY",
    "ppi_yoy": "PPI YoY",
    "unemployment_rate": "Unemployment rate",
    "unemployment_trend": "Unemployment trend",
    "vix": "VIX",
    "equity_drawdown": "Equity drawdown",
    "dxy_trend": "DXY trend",
    "gold_trend": "Gold trend",
    "oil_trend": "Oil trend",
    "gain_from_recent_trough": "Gain from recent trough",
}
EXCLUDED_INDICATOR_DISPLAY_NAMES = {
    "ism_manufacturing_pmi": "ISM Manufacturing PMI",
    "cnn_fear_greed": "CNN Fear & Greed",
}
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
CONTEXT_ONLY_FRED_FIELDS = ["consumer_sentiment"]
MOCK_CONTEXT_FIELDS = [
    "vix",
    "dxy_trend",
    "gold_trend",
    "oil_trend",
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
    "Macro confidence is adjusted when mock context fields contribute to the score.",
]
REQUIRED_FIELDS = [
    "vix",
    "fed_funds_rate",
    "ten_year_minus_two_year_spread_bps",
    "unemployment_rate",
    "unemployment_trend",
    "cpi_yoy",
    "ppi_yoy",
    "fed_policy_trend",
    "dxy_trend",
    "gold_trend",
    "oil_trend",
    "sp500_drawdown_pct",
    "nasdaq_drawdown_pct",
    "sp500_gain_from_trough_pct",
    "nasdaq_gain_from_trough_pct",
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
    cpi = data.get("cpi_yoy")
    ppi = data.get("ppi_yoy")
    fed = data.get("fed_policy_trend")
    oil = data.get("oil_trend")
    max_drawdown = _max_drawdown(data)
    max_gain = _max_gain_from_trough(data)
    equity_trend = data.get("equity_trend")
    vix_trend = data.get("vix_trend")
    if unemployment_trend == "rising" and max_drawdown is not None and max_drawdown <= -20:
        return "recession_confirmed", 92
    if vix is not None and vix >= 30 and max_drawdown is not None and max_drawdown <= -10:
        return "fear_crisis", 88
    if spread is not None and spread < 0 and unemployment_trend == "rising":
        return "recession_warning", 78
    if ((cpi is not None and cpi >= 4) or (ppi is not None and ppi >= 4)) and oil == "rising":
        return "inflation_pressure", 74
    if vix_trend == "falling" and equity_trend == "recovering" and fed in {"easing", "neutral"}:
        return "recovery", 72
    if max_gain is not None and max_gain >= 30:
        return "overheated", 82
    return "normal", 55


def _score_label(score: float, missing_active_components: list[str]) -> str:
    if len(missing_active_components) > 6:
        return "insufficient_data"
    if score <= 30:
        return "restrictive_or_stress"
    if score <= 55:
        return "cautious"
    if score <= 75:
        return "neutral_to_constructive"
    return "supportive_macro_backdrop"


def _scoring_model() -> dict[str, Any]:
    excluded = [
        {
            **indicator,
            "weight": 0,
        }
        for indicator in EXCLUDED_INDICATORS
    ]
    return {
        "version": SCORING_MODEL_VERSION,
        "total_weight": 100,
        "groups": MACRO_SCORING_GROUPS,
        "excluded_indicators": excluded,
        "score_normalization": "weighted_component_score",
    }


def _component_display_name(name: str) -> str:
    return COMPONENT_DISPLAY_NAMES.get(name, name.replace("_", " ").title())


def _group_display_name(name: str) -> str:
    return GROUP_DISPLAY_NAMES.get(name, name.replace("_", " ").title())


def _excluded_indicators_with_display(indicators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **indicator,
            "display_name": EXCLUDED_INDICATOR_DISPLAY_NAMES.get(str(indicator.get("name")), str(indicator.get("name"))),
            "affects_score": False,
            "weight": 0,
        }
        for indicator in indicators
    ]


def _component_value(component: Any) -> Any:
    return component.raw_data.get(component.name)


def _status_payload(component: Any) -> dict[str, Any]:
    if component.source_status is None:
        return {
            "source_type": "unknown",
            "provider": "unknown",
            "source_date": component.source_date,
            "is_fresh": False,
            "fallback_used": False,
            "fallback_reason": None,
        }
    return component.source_status.model_dump(mode="json")


def _component_contributions(components: list[Any]) -> list[dict[str, Any]]:
    by_name = {component.name: component for component in components}
    contributions: list[dict[str, Any]] = []
    for name, (group, weight) in ACTIVE_COMPONENT_WEIGHTS.items():
        component = by_name.get(name)
        if component is None:
            contributions.append(
                {
                    "name": name,
                    "display_name": _component_display_name(name),
                    "group": group,
                    "weight": weight,
                    "raw_value": None,
                    "component_score": 0,
                    "weighted_contribution": 0,
                    "source_type": "unknown",
                    "provider": "unknown",
                    "source_date": "",
                    "freshness_window": "unknown",
                    "is_fresh": False,
                    "limitation": "active macro component unavailable",
                }
            )
            continue
        status = _status_payload(component)
        component_score = round(float(component.score), 2)
        contributions.append(
            {
                "name": name,
                "display_name": _component_display_name(name),
                "group": group,
                "weight": weight,
                "raw_value": _component_value(component),
                "component_score": component_score,
                "weighted_contribution": round(component_score * weight / 100, 4),
                "source_type": status.get("source_type", "unknown"),
                "provider": status.get("provider", "unknown"),
                "source_date": status.get("source_date") or component.source_date,
                "freshness_window": status.get("freshness_window", "unknown"),
                "is_fresh": bool(status.get("is_fresh", False)),
                "limitation": component.limitations[0] if component.limitations else None,
            }
        )
    return contributions


def _score_from_contributions(contributions: list[dict[str, Any]]) -> float:
    return round(sum(float(item["weighted_contribution"]) for item in contributions), 2)


def _scoring_quality(contributions: list[dict[str, Any]], components: list[Any], macro_data_quality: MacroDataQuality) -> dict[str, Any]:
    by_name = {component.name: component for component in components}
    missing_active: list[str] = []
    stale_active: list[str] = []
    fallback_active: list[str] = []
    cached_live_after_failure: list[str] = []
    available_weight = 0.0
    for contribution in contributions:
        name = contribution["name"]
        source_type = contribution.get("source_type")
        component = by_name.get(name)
        value_missing = contribution.get("raw_value") is None
        source_available = source_type in {"live", "cached_live", "derived"}
        if value_missing:
            missing_active.append(name)
        if not value_missing and source_available:
            available_weight += float(contribution["weight"])
        status = component.source_status if component else None
        if status and status.source_type in {"live", "cached_live", "derived", "fallback"} and not status.is_fresh:
            stale_active.append(name)
        if status and status.source_type == "fallback":
            fallback_active.append(name)
        if status and status.source_type == "cached_live" and status.fallback_used:
            cached_live_after_failure.append(name)
    return {
        "scoring_model_version": SCORING_MODEL_VERSION,
        "active_component_count": len(ACTIVE_COMPONENT_NAMES),
        "active_weight_total": 100,
        "excluded_component_count": len(EXCLUDED_INDICATORS),
        "context_only_components_count_as_missing": False,
        "excluded_indicators": [
            *_excluded_indicators_with_display(macro_data_quality.excluded_indicators)
        ],
        "missing_active_components": sorted(set(missing_active)),
        "stale_active_components": sorted(set(stale_active)),
        "fallback_active_components": sorted(set(fallback_active)),
        "cached_live_after_failure_components": sorted(set(cached_live_after_failure)),
        "active_available_weight_pct": round(available_weight, 2),
        "confidence_basis": {
            "all_active_components_available": round(available_weight, 2) == 100,
            "all_active_components_fresh": not stale_active,
            "fallback_used": bool(fallback_active),
            "cached_live_after_failure_used": bool(cached_live_after_failure),
            "mock_context_used": macro_data_quality.has_mock_macro_context,
            "excluded_indicators_count_as_missing": False,
        },
    }


def _confidence_from_scoring(scoring: dict[str, Any]) -> float:
    available_weight = float(scoring.get("active_available_weight_pct", 0))
    confidence = 0.50 + 0.45 * (available_weight / 100)
    for deduction in _confidence_deductions(scoring):
        confidence -= float(deduction["amount"])
    return round(min(0.95, max(0.50, confidence)), 2)


def _confidence_deductions(scoring: dict[str, Any]) -> list[dict[str, Any]]:
    deductions: list[dict[str, Any]] = []
    stale_components = set(scoring.get("stale_active_components", []))
    missing_components = set(scoring.get("missing_active_components", []))
    fallback_components = set(scoring.get("fallback_active_components", []))
    cached_live_after_failure = set(scoring.get("cached_live_after_failure_components", []))
    stale_market = stale_components & {"vix", "equity_drawdown", "gain_from_recent_trough", "dxy_trend", "gold_trend", "oil_trend"}
    stale_macro = stale_components & {"fed_funds_rate", "fed_policy_trend", "ten_year_minus_two_year_spread_bps", "cpi_yoy", "ppi_yoy", "unemployment_rate", "unemployment_trend"}
    if stale_market:
        deductions.append({"reason": "stale_daily_market_context", "amount": 0.05, "affected_components": sorted(stale_market)})
    if stale_macro:
        deductions.append({"reason": "stale_macro_field", "amount": 0.05, "affected_components": sorted(stale_macro)})
    if missing_components:
        deductions.append({"reason": "missing_active_component", "amount": 0.10, "affected_components": sorted(missing_components)})
    if cached_live_after_failure:
        deductions.append({"reason": "cached_live_after_failure", "amount": 0.10, "affected_components": sorted(cached_live_after_failure)})
    if fallback_components:
        deductions.append({"reason": "fallback_active_component", "amount": 0.15, "affected_components": sorted(fallback_components)})
    return deductions


def _macro_score_explanation(
    *,
    score: float,
    label: str,
    confidence: float,
    scoring_model: dict[str, Any],
    component_contributions: list[dict[str, Any]],
    scoring_quality: dict[str, Any],
    limitations: list[str],
) -> dict[str, Any]:
    by_name = {str(item["name"]): item for item in component_contributions}
    groups: list[dict[str, Any]] = []
    for group in scoring_model["groups"]:
        group_components: list[dict[str, Any]] = []
        for component_ref in group["components"]:
            contribution = by_name.get(component_ref["name"])
            if contribution is None:
                continue
            group_components.append(
                {
                    "name": contribution["name"],
                    "display_name": contribution.get("display_name") or _component_display_name(str(contribution["name"])),
                    "weight": contribution["weight"],
                    "raw_value": contribution.get("raw_value"),
                    "component_score": contribution.get("component_score"),
                    "weighted_contribution": contribution.get("weighted_contribution"),
                    "source_type": contribution.get("source_type", "unknown"),
                    "provider": contribution.get("provider", "unknown"),
                    "source_date": contribution.get("source_date", ""),
                    "freshness_window": contribution.get("freshness_window", "unknown"),
                    "is_fresh": bool(contribution.get("is_fresh", False)),
                    "limitation": contribution.get("limitation"),
                }
            )
        groups.append(
            {
                "name": group["name"],
                "display_name": _group_display_name(str(group["name"])),
                "weight": group["weight"],
                "weighted_contribution_sum": round(sum(float(item.get("weighted_contribution") or 0) for item in group_components), 4),
                "components": group_components,
            }
        )
    weighted_sum = round(sum(float(item.get("weighted_contribution") or 0) for item in component_contributions), 4)
    rounding_difference = round(float(score) - weighted_sum, 4)
    confidence_basis = dict(scoring_quality.get("confidence_basis", {}))
    confidence_basis["excluded_indicators_count_as_missing"] = False
    return {
        "scoring_model_version": scoring_model["version"],
        "score": round(score, 2),
        "max_score": 100,
        "label": label,
        "confidence": confidence,
        "active_weight_total": scoring_quality.get("active_weight_total", 100),
        "weighted_contribution_sum": weighted_sum,
        "rounding_difference": rounding_difference,
        "rounding_tolerance": 1.0,
        "groups": groups,
        "excluded_indicators": _excluded_indicators_with_display(scoring_model.get("excluded_indicators", [])),
        "confidence_basis": confidence_basis,
        "confidence_explanation": {
            "confidence": confidence,
            "basis": confidence_basis,
            "deductions": _confidence_deductions(scoring_quality),
            "max_confidence": 0.95,
        },
        "limitations": limitations,
    }


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
    context_only_fred: list[str] = []
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
    for field in CONTEXT_ONLY_FRED_FIELDS:
        status = component_status.get(field, {}) if isinstance(component_status.get(field), dict) else {}
        if data.get(field) is not None and status.get("provider") == "FRED":
            context_only_fred.append(field)
    fred_backed = sorted(set(fred_backed))
    context_only_fred = sorted(set(context_only_fred))
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
        context_only_fred_fields=context_only_fred,
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
        excluded_indicators=EXCLUDED_INDICATORS,
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
    legacy_label, legacy_score = _classify(data)
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
            if macro_data_quality.mock_context_fields:
                limitations = sorted(set([*limitations, "Remaining market or sentiment context fields are mock until live providers are available."]))
        for component in components:
            if component.name in macro_data_quality.mock_context_fields:
                limitation = MOCK_CONTEXT_LIMITATION
                component.limitations = sorted(set([*component.limitations, limitation]))
                if component.source_status:
                    component.source_status.fallback_used = False
                    component.source_status.limitations = sorted(set([*component.source_status.limitations, limitation]))
        macro_data_quality = _build_macro_data_quality(data, components, limitations)
    contributions = _component_contributions(components)
    score = _score_from_contributions(contributions)
    scoring_quality = _scoring_quality(contributions, components, macro_data_quality)
    macro_data_quality.scoring = scoring_quality
    label = _score_label(score, scoring_quality["missing_active_components"])
    confidence = _confidence_from_scoring(scoring_quality)
    limitations = sorted(set([*limitations, ISM_PMI_EXCLUSION_NOTE, "CNN Fear & Greed is excluded from scoring because no licensed/stable source is configured."]))
    scoring_model = _scoring_model()
    macro_score_explanation = _macro_score_explanation(
        score=score,
        label=label,
        confidence=confidence,
        scoring_model=scoring_model,
        component_contributions=contributions,
        scoring_quality=scoring_quality,
        limitations=limitations,
    )
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
            "excluded_indicators": EXCLUDED_INDICATORS,
            "source_contribution": _source_contribution(components, macro_data_quality, score),
            "scoring_model": scoring_model,
            "component_contributions": contributions,
            "legacy_rule_classification": {
                "label": legacy_label,
                "score": legacy_score,
                "used_for_final_score": False,
            },
        },
        benchmark={
            "restrictive_or_stress_max": 30,
            "cautious_max": 55,
            "neutral_to_constructive_max": 75,
            "supportive_macro_backdrop_min": 76,
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
        macro_score_explanation=macro_score_explanation,
    )
