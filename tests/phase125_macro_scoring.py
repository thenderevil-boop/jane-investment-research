from __future__ import annotations

import json
from copy import deepcopy

from backend.app.engines.macro_regime_engine import ACTIVE_COMPONENT_WEIGHTS, evaluate_macro_regime


def status(source_type: str, provider: str, *, source_date: str = "2026-04-29", is_fresh: bool = True, fallback_used: bool = False) -> dict:
    return {
        "source_type": source_type,
        "provider": provider,
        "source_date": source_date,
        "is_fresh": is_fresh,
        "fallback_used": fallback_used,
        "limitations": [],
        "missing_data": [],
    }


def base_payload() -> dict:
    return {
        "fed_funds_rate": 4.25,
        "fed_policy_trend": "easing",
        "ten_year_yield": 4.3,
        "two_year_yield": 4.05,
        "ten_year_minus_two_year_spread_bps": 25,
        "cpi_yoy": 3.0,
        "ppi_yoy": 2.8,
        "unemployment_rate": 4.2,
        "unemployment_trend": "stable",
        "vix": 18.5,
        "vix_trend": "stable",
        "dxy_trend": "stable",
        "gold_trend": "stable",
        "oil_trend": "stable",
        "sp500_drawdown_pct": -4.0,
        "nasdaq_drawdown_pct": -6.0,
        "sp500_gain_from_trough_pct": 14.0,
        "nasdaq_gain_from_trough_pct": 18.0,
        "equity_trend": "stable",
        "source_type": "derived",
        "provider": "mixed_FRED_and_yfinance_macro",
        "source": ["FRED", "yfinance"],
        "source_date": "2026-04-29",
        "limitations": [],
        "missing_data": [],
        "component_source_status": {
            "fed_funds_rate": status("live", "FRED"),
            "fed_policy_trend": status("derived", "derived_from_FRED"),
            "ten_year_minus_two_year_spread_bps": status("derived", "derived_from_FRED"),
            "cpi_yoy": status("derived", "derived_from_FRED"),
            "ppi_yoy": status("derived", "derived_from_FRED"),
            "unemployment_rate": status("live", "FRED"),
            "unemployment_trend": status("derived", "derived_from_FRED"),
            "vix": status("derived", "derived_from_yfinance"),
            "equity_drawdown": status("derived", "derived_from_yfinance"),
            "dxy_trend": status("derived", "derived_from_yfinance"),
            "gold_trend": status("derived", "derived_from_yfinance"),
            "oil_trend": status("derived", "derived_from_yfinance"),
            "gain_from_recent_trough": status("derived", "derived_from_yfinance"),
        },
    }


def test_macro_v125_scoring_model_weights_and_exclusions() -> None:
    result = evaluate_macro_regime(base_payload())
    model = result.derived_metrics["scoring_model"]
    contributions = result.derived_metrics["component_contributions"]
    names = {item["name"] for item in contributions}
    excluded = {item["name"]: item for item in model["excluded_indicators"]}

    assert model["version"] == "macro_v12_5"
    assert model["total_weight"] == 100
    assert sum(group["weight"] for group in model["groups"]) == 100
    assert sum(weight for _group, weight in ACTIVE_COMPONENT_WEIGHTS.values()) == 100
    assert excluded["cnn_fear_greed"]["weight"] == 0
    assert excluded["ism_manufacturing_pmi"]["weight"] == 0
    assert "cnn_fear_greed" not in names
    assert "ism_manufacturing_pmi" not in names
    assert {"fed_policy_trend", "fed_funds_rate", "cpi_yoy", "unemployment_rate"}.issubset(names)
    assert {"vix", "equity_drawdown", "dxy_trend", "gold_trend", "oil_trend", "gain_from_recent_trough"}.issubset(names)
    assert all(item["source_type"] in {"live", "cached_live", "derived"} for item in contributions)
    assert round(sum(item["weighted_contribution"] for item in contributions), 2) == result.score


def test_macro_v125_quality_scoring_basis_excludes_unlicensed_indicators() -> None:
    result = evaluate_macro_regime(base_payload())
    scoring = result.macro_data_quality.scoring

    assert scoring["scoring_model_version"] == "macro_v12_5"
    assert scoring["active_weight_total"] == 100
    assert scoring["excluded_component_count"] == 2
    assert scoring["missing_active_components"] == []
    assert scoring["stale_active_components"] == []
    assert scoring["fallback_active_components"] == []
    assert scoring["confidence_basis"]["all_active_components_available"] is True
    assert scoring["confidence_basis"]["all_active_components_fresh"] is True
    assert scoring["confidence_basis"]["excluded_indicators_count_as_missing"] is False
    assert result.confidence == 0.95


