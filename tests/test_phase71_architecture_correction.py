from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.engines.future_industry_engine import evaluate_future_industry_radar, evaluate_future_theme
from backend.app.engines.market_timing_engine import evaluate_market_timing
from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.engines.risk_allocation_engine import evaluate_risk_allocation
from backend.app.main import app
from backend.app.pipelines.mock_pipeline import build_daily_report
from backend.app.schemas.daily_report import DailyResearchReport
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)

REQUIRED_CANDIDATE_FIELDS = {
    "ticker",
    "company_name",
    "theme",
    "leadership_score",
    "smart_money_score",
    "market_timing_score",
    "overheat_score",
    "risk_score",
    "label",
    "source",
    "source_date",
    "confidence",
    "limitations",
    "missing_data",
}

REQUIRED_RISK_FIELDS = {
    "risk_posture",
    "score",
    "reference",
    "risk_flags",
    "raw_data",
    "derived_metrics",
    "benchmark",
    "trend",
    "source",
    "source_date",
    "confidence",
    "limitations",
    "missing_data",
}


def test_daily_report_stock_candidates_are_typed_contract() -> None:
    report = build_daily_report()
    assert report.stock_candidates
    first = report.stock_candidates[0].model_dump()
    assert REQUIRED_CANDIDATE_FIELDS.issubset(first)
    assert first["ticker"] == "NVDA"
    assert first["company_name"]
    assert 0 <= first["confidence"] <= 1
    assert detect_forbidden_language(report.model_dump()) == []


def test_future_industry_engine_returns_componentized_theme_scores() -> None:
    themes = evaluate_future_industry_radar()
    assert len(themes) >= 5
    first = themes[0]
    components = first.derived_metrics["components"]
    for key in [
        "news_momentum_score",
        "capital_flow_score",
        "policy_support_score",
        "technology_progress_score",
        "commercialization_score",
        "strategic_relevance_score",
    ]:
        assert key in components
    assert first.candidate_companies
    assert detect_forbidden_language(first.model_dump()) == []


def test_future_industry_engine_handles_missing_data_theme() -> None:
    theme = evaluate_future_theme(
        {
            "theme": "mock sparse theme",
            "candidate_companies": [],
            "missing_data": ["news", "capital", "policy", "commercialization"],
        }
    )
    assert theme.label == "insufficient_data"
    assert theme.score == 0
    assert theme.confidence < 0.9


def test_risk_allocation_engine_uses_allowed_research_labels() -> None:
    report = build_daily_report("overheated")
    risk = report.risk_allocation
    assert REQUIRED_RISK_FIELDS.issubset(risk.model_dump())
    assert risk.risk_posture == "overheat_warning"
    assert set(risk.reference.values()).issubset(
        {
            "risk_on_watch",
            "balanced_watch",
            "defensive_watch",
            "crisis_watch",
            "overheat_warning",
            "insufficient_data",
        }
    )
    assert detect_forbidden_language(risk.model_dump()) == []


def test_risk_allocation_engine_can_classify_crisis_watch() -> None:
    report = build_daily_report("fearful")
    assert report.risk_allocation.risk_posture == "crisis_watch"


def test_daily_report_latest_matches_pydantic_schema_contract() -> None:
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    report = DailyResearchReport.model_validate(response.json())
    payload = report.model_dump()
    assert "risk_allocation" in payload
    assert REQUIRED_CANDIDATE_FIELDS.issubset(payload["stock_candidates"][0])
    assert REQUIRED_RISK_FIELDS.issubset(payload["risk_allocation"])
    assert detect_forbidden_language(payload) == []


def test_corrected_vix_logic_requires_falling_spike_and_stabilization() -> None:
    base = {
        "consecutive_rate_cut_count": 0,
        "rate_trend": "steady",
        "sp500_drawdown_pct": -22.0,
        "nasdaq_drawdown_pct": -25.0,
        "index_range_20d_pct": 6.0,
        "realized_vol_20d": 20.0,
        "previous_realized_vol_20d": 28.0,
        "fear_greed": 22,
        "vix": 35.0,
        "cash_to_market_cap_pct": None,
        "revenue_growth_yoy_pct": None,
        "revenue_cagr_3y_pct": None,
        "founder_is_ceo": False,
    }
    confirmed = evaluate_market_timing({**base, "vix_recent_spike": True, "vix_trend": "falling", "vix_falling_from_spike": True})
    not_confirmed = evaluate_market_timing({**base, "vix_recent_spike": True, "vix_trend": "rising", "vix_falling_from_spike": False})
    assert confirmed.derived_metrics["components"]["vix_confirmation_score"]["score"] == 100
    assert not_confirmed.derived_metrics["components"]["vix_confirmation_score"]["score"] < 100
    assert not_confirmed.derived_metrics["components"]["vix_confirmation_score"]["derived_metrics"]["full_confirmation"] is False


def test_corrected_overheat_benchmark_uses_cycle_and_trough_fields() -> None:
    result = evaluate_overheat(
        {
            "index_gain_vs_prior_cycle_high": 31.0,
            "index_gain_from_recent_trough": 42.0,
            "distance_from_52w_high": -1.0,
            "index_extension_from_200d_pct": 8.0,
            "fear_greed": 55,
            "media_hype_ratio": 1.0,
            "youtube_hype_ratio": 1.0,
            "user_reported_social_heat": "low",
        }
    )
    index_component = result.derived_metrics["components"]["index_overextension_score"]
    assert index_component["score"] == 100
    assert index_component["raw_data"]["index_extension_from_200d_pct"] == 8.0
