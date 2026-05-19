from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from backend.app import config
from backend.app.data_sources import live_macro_fred
from backend.app.features.market_features import build_market_snapshot_features
from backend.app.pipelines.research_pipeline import build_daily_report


class FakeResponse:
    def __init__(self, payload: dict | list[dict]):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        if isinstance(self._payload, list):
            return {"observations": self._payload}
        return self._payload


def _workspace_tmp_dir() -> Path:
    path = Path("backend/raw_store/cache/test_phase35") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _recent_business_days(count: int, *, as_of: datetime | None = None) -> list[str]:
    current = (as_of or datetime.now(timezone.utc)).date()
    dates: list[str] = []
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current -= timedelta(days=1)
    return list(reversed(dates))


def _daily_rows(values: list[float], *, as_of: datetime | None = None) -> list[dict]:
    dates = _recent_business_days(len(values), as_of=as_of)
    return [{"date": date_text, "value": str(value)} for date_text, value in zip(dates, values)]


def _monthly_rows(values: list[float], start_year: int = 2025, start_month: int = 1) -> list[dict]:
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


def _fred_payloads() -> dict[str, list[dict]]:
    return {
        "FEDFUNDS": _monthly_rows([4.5] * 12 + [4.5, 4.4, 4.25], start_month=2),
        "DGS10": _daily_rows([4.1, 4.2, 4.3]),
        "DGS2": _daily_rows([3.9, 4.0, 4.05]),
        "CPIAUCSL": _monthly_rows([300.0] * 12 + [306.0, 307.0, 309.0], start_month=2),
        "PPIACO": _monthly_rows([250.0] * 12 + [255.0, 256.0, 257.5], start_month=2),
        "UNRATE": _monthly_rows([4.0] * 12 + [4.0, 4.1, 4.2], start_month=2),
        "UMCSENT": _monthly_rows([70.0] * 12 + [72.0, 74.0, 76.0], start_month=2),
    }


def _install_fake_fred(monkeypatch):
    payloads = _fred_payloads()

    def fake_get(_url: str, params: dict, timeout: int):
        assert timeout == 20
        return FakeResponse(payloads[params["series_id"]])

    monkeypatch.setattr(config, "FRED_API_KEY", "test-key")
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", False)
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _workspace_tmp_dir())
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", _workspace_tmp_dir())
    monkeypatch.setattr(live_macro_fred.httpx, "get", fake_get)


def _ohlcv_snapshot(ticker: str, base: float, latest_volume: int) -> dict:
    rows = []
    start = datetime(2025, 5, 1, tzinfo=timezone.utc).date()
    for index in range(260):
        price = base + index * 0.25
        volume = 1_000_000
        if index == 259:
            volume = latest_volume
        rows.append(
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": volume,
            }
        )
    return {
        "ticker": ticker,
        "source_type": "live",
        "provider": "yfinance",
        "source": "yfinance",
        "source_date": rows[-1]["date"],
        "rows": rows,
        "limitations": [],
        "missing_data": [],
    }


def test_phase35_fred_umcsent_is_context_only_and_covered_in_daily_report(monkeypatch):
    _install_fake_fred(monkeypatch)

    report = build_daily_report()
    raw = report.macro_regime.raw_data
    quality = report.macro_regime.macro_data_quality
    scoring_names = {
        item["name"]
        for group in report.macro_regime.macro_score_explanation["groups"]
        for item in group["components"]
    }

    assert raw["consumer_sentiment"] == 76.0
    assert raw["consumer_sentiment_trend"] == "rising"
    assert raw["component_source_status"]["consumer_sentiment"]["provider"] == "FRED"
    assert raw["component_source_status"]["consumer_sentiment"]["source"] == ["UMCSENT"]
    assert "consumer_sentiment" in quality.context_only_fred_fields
    assert "consumer_sentiment" not in quality.fred_backed_fields
    assert "consumer_sentiment" not in scoring_names
    assert quality.scoring["context_only_components_count_as_missing"] is False


def test_phase35_market_features_preserve_spy_qqq_volume_extension_context():
    features = build_market_snapshot_features(
        _ohlcv_snapshot("SPY", 400, latest_volume=2_500_000),
        _ohlcv_snapshot("QQQ", 300, latest_volume=2_000_000),
        _ohlcv_snapshot("^VIX", 18, latest_volume=100_000),
    )

    assert features["source_type"] == "live"
    assert features["market_context_coverage"]["provider"] == "derived_from_yfinance"
    assert features["market_context_coverage"]["source_type"] == "derived"
    assert set(features["market_context_coverage"]["symbols"]) == {"SPY", "QQQ", "^VIX"}
    assert "volume_and_extension_context" in features["market_context_coverage"]["derived_context_fields"]
    assert features["market_context_coverage"]["source_status"]["source_type"] == "derived"
    assert features["market_context_coverage"]["source_status"]["provider"] == "derived_from_yfinance"
    assert features["index_market_data"]["SPY"]["avg_volume_52w"] is not None
    assert features["index_market_data"]["QQQ"]["ma_200d"] is not None
