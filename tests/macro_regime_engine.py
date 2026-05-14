from __future__ import annotations

from backend.app.data_sources.mock_macro import MOCK_MACRO_SCENARIOS
from backend.app.engines.macro_regime_engine import evaluate_macro_regime

REQUIRED_COMPONENT_FIELDS = {
    "raw_data",
    "source",
    "source_date",
    "derived_metrics",
    "benchmark",
    "trend",
    "confidence",
    "limitations",
    "missing_data",
}


def assert_components_complete(result) -> None:
    assert result.components
    for component in result.components:
        payload = component.model_dump()
        assert REQUIRED_COMPONENT_FIELDS.issubset(payload.keys())
        assert 0 <= component.confidence <= 1


def test_macro_normal_regime() -> None:
    result = evaluate_macro_regime(MOCK_MACRO_SCENARIOS["normal"])
    assert result.label == "neutral_to_constructive"
    assert_components_complete(result)
    assert result.derived_metrics["legacy_rule_classification"]["label"] == "normal"


def test_macro_fear_crisis_regime() -> None:
    result = evaluate_macro_regime(MOCK_MACRO_SCENARIOS["fear_crisis"])
    assert result.label == "cautious"
    assert result.derived_metrics["legacy_rule_classification"]["label"] == "fear_crisis"


def test_macro_inflation_pressure_regime() -> None:
    result = evaluate_macro_regime(MOCK_MACRO_SCENARIOS["inflation_pressure"])
    assert result.label == "neutral_to_constructive"
    assert result.derived_metrics["legacy_rule_classification"]["label"] == "inflation_pressure"


def test_macro_recession_warning_regime() -> None:
    result = evaluate_macro_regime(MOCK_MACRO_SCENARIOS["recession_warning"])
    assert result.label == "neutral_to_constructive"
    assert result.derived_metrics["legacy_rule_classification"]["label"] == "recession_warning"


def test_macro_recession_confirmed_regime() -> None:
    result = evaluate_macro_regime(MOCK_MACRO_SCENARIOS["recession_confirmed"])
    assert result.label == "cautious"
    assert result.derived_metrics["legacy_rule_classification"]["label"] == "recession_confirmed"


def test_macro_recovery_regime() -> None:
    result = evaluate_macro_regime(MOCK_MACRO_SCENARIOS["recovery"])
    assert result.label == "neutral_to_constructive"
    assert result.derived_metrics["legacy_rule_classification"]["label"] == "recovery"


def test_macro_overheated_regime() -> None:
    result = evaluate_macro_regime(MOCK_MACRO_SCENARIOS["overheated"])
    assert result.label == "neutral_to_constructive"
    assert result.derived_metrics["legacy_rule_classification"]["label"] == "overheated"


def test_macro_insufficient_data_regime() -> None:
    result = evaluate_macro_regime(MOCK_MACRO_SCENARIOS["insufficient_data"])
    assert result.label == "insufficient_data"
    assert result.confidence == 0.5
    assert result.missing_data
