from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from backend.app import config
from backend.app.data_sources import live_macro_fred, market_context
from backend.app.pipelines.mock_pipeline import build_daily_report
from backend.app.raw_store import repository


def workspace_tmp_dir() -> Path:
    path = Path("backend/raw_store/cache/test_phase121") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeFredResponse:
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


def daily_fred_rows(values: list[float]) -> list[dict]:
    return [{"date": f"2026-04-{20 + index:02d}", "value": str(value)} for index, value in enumerate(values)]


def install_fake_fred(monkeypatch):
    payloads = {
        "FEDFUNDS": monthly_rows([4.5] * 12 + [4.5, 4.4, 4.25], start_month=2),
        "DGS10": daily_fred_rows([4.1, 4.2, 4.3]),
        "DGS2": daily_fred_rows([3.9, 4.0, 4.05]),
        "CPIAUCSL": monthly_rows([300.0] * 12 + [306.0, 307.0, 309.0], start_month=2),
        "PPIACO": monthly_rows([250.0] * 12 + [255.0, 256.0, 257.5], start_month=2),
        "UNRATE": monthly_rows([4.0] * 12 + [4.0, 4.1, 4.2], start_month=2),
    }

    def fake_get(_url: str, params: dict, timeout: int):
        assert timeout == 20
        return FakeFredResponse(payloads[params["series_id"]])

    monkeypatch.setattr(config, "FRED_API_KEY", "test-key")
    monkeypatch.setattr(live_macro_fred.httpx, "get", fake_get)


def market_rows(start: float, step: float, days: int = 260) -> list[dict]:
    rows = []
    start_date = date(2025, 8, 13)
    for index in range(days):
        close = round(start + step * index, 4)
        rows.append(
            {
                "date": (start_date + timedelta(days=index)).isoformat(),
                "open": close,
                "high": round(close * 1.01, 4),
                "low": round(close * 0.99, 4),
                "close": close,
                "volume": 1000000 + index,
            }
        )
    return rows


def snapshot(symbol: str, rows: list[dict], source_type: str = "live") -> dict:
    return {
        "ticker": symbol,
        "source": "yfinance",
        "source_type": source_type,
        "provider": "yfinance",
        "source_date": rows[-1]["date"],
        "period": "1y",
        "interval": "1d",
        "rows": rows,
        "limitations": ["Yfinance data is suitable for MVP research reference only."],
        "missing_data": [],
    }


def market_fixture() -> dict[str, dict]:
    return {
        "SPY": snapshot("SPY", market_rows(300, 0.4)),
        "QQQ": snapshot("QQQ", market_rows(250, 0.55)),
        "^VIX": snapshot("^VIX", market_rows(16, 0.02)),
        "DX-Y.NYB": snapshot("DX-Y.NYB", market_rows(100, 0.02)),
        "GC=F": snapshot("GC=F", market_rows(2000, 3.0)),
        "GLD": snapshot("GLD", market_rows(185, 0.2)),
        "CL=F": snapshot("CL=F", market_rows(70, -0.02)),
        "USO": snapshot("USO", market_rows(75, 0.05)),
    }


def install_fake_market(monkeypatch, fixtures: dict[str, dict], fail_symbols: set[str] | None = None):
    calls: list[str] = []
    fail_symbols = fail_symbols or set()

    def fake_get_market_data(symbol: str, use_live: bool | None = None, period: str = "1y", interval: str = "1d"):
        calls.append(symbol)
        if symbol in fail_symbols or symbol not in fixtures:
            return {
                "ticker": symbol,
                "source_type": "fallback",
                "provider": "mock",
                "source": "phase1_mock_dataset",
                "source_date": "2026-04-24",
                "rows": [],
                "fallback_used": True,
                "fallback_reason": "market context fixture unavailable",
                "limitations": ["fixture unavailable"],
                "missing_data": ["live market price data"],
            }
        return fixtures[symbol]

    monkeypatch.setattr(repository, "get_market_data", fake_get_market_data)
    return calls


def test_live_market_context_adapter_returns_vix_metrics():
    payload = market_context.vix_metrics(market_fixture()["^VIX"])

    assert payload["latest_value"] is not None
    assert payload["high_20d"] is not None
    assert payload["trend"] in {"rising", "falling", "stable", "elevated"}
    assert payload["source_status"]["provider"] == "derived_from_yfinance"


