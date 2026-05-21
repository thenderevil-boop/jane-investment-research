from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.reports import stock_analysis

client = TestClient(app)


class DummyResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        return None


def _tmp_cache() -> Path:
    path = Path("backend/raw_store/cache/test_phase41") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stockgrid_payload() -> dict:
    return {
        "data": [
            {
                "symbol": "NVDA",
                "sentiment": "bullish",
                "sentiment_score": 0.82,
                "size": 1_500_000,
                "premium": 1_500_000,
                "volume": 12_000,
                "open_interest": 3_000,
                "option_type": "call",
                "order_type": "sweep",
                "expiration": "2026-06-19",
                "trade_date": "2026-05-20",
            },
            {
                "symbol": "NVDA",
                "sentiment": "neutral",
                "sentiment_score": 0.5,
                "size": 250_000,
                "premium": 250_000,
                "volume": 2_000,
                "open_interest": 2_000,
                "option_type": "put",
                "order_type": "block",
                "expiration": "2026-06-19",
                "trade_date": "2026-05-20",
            },
        ]
    }


def _fake_openbb_get(url: str, timeout: int = 15):
    assert "NVDA" in url or "nvda" in url
    assert "apikey" not in url.lower()
    return DummyResponse(_stockgrid_payload())


def test_openbb_options_adapter_disabled_state_is_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "USE_OPENBB_SIDECAR", False)
    import backend.app.data_sources.openbb_options as openbb_options

    payload = openbb_options.fetch_openbb_options_activity("NVDA", http_get=_fake_openbb_get)

    assert payload["available"] is False
    assert payload["provider"] == "openbb_stockgrid"
    assert payload["source_status"]["source_type"] == "unknown"
    assert "openbb_stockgrid_options" in payload["missing_data"]


def test_openbb_options_adapter_normalizes_stockgrid_large_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "USE_OPENBB_SIDECAR", True)
    monkeypatch.setattr(config, "OPENBB_BASE_URL", "http://127.0.0.1:6900")
    monkeypatch.setattr(config, "OPENBB_CACHE_TTL_DAYS", 3)
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", tmp_path)
    import backend.app.data_sources.openbb_options as openbb_options

    payload = openbb_options.fetch_openbb_options_activity("nvda", http_get=_fake_openbb_get)

    assert payload["available"] is True
    assert payload["provider"] == "openbb_stockgrid"
    assert payload["source_status"]["source_type"] == "live"
    assert payload["source_status"]["provider"] == "openbb_stockgrid"
    assert payload["source_status"]["source_date"] == "2026-05-20"
    assert payload["options_activity"]["option_volume"] == 14_000
    assert payload["options_activity"]["open_interest"] == 5_000
    assert payload["options_activity"]["abnormal_volume_ratio"] == 2.8
    assert payload["options_activity"]["call_put_ratio"] == 6.0
    assert payload["derived_metrics"]["large_block_count"] == 2
    assert payload["derived_metrics"]["total_premium"] == 1_750_000
    assert payload["normalized_blocks"][0]["order_type"] == "sweep"
    assert payload["normalized_blocks"][0]["sentiment_score"] == 0.82


def test_analyze_stock_uses_openbb_options_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.app.data_sources.openbb_options as openbb_options

    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", _tmp_cache())
    monkeypatch.setattr(stock_analysis, "get_openbb_options_activity", lambda ticker: openbb_options._options_payload_from_raw("NVDA", _stockgrid_payload(), source_type="live", fetched_at="2026-05-20T12:00:00+00:00"))

    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200
    payload = response.json()

    options_component = payload["smart_money"]["derived_metrics"]["components"]["options_abnormal_activity"]
    options_raw = payload["smart_money"]["raw_data"]["options"]
    options_breakdown = payload["smart_money"]["source_quality_breakdown"]["options"]

    assert options_component["source_status"]["provider"] == "openbb_stockgrid"
    assert options_component["source_status"]["source_type"] == "live"
    assert options_raw["provider"] == "openbb_stockgrid"
    assert options_raw["large_block_count"] == 2
    assert options_breakdown["source_type"] == "live"
    assert "Mock options" not in options_breakdown["score_impact"]
    assert "option_volume" not in payload["smart_money"]["missing_data"]
    assert payload["not_investment_advice"] is True
