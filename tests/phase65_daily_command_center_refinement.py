from __future__ import annotations

from datetime import datetime, timezone

from backend.app.pipelines import research_pipeline
from backend.app.pipelines.research_pipeline import build_daily_report


def test_daily_report_command_center_aggregates_top_actions_and_routes(monkeypatch) -> None:
    previous_snapshot = {
        "date": "2026-05-28",
        "macro_regime": {"score": 52, "raw_data": {"vix": 18, "ten_year_minus_two_year_spread_bps": -25}},
        "stock_candidates": [
            {"ticker": "NVDA", "overheat_score": 20, "institutional_13f": {"source_status": {"source_type": "cached_live"}}, "missing_data": []}
        ],
    }
    monkeypatch.setattr(research_pipeline, "read_daily_report_snapshot", lambda *args, **kwargs: previous_snapshot, raising=False)

    report = build_daily_report(report_clock=datetime(2026, 5, 29, tzinfo=timezone.utc))

    command_center = report.command_center
    assert command_center.version == "phase65_daily_command_center_v1"
    assert command_center.headline
    assert command_center.workflow_focus in {"macro_first", "source_health_first", "watchlist_first", "evidence_gap_first"}
    assert 1 <= len(command_center.top_actions) <= 3
    assert all(action.source == "existing_data" for action in command_center.top_actions)
    assert all(action.affects_score is False for action in command_center.top_actions)
    assert all(action.not_investment_advice is True for action in command_center.top_actions)
    assert {action.route_hint for action in command_center.top_actions} & {"operations", "stock_research", "evidence_library", "daily_report"}
    assert command_center.affects_score is False
    assert command_center.final_score_unchanged is True
    assert command_center.not_investment_advice is True


def test_daily_report_command_center_surfaces_source_and_watchlist_attention(monkeypatch) -> None:
    previous_snapshot = {
        "date": "2026-05-28",
        "macro_regime": {"score": 80, "raw_data": {"vix": 10, "ten_year_minus_two_year_spread_bps": -10}},
        "stock_candidates": [
            {"ticker": "NVDA", "overheat_score": 10, "institutional_13f": {"source_status": {"source_type": "live"}}, "missing_data": []}
        ],
    }
    monkeypatch.setattr(research_pipeline, "read_daily_report_snapshot", lambda *args, **kwargs: previous_snapshot, raising=False)

    report = build_daily_report(report_clock=datetime(2026, 5, 29, tzinfo=timezone.utc))

    command_center = report.command_center
    assert command_center.source_health_alerts
    assert any(alert.route_hint == "operations" for alert in command_center.source_health_alerts)
    assert command_center.watchlist_focus
    assert any(item.ticker == "NVDA" for item in command_center.watchlist_focus)
    assert command_center.macro_snapshot is not None
    assert command_center.macro_snapshot.not_investment_advice is True