def test_live_market_context_adapter_computes_equity_drawdown_and_trough_gain():
    payload = market_context.equity_metrics(market_fixture()["SPY"], market_fixture()["QQQ"])

    assert payload["max_index_drawdown_pct"] is not None
    assert payload["max_gain_from_recent_trough_pct"] is not None
    assert payload["drawdown_state"] in {"deep_drawdown", "correction", "normal"}
    assert payload["rebound_state"] in {"strong_rebound", "normal_rebound"}


def test_live_market_context_adapter_computes_dxy_gold_and_oil_trends():
    fixtures = market_fixture()

    assert market_context.classify_trend(fixtures["DX-Y.NYB"])["trend"] in {"rising", "falling", "stable"}
    assert market_context.classify_trend(fixtures["GC=F"])["trend"] in {"rising", "falling", "stable"}
    assert market_context.classify_trend(fixtures["CL=F"])["trend"] in {"rising", "falling", "stable"}


def test_gold_and_oil_primary_failure_can_use_documented_yfinance_fallback(monkeypatch):
    fixtures = market_fixture()
    install_fake_market(monkeypatch, fixtures, fail_symbols={"GC=F", "CL=F"})
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", True)
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())

    payload = repository.get_live_market_context(allow_live_fetch=True)

    assert payload["fields"]["gold_trend"] in {"rising", "falling", "stable"}
    assert payload["fields"]["oil_trend"] in {"rising", "falling", "stable"}
    assert payload["raw_market_context"]["gold"]["fallback_symbol_used"] == "GLD"
    assert payload["raw_market_context"]["oil"]["fallback_symbol_used"] == "USO"
    assert payload["component_source_status"]["gold_trend"]["provider"] == "derived_from_yfinance"
    assert payload["component_source_status"]["oil_trend"]["provider"] == "derived_from_yfinance"


def test_dxy_failure_keeps_mock_context_and_does_not_pretend_live(monkeypatch):
    fixtures = market_fixture()
    install_fake_market(monkeypatch, fixtures, fail_symbols={"DX-Y.NYB"})
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", True)
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())

    payload = repository.get_live_market_context(allow_live_fetch=True)

    assert "dxy_trend" not in payload["fields"]
    assert payload["component_source_status"]["dxy_trend"]["source_type"] == "mock"
    assert payload["component_source_status"]["dxy_trend"]["fallback_used"] is False


def test_macro_regime_uses_yfinance_context_and_reduces_mock_fields(monkeypatch):
    fixtures = market_fixture()
    calls = install_fake_market(monkeypatch, fixtures)
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", True)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())

    report = build_daily_report()
    quality = report.macro_regime.macro_data_quality
    components = {component.name: component for component in report.macro_regime.components}

    assert report.macro_regime.source_status.source_type == "derived"
    assert report.macro_regime.source_status.provider == "mixed_FRED_yfinance_and_mock_macro"
    assert quality.yfinance_macro_fields_count > 0
    assert quality.mock_macro_fields_count < 8
    assert "vix" not in quality.mock_context_fields
    assert "dxy_trend" not in quality.mock_context_fields
    assert "gold_trend" not in quality.mock_context_fields
    assert "oil_trend" not in quality.mock_context_fields
    assert "equity_drawdown" not in quality.mock_context_fields
    assert "gain_from_recent_trough" not in quality.mock_context_fields
    assert {"fear_greed", "ism_manufacturing_pmi"}.issubset(set(quality.mock_context_fields))
    assert components["vix"].source_status.provider == "derived_from_yfinance"
    assert components["dxy_trend"].source_status.provider == "derived_from_yfinance"
    assert components["fear_greed"].source_status.source_type == "mock"
    assert components["fear_greed"].source_status.freshness_window != "derived_from_FRED"
    assert report.data_quality.macro["yfinance_macro_fields_count"] > 0
    assert report.data_quality.macro["provider"] == "mixed_FRED_yfinance_and_mock_macro"
    assert calls.count("SPY") == 1
    assert calls.count("QQQ") == 1
    assert calls.count("^VIX") == 1


def test_macro_market_context_reuses_daily_market_data(monkeypatch):
    fixtures = market_fixture()
    calls = install_fake_market(monkeypatch, fixtures)
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", True)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())

    report = build_daily_report()

    assert report.data_quality.macro["market_context_reused_from_daily_market_data"] is True
    assert calls.count("SPY") == 1
    assert calls.count("QQQ") == 1
    assert calls.count("^VIX") == 1


def test_market_context_disabled_keeps_mock_context(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", False)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())

    report = build_daily_report()
    quality = report.macro_regime.macro_data_quality

    assert "vix" in quality.mock_context_fields
    assert quality.yfinance_macro_fields_count == 0
    assert report.macro_regime.source_status.provider == "mixed_FRED_and_mock_macro"
