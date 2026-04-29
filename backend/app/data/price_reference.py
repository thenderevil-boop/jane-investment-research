from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.app import config


@dataclass(frozen=True)
class PriceReference:
    ticker: str
    price: float
    source_date: str
    provider: str
    confidence: str = "medium"

    def model_dump(self) -> dict[str, object]:
        return asdict(self)


def _cache_key(ticker: str) -> str:
    return ticker.replace("^", "index_").replace("/", "_").upper()


def _candidate_cache_paths(ticker: str) -> list[Path]:
    return [
        config.MARKET_DATA_CACHE_DIR / f"{_cache_key(ticker)}.json",
        config.MARKET_DATA_CACHE_DIR / "market" / f"{_cache_key(ticker)}.json",
    ]


def _extract_price(payload: dict) -> tuple[float | None, str]:
    if isinstance(payload.get("latest_close"), (int, float)):
        return float(payload["latest_close"]), str(payload.get("source_date") or "")
    rows = payload.get("rows") or payload.get("prices") or []
    if isinstance(rows, list):
        for row in reversed(rows):
            if not isinstance(row, dict):
                continue
            price = row.get("close") or row.get("Close") or row.get("adj_close") or row.get("Adj Close")
            if isinstance(price, (int, float)):
                return float(price), str(row.get("date") or row.get("Date") or payload.get("source_date") or "")
    return None, str(payload.get("source_date") or "")


def get_price_reference(ticker: str, as_of_date: str | None = None) -> PriceReference | None:
    normalized = str(ticker or "").strip().upper()
    if not normalized or not config.USE_LIVE_MARKET_DATA:
        return None
    for path in _candidate_cache_paths(normalized):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        price, source_date = _extract_price(payload)
        if price is None or price <= 0:
            continue
        return PriceReference(
            ticker=normalized,
            price=price,
            source_date=source_date or as_of_date or "",
            provider=str(payload.get("provider") or "yfinance_cache"),
            confidence="medium",
        )
    return None
