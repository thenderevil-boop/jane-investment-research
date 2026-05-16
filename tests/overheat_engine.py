from __future__ import annotations

import json
import re

from backend.app.engines.overheat_engine import evaluate_overheat

PROHIBITED_PATTERNS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\bliquidate\b",
    r"\bexit all\b",
    r"\bsell half\b",
    r"\bmust invest\b",
    r"\bguaranteed\b",
]


def assert_no_prohibited_language(payload: dict) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    for pattern in PROHIBITED_PATTERNS:
        assert not re.search(pattern, text), pattern


def test_overheated_environment_reaches_high_risk_warning() -> None:
    result = evaluate_overheat(
        {
            "index_gain_vs_prior_cycle_high": 34.0,
            "index_gain_from_recent_trough": 48.0,
            "distance_from_52w_high": 0.0,
            "index_extension_from_200d_pct": 32.0,
            "fear_greed": 91,
            "media_hype_ratio": 3.3,
            "youtube_hype_ratio": 3.2,
            "current_volume": 2_500_000,
            "avg_volume_52w": 1_000_000,
            "current_price": 130.0,
            "ma_200d": 100.0,
            "user_reported_social_heat": "high",
            "friends_asking_about_stock": True,
        }
    )
    assert result.score >= 80
    assert result.label == "high_risk_warning"
    assert len(result.derived_metrics["components"]) == 4
    assert "fear_greed_greed_score" not in result.derived_metrics["components"]
    assert "fear_greed" not in result.raw_data
    assert_no_prohibited_language(result.model_dump())
    assert result.confidence == 0.79


def test_live_overheat_confidence_can_exceed_085() -> None:
    result = evaluate_overheat(
        {
            "source_type": "live",
            "source": ["yfinance"],
            "source_date": "2026-05-12",
            "index_gain_vs_prior_cycle_high": 34.0,
            "index_gain_from_recent_trough": 48.0,
            "distance_from_52w_high": 0.0,
            "index_extension_from_200d_pct": 32.0,
            "media_hype_ratio": 3.3,
            "youtube_hype_ratio": 3.2,
            "current_volume": 2_500_000,
            "avg_volume_52w": 1_000_000,
            "current_price": 130.0,
            "ma_200d": 100.0,
            "user_reported_social_heat": "high",
            "friends_asking_about_stock": True,
        }
    )

    assert result.confidence == 0.97


def test_neutral_overheat_environment_stays_normal() -> None:
    result = evaluate_overheat(
        {
            "index_gain_vs_prior_cycle_high": 4.0,
            "index_gain_from_recent_trough": 11.0,
            "distance_from_52w_high": -12.0,
            "index_extension_from_200d_pct": 5.0,
            "fear_greed": 50,
            "media_hype_ratio": 1.0,
            "youtube_hype_ratio": 1.0,
            "current_volume": 1_000_000,
            "avg_volume_52w": 1_000_000,
            "current_price": 100.0,
            "ma_200d": 100.0,
            "user_reported_social_heat": "low",
            "friends_asking_about_stock": False,
        }
    )
    assert result.score == 1.2
    assert result.label == "normal"
    assert_no_prohibited_language(result.model_dump())


def test_fear_greed_data_is_excluded_for_overheat() -> None:
    result = evaluate_overheat(
        {
            "index_gain_vs_prior_cycle_high": 22.0,
            "index_gain_from_recent_trough": 24.0,
            "distance_from_52w_high": -4.0,
            "index_extension_from_200d_pct": 22.0,
            "fear_greed": None,
            "media_hype_ratio": 2.2,
            "youtube_hype_ratio": 1.8,
            "user_reported_social_heat": "medium",
        }
    )
    assert "fear_greed_greed_score" not in result.derived_metrics["components"]
    assert "fear_greed" not in result.missing_data
    assert "fear_greed" not in result.raw_data
    assert result.label in {"elevated_heat", "overheated"}


def test_200d_extension_is_supplemental_not_primary_overheat_benchmark() -> None:
    result = evaluate_overheat(
        {
            "index_gain_vs_prior_cycle_high": 5.0,
            "index_gain_from_recent_trough": 12.0,
            "distance_from_52w_high": -14.0,
            "index_extension_from_200d_pct": 35.0,
            "fear_greed": 50,
            "media_hype_ratio": 1.0,
            "youtube_hype_ratio": 1.0,
            "current_volume": 1_000_000,
            "avg_volume_52w": 1_000_000,
            "current_price": 135.0,
            "ma_200d": 100.0,
        }
    )
    index_component = result.derived_metrics["components"]["index_overextension_score"]
    assert index_component["score"] == 0
    assert index_component["derived_metrics"]["supplemental_200d_extension"] == 35.0
    assert result.label == "normal"


def test_volume_and_extension_context_scores_high_when_volume_and_price_are_extended() -> None:
    result = evaluate_overheat(
        {
            "index_gain_vs_prior_cycle_high": 5.0,
            "index_gain_from_recent_trough": 10.0,
            "distance_from_52w_high": -10.0,
            "media_hype_ratio": 1.0,
            "youtube_hype_ratio": 1.0,
            "current_volume": 2_500_000,
            "avg_volume_52w": 1_000_000,
            "current_price": 130.0,
            "ma_200d": 100.0,
            "user_reported_social_heat": "low",
        }
    )

    component = result.derived_metrics["components"]["volume_and_extension_context_score"]
    assert component["score"] >= 75
    assert component["derived_metrics"]["volume_ratio"] == 2.5
    assert component["derived_metrics"]["price_vs_200d_pct"] == 30.0
    assert "user_reported_social_heat_score" not in result.derived_metrics["components"]


def test_volume_and_extension_context_missing_volume_and_ma_fields_are_reported() -> None:
    result = evaluate_overheat(
        {
            "index_gain_vs_prior_cycle_high": 5.0,
            "index_gain_from_recent_trough": 10.0,
            "distance_from_52w_high": -10.0,
            "media_hype_ratio": 1.0,
            "youtube_hype_ratio": 1.0,
        }
    )

    component = result.derived_metrics["components"]["volume_and_extension_context_score"]
    assert component["score"] == 10
    assert component["missing_data"] == ["volume_ratio_52w", "price_vs_200d_ma"]
    assert "volume_ratio_52w" in result.missing_data
    assert "price_vs_200d_ma" in result.missing_data


def test_user_reported_social_heat_no_longer_changes_overheat_score() -> None:
    base = {
        "index_gain_vs_prior_cycle_high": 5.0,
        "index_gain_from_recent_trough": 10.0,
        "distance_from_52w_high": -10.0,
        "media_hype_ratio": 1.0,
        "youtube_hype_ratio": 1.0,
        "current_volume": 1_300_000,
        "avg_volume_52w": 1_000_000,
        "current_price": 108.0,
        "ma_200d": 100.0,
        "user_reported_social_heat": "low",
        "friends_asking_about_stock": False,
    }
    hot_social = {
        **base,
        "user_reported_social_heat": "high",
        "friends_asking_about_stock": True,
    }

    assert evaluate_overheat(base).score == evaluate_overheat(hot_social).score
