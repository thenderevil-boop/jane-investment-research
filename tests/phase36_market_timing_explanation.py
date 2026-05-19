from __future__ import annotations

import json
import re

from backend.app.engines.market_timing_engine import evaluate_market_timing

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


def test_phase36_market_timing_explanation_checklist_is_non_scoring() -> None:
    data = {
        "source_type": "live",
        "source": ["yfinance", "FRED"],
        "source_date": "2026-05-19",
        "consecutive_rate_cut_count": 0,
        "rate_trend": "steady",
        "sp500_drawdown_pct": -4.0,
        "nasdaq_drawdown_pct": -7.0,
        "index_range_20d_pct": 6.0,
        "realized_vol_20d": 14.0,
        "previous_realized_vol_20d": 16.0,
        "vix": 17.0,
        "vix_recent_spike": False,
        "vix_trend": "flat",
        "vix_falling_from_spike": False,
        "cash_to_market_cap_pct": 4.0,
        "revenue_growth_yoy_pct": [6.0, 8.0, 9.0],
        "revenue_cagr_3y_pct": 8.0,
        "founder_is_ceo": False,
    }

    result = evaluate_market_timing(data)
    metrics = result.derived_metrics

    assert result.score == 0
    assert result.label == "insufficient_data_or_unfavorable"
    assert metrics["phase36_explanation_version"] == "market_timing_condition_explanation_v2"
    assert metrics["scoring_unchanged"] is True
    assert metrics["score_zero_interpretation"] == (
        "Score 0 means Jane entry timing conditions are not met; this is expected near market highs."
    )

    checklist = {item["id"]: item for item in metrics["condition_checklist"]}
    assert set(checklist) == {
        "fed_consecutive_cuts",
        "market_drawdown_stabilization",
        "vix_spike_recovery",
        "overheat_state",
    }
    assert checklist["fed_consecutive_cuts"]["status"] == "not_met"
    assert checklist["fed_consecutive_cuts"]["observed_value"] == "0 consecutive cut(s)"
    assert checklist["market_drawdown_stabilization"]["status"] == "not_met"
    assert checklist["market_drawdown_stabilization"]["observed_value"] == "SPY -4.0%, QQQ -7.0% drawdown"
    assert checklist["vix_spike_recovery"]["status"] == "not_met"
    assert checklist["overheat_state"]["status"] == "normal"
    assert checklist["overheat_state"]["observed_value"] == "VIX 17.0; drawdown -7.0%"
    assert all(item["affects_score"] is False for item in checklist.values())
    assert_no_prohibited_language(result.model_dump())


def test_phase36_market_timing_explanation_marks_confirmed_fear_recovery_context() -> None:
    result = evaluate_market_timing(
        {
            "source_type": "live",
            "source": ["yfinance", "FRED"],
            "source_date": "2026-05-19",
            "consecutive_rate_cut_count": 2,
            "rate_trend": "easing",
            "sp500_drawdown_pct": -24.0,
            "nasdaq_drawdown_pct": -31.0,
            "index_range_20d_pct": 5.0,
            "realized_vol_20d": 20.0,
            "previous_realized_vol_20d": 34.0,
            "vix": 33.0,
            "vix_recent_spike": True,
            "vix_trend": "falling",
            "vix_falling_from_spike": True,
            "cash_to_market_cap_pct": 11.0,
            "revenue_growth_yoy_pct": [12.0, 15.0, 18.0],
            "revenue_cagr_3y_pct": 15.0,
            "founder_is_ceo": True,
            "net_insider_buy_value_180d": 300000,
            "insider_buy_count_180d": 3,
        }
    )

    checklist = {item["id"]: item for item in result.derived_metrics["condition_checklist"]}
    assert result.score == 100
    assert checklist["fed_consecutive_cuts"]["status"] == "met"
    assert checklist["market_drawdown_stabilization"]["status"] == "met"
    assert checklist["vix_spike_recovery"]["status"] == "met"
    assert checklist["overheat_state"]["status"] == "fear_recovery"
    assert result.derived_metrics["entry_timing_summary"] == "Jane timing conditions are broadly met for research context."
    assert_no_prohibited_language(result.model_dump())
