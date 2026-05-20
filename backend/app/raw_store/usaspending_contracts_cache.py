from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.app import config


def _cache_dir() -> Path:
    path = config.MARKET_DATA_CACHE_DIR / "usaspending_contracts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_key(ticker: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in ticker.strip().upper()).strip("_") or "UNKNOWN"


def _cache_path(ticker: str) -> Path:
    return _cache_dir() / f"{_cache_key(ticker)}.json"


def _as_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def save_usaspending_contracts_snapshot(ticker: str, payload: dict[str, Any], fetched_at: datetime | None = None) -> dict[str, Any]:
    now = fetched_at or datetime.now(timezone.utc)
    snapshot = {
        "ticker": ticker.strip().upper(),
        "fetched_at": now.isoformat(),
        "payload": payload,
    }
    _cache_path(ticker).write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return snapshot


def load_cached_usaspending_contracts(ticker: str, ttl_days: int, now: datetime | None = None) -> dict[str, Any] | None:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fetched_at = _as_datetime(snapshot.get("fetched_at"))
    if not fetched_at:
        return None
    current = now or datetime.now(timezone.utc)
    if current - fetched_at > timedelta(days=max(ttl_days, 0)):
        return None
    payload = dict(snapshot.get("payload") or {})
    payload.update({
        "ticker": snapshot.get("ticker", ticker.strip().upper()),
        "fetched_at": snapshot.get("fetched_at"),
        "cache_hit": True,
    })
    return payload
