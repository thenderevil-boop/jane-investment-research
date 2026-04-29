from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import live_macro_fred
from backend.app.main import app
from backend.app.pipelines.mock_pipeline import build_daily_report
from backend.app.raw_store import repository
from backend.app.schemas.daily_report import DailyResearchReport
from backend.app.utils.freshness import build_source_status, is_daily_rate_data_fresh
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def workspace_tmp_dir() -> Path:
    path = Path("backend/raw_store/cache/test_phase91") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeResponse:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def raise_for_status(self):
        return None

    def json(self):
        return {"observations": self._rows}


def monthly_rows(values: list[float], start_year: int = 2025, start_month: int = 1) -> list[dict]:
    rows = []
    year = start_year
    month = start_month
    for value in values:
        rows.append({"date": f"{year}-{month:02d}-01", "value": str(value)})
        month += 1
        if month == 13:
            month = 1
            year += 1
    return rows


def daily_rows(values: list[float]) -> list[dict]:
    return [{"date": f"2026-04-{20 + index:02d}", "value": str(value)} for index, value in enumerate(values)]


def fred_payloads() -> dict[str, list[dict]]:
    return {
        "FEDFUNDS": monthly_rows([4.5] * 12 + [4.5, 4.4, 4.25], start_month=2),
        "DGS10": daily_rows([4.1, 4.2, 4.3]),
        "DGS2": daily_rows([3.9, 4.0, 4.05]),
        "CPIAUCSL": monthly_rows([300.0] * 12 + [306.0, 307.0, 309.0], start_month=2),
        "PPIACO": monthly_rows([250.0] * 12 + [255.0, 256.0, 257.5], start_month=2),
        "UNRATE": monthly_rows([4.0] * 12 + [4.0, 4.1, 4.2], start_month=2),
    }


def install_fake_fred(monkeypatch):
    payloads = fred_payloads()

    def fake_get(_url: str, params: dict, timeout: int):
        assert timeout == 20
        return FakeResponse(payloads[params["series_id"]])

    monkeypatch.setattr(config, "FRED_API_KEY", "test-key")
    monkeypatch.setattr(live_macro_fred.httpx, "get", fake_get)


def test_fred_adapter_normalizes_mocked_http_responses(monkeypatch):
    install_fake_fred(monkeypatch)

    payload = live_macro_fred.fetch_macro_snapshot()

    assert payload["source_type"] == "live"
    assert payload["provider"] == "FRED"
    assert payload["indicators"]["fed_policy_trend"] == "easing"
    assert payload["indicators"]["unemployment_trend"] == "rising"
    assert payload["indicators"]["ten_year_minus_two_year_spread_bps"] == 25.0
    assert payload["indicators"]["cpi_yoy"] == 3.0
    assert payload["indicators"]["ppi_yoy"] == 3.0


def test_cpi_yoy_calculation():
    rows = monthly_rows([100.0] * 12 + [104.0])

    assert live_macro_fred.calculate_yoy(rows) == 4.0


def test_ppi_yoy_calculation():
    rows = monthly_rows([200.0] * 12 + [210.0])

    assert live_macro_fred.calculate_yoy(rows) == 5.0


def test_spread_unemployment_and_fed_policy_calculations():
    assert round((4.3 - 4.05) * 100, 2) == 25.0
    assert live_macro_fred.calculate_trend(daily_rows([4.0, 4.1, 4.2])) == "rising"
    assert live_macro_fred.calculate_trend(daily_rows([4.2, 4.1, 4.0])) == "falling"
    assert live_macro_fred.calculate_fed_policy_trend(daily_rows([4.5, 4.4, 4.25])) == "easing"
    assert live_macro_fred.calculate_fed_policy_trend(daily_rows([4.25, 4.4, 4.5])) == "tightening"


