from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from backend.app import config
from backend.app.schemas.operations_settings import SEC13FManagerUniverseSettings, SEC13FManagerUniverseUpdate, normalize_cik


def _settings_path() -> Path:
    return Path(os.getenv("OPERATIONS_SETTINGS_PATH", "backend/raw_store/operations_settings.json"))


def _read_payload() -> dict[str, Any]:
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_payload(payload: dict[str, Any]) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    try:
        tmp.replace(path)
    except PermissionError:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _split_ciks(raw: str | None) -> list[str]:
    if not raw:
        return []
    normalized: list[str] = []
    for item in raw.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        try:
            cik = normalize_cik(stripped)
        except ValueError:
            continue
        if cik not in normalized:
            normalized.append(cik)
    return normalized


def get_local_13f_manager_ciks() -> list[str]:
    section = _read_payload().get("sec_13f_manager_universe")
    if not isinstance(section, dict):
        return []
    values = section.get("manager_ciks")
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for item in values:
        try:
            cik = normalize_cik(str(item))
        except ValueError:
            continue
        if cik not in normalized:
            normalized.append(cik)
    return normalized


def get_local_13f_note() -> str | None:
    section = _read_payload().get("sec_13f_manager_universe")
    if not isinstance(section, dict):
        return None
    note = section.get("note")
    return str(note) if note else None


def startup_env_13f_manager_ciks() -> list[str]:
    return _split_ciks(config.SEC_13F_TARGET_MANAGERS)


def effective_13f_manager_ciks(*, include_bundled_default: bool = True) -> list[str]:
    local = get_local_13f_manager_ciks()
    if local:
        return local
    startup = startup_env_13f_manager_ciks()
    if startup:
        return startup
    if not include_bundled_default:
        return []
    return list(config.DEFAULT_SEC_13F_TARGET_MANAGERS)


def manager_universe_source() -> str:
    if get_local_13f_manager_ciks():
        return "local_settings"
    if os.getenv("SEC_13F_TARGET_MANAGERS") is not None:
        return "startup_env"
    return "bundled_starter_universe"


def _warnings(effective: list[str], source: str) -> list[str]:
    starter = set(config.DEFAULT_SEC_13F_TARGET_MANAGERS)
    missing = sorted(starter - set(effective))
    if source in {"local_settings", "startup_env"} and missing:
        return [
            "SEC 13F manager universe is narrower than the bundled starter universe; compare C19/smart-money target-match evidence across runs only if this scope is intentional."
        ]
    return []


def get_13f_manager_universe_settings() -> SEC13FManagerUniverseSettings:
    local = get_local_13f_manager_ciks()
    startup = startup_env_13f_manager_ciks() or list(config.DEFAULT_SEC_13F_TARGET_MANAGERS)
    effective = effective_13f_manager_ciks()
    source = manager_universe_source()
    return SEC13FManagerUniverseSettings(
        source=source,  # type: ignore[arg-type]
        effective_manager_ciks=effective,
        local_manager_ciks=local,
        startup_env_manager_ciks=startup,
        note=get_local_13f_note(),
        warnings=_warnings(effective, source),
    )


def update_13f_manager_universe_settings(update: SEC13FManagerUniverseUpdate) -> SEC13FManagerUniverseSettings:
    payload = _read_payload()
    payload["sec_13f_manager_universe"] = {
        "manager_ciks": update.manager_ciks,
        "note": update.note,
    }
    _write_payload(payload)
    return get_13f_manager_universe_settings()


def clear_13f_manager_universe_settings() -> SEC13FManagerUniverseSettings:
    payload = _read_payload()
    payload.pop("sec_13f_manager_universe", None)
    _write_payload(payload)
    return get_13f_manager_universe_settings()


def effective_13f_manager_ciks_csv() -> str:
    return ",".join(effective_13f_manager_ciks())
