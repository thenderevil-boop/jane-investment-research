from __future__ import annotations

from datetime import datetime, timezone

from backend.app.pipelines import research_pipeline
from backend.app.pipelines.research_pipeline import build_daily_report
from backend.app.services import operations_diagnostics_service
from backend.app.services.operations_diagnostics_service import build_operations_diagnostics


def _action_by_id(payload, action_id: str):
    return next(action for action in payload.source_health_actions if action.action_id == action_id)


def test_operations_diagnostics_exposes_routeable_source_health_actions(monkeypatch) -> None:
    monkeypatch.setattr(operations_diagnostics_service.config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(operations_diagnostics_service.config, "USE_LIVE_FMP_DATA", True)
    monkeypatch.setattr(operations_diagnostics_service.config, "USE_LIVE_SEC_FORM4", True)
    monkeypatch.setattr(operations_diagnostics_service.config, "USE_LIVE_USPTO_PATENTS_DATA", False)
    monkeypatch.setattr(operations_diagnostics_service.config, "USE_LIVE_SEC_13F", True)
    monkeypatch.setattr(operations_diagnostics_service, "_has_env", lambda name, placeholders=None: False)

    payload = build_operations_diagnostics()

    assert payload.version == "phase62_operations_diagnostics_v1"
    assert payload.source_health_actions
    assert payload.source_health_actions_version == "phase66_source_health_actions_v1"

    fmp = _action_by_id(payload, "missing_fmp_key")
    assert fmp.provider_id == "fmp_financial_proxy"
    assert fmp.category == "missing_key"
    assert fmp.severity == "high"
    assert fmp.route_hint == "operations"
    assert 5 in fmp.affected_criteria
    assert "stock_research" in fmp.affected_surfaces
    assert fmp.affects_score is False
    assert fmp.not_investment_advice is True

    form4 = _action_by_id(payload, "missing_sec_user_agent")
    assert form4.provider_id == "sec_form4"
    assert form4.category == "source_setup_required"
    assert "daily_report" in form4.affected_surfaces

    uspto = _action_by_id(payload, "disabled_uspto")
    assert uspto.provider_id == "uspto_patentsview"
    assert uspto.category == "provider_disabled"
    assert uspto.affected_criteria == [18]

    as_text = payload.model_dump_json()
    assert "api_key_values_returned" in as_text
    assert "uSOtTvlWjHS4LI3MPjfnaooHTvED53c3" not in as_text
    assert "sk-" not in as_text


def test_daily_command_center_uses_source_health_action_routes(monkeypatch) -> None:
    previous_snapshot = {
        "date": "2026-05-28",
        "macro_regime": {"score": 52, "raw_data": {"vix": 18, "ten_year_minus_two_year_spread_bps": -25}},
        "stock_candidates": [],
    }
    monkeypatch.setattr(research_pipeline, "read_daily_report_snapshot", lambda *args, **kwargs: previous_snapshot, raising=False)
    monkeypatch.setattr(operations_diagnostics_service.config, "USE_LIVE_FMP_DATA", True)
    monkeypatch.setattr(operations_diagnostics_service, "_has_env", lambda name, placeholders=None: False)

    report = build_daily_report(report_clock=datetime(2026, 5, 29, tzinfo=timezone.utc))

    assert report.command_center is not None
    assert report.command_center.source_health_alerts
    alert = report.command_center.source_health_alerts[0]
    assert alert.action_id in {"missing_fmp_key", "missing_fred_key", "missing_sec_user_agent"}
    assert alert.provider_id
    assert alert.category in {"missing_key", "source_setup_required", "provider_disabled", "cache_refresh_required"}
    assert alert.route_hint == "operations"
    assert "daily_report" in alert.affected_surfaces
    assert alert.not_investment_advice is True