def test_live_macro_enabled_routes_fred_data_into_macro_regime(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())

    report = build_daily_report()
    components = {component.name: component for component in report.macro_regime.components}

    assert report.macro_regime.raw_data["cpi_yoy"] == 3.0
    assert report.macro_regime.raw_data["source_type"] == "derived"
    assert report.macro_regime.raw_data["provider"] == "mixed_FRED_and_mock_macro"
    assert report.macro_regime.source_status.source_type == "derived"
    assert report.macro_regime.source_status.provider == "mixed_FRED_and_mock_macro"
    assert report.macro_regime.source_status.fallback_used is False
    assert components["cpi_yoy"].source_status.source_type == "derived"
    assert components["cpi_yoy"].source_status.provider == "derived_from_FRED"
    assert components["ten_year_minus_two_year_spread_bps"].source_status.source_type == "derived"
    assert components["ten_year_minus_two_year_spread_bps"].source_status.provider == "derived_from_FRED"
    assert components["ism_manufacturing_pmi"].source_status.source_type == "mock"
    assert components["ism_manufacturing_pmi"].source_status.fallback_used is False
    assert "This field remains mock context in Phase 9 and is not live market evidence." in components["ism_manufacturing_pmi"].source_status.limitations


def test_macro_data_quality_separates_fred_and_mock_context(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())

    report = build_daily_report()
    quality = report.macro_regime.macro_data_quality
    components = {component.name: component for component in report.macro_regime.components}

    assert quality is not None
    assert set(["fed_funds_rate", "ten_year_yield", "two_year_yield", "unemployment_rate"]).issubset(quality.fred_backed_fields)
    assert set(["cpi_yoy", "ppi_yoy", "ten_year_minus_two_year_spread_bps", "fed_policy_trend", "unemployment_trend"]).issubset(quality.derived_from_fred_fields)
    assert set(["ism_manufacturing_pmi", "dxy_trend", "gold_trend", "oil_trend", "fear_greed", "equity_drawdown"]).issubset(quality.mock_context_fields)
    assert quality.live_macro_fields_count > 0
    assert quality.derived_macro_fields_count > 0
    assert quality.mock_macro_fields_count > 0
    assert quality.has_mock_macro_context is True
    assert quality.confidence_adjustment_applied is True
    assert quality.mock_context_score_weight_pct >= 40
    assert report.macro_regime.confidence <= 0.78
    assert report.macro_regime.source_status.source_type == "derived"
    assert report.macro_regime.source_status.provider == "mixed_FRED_and_mock_macro"
    assert report.macro_regime.source_status.fallback_used is False
    assert "live FRED macro data" not in report.macro_regime.source_status.missing_data
    assert "ISM, DXY, gold, oil, Fear & Greed, and equity context remain Phase 9 mock context until live providers are added." in report.macro_regime.limitations
    assert components["fear_greed"].source_status.source_type == "mock"
    assert components["fear_greed"].source_status.fallback_used is False


def test_macro_source_contribution_and_data_quality_summary(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())

    report = build_daily_report()
    contribution = report.macro_regime.derived_metrics["source_contribution"]
    macro_summary = report.data_quality.macro

    assert contribution["fred_backed_score"] > 0
    assert contribution["fred_derived_score"] > 0
    assert contribution["mock_context_score"] > 0
    assert "fear_greed" in contribution["mock_context_component_names"]
    assert "ten_year_yield" in contribution["fred_component_names"]
    assert macro_summary["provider"] == "mixed_FRED_and_mock_macro"
    assert macro_summary["live_macro_fields_count"] > 0
    assert macro_summary["derived_macro_fields_count"] > 0
    assert macro_summary["mock_macro_fields_count"] > 0
    assert macro_summary["has_mock_macro_context"] is True
    assert macro_summary["confidence_adjustment_applied"] is True


def test_monthly_fred_march_2026_is_fresh_for_april_27_report_date():
    status = build_source_status(
        {
            "source_type": "live",
            "provider": "FRED",
            "source_date": "2026-03-01",
            "limitations": [],
            "missing_data": [],
        },
        freshness_window="monthly_macro_latest_observation",
        as_of=datetime.fromisoformat("2026-04-27T09:30:00+00:00").date(),
    )

    assert status.is_fresh is True
    assert status.freshness_window == "monthly_macro_latest_observation"
    assert "Monthly FRED series are evaluated using observation-month freshness, not latest trading-day freshness." in status.limitations


def test_monthly_fred_older_than_70_days_is_stale():
    status = build_source_status(
        {
            "source_type": "live",
            "provider": "FRED",
            "source_date": "2026-01-01",
        },
        freshness_window="monthly_macro_latest_observation",
        as_of=datetime.fromisoformat("2026-04-27T09:30:00+00:00").date(),
    )

    assert status.is_fresh is False


