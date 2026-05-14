from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.data_sources import live_macro_fred
from backend.app.main import app
from backend.app.pipelines.mock_pipeline import build_daily_report
from backend.app.raw_store import repository
from backend.app.tools import fred_series_search, fred_series_validate

client = TestClient(app)

EXPECTED_JANE_DISPLAY_TEXT = {
    "fed_rate_cut_cycle": "當美國聯準會開始連續降息時",
    "major_index_drawdown_and_base": "當整體股價指數（S&P 500、那斯達克）下跌 20% 以上後進入盤整時",
    "cnn_fear_greed_extreme_fear": "當 CNN 恐懼與貪婪指數低於 20，進入極度恐慌時",
}
MOJIBAKE_FRAGMENTS = ("ç¶", "è", "æ", "ï¼")


def workspace_tmp_dir() -> Path:
    path = Path("backend/raw_store/cache/test_phase123") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeResponse:
    def __init__(self, payload: dict | list[dict], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise live_macro_fred.httpx.HTTPStatusError("bad request api_key=test-key https://api.stlouisfed.org/fred/series?series_id=NAPM", request=None, response=self)
        return None

    def json(self):
        if isinstance(self._payload, list):
            return {"observations": self._payload}
        return self._payload


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
    return [{"date": f"2026-04-{27 + index:02d}", "value": str(value)} for index, value in enumerate(values)]


def fred_payloads() -> dict[str, list[dict]]:
    return {
        "FEDFUNDS": monthly_rows([4.5] * 12 + [4.5, 4.4, 4.25], start_month=2),
        "DGS10": daily_rows([4.1, 4.2, 4.3]),
        "DGS2": daily_rows([3.9, 4.0, 4.05]),
        "CPIAUCSL": monthly_rows([300.0] * 12 + [306.0, 307.0, 309.0], start_month=2),
        "PPIACO": monthly_rows([250.0] * 12 + [255.0, 256.0, 257.5], start_month=2),
        "UNRATE": monthly_rows([4.0] * 12 + [4.0, 4.1, 4.2], start_month=2),
        "PMITEST": monthly_rows([49.0] * 12 + [50.5, 51.0, 52.0], start_month=2),
        "IPMAN": monthly_rows([95.0] * 12 + [96.0, 96.5, 97.0], start_month=2),
    }


def market_rows(start: float, step: float, days: int = 260) -> list[dict]:
    rows = []
    for index in range(days):
        close = round(start + step * index, 4)
        rows.append({"date": f"2026-04-{1 + min(index, 29):02d}", "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1000000 + index})
    return rows


def market_snapshot(symbol: str, rows: list[dict]) -> dict:
    return {
        "ticker": symbol,
        "source": "yfinance",
        "source_type": "live",
        "provider": "yfinance",
        "source_date": rows[-1]["date"],
        "period": "1y",
        "interval": "1d",
        "rows": rows,
        "limitations": ["Yfinance data is suitable for MVP research reference only."],
        "missing_data": [],
    }


def install_fake_market(monkeypatch):
    fixtures = {
        "SPY": market_snapshot("SPY", market_rows(300, 0.4)),
        "QQQ": market_snapshot("QQQ", market_rows(250, 0.55)),
        "^VIX": market_snapshot("^VIX", market_rows(16, 0.02)),
        "DX-Y.NYB": market_snapshot("DX-Y.NYB", market_rows(100, 0.02)),
        "GC=F": market_snapshot("GC=F", market_rows(2000, 3.0)),
        "CL=F": market_snapshot("CL=F", market_rows(70, -0.02)),
    }

    def fake_get_market_data(symbol: str, use_live: bool | None = None, period: str = "1y", interval: str = "1d"):
        return fixtures[symbol]

    monkeypatch.setattr(repository, "get_market_data", fake_get_market_data)


def install_live_macro_and_market_fakes(monkeypatch) -> None:
    install_fake_fred(monkeypatch)
    install_fake_market(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())


def assert_no_mixed_source_type(payload) -> None:
    if isinstance(payload, dict):
        assert payload.get("source_type") != "mixed"
        for value in payload.values():
            assert_no_mixed_source_type(value)
    elif isinstance(payload, list):
        for value in payload:
            assert_no_mixed_source_type(value)


def install_fake_fred(monkeypatch, *, fail_napm: bool = True):
    payloads = fred_payloads()

    def fake_get(_url: str, params: dict, timeout: int):
        series_id = params.get("series_id")
        if "series/search" in _url:
            return FakeResponse({"seriess": [{"id": "PMITEST", "title": "Manufacturing PMI test proxy", "frequency": "Monthly", "units": "Index", "seasonal_adjustment": "Seasonally Adjusted", "observation_start": "2020-01-01", "observation_end": "2026-03-01", "popularity": 50, "last_updated": "2026-04-01", "notes": "safe notes"}]})
        if "series/observations" not in _url:
            if fail_napm and series_id == "NAPM":
                return FakeResponse({}, status_code=400)
            title = "Industrial Production: Manufacturing" if series_id == "IPMAN" else "Manufacturing PMI test proxy"
            return FakeResponse({"seriess": [{"id": series_id, "title": title, "frequency": "Monthly", "observation_start": "2020-01-01", "observation_end": "2026-03-01", "last_updated": "2026-04-01", "notes": "safe notes"}]})
        if fail_napm and series_id == "NAPM":
            return FakeResponse({}, status_code=400)
        return FakeResponse(payloads[series_id])

    monkeypatch.setattr(config, "FRED_API_KEY", "test-key")
    monkeypatch.setattr(config, "ENABLE_LIVE_ISM_MANUFACTURING_PMI", True)
    monkeypatch.setattr(config, "ISM_MANUFACTURING_PMI_SERIES_ID", "PMITEST")
    monkeypatch.setattr(config, "ISM_MANUFACTURING_PMI_SOURCE_LABEL", "Manufacturing PMI test proxy")
    monkeypatch.setattr(config, "ISM_MANUFACTURING_PMI_IS_PROXY", True)
    monkeypatch.setattr(live_macro_fred.httpx, "get", fake_get)


def test_validate_fred_series_returns_invalid_series_for_http_400(monkeypatch):
    install_fake_fred(monkeypatch)

    result = live_macro_fred.validate_fred_series("NAPM")

    assert result["is_valid"] is False
    assert result["error_type"] == "invalid_series"
    assert result["sanitized_error"] == "Configured FRED PMI series is unavailable or invalid."


def test_validate_fred_series_redacts_api_key_and_url(monkeypatch):
    install_fake_fred(monkeypatch)

    result = live_macro_fred.validate_fred_series("NAPM")
    combined = str(result)

    assert "test-key" not in combined
    assert "api_key" not in combined.lower()
    assert "stlouisfed.org" not in combined.lower()


def test_fred_series_validate_cli_handles_invalid_napm_safely(monkeypatch, capsys):
    install_fake_fred(monkeypatch)

    code = fred_series_validate.main(["NAPM"])
    output = capsys.readouterr().out

    assert code == 1
    assert '"is_valid": false' in output
    assert "test-key" not in output
    assert "api_key" not in output.lower()
    assert "stlouisfed.org" not in output.lower()


def test_fred_series_search_cli_prints_safe_candidate_metadata(monkeypatch, capsys):
    install_fake_fred(monkeypatch)

    code = fred_series_search.main(["ISM Manufacturing PMI"])
    output = capsys.readouterr().out

    assert code == 0
    assert "PMITEST" in output
    assert "Manufacturing PMI test proxy" in output
    assert "test-key" not in output
    assert "api_key" not in output.lower()
    assert "stlouisfed.org" not in output.lower()


def test_fred_adapter_excludes_ism_manufacturing_pmi_even_when_configured(monkeypatch):
    install_fake_fred(monkeypatch)

    payload = live_macro_fred.fetch_macro_snapshot()

    assert "ism_manufacturing_pmi" not in payload["indicators"]
    assert "ism_manufacturing_pmi" not in payload["raw_series"]
    assert payload["excluded_indicators"][0]["name"] == "ism_manufacturing_pmi"
    assert payload["excluded_indicators"][0]["affects_score"] is False


def test_macro_regime_excludes_ism_manufacturing_pmi_from_scoring(monkeypatch):
    install_fake_fred(monkeypatch)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", False)
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())
    install_fake_market(monkeypatch)

    report = build_daily_report()
    quality = report.macro_regime.macro_data_quality
    components = {component.name: component for component in report.macro_regime.components}
    contribution = report.macro_regime.derived_metrics["source_contribution"]

    assert "ism_manufacturing_pmi" not in report.macro_regime.raw_data
    assert "ism_manufacturing_pmi" not in components
    assert "ism_manufacturing_pmi" not in report.macro_regime.raw_data["component_source_status"]
    assert "ism_manufacturing_pmi" not in quality.mock_context_fields
    assert "ism_manufacturing_pmi" not in contribution["mock_context_component_names"]
    assert "live ISM Manufacturing PMI data" not in report.macro_regime.missing_data
    assert all("ISM Manufacturing PMI remains mock context" not in item for item in report.macro_regime.limitations)
    assert quality.excluded_indicators[0]["name"] == "ism_manufacturing_pmi"
    assert quality.excluded_indicators[0]["affects_score"] is False


def test_macro_score_does_not_depend_on_ism_manufacturing_pmi():
    base = repository.read_macro_data(use_live=False)
    with_low_pmi = {**base, "ism_manufacturing_pmi": 1.0}
    with_high_pmi = {**base, "ism_manufacturing_pmi": 100.0}

    low_report = build_daily_report()
    from backend.app.engines.macro_regime_engine import evaluate_macro_regime

    low = evaluate_macro_regime(with_low_pmi)
    high = evaluate_macro_regime(with_high_pmi)

    assert low.score == high.score
    assert low.label == high.label
    assert low.derived_metrics["component_count"] == high.derived_metrics["component_count"]
    assert "ism_manufacturing_pmi" not in {component.name for component in low.components}
    assert low_report.macro_regime.macro_data_quality.excluded_indicators[0]["affects_score"] is False


def test_ipman_is_not_used_as_pmi_runtime_source(monkeypatch):
    install_fake_fred(monkeypatch, fail_napm=False)
    monkeypatch.setattr(config, "ISM_MANUFACTURING_PMI_SERIES_ID", "IPMAN")
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", workspace_tmp_dir())
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", False)
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", workspace_tmp_dir())

    report = build_daily_report()

    assert live_macro_fred.validate_fred_series("IPMAN")["is_valid"] is True
    assert "ism_manufacturing_pmi" not in report.macro_regime.raw_data
    assert "ism_manufacturing_pmi" not in report.macro_regime.macro_data_quality.fred_backed_fields
    assert report.macro_regime.macro_data_quality.excluded_indicators[0]["reason"].endswith("IPMAN is not PMI.")


def test_fear_greed_is_excluded_from_macro_scoring_and_context(monkeypatch):
    install_live_macro_and_market_fakes(monkeypatch)

    report = build_daily_report()
    quality = report.macro_regime.macro_data_quality
    contribution = report.macro_regime.derived_metrics["source_contribution"]
    components = {component.name for component in report.macro_regime.components}
    excluded = {item["name"]: item for item in quality.excluded_indicators}

    assert "fear_greed" not in report.macro_regime.raw_data.get("component_source_status", {})
    assert "fear_greed" not in quality.mock_context_fields
    assert "fear_greed" not in contribution["mock_context_component_names"]
    assert "fear_greed" not in components
    assert quality.mock_macro_fields_count == 0
    assert quality.has_mock_macro_context is False
    assert quality.confidence_adjustment_applied is False
    assert excluded["cnn_fear_greed"]["affects_score"] is False
    assert excluded["ism_manufacturing_pmi"]["affects_score"] is False
    assert "live Fear & Greed data" not in report.missing_data
    assert all("Fear & Greed remains mock context" not in item for item in report.limitations)


def test_jane_reference_conditions_are_utf8_display_only():
    report = build_daily_report()
    reference = report.jane_reference_conditions
    payload = report.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert reference is not None
    assert reference.affects_score is False
    assert reference.not_investment_advice is True
    by_name = {condition.name: condition for condition in reference.conditions}
    for name, expected_text in EXPECTED_JANE_DISPLAY_TEXT.items():
        assert by_name[name].display_text == expected_text
        assert expected_text in text
    for fragment in MOJIBAKE_FRAGMENTS:
        assert fragment not in text
    assert by_name["fed_rate_cut_cycle"].mapped_system_fields == ["fed_funds_rate", "fed_policy_trend"]
    assert by_name["major_index_drawdown_and_base"].mapped_system_fields == ["equity_drawdown", "gain_from_recent_trough", "SPY", "QQQ"]
    assert by_name["cnn_fear_greed_extreme_fear"].system_status == "excluded_unlicensed_source"
    assert all(condition.score_contribution_allowed is False for condition in reference.conditions)
    assert_no_mixed_source_type(payload)


def test_jane_reference_condition_text_source_is_utf8_json():
    source_path = Path("backend/app/data/jane_reference_conditions.json")
    raw_text = source_path.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    by_name = {condition["name"]: condition for condition in data["conditions"]}

    for name, expected_text in EXPECTED_JANE_DISPLAY_TEXT.items():
        assert by_name[name]["display_text"] == expected_text
        assert expected_text in raw_text
    for fragment in MOJIBAKE_FRAGMENTS:
        assert fragment not in raw_text


def test_api_daily_report_preserves_jane_reference_utf8_and_exclusions(monkeypatch):
    install_live_macro_and_market_fakes(monkeypatch)
    monkeypatch.setattr(config, "DAILY_REPORT_READ_MODE", "compute")

    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    payload = response.json()
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    reference = payload["jane_reference_conditions"]
    by_name = {condition["name"]: condition for condition in reference["conditions"]}
    quality = payload["macro_regime"]["macro_data_quality"]
    excluded = {item["name"]: item for item in quality["excluded_indicators"]}

    assert payload["not_investment_advice"] is True
    assert reference["affects_score"] is False
    assert reference["not_investment_advice"] is True
    for name, expected_text in EXPECTED_JANE_DISPLAY_TEXT.items():
        assert by_name[name]["display_text"] == expected_text
        assert expected_text in text
    for fragment in MOJIBAKE_FRAGMENTS:
        assert fragment not in text
    assert excluded["cnn_fear_greed"]["affects_score"] is False
    assert excluded["ism_manufacturing_pmi"]["affects_score"] is False
    assert payload["macro_regime"]["derived_metrics"]["scoring_model"]["version"] == "macro_v12_5"
    assert payload["macro_regime"]["macro_data_quality"]["scoring"]["active_weight_total"] == 100
    assert payload["data_quality"]["macro"]["scoring"]["scoring_model_version"] == "macro_v12_5"
    assert "cnn_fear_greed" not in {item["name"] for item in payload["macro_regime"]["derived_metrics"]["component_contributions"]}
    assert "ism_manufacturing_pmi" not in {item["name"] for item in payload["macro_regime"]["derived_metrics"]["component_contributions"]}
    assert "fear_greed" not in payload["macro_regime"]["raw_data"]["component_source_status"]
    assert "ism_manufacturing_pmi" not in payload["macro_regime"]["raw_data"]["component_source_status"]
    assert quality["mock_macro_fields_count"] == 0
    assert_no_mixed_source_type(payload)


def test_jane_reference_conditions_do_not_change_scores():
    report = build_daily_report()
    dumped = report.model_dump()
    dumped.pop("jane_reference_conditions", None)

    assert report.macro_regime.score == dumped["macro_regime"]["score"]
    assert report.market_timing.score == dumped["market_timing"]["score"]
    assert report.overheat_risk.score == dumped["overheat_risk"]["score"]
    assert report.smart_money.score == dumped["smart_money"]["score"]
