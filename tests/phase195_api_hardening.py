from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api import routes
from backend.app.raw_store import _repository_impl as repository_impl
from backend.app.main import app
from backend.app.pipelines.research_pipeline import build_daily_report
from backend.app.schemas.daily_report import DailyResearchReport

client = TestClient(app)


def test_phase195_supplemental_endpoints_use_snapshot_service_not_direct_rebuild(monkeypatch):
    report = build_daily_report()

    def fake_latest_daily_report_response(*, use_live_market_data, build_report):
        assert use_live_market_data is None
        return report

    def fail_direct_rebuild(*args, **kwargs):
        raise AssertionError("supplemental endpoint should use snapshot-first daily report service")

    monkeypatch.setattr(routes, "latest_daily_report_response", fake_latest_daily_report_response)
    monkeypatch.setattr(routes, "build_daily_report", fail_direct_rebuild)

    themes = client.get("/api/themes/latest")
    macro = client.get("/api/macro-regime/latest")

    assert themes.status_code == 200
    assert themes.json()["themes"]
    assert macro.status_code == 200
    assert macro.json()["name"] == report.macro_regime.name


def test_phase195_safety_filter_runs_on_supplemental_json_responses(monkeypatch):
    seen: list[object] = []

    def spy(payload):
        seen.append(payload)

    monkeypatch.setattr(routes, "check_safety", spy)

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/data-health").status_code == 200
    assert client.get("/api/manual-evidence").status_code == 200

    assert len(seen) == 3


def test_phase195_price_reference_warmup_uses_pydantic_request(monkeypatch):
    captured: dict = {}

    def fake_warm_price_reference_cache(tickers, *, max_tickers, allow_live_fetch):
        captured.update({"tickers": tickers, "max_tickers": max_tickers, "allow_live_fetch": allow_live_fetch})
        return {"requested": len(tickers), "warmed": []}

    monkeypatch.setattr(routes, "warm_price_reference_cache", fake_warm_price_reference_cache)

    response = client.post(
        "/api/price-reference/warmup",
        json={"tickers": "nvda, tsla", "max_tickers": 2, "allow_live_fetch": False},
    )

    assert response.status_code == 200
    assert response.json()["not_investment_advice"] is True
    assert captured == {"tickers": ["NVDA", "TSLA"], "max_tickers": 2, "allow_live_fetch": False}


def test_phase195_safety_filter_blocks_unsafe_response(monkeypatch):
    report = build_daily_report()
    unsafe = DailyResearchReport.model_validate(report.model_dump(mode="json"))
    unsafe.future_themes[0].limitations.append("must buy")

    monkeypatch.setattr(routes, "latest_daily_report_response", lambda **kwargs: unsafe)
    response = client.get("/api/themes/latest")

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "internal_safety_filter_blocked_response"
    assert response.json()["detail"]["not_investment_advice"] is True


def test_phase195_sec_13f_enrichment_logs_sanitized_warning(monkeypatch, caplog):
    from backend.app.data_sources import sec_edgar_13f

    def fail_enrichment(holding):
        raise RuntimeError("provider failure at https://www.sec.gov/raw/path")

    monkeypatch.setattr(sec_edgar_13f, "enrich_13f_holding_with_local_context", fail_enrichment)

    payload = repository_impl._sanitize_sec_13f_cached_payload(
        {
            "manager": "0001067983",
            "manager_cik": "0001067983",
            "holdings": [{"ticker": "NVDA", "cusip": "67066G104", "source_status": {"provider": "legacy"}}],
            "limitations": [],
            "missing_data": [],
        }
    )

    assert payload["holdings"][0]["ticker"] == "NVDA"
    assert "SEC 13F local holding enrichment failed" in caplog.text
    assert "sec.gov" not in caplog.text.lower()
    assert "SEC_EDGAR_USER_AGENT" not in caplog.text
