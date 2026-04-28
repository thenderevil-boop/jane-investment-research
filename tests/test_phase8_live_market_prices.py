from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import live_market_prices
from backend.app.engines.market_timing_engine import evaluate_market_timing
from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.features.market_features import build_market_snapshot_features, build_price_features
from backend.app.main import app
from backend.app.pipelines.mock_pipeline import build_daily_report
from backend.app.raw_store import repository
from backend.app.schemas.daily_report import DailyResearchReport
from backend.app.utils.forbidden_language import detect_forbidden_language

client = TestClient(app)


def workspace_tmp_dir() -> Path:
    path = Path("backend/raw_store/cache/test_phase8") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeHistory:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self.empty = len(rows) == 0

    def iterrows(self):
        for row in self._rows:
            yield row["date"], row


class FakeTicker:
    def __init__(self, _ticker: str):
        self.ticker = _ticker

    def history(self, period: str, interval: str, auto_adjust: bool):
        assert period
        assert interval
        assert auto_adjust is False
        rows = [
            {
                "date": f"2026-01-{day:02d}",
                "Open": 100 + day,
                "High": 102 + day,
                "Low": 99 + day,
                "Close": 101 + day,
                "Volume": 1_000_000 + day,
            }
            for day in range(1, 29)
        ]
        return FakeHistory(rows)


def make_snapshot(ticker: str, closes: list[float]) -> dict:
    rows = [
        {
            "date": f"2026-01-{(index % 28) + 1:02d}",
            "open": close - 0.5,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1_000_000 + index,
        }
        for index, close in enumerate(closes)
    ]
    return {
        "ticker": ticker,
        "source": "yfinance",
        "source_date": rows[-1]["date"],
        "period": "1y",
        "interval": "1d",
        "rows": rows,
        "limitations": ["Data source is suitable for MVP research reference only."],
        "missing_data": [],
    }


def test_live_market_adapter_normalizes_mocked_yfinance_response(monkeypatch):
    monkeypatch.setattr(live_market_prices, "_load_yfinance", lambda: SimpleNamespace(Ticker=FakeTicker))

    payload = live_market_prices.fetch_ohlcv("spy")

    assert payload["ticker"] == "SPY"
    assert payload["source"] == "yfinance"
    assert payload["source_date"] == "2026-01-28"
    assert payload["rows"][0] == {
        "date": "2026-01-01",
        "open": 101.0,
        "high": 103.0,
        "low": 100.0,
        "close": 102.0,
        "volume": 1000001,
    }
    assert payload["limitations"]
    assert payload["missing_data"] == []


def test_live_fetch_failure_falls_back_to_mock_data(monkeypatch):
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())

    def fail_fetch(*_args, **_kwargs):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(live_market_prices, "fetch_ohlcv", fail_fetch)
    payload = repository.read_market_data(use_live=True)

    assert payload["source_type"] == "fallback"
    assert payload["vix"] > 0
    assert "live market price data" in payload["missing_data"]
    assert payload["source_status"]["fallback_used"] is True


def test_repository_returns_live_source_type_when_fetch_succeeds(monkeypatch):
    cache_dir = workspace_tmp_dir()
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", cache_dir)
    closes = [100 + index for index in range(80)]
    vix_closes = [28, 32, 34, *([22] * 77)]

    def fake_fetch(ticker: str, period: str = "1y", interval: str = "1d"):
        return make_snapshot(ticker, vix_closes if ticker == "^VIX" else closes)

    monkeypatch.setattr(live_market_prices, "fetch_ohlcv", fake_fetch)

    payload = repository.read_market_data(use_live=True)

    assert payload["source_type"] == "live"
    assert payload["source"] == ["yfinance"]
    assert payload["latest_close"] == 179
    assert (cache_dir / "SPY.json").exists()


def test_market_features_calculate_drawdown_correctly():
    snapshot = make_snapshot("SPY", [100, 120, 110, 90])
    features = build_price_features(snapshot)

    assert features["latest_close"] == 90
    assert features["drawdown_from_52w_high"] == -25.0
    assert features["drawdown_from_all_time_high"] == -25.0
    assert features["index_gain_from_recent_trough"] == 0.0


def test_market_timing_engine_works_with_repository_backed_market_features():
    spy = make_snapshot("SPY", [140] * 30 + [100] * 10 + [101, 102, 103, 104, 105])
    qqq = make_snapshot("QQQ", [150] * 30 + [95] * 10 + [96, 97, 98, 99, 100])
    vix = make_snapshot("^VIX", [18] * 20 + [36, 34, 31, 28, 24, 23])
    features = build_market_snapshot_features(spy, qqq, vix)
    result = evaluate_market_timing({**features, "fear_greed": 18, "consecutive_rate_cut_count": 2})

    assert result.source == ["yfinance"]
    assert result.raw_data["source_type"] == "live"
    assert result.label in {"watch_for_confirmation", "favorable_research_environment"}


def test_overheat_engine_works_with_repository_backed_market_features():
    spy = make_snapshot("SPY", [100] * 40 + [130, 135, 140, 145, 150])
    qqq = make_snapshot("QQQ", [100] * 40 + [125, 130, 135, 140, 145])
    vix = make_snapshot("^VIX", [15] * 45)
    features = build_market_snapshot_features(spy, qqq, vix)
    result = evaluate_overheat({**features, "fear_greed": 80, "media_hype_ratio": 1.0, "youtube_hype_ratio": 1.0})

    assert result.source == ["yfinance"]
    assert result.raw_data["source_type"] == "live"
    assert result.derived_metrics["components"]["index_overextension_score"]["raw_data"]["index_gain_from_recent_trough"] >= 30


def test_phase8_forbidden_language_guard_still_passes():
    payload = client.get("/api/daily-report/latest").json()
    assert detect_forbidden_language(payload) == []


def test_daily_report_schema_remains_stable():
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    report = DailyResearchReport.model_validate(response.json())
    assert set(report.model_dump()) == set(build_daily_report().model_dump())
