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

USE_LIVE_MACRO_DATA = _env_bool("USE_LIVE_MACRO_DATA", False)
FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()
MACRO_DATA_PROVIDER = os.getenv("MACRO_DATA_PROVIDER", "fred").strip().lower() or "fred"
MACRO_DATA_CACHE_DIR = Path(os.getenv("MACRO_DATA_CACHE_DIR", "backend/raw_store/cache/macro"))

USE_LIVE_SEC_FORM4 = _env_bool("USE_LIVE_SEC_FORM4", False)
SEC_FORM4_PROVIDER = os.getenv("SEC_FORM4_PROVIDER", "sec_edgar").strip().lower() or "sec_edgar"
SEC_EDGAR_USER_AGENT = os.getenv("SEC_EDGAR_USER_AGENT", "paul.chang thenderevil@gmail.com").strip()
SEC_FORM4_CACHE_DIR = Path(os.getenv("SEC_FORM4_CACHE_DIR", "backend/raw_store/cache/sec"))
SEC_EDGAR_REQUEST_DELAY_SECONDS = float(os.getenv("SEC_EDGAR_REQUEST_DELAY_SECONDS", "0.2") or "0.2")
SEC_FORM4_CACHE_TTL_HOURS = float(os.getenv("SEC_FORM4_CACHE_TTL_HOURS", "24") or "24")
SEC_FORM4_LOOKBACK_DAYS = int(os.getenv("SEC_FORM4_LOOKBACK_DAYS", "180") or "180")
ALLOW_LIVE_FETCH_ON_REPORT_REQUEST = _env_bool("ALLOW_LIVE_FETCH_ON_REPORT_REQUEST", False)
