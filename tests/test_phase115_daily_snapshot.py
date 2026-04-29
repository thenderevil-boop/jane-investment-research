from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import live_market_prices, sec_edgar_13f, sec_edgar_form4
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.jobs.daily_research_refresh import refresh_daily_research_snapshot
from backend.app.main import app
from backend.app.pipelines.mock_pipeline import build_daily_report
from backend.app.raw_store import repository
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def workspace_tmp_dir() -> Path:
    path = Path("backend/raw_store/cache/test_phase115") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _isolate_snapshot_store(monkeypatch) -> Path:
    cache_dir = workspace_tmp_dir()
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", cache_dir)
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", cache_dir / "macro")
    monkeypatch.setattr(config, "SEC_FORM4_CACHE_DIR", cache_dir / "sec")
    monkeypatch.setattr(config, "SEC_13F_CACHE_DIR", cache_dir / "sec_13f")
    monkeypatch.setattr(config, "DAILY_REPORT_READ_MODE", "snapshot_first")
    monkeypatch.setattr(config, "DAILY_BATCH_ALLOW_LIVE_FETCH", True)
    monkeypatch.setattr(config, "DAILY_BATCH_PRICE_REFERENCE_WARMUP", True)
    monkeypatch.setattr(config, "DAILY_BATCH_MAX_RUNTIME_SECONDS", 180)
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", False)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", False)
    monkeypatch.setattr(config, "USE_LIVE_SEC_FORM4", False)
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", False)
    monkeypatch.setattr(config, "SEC_13F_TARGET_MANAGERS", "")
    monkeypatch.setattr(config, "DAILY_BATCH_PRICE_REFERENCE_WARMED", False)
    return cache_dir


def _write_fresh_snapshot() -> dict:
    report = build_daily_report(report_clock=datetime.now(timezone.utc))
    return repository.write_daily_report_snapshot(report.model_dump(mode="json"))


def _live_13f_cache_payload() -> dict:
    return {
        "manager": "0001067983",
        "manager_cik": "0001067983",
        "filings": [{"accession_number": "x", "filing_date": "2026-04-15", "report_date": "2026-03-31"}],
        "holdings": [
            {
                "manager_cik": "0001067983",
                "accession_number": "x",
                "filing_date": "2026-04-15",
                "report_date": "2026-03-31",
                "issuer_name": "NVIDIA CORP",
                "title_of_class": "COM",
                "cusip": "67066G104",
                "reported_value_raw": 900000,
                "shares_or_principal_amount": 1000,
                "source": ["SEC EDGAR"],
                "source_status": {"source_type": "live", "provider": "SEC EDGAR", "source_date": "2026-03-31", "is_fresh": True},
            }
        ],
        "source_type": "live",
        "provider": "SEC EDGAR",
        "source": ["SEC EDGAR"],
        "source_date": "2026-03-31",
        "limitations": [],
        "missing_data": [],
    }


def _write_nvda_price_reference() -> None:
    repository.write_market_data(
        "NVDA",
        {
            "ticker": "NVDA",
            "latest_close": 900.0,
            "source_date": datetime.now(timezone.utc).date().isoformat(),
            "source_type": "live",
            "provider": "yfinance",
            "source": ["yfinance"],
            "limitations": [],
            "missing_data": [],
        },
    )


def _stub_market_refresh(monkeypatch) -> None:
    monkeypatch.setattr(
        repository,
        "get_market_data",
        lambda ticker, use_live=None, period="1y", interval="1d": {
            "ticker": ticker,
            "source_type": "live",
            "provider": "yfinance",
            "source": "yfinance",
            "source_date": datetime.now(timezone.utc).date().isoformat(),
            "latest_close": 900.0,
            "rows": [{"date": datetime.now(timezone.utc).date().isoformat(), "close": 900.0}],
            "limitations": [],
            "missing_data": [],
        },
    )


def test_batch_refresh_writes_snapshot(monkeypatch):
    _isolate_snapshot_store(monkeypatch)
    result = refresh_daily_research_snapshot()
    snapshot = repository.read_daily_report_snapshot()
    assert result["status"] == "completed"
    assert snapshot is not None
    assert snapshot["not_investment_advice"] is True
    assert snapshot["source_status"]["provider"] == "daily_report_snapshot"
    assert snapshot["daily_report_metadata"]["snapshot_id"] == result["snapshot_id"]
    assert snapshot["daily_report_metadata"]["batch_duration_ms"] >= 0


