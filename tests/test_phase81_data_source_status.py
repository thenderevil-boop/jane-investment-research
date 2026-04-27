from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import live_market_prices
from backend.app.main import app
from backend.app.raw_store import repository
from backend.app.utils.freshness import build_source_status, is_daily_market_data_fresh
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def test_live_source_status(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", tmp_path)

    def fake_fetch(ticker: str, period: str = "1y", interval: str = "1d"):
        return {
            "ticker": ticker,
            "source": "yfinance",
            "source_date": "2026-04-24",
            "period": period,
            "interval": interval,
            "rows": [{"date": "2026-04-24", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}],
            "limitations": [],
            "missing_data": [],
        }

    monkeypatch.setattr(live_market_prices, "fetch_ohlcv", fake_fetch)
    payload = repository.get_market_data("SPY", use_live=True)

    assert payload["source_status"]["source_type"] == "live"
    assert payload["source_status"]["provider"] == "yfinance"
    assert payload["source_status"]["fallback_used"] is False


def test_mock_source_status():
    payload = repository.get_market_data("SPY", use_live=False)

    assert payload["source_status"]["source_type"] == "mock"
    assert payload["source_status"]["is_fresh"] is True
    assert "live market price data" in payload["source_status"]["missing_data"]


def test_fallback_source_status(monkeypatch):
    def fail_fetch(*_args, **_kwargs):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(live_market_prices, "fetch_ohlcv", fail_fetch)
    payload = repository.get_market_data("SPY", use_live=True)

    assert payload["source_type"] == "fallback"
    assert payload["source_status"]["source_type"] == "fallback"
    assert payload["source_status"]["fallback_used"] is True
    assert payload["source_status"]["provider"] == "mock"
    assert "network unavailable" in payload["source_status"]["fallback_reason"]


def test_stale_and_missing_source_date_detection():
    assert is_daily_market_data_fresh("2026-04-20", as_of=date(2026, 4, 27)) is False
    missing = build_source_status({"source": "yfinance", "source_type": "live"})
    assert missing.is_fresh is False
    assert "source_date" in missing.missing_data


def test_daily_report_latest_includes_data_quality():
    payload = client.get("/api/daily-report/latest").json()

    assert payload["data_quality"]["mode"] in {"all_mock", "mixed", "mostly_live", "live_with_fallback"}
    assert payload["data_quality"]["mock_components"] >= 1
    assert "source_status" in payload["market_timing"]
    assert payload["market_timing"]["source_status"]["source_type"] in {"mock", "live", "fallback", "unknown"}


def test_phase81_forbidden_language_guard_still_passes():
    payload = client.get("/api/daily-report/latest").json()
    assert detect_forbidden_language(payload) == []