def test_fred_monthly_series_within_latest_observation_window_are_fresh(monkeypatch):
    install_fake_fred(monkeypatch)

    payload = live_macro_fred.fetch_macro_snapshot()
    raw_series = payload["raw_series"]

    for key in ["fed_funds_rate", "cpi", "ppi", "unemployment_rate"]:
        status = raw_series[key]["source_status"]
        assert status["is_fresh"] is True
        assert status["freshness_window"] == "monthly_macro_latest_observation"
        assert "Monthly FRED series are evaluated using observation-month freshness, not latest trading-day freshness." in status["limitations"]


def test_fred_daily_rate_series_within_5_business_days_are_fresh(monkeypatch):
    install_fake_fred(monkeypatch)

    payload = live_macro_fred.fetch_macro_snapshot()

    for key in ["ten_year_yield", "two_year_yield"]:
        status = payload["raw_series"][key]["source_status"]
        assert status["is_fresh"] is True
        assert status["freshness_window"] == "daily_rate_5_business_days"
    assert is_daily_rate_data_fresh("2026-04-17", as_of=datetime.fromisoformat("2026-04-27T09:30:00+00:00").date()) is False


def test_derived_spread_inherits_fred_source_status(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())

    report = build_daily_report()
    components = {component.name: component for component in report.macro_regime.components}
    status = components["ten_year_minus_two_year_spread_bps"].source_status

    assert status.source_type == "derived"
    assert status.provider == "derived_from_FRED"
    assert status.freshness_window == "derived_from_FRED"
    assert status.is_fresh is True


def test_derived_fred_fields_inherit_stale_input_status(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())
    original_fetch = live_macro_fred.fetch_fred_series

    def stale_ten_year(series_id: str):
        payload = original_fetch(series_id)
        if series_id == "DGS10":
            payload["source_date"] = "2026-04-10"
            payload["source_status"] = build_source_status(
                payload,
                freshness_window="daily_rate_5_business_days",
                as_of=datetime.fromisoformat("2026-04-27T09:30:00+00:00").date(),
            ).model_dump(mode="json")
        return payload

    monkeypatch.setattr(live_macro_fred, "fetch_fred_series", stale_ten_year)

    report = build_daily_report()
    components = {component.name: component for component in report.macro_regime.components}
    status = components["ten_year_minus_two_year_spread_bps"].source_status

    assert status.is_fresh is False
    assert "stale input: DGS10" in status.missing_data


def test_fred_source_status_propagates_snapshot_fetched_at(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())

    payload = repository.read_macro_data(use_live=True)
    fetched_at = payload["fetched_at"]
    raw_snapshot = payload["raw_fred_snapshot"]

    assert payload["source_type"] == "derived"
    assert payload["provider"] == "mixed_FRED_and_mock_macro"
    assert payload["source_status"]["source_type"] == "derived"
    assert payload["source_status"]["provider"] == "mixed_FRED_and_mock_macro"
    assert payload["source_status"]["fallback_used"] is False
    assert fetched_at
    assert payload["component_source_status"]["cpi_yoy"]["fetched_at"] == fetched_at
    for summary in raw_snapshot["raw_series"].values():
        assert summary["source_status"]["fetched_at"] == fetched_at


def test_daily_report_uses_compact_fred_raw_snapshot(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())

    payload = build_daily_report().model_dump(mode="json")
    raw_fred_snapshot = payload["macro_regime"]["raw_data"]["raw_fred_snapshot"]

    for summary in raw_fred_snapshot["raw_series"].values():
        assert "observations" not in summary
        assert set(summary) >= {
            "series_id",
            "latest_date",
            "latest_value",
            "previous_value",
            "recent_observations",
            "source_status",
            "limitations",
            "missing_data",
        }
        assert len(summary["recent_observations"]) <= 12


def test_daily_report_clock_can_be_injected():
    generated_at = "2026-04-27T09:30:00+00:00"
    report = build_daily_report(report_clock=datetime.fromisoformat(generated_at))

    assert report.date == "2026-04-27"
    assert report.report_generated_at == generated_at


def test_data_quality_does_not_mark_valid_fred_macro_stale(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())

    report = build_daily_report()

    assert report.data_quality.live_components >= 5
    assert report.data_quality.stale_components == 0
    assert not any("stale live or derived" in item for item in report.human_verification_queue)