def test_latest_report_reads_snapshot_first(monkeypatch):
    _isolate_snapshot_store(monkeypatch)
    snapshot = _write_fresh_snapshot()
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["report_generated_at"] == snapshot["report_generated_at"]
    assert payload["source_status"]["provider"] == "daily_report_snapshot"
    assert payload["daily_report_metadata"]["read_mode"] == "snapshot_first"
    assert payload["daily_report_metadata"]["snapshot_used"] is True
    assert payload["daily_report_metadata"]["snapshot_id"] == snapshot["snapshot_id"]
    assert payload["daily_report_metadata"]["snapshot_generated_at"] == snapshot["report_generated_at"]
    assert payload["daily_report_metadata"]["snapshot_is_fresh"] is True
    assert payload["daily_report_metadata"]["batch_refresh_status"] == snapshot["daily_report_metadata"]["batch_refresh_status"]
    assert "batch_refresh_started_at" in payload["daily_report_metadata"]
    assert "batch_refresh_completed_at" in payload["daily_report_metadata"]
    assert "batch_duration_ms" in payload["daily_report_metadata"]


def test_api_latest_does_not_live_fetch_when_snapshot_is_fresh(monkeypatch):
    _isolate_snapshot_store(monkeypatch)
    _write_fresh_snapshot()

    def fail_build(*args, **kwargs):
        raise AssertionError("latest endpoint should not compute live report when snapshot is fresh")

    monkeypatch.setattr("backend.app.api.routes.build_daily_report", fail_build)
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    assert response.json()["source_status"]["provider"] == "daily_report_snapshot"


def test_stale_snapshot_fallback_is_controlled_by_config(monkeypatch):
    _isolate_snapshot_store(monkeypatch)
    old_report = build_daily_report(report_clock=datetime.now(timezone.utc) - timedelta(days=1))
    repository.write_daily_report_snapshot(old_report.model_dump(mode="json"))
    monkeypatch.setattr(config, "DAILY_BATCH_ALLOW_LIVE_FETCH", False)
    blocked = client.get("/api/daily-report/latest")
    assert blocked.status_code == 503
    assert blocked.json()["detail"]["daily_report_metadata"]["snapshot_used"] is False

    monkeypatch.setattr(config, "DAILY_BATCH_ALLOW_LIVE_FETCH", True)
    allowed = client.get("/api/daily-report/latest")
    assert allowed.status_code == 200
    assert allowed.json()["date"] == datetime.now(timezone.utc).date().isoformat()
    assert allowed.json()["daily_report_metadata"]["batch_refresh_status"] == "computed_without_fresh_snapshot"


