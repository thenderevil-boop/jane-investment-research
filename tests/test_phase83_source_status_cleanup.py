from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from backend.app import config
from backend.app.data_sources import live_market_prices
from backend.app.pipelines.mock_pipeline import build_daily_report
from backend.app.raw_store import repository
from backend.app.utils.forbidden_language import detect_forbidden_language


def workspace_tmp_dir() -> Path:
    path = Path("backend/raw_store/cache/test_phase83") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_snapshot(ticker: str, source_date: str) -> dict:
    start = datetime.fromisoformat(source_date) - timedelta(days=90)
    rows = []
    for index in range(80):
        close = 100 + index
        day = start + timedelta(days=index)
        rows.append(
            {
                "date": day.date().isoformat(),
                "open": close - 0.5,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1_000_000 + index,
            }
        )
    rows[-1]["date"] = source_date
    return {
        "ticker": ticker,
        "source": "yfinance",
        "source_date": source_date,
        "period": "1y",
        "interval": "1d",
        "rows": rows,
        "limitations": ["Data source is suitable for MVP research reference only."],
        "missing_data": [],
    }


def test_live_nested_spy_qqq_source_status_is_current_and_not_stale(monkeypatch):
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", False)
    current_source_date = date.today().isoformat()

    def fake_fetch(ticker: str, period: str = "1y", interval: str = "1d"):
        return make_snapshot(ticker, current_source_date)

    monkeypatch.setattr(live_market_prices, "fetch_ohlcv", fake_fetch)
    report = build_daily_report(use_live_market_data=True)
    payload = report.model_dump(mode="json")

    for score_key in ["market_timing", "overheat_risk"]:
        index_market_data = payload[score_key]["raw_data"]["index_market_data"]
        for ticker in ["SPY", "QQQ"]:
            assert index_market_data[ticker]["source_date"] == payload[score_key]["source_date"]
            assert index_market_data[ticker]["source_status"]["source_type"] == "live"
            assert index_market_data[ticker]["source_status"]["provider"] == "yfinance"
            assert index_market_data[ticker]["source_status"]["is_fresh"] is True

    assert payload["data_quality"]["stale_components"] == 0
    assert payload["data_quality"]["missing_source_date_components"] == 0


def test_live_fetch_ignores_stale_cache_when_live_mode_is_enabled(monkeypatch):
    cache_dir = workspace_tmp_dir()
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", cache_dir)
    repository.write_market_data("SPY", make_snapshot("SPY", "2020-01-01"))
    current_source_date = date.today().isoformat()

    def fake_fetch(ticker: str, period: str = "1y", interval: str = "1d"):
        return make_snapshot(ticker, current_source_date)

    monkeypatch.setattr(live_market_prices, "fetch_ohlcv", fake_fetch)
    payload = repository.get_market_data("SPY", use_live=True)

    assert payload["source_date"] == current_source_date
    assert payload["source_status"]["is_fresh"] is True
    cached = json.loads((cache_dir / "SPY.json").read_text(encoding="utf-8"))
    assert cached["source_date"] == current_source_date


def test_crisis_aggregate_source_status_is_derived_from_components():
    report = build_daily_report()
    crisis_status = report.crisis.source_status

    assert crisis_status is not None
    assert crisis_status.source_type == "derived"
    assert crisis_status.provider == "derived_from_crisis_components"
    assert crisis_status.source_date == max(component.source_date for component in report.crisis.components)
    assert crisis_status.is_fresh is True


def test_live_price_and_mock_non_price_data_quality_is_mixed_without_stale_or_missing_dates(monkeypatch):
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", False)
    current_source_date = date.today().isoformat()

    def fake_fetch(ticker: str, period: str = "1y", interval: str = "1d"):
        return make_snapshot(ticker, current_source_date)

    monkeypatch.setattr(live_market_prices, "fetch_ohlcv", fake_fetch)
    report = build_daily_report(use_live_market_data=True)
    payload = report.model_dump(mode="json")

    assert payload["data_quality"]["mode"] == "mixed"
    assert payload["data_quality"]["live_components"] > 0
    assert payload["data_quality"]["mock_components"] > 0
    assert payload["data_quality"]["stale_components"] == 0
    assert payload["data_quality"]["missing_source_date_components"] == 0
    assert detect_forbidden_language(payload) == []
