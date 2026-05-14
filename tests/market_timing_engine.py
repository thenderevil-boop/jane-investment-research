from __future__ import annotations

import json
import re

from backend.app.engines.market_timing_engine import (
    evaluate_market_timing,
    founder_ceo_insider_component,
)

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

REQUIRED_SCORE_FIELDS = {
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


def assert_score_contract(payload: dict) -> None:
    assert REQUIRED_SCORE_FIELDS.issubset(payload.keys())
    assert 0 <= payload["confidence"] <= 1


def assert_no_prohibited_language(payload: dict) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    for pattern in PROHIBITED_PATTERNS:
        assert not re.search(pattern, text), pattern


def test_extreme_fear_environment_scores_as_favorable_research_context() -> None:
    result = evaluate_market_timing(
        {
            "consecutive_rate_cut_count": 2,
            "rate_trend": "easing",
            "sp500_drawdown_pct": -24.0,
            "nasdaq_drawdown_pct": -30.0,
            "index_range_20d_pct": 6.0,
            "realized_vol_20d": 24.0,
            "previous_realized_vol_20d": 32.0,
            "fear_greed": 15,
            "vix": 34.0,
            "vix_recent_spike": True,
            "vix_trend": "falling",
            "vix_falling_from_spike": True,
            "cash_to_market_cap_pct": 12.0,
            "revenue_growth_yoy_pct": [12.0, 14.0, 18.0],
            "revenue_cagr_3y_pct": 14.5,
            "founder_is_ceo": True,
            "net_insider_buy_value_180d": 500000,
            "insider_buy_count_180d": 2,
        }
    )
    payload = result.model_dump()
    assert result.score == 100
    assert result.label == "favorable_research_environment"
    assert len(result.derived_metrics["components"]) == 6
    assert "fear_greed_extreme_fear_score" not in result.derived_metrics["components"]
    assert "fear_greed" not in result.raw_data
    assert_score_contract(payload)
    assert_no_prohibited_language(payload)
    assert result.confidence == 0.79


def test_live_market_timing_confidence_can_exceed_085() -> None:
    result = evaluate_market_timing(
        {
            "source_type": "live",
            "source": ["yfinance"],
            "source_date": "2026-05-12",
            "consecutive_rate_cut_count": 2,
            "rate_trend": "easing",
            "sp500_drawdown_pct": -24.0,
            "nasdaq_drawdown_pct": -30.0,
            "index_range_20d_pct": 6.0,
            "realized_vol_20d": 24.0,
            "previous_realized_vol_20d": 32.0,
            "vix": 34.0,
            "vix_recent_spike": True,
            "vix_trend": "falling",
            "vix_falling_from_spike": True,
            "cash_to_market_cap_pct": 12.0,
            "revenue_growth_yoy_pct": [12.0, 14.0, 18.0],
            "revenue_cagr_3y_pct": 14.5,
            "founder_is_ceo": True,
            "net_insider_buy_value_180d": 500000,
            "insider_buy_count_180d": 2,
        }
    )

    assert result.confidence == 0.97


def test_neutral_environment_scores_below_confirmation_level() -> None:
    result = evaluate_market_timing(
        {
            "consecutive_rate_cut_count": 0,
            "rate_trend": "steady",
            "sp500_drawdown_pct": -5.0,
            "nasdaq_drawdown_pct": -7.0,
            "index_range_20d_pct": 7.0,
            "realized_vol_20d": 14.0,
            "previous_realized_vol_20d": 16.0,
            "fear_greed": 48,
            "vix": 18.0,
            "vix_recent_spike": False,
            "cash_to_market_cap_pct": 6.0,
            "revenue_growth_yoy_pct": [5.0, 8.0, 11.0],
            "revenue_cagr_3y_pct": 8.0,
            "founder_is_ceo": True,
            "net_insider_buy_value_180d": 0,
            "insider_buy_count_180d": 0,
        }
    )
    assert result.label == "insufficient_data_or_unfavorable"
    assert result.score < 40
    assert_no_prohibited_language(result.model_dump())


def test_fear_greed_data_is_excluded_from_market_timing() -> None:
    result = evaluate_market_timing(
        {
            "consecutive_rate_cut_count": 1,
            "sp500_drawdown_pct": -21.0,
            "nasdaq_drawdown_pct": -19.0,
            "index_range_20d_pct": 10.0,
            "realized_vol_20d": 20.0,
            "previous_realized_vol_20d": 18.0,
            "fear_greed": None,
            "vix": 27.0,
            "cash_to_market_cap_pct": 4.0,
            "revenue_growth_yoy_pct": [8.0, 9.0, 10.0],
            "revenue_cagr_3y_pct": 9.0,
            "founder_is_ceo": False,
        }
    )
    assert "fear_greed_extreme_fear_score" not in result.derived_metrics["components"]
    assert "fear_greed" not in result.missing_data
    assert "fear_greed" not in result.raw_data


def test_high_vix_alone_is_not_favorable_confirmation() -> None:
    result = evaluate_market_timing(
        {
            "consecutive_rate_cut_count": 0,
            "rate_trend": "steady",
            "sp500_drawdown_pct": -6.0,
            "nasdaq_drawdown_pct": -8.0,
            "index_range_20d_pct": 12.0,
            "realized_vol_20d": 31.0,
            "previous_realized_vol_20d": 22.0,
            "fear_greed": 42,
            "vix": 34.0,
            "vix_recent_spike": False,
            "vix_trend": "rising",
            "vix_falling_from_spike": False,
            "cash_to_market_cap_pct": None,
            "revenue_growth_yoy_pct": None,
            "revenue_cagr_3y_pct": None,
            "founder_is_ceo": False,
        }
    )
    vix_component = result.derived_metrics["components"]["vix_confirmation_score"]
    assert vix_component["score"] == 30
    assert vix_component["label"] == "neutral"
    assert vix_component["derived_metrics"]["full_confirmation"] is False


def test_founder_ceo_with_insider_activity_component_scores_full_points() -> None:
    result = founder_ceo_insider_component(
        {
            "founder_is_ceo": True,
            "net_insider_buy_value_180d": 250000,
            "insider_buy_count_180d": 3,
        }
    )
    assert result.score == 100
    assert result.label == "favorable_research_environment"
    assert result.derived_metrics["founder_with_positive_insider_activity"] is True
    assert_no_prohibited_language(result.model_dump())
