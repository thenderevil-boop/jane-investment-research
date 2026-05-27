from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def _payload() -> dict:
    response = client.get("/api/operations/diagnostics")
    assert response.status_code == 200
    return response.json()


def test_operations_diagnostics_contract_redacts_secrets(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "should_not_leak_phase62")
    monkeypatch.setenv("FRED_API_KEY", "fred_should_not_leak_phase62")
    payload = _payload()

    serialized = str(payload)
    assert payload["version"] == "phase62_operations_diagnostics_v1"
    assert payload["not_investment_advice"] is True
    assert payload["secrets_policy"]["api_key_values_returned"] is False
    assert "only safe booleans" in payload["secrets_policy"]["redaction_policy"]
    assert "should_not_leak_phase62" not in serialized
    assert "fred_should_not_leak_phase62" not in serialized


def test_operations_diagnostics_includes_phase61_priority_sources():
    payload = _payload()
    providers = {row["provider_id"]: row for row in payload["providers"]}

    for provider_id in {
        "sec_13f",
        "sec_form4",
        "uspto_patentsview",
        "fred_macro",
        "yfinance_market",
        "fmp_financial_proxy",
        "fmp_transcript",
        "usaspending",
        "openbb_sidecar",
        "sec_companyfacts",
        "daily_report_snapshot",
    }:
        assert provider_id in providers
        assert "enabled" in providers[provider_id]
        assert providers[provider_id]["source_type"] in {"live", "cached_live", "derived", "fallback", "mock", "disabled", "unknown"}
        assert "next_action" in providers[provider_id]


def test_operations_diagnostics_maps_c18_c19_readiness():
    payload = _payload()
    rows = {(row["criterion_id"], row["provider_id"]): row for row in payload["coverage_readiness"]}

    c18 = rows[(18, "uspto_patentsview")]
    c19 = rows[(19, "sec_13f")]
    assert c18["readiness"] in {"ready", "partial", "disabled", "missing_key", "stale", "unavailable"}
    assert "patent_count" in c18["covered_submetrics"]
    assert c19["readiness"] in {"ready", "partial", "disabled", "missing_key", "stale", "unavailable"}
    assert "institutional_support" in c19["covered_submetrics"]
    assert "fund_support" in c19["covered_submetrics"]
    assert c18["not_investment_advice"] is True
    assert c19["not_investment_advice"] is True


def test_operations_diagnostics_13f_universe_is_runtime_not_default_requirement():
    payload = _payload()
    universe = payload["manager_universe"]
    assert universe["source"] in {"startup_env", "local_settings", "bundled_starter_universe"}
    assert universe["manager_count"] >= 0
    assert isinstance(universe["is_runtime_override"], bool)
    assert "default managers" not in str(payload).lower()


def test_operations_diagnostics_runtime_is_read_only_and_no_provider_fetch(monkeypatch):
    # The diagnostics endpoint should summarize configuration/readiness only.
    # If a future implementation calls live provider fetches, this test should be updated to fail loudly.
    payload = _payload()
    assert payload["runtime"]["not_investment_advice"] is True
    assert payload["runtime"]["read_only"] is True
    assert payload["runtime"]["triggers_provider_calls"] is False