def test_macro_score_explanation_groups_components_and_exclusions() -> None:
    result = evaluate_macro_regime(base_payload())
    explanation = result.macro_score_explanation
    contributions = result.derived_metrics["component_contributions"]
    contribution_names = {item["name"] for item in contributions}

    assert explanation is not None
    assert explanation["scoring_model_version"] == "macro_v12_5"
    assert explanation["active_weight_total"] == 100
    assert explanation["score"] == result.score
    assert explanation["label"] == result.label
    assert explanation["confidence"] == result.confidence
    assert explanation["confidence_explanation"]["basis"]["excluded_indicators_count_as_missing"] is False

    grouped_names = {
        component["name"]
        for group in explanation["groups"]
        for component in group["components"]
    }
    assert grouped_names == contribution_names
    for group in explanation["groups"]:
        component_sum = round(sum(component["weighted_contribution"] for component in group["components"]), 4)
        assert group["weighted_contribution_sum"] == component_sum
        assert group["display_name"]

    contribution_sum = round(sum(item["weighted_contribution"] for item in contributions), 4)
    assert explanation["weighted_contribution_sum"] == contribution_sum
    assert abs(explanation["rounding_difference"]) <= explanation["rounding_tolerance"]

    excluded = {item["name"]: item for item in explanation["excluded_indicators"]}
    assert excluded["ism_manufacturing_pmi"]["display_name"] == "ISM Manufacturing PMI"
    assert excluded["cnn_fear_greed"]["display_name"] == "CNN Fear & Greed"
    assert excluded["ism_manufacturing_pmi"]["affects_score"] is False
    assert excluded["cnn_fear_greed"]["affects_score"] is False
    assert excluded["ism_manufacturing_pmi"]["weight"] == 0
    assert excluded["cnn_fear_greed"]["weight"] == 0
    assert "ism_manufacturing_pmi" not in grouped_names
    assert "cnn_fear_greed" not in grouped_names


def test_missing_active_fred_field_reduces_confidence_without_counting_exclusions() -> None:
    payload = base_payload()
    payload["cpi_yoy"] = None
    result = evaluate_macro_regime(payload)
    scoring = result.macro_data_quality.scoring

    assert "cpi_yoy" in scoring["missing_active_components"]
    assert "cnn_fear_greed" not in scoring["missing_active_components"]
    assert "ism_manufacturing_pmi" not in scoring["missing_active_components"]
    assert result.confidence < 0.95


def test_stale_yfinance_component_reduces_confidence() -> None:
    payload = base_payload()
    payload["component_source_status"]["vix"] = status("derived", "derived_from_yfinance", source_date="2025-01-01", is_fresh=False)

    result = evaluate_macro_regime(payload)

    assert "vix" in result.macro_data_quality.scoring["stale_active_components"]
    assert result.confidence == 0.9


def test_fallback_active_component_reduces_confidence_and_is_diagnostic_only() -> None:
    payload = base_payload()
    payload["component_source_status"]["cpi_yoy"] = status("fallback", "mock", is_fresh=False, fallback_used=True)

    result = evaluate_macro_regime(payload)
    scoring = result.macro_data_quality.scoring

    assert "cpi_yoy" in scoring["fallback_active_components"]
    assert result.confidence < 0.85


def test_cached_live_after_failure_reduces_confidence_without_secret_urls() -> None:
    payload = base_payload()
    payload["component_source_status"]["fed_funds_rate"] = {
        **status("cached_live", "FRED", fallback_used=True),
        "fallback_reason": "Live FRED macro fetch failed; cached live macro data used.",
    }

    result = evaluate_macro_regime(payload)
    text = json.dumps(result.model_dump(mode="json"), sort_keys=True)

    assert "fed_funds_rate" in result.macro_data_quality.scoring["cached_live_after_failure_components"]
    assert result.confidence == 0.85
    assert "api_key" not in text.lower()
    assert "stlouisfed.org" not in text.lower()


def test_source_type_never_uses_mixed_in_macro_output() -> None:
    payload = result_payload = evaluate_macro_regime(base_payload()).model_dump(mode="json")

    def walk(value):
        if isinstance(value, dict):
            assert value.get("source_type") != "mixed"
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    assert result_payload["source_status"]["provider"] == "mixed_FRED_and_yfinance_macro"


def test_jane_reference_conditions_are_not_macro_inputs() -> None:
    payload = base_payload()
    with_reference = deepcopy(payload)
    with_reference["jane_reference_conditions"] = {"affects_score": False}

    assert evaluate_macro_regime(payload).score == evaluate_macro_regime(with_reference).score
    assert evaluate_macro_regime(payload).confidence == evaluate_macro_regime(with_reference).confidence
