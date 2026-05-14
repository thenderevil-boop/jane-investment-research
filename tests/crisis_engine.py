from __future__ import annotations

from backend.app.data_sources.mock_crisis import MOCK_CRISIS_SCENARIOS
from backend.app.engines.crisis_engine import crisis_to_score_object, evaluate_crisis


def test_crisis_normal_level() -> None:
    result = evaluate_crisis(MOCK_CRISIS_SCENARIOS["normal"])
    assert result.level == "normal"
    assert set(result.reference.values()) == {"no_crisis_signal"}


def test_crisis_elevated_level() -> None:
    result = evaluate_crisis(MOCK_CRISIS_SCENARIOS["elevated"])
    assert result.level == "elevated"
    assert result.reference["energy"] == "monitor_energy_and_defense"


def test_crisis_high_level() -> None:
    result = evaluate_crisis(MOCK_CRISIS_SCENARIOS["high"])
    assert result.level == "high"
    score = crisis_to_score_object(result)
    assert score.label == "high_risk_warning"


def test_crisis_severe_level() -> None:
    result = evaluate_crisis(MOCK_CRISIS_SCENARIOS["severe"])
    assert result.level == "severe"
    assert result.reference["growth_stocks"] == "risk_assets_under_pressure"


def test_crisis_insufficient_data_level() -> None:
    result = evaluate_crisis(MOCK_CRISIS_SCENARIOS["insufficient_data"])
    assert result.level == "insufficient_data"
    assert result.confidence < 0.5
    assert result.missing_data
