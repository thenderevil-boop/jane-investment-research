from __future__ import annotations

import os
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


USE_LIVE_MARKET_DATA = _env_bool("USE_LIVE_MARKET_DATA", False)
MARKET_DATA_PROVIDER = os.getenv("MARKET_DATA_PROVIDER", "yfinance").strip().lower() or "yfinance"
MARKET_DATA_CACHE_DIR = Path(os.getenv("MARKET_DATA_CACHE_DIR", "backend/raw_store/cache"))