def test_missing_fred_api_key_falls_back_to_mock_macro(monkeypatch):
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "FRED_API_KEY", "")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())

    payload = repository.read_macro_data(use_live=True)

    assert payload["source_type"] == "fallback"
    assert payload["provider"] == "mock"
    assert payload["source_status"]["fallback_used"] is True
    assert "live FRED macro data" in payload["missing_data"]


def test_fred_fetch_failure_falls_back_to_mock_and_marks_fallback(monkeypatch):
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "FRED_API_KEY", "test-key")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())

    def fail_fetch():
        raise RuntimeError("fred unavailable")

    monkeypatch.setattr(live_macro_fred, "fetch_macro_snapshot", fail_fetch)
    payload = repository.read_macro_data(use_live=True)

    assert payload["source_type"] == "fallback"
    assert payload["source_status"]["source_type"] == "fallback"
    assert "fred unavailable" in payload["source_status"]["fallback_reason"]


def test_fred_fallback_reason_redacts_api_key_and_url(monkeypatch):
    fixture_key = "redaction-fixture-key-123"
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "FRED_API_KEY", fixture_key)
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())

    def fail_fetch():
        raise RuntimeError(
            "Server error for url https://api.stlouisfed.org/fred/series/observations"
            f"?series_id=DGS10&api_key={fixture_key}&file_type=json"
        )

    monkeypatch.setattr(live_macro_fred, "fetch_macro_snapshot", fail_fetch)
    payload = repository.read_macro_data(use_live=True)
    payload_text = str(payload)

    assert payload["source_type"] == "fallback"
    assert fixture_key not in payload_text
    assert "api_key" not in payload["source_status"]["fallback_reason"].lower()
    assert "stlouisfed.org" not in payload["source_status"]["fallback_reason"].lower()


def test_fred_fetch_failure_prefers_fresh_cached_live_macro(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())
    live_snapshot = live_macro_fred.fetch_macro_snapshot()
    repository.write_macro_data(live_snapshot)

    def fail_fetch():
        raise RuntimeError("fred unavailable")

    monkeypatch.setattr(live_macro_fred, "fetch_macro_snapshot", fail_fetch)
    payload = repository.read_macro_data(use_live=True)

    assert payload["source_type"] == "derived"
    assert payload["provider"] == "mixed_FRED_and_mock_macro"
    assert payload["raw_fred_snapshot"]["source_type"] == "cached_live"
    assert payload["raw_fred_snapshot"]["source_status"]["fallback_used"] is True
    assert payload["source_status"]["fallback_reason"] == "fred unavailable"
    assert payload["component_source_status"]["fed_funds_rate"]["source_type"] == "cached_live"
    assert payload["component_source_status"]["ten_year_yield"]["source_type"] == "cached_live"
    assert "live FRED macro data" not in payload["missing_data"]


def test_fred_adapter_retries_transient_500(monkeypatch):
    rows = daily_rows([4.1, 4.2, 4.3])
    request = httpx.Request("GET", live_macro_fred.FRED_BASE_URL)
    calls = {"count": 0}

    def fake_get(_url: str, params: dict, timeout: int):
        assert timeout == 20
        assert params["api_key"] == "test-key"
        calls["count"] += 1
        if calls["count"] == 1:
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError("Server error", request=request, response=response)
        return FakeResponse(rows)

    monkeypatch.setattr(config, "FRED_API_KEY", "test-key")
    monkeypatch.setattr(live_macro_fred.httpx, "get", fake_get)

    payload = live_macro_fred.fetch_fred_series("DGS10")

    assert calls["count"] == 2
    assert payload["source_type"] == "live"
    assert payload["latest_value"] == 4.3


def test_data_quality_counts_live_macro_components_when_enabled(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())

    report = build_daily_report()

    assert report.data_quality.live_components >= 5
    assert report.data_quality.mock_components >= 1


def test_phase9_forbidden_language_guard_still_passes():
    payload = client.get("/api/daily-report/latest").json()
    assert detect_forbidden_language(payload) == []


def test_phase9_daily_report_schema_remains_stable():
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    report = DailyResearchReport.model_validate(response.json())
    assert set(report.model_dump()) == set(build_daily_report().model_dump())