def test_price_reference_warmup_affects_snapshot(monkeypatch):
    cache_dir = _isolate_snapshot_store(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", True)
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", True)
    monkeypatch.setattr(config, "SEC_13F_TARGET_MANAGERS", "0001067983")
    monkeypatch.setattr(config, "ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST", False)
    _stub_market_refresh(monkeypatch)
    _write_nvda_price_reference()
    repository.write_sec_13f_data("0001067983", _live_13f_cache_payload())
    result = refresh_daily_research_snapshot()
    snapshot = repository.read_daily_report_snapshot()
    portfolio = snapshot["smart_money"]["raw_data"]["institutional_13f"]["portfolio_summary"]
    assert result["refreshed"]["price_reference_warmup"]["cache_hit_count"] >= 1
    assert portfolio["price_reference_used_count"] >= 1
    assert portfolio["price_reference_cache_hit_count"] > 0 or portfolio["price_reference_live_fetch_count"] > 0
    assert portfolio["value_confidence_breakdown"]["low"] < sum(portfolio["value_confidence_breakdown"].values())
    assert portfolio["price_reference_mode"] in {"batch_warmed", "cache_with_bounded_warmup"}
    assert (cache_dir / "NVDA.json").exists()


def test_batch_snapshot_uses_cached_live_sec_13f_when_available(monkeypatch):
    _isolate_snapshot_store(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", True)
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", True)
    monkeypatch.setattr(config, "SEC_13F_TARGET_MANAGERS", "0001067983")
    _stub_market_refresh(monkeypatch)
    _write_nvda_price_reference()
    repository.write_sec_13f_data("0001067983", _live_13f_cache_payload())

    refresh_daily_research_snapshot()
    snapshot = repository.read_daily_report_snapshot()
    institutional = snapshot["smart_money"]["raw_data"]["institutional_13f"]
    portfolio = institutional["portfolio_summary"]
    candidate_portfolio = snapshot["stock_candidates"][0]["institutional_13f"]["portfolio_summary"]
    assert portfolio["provider"] == "derived_from_SEC_EDGAR_13F"
    assert portfolio["underlying_source_type"] in {"cached_live", "live"}
    assert "live SEC 13F data" not in institutional["missing_data"]
    assert candidate_portfolio["provider"] == "derived_from_SEC_EDGAR_13F"
    assert "live SEC 13F data" not in snapshot["stock_candidates"][0]["missing_data"]


def test_warmup_failure_does_not_report_batch_warmed(monkeypatch):
    _isolate_snapshot_store(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", True)
    monkeypatch.setattr(config, "SEC_13F_TARGET_MANAGERS", "0001067983")
    repository.write_sec_13f_data("0001067983", _live_13f_cache_payload())
    result = refresh_daily_research_snapshot()
    snapshot = repository.read_daily_report_snapshot()
    portfolio = snapshot["smart_money"]["raw_data"]["institutional_13f"]["portfolio_summary"]
    assert result["refreshed"]["price_reference_warmup"]["failed_tickers"]
    assert portfolio["price_reference_used_count"] == 0
    assert portfolio["price_reference_cache_hit_count"] == 0
    assert portfolio["price_reference_live_fetch_count"] == 0
    assert portfolio["price_reference_mode"] != "batch_warmed"


def test_mock_13f_target_matches_do_not_boost_institutional_evidence():
    mock_snapshot = repository._mock_13f_snapshot("mock_manager", "NVDA")
    result = evaluate_smart_money(
        {
            "institutional_13f": {"cusip": "67066G104"},
            "institutional_13f_snapshot": mock_snapshot,
            "institutional_13f_source_status": mock_snapshot["source_status"],
            "form4_transactions": [],
            "options_activity": {},
        }
    )
    institutional = result.derived_metrics["components"]["institutional_support_13f"]
    assert institutional["score"] <= 40
    assert institutional["label"] in {"insufficient_data", "institutional_evidence_limited"}
    assert institutional["derived_metrics"]["high_confidence_target_match_count"] == 0
    assert institutional["derived_metrics"]["target_match_count"] == 0
    assert institutional["derived_metrics"]["diagnostic_target_match_count"] >= 0
    assert "Mock 13F target matches are diagnostics only and do not count as live institutional evidence." in institutional["limitations"]


def test_snapshot_first_survives_external_client_failures(monkeypatch):
    _isolate_snapshot_store(monkeypatch)
    refresh_daily_research_snapshot()

    monkeypatch.setattr(live_market_prices, "fetch_ohlcv", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("yfinance should not run")))
    monkeypatch.setattr(sec_edgar_13f, "fetch_13f_holdings_for_manager", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("13F should not run")))
    monkeypatch.setattr(sec_edgar_form4, "fetch_insider_transactions", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Form 4 should not run")))
    monkeypatch.setattr("backend.app.api.routes.build_daily_report", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("compute should not run")))

    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["daily_report_metadata"]["snapshot_used"] is True
    assert payload["daily_report_metadata"]["read_mode"] == "snapshot_first"


def test_snapshot_metadata_does_not_expose_secrets(monkeypatch):
    _isolate_snapshot_store(monkeypatch)
    monkeypatch.setattr(config, "SEC_EDGAR_USER_AGENT", "Secret Name secret@example.com")
    result = refresh_daily_research_snapshot()
    snapshot = repository.read_daily_report_snapshot()
    combined = str({"result": result, "snapshot_metadata": snapshot["daily_report_metadata"], "source_status": snapshot["source_status"]})
    assert "secret@example.com" not in combined
    assert "Secret Name" not in combined


def test_source_type_never_uses_mixed_in_snapshot(monkeypatch):
    _isolate_snapshot_store(monkeypatch)
    refresh_daily_research_snapshot()
    snapshot = repository.read_daily_report_snapshot()

    def walk(value):
        if isinstance(value, dict):
            if "source_type" in value:
                assert value["source_type"] != "mixed"
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(snapshot)


def test_snapshot_forbidden_language_guard_still_passes(monkeypatch):
    _isolate_snapshot_store(monkeypatch)
    refresh_daily_research_snapshot()
    snapshot = repository.read_daily_report_snapshot()
    assert detect_forbidden_language(snapshot) == []
