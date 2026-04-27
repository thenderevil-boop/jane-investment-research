from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from backend.app.engines.market_timing_engine import evaluate_market_timing
from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.main import app
from backend.app.pipelines.mock_pipeline import build_daily_report
from backend.app.utils.freshness import build_source_status, summarize_data_quality
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def live_market_context() -> dict:
    return {
        "source_type": "live",
        "provider": "yfinance",
        "source": ["yfinance"],
        "source_date": "2026-04-24",
        "sp500_drawdown_pct": -4.0,
        "nasdaq_drawdown_pct": -1.0,
        "index_range_20d_pct": 6.0,
        "realized_vol_20d": 12.0,
        "previous_realized_vol_20d": 16.0,
        "days_since_low": 22,
        "vix": 24.0,
        "vix_recent_spike": True,
        "vix_trend": "falling",
        "vix_falling_from_spike": True,
        "stabilization_status": "stabilizing",
        "fear_greed": 52,
        "index_gain_vs_prior_cycle_high": 10.0,
        "index_gain_from_recent_trough": 24.0,
        "distance_from_52w_high": -4.0,
        "index_extension_from_200d_pct": 6.0,
        "media_hype_ratio": 1.0,
        "youtube_hype_ratio": 1.0,
        "user_reported_social_heat": "low",
    }


def test_live_yfinance_source_date_fresh_on_latest_expected_trading_day():
    status = build_source_status(
        {
            "source_type": "live",
            "provider": "yfinance",
            "source": ["yfinance"],
            "source_date": "2026-04-24",
        },
        as_of=date(2026, 4, 24),
    )

    assert status.is_fresh is True


def test_mock_components_count_as_mock_not_stale():
    mock = build_source_status({"source_type": "mock", "source": ["phase1_mock_dataset"], "source_date": "2026-04-24"})
    summary = summarize_data_quality([mock])

    assert mock.is_fresh is True
    assert summary.mock_components == 1
    assert summary.stale_components == 0


def test_live_derived_market_timing_subcomponents_are_not_marked_mock():
    result = evaluate_market_timing(live_market_context())
    index_component = result.derived_metrics["components"]["index_drawdown_stabilization_score"]
    vix_component = result.derived_metrics["components"]["vix_confirmation_score"]

    assert index_component["raw_data"]["source_type"] == "derived"
    assert index_component["raw_data"]["provider"] == "derived_from_yfinance"
    assert index_component["source"] == ["yfinance"]
    assert vix_component["raw_data"]["source_type"] == "derived"


def test_smart_money_labels_no_longer_use_positive_signal_language():
    result = evaluate_smart_money(
        {
            "institutional_13f": {
                "quarter": "2026-Q1",
                "filing_date": "2026-05-15",
                "holder_count_change": 4,
                "quarterly_position_change_pct": 4.0,
                "peer_average_quarterly_position_change_pct": 2.0,
            },
            "form4_transactions": [
                {
                    "insider_name": "Mock CEO",
                    "role": "Founder CEO",
                    "transaction_type": "accumulation",
                    "shares": 100,
                    "price": 50.0,
                    "value": 5000,
                    "transaction_date": "2026-04-02",
                    "filing_date": "2026-04-04",
                }
            ],
            "options_activity": {
                "option_volume": 30000,
                "open_interest": 10000,
                "abnormal_volume_ratio": 3.0,
                "direction_consistent_with_price_action": True,
            },
        }
    )
    payload = result.model_dump()

    assert result.label == "smart_money_supportive"
    assert "positive_signal" not in str(payload)
    assert "weak_positive_signal" not in str(payload)
    assert "negative_signal" not in str(payload)


def test_overheat_response_includes_primary_secondary_index_explanation():
    result = evaluate_overheat(live_market_context())

    assert result.derived_metrics["primary_index_used"] == "SPY"
    assert result.derived_metrics["secondary_index_used"] == "QQQ"
    assert isinstance(result.derived_metrics["supporting_conditions"], list)
    assert isinstance(result.derived_metrics["unmet_conditions"], list)
    assert "primary index confirmation is not strong enough for overall overheat by itself" in result.derived_metrics["unmet_conditions"]


def test_phase82_forbidden_language_guard_still_passes():
    payload = client.get("/api/daily-report/latest").json()
    assert detect_forbidden_language(payload) == []
    assert detect_forbidden_language(build_daily_report().model_dump(mode="json")) == []

