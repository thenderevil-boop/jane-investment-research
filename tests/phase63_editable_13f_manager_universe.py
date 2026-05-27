from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app

client = TestClient(app)


def _settings_path() -> Path:
    path = Path("backend/raw_store/cache/test_phase63_operations_settings") / f"{uuid4().hex}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_get_13f_manager_universe_settings_defaults_to_startup_or_bundled(monkeypatch):
    monkeypatch.setenv("OPERATIONS_SETTINGS_PATH", str(_settings_path()))
    monkeypatch.delenv("SEC_13F_TARGET_MANAGERS", raising=False)
    monkeypatch.setattr(config, "SEC_13F_TARGET_MANAGERS", ",".join(config.DEFAULT_SEC_13F_TARGET_MANAGERS))

    response = client.get("/api/operations/settings/13f-manager-universe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "phase63_13f_manager_universe_settings_v1"
    assert payload["source"] == "bundled_starter_universe"
    assert payload["effective_manager_ciks"] == config.DEFAULT_SEC_13F_TARGET_MANAGERS
    assert payload["local_manager_ciks"] == []
    assert payload["startup_env_manager_ciks"] == config.DEFAULT_SEC_13F_TARGET_MANAGERS
    assert payload["editable"] is True
    assert payload["not_investment_advice"] is True


def test_put_13f_manager_universe_persists_local_settings_and_updates_diagnostics(monkeypatch):
    settings_path = _settings_path()
    monkeypatch.setenv("OPERATIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.delenv("SEC_13F_TARGET_MANAGERS", raising=False)
    monkeypatch.setattr(config, "SEC_13F_TARGET_MANAGERS", ",".join(config.DEFAULT_SEC_13F_TARGET_MANAGERS))
    managers = ["1067983", "0000102909", "0001364742"]

    response = client.put(
        "/api/operations/settings/13f-manager-universe",
        json={"manager_ciks": managers, "note": "core institutional review list"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_settings"
    assert payload["effective_manager_ciks"] == ["0001067983", "0000102909", "0001364742"]
    assert payload["local_manager_ciks"] == ["0001067983", "0000102909", "0001364742"]
    assert payload["note"] == "core institutional review list"
    assert settings_path.exists()

    diagnostics = client.get("/api/operations/diagnostics").json()
    assert diagnostics["manager_universe"]["source"] == "local_settings"
    assert diagnostics["manager_universe"]["manager_count"] == 3
    assert diagnostics["manager_universe"].get("editable") is True


def test_13f_manager_universe_local_settings_override_startup_env_but_show_env(monkeypatch):
    monkeypatch.setenv("OPERATIONS_SETTINGS_PATH", str(_settings_path()))
    monkeypatch.setenv("SEC_13F_TARGET_MANAGERS", "0000000001,0000000002")
    monkeypatch.setattr(config, "SEC_13F_TARGET_MANAGERS", "0000000001,0000000002")

    client.put(
        "/api/operations/settings/13f-manager-universe",
        json={"manager_ciks": ["0001067983"]},
    )
    payload = client.get("/api/operations/settings/13f-manager-universe").json()

    assert payload["source"] == "local_settings"
    assert payload["effective_manager_ciks"] == ["0001067983"]
    assert payload["startup_env_manager_ciks"] == ["0000000001", "0000000002"]
    assert payload["precedence"] == ["local_settings", "startup_env", "bundled_starter_universe"]


def test_13f_manager_universe_rejects_invalid_or_empty_ciks(monkeypatch):
    monkeypatch.setenv("OPERATIONS_SETTINGS_PATH", str(_settings_path()))

    invalid = client.put("/api/operations/settings/13f-manager-universe", json={"manager_ciks": ["abc"]})
    empty = client.put("/api/operations/settings/13f-manager-universe", json={"manager_ciks": []})

    assert invalid.status_code == 422
    assert empty.status_code == 422


def test_13f_manager_universe_reset_clears_local_settings(monkeypatch):
    monkeypatch.setenv("OPERATIONS_SETTINGS_PATH", str(_settings_path()))
    monkeypatch.delenv("SEC_13F_TARGET_MANAGERS", raising=False)
    monkeypatch.setattr(config, "SEC_13F_TARGET_MANAGERS", ",".join(config.DEFAULT_SEC_13F_TARGET_MANAGERS))

    client.put("/api/operations/settings/13f-manager-universe", json={"manager_ciks": ["0001067983"]})
    response = client.delete("/api/operations/settings/13f-manager-universe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "bundled_starter_universe"
    assert payload["local_manager_ciks"] == []
    assert payload["effective_manager_ciks"] == config.DEFAULT_SEC_13F_TARGET_MANAGERS
