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
FRED_API_KEY_PLACEHOLDERS = {"your_key_here", "none", "null", "placeholder", "demo"}
# Deprecated in Phase 12.3b. Developer tools may still validate candidate FRED series,
# but production reports do not enable ISM Manufacturing PMI scoring.
ENABLE_LIVE_ISM_MANUFACTURING_PMI = _env_bool("ENABLE_LIVE_ISM_MANUFACTURING_PMI", False)
ISM_MANUFACTURING_PMI_SERIES_ID = os.getenv("ISM_MANUFACTURING_PMI_SERIES_ID", "").strip().upper()
ISM_MANUFACTURING_PMI_SOURCE_LABEL = os.getenv("ISM_MANUFACTURING_PMI_SOURCE_LABEL", "Unconfigured FRED PMI source").strip() or "Unconfigured FRED PMI source"
ISM_MANUFACTURING_PMI_IS_PROXY = _env_bool("ISM_MANUFACTURING_PMI_IS_PROXY", True)


def is_fred_api_key_configured() -> bool:
    return bool(FRED_API_KEY) and FRED_API_KEY.lower() not in FRED_API_KEY_PLACEHOLDERS

USE_LIVE_SEC_FORM4 = _env_bool("USE_LIVE_SEC_FORM4", False)
SEC_FORM4_PROVIDER = os.getenv("SEC_FORM4_PROVIDER", "sec_edgar").strip().lower() or "sec_edgar"
SEC_EDGAR_USER_AGENT = os.getenv("SEC_EDGAR_USER_AGENT", "").strip()
SEC_FORM4_CACHE_DIR = Path(os.getenv("SEC_FORM4_CACHE_DIR", "backend/raw_store/cache/sec"))
SEC_EDGAR_REQUEST_DELAY_SECONDS = float(os.getenv("SEC_EDGAR_REQUEST_DELAY_SECONDS", "0.2") or "0.2")
SEC_FORM4_CACHE_TTL_HOURS = float(os.getenv("SEC_FORM4_CACHE_TTL_HOURS", "24") or "24")
SEC_FORM4_LOOKBACK_DAYS = int(os.getenv("SEC_FORM4_LOOKBACK_DAYS", "180") or "180")

USE_LIVE_SEC_13F = _env_bool("USE_LIVE_SEC_13F", False)
SEC_13F_PROVIDER = os.getenv("SEC_13F_PROVIDER", "sec_edgar").strip().lower() or "sec_edgar"
SEC_13F_CACHE_DIR = Path(os.getenv("SEC_13F_CACHE_DIR", "backend/raw_store/cache/sec_13f"))
SEC_13F_CACHE_TTL_DAYS = float(os.getenv("SEC_13F_CACHE_TTL_DAYS", "7") or "7")
SEC_13F_LOOKBACK_QUARTERS = int(os.getenv("SEC_13F_LOOKBACK_QUARTERS", "4") or "4")
SEC_13F_TARGET_MANAGERS = os.getenv("SEC_13F_TARGET_MANAGERS", "").strip()
SEC_13F_TARGET_CUSIPS = os.getenv("SEC_13F_TARGET_CUSIPS", "").strip()
SEC_13F_TARGET_TICKERS = os.getenv("SEC_13F_TARGET_TICKERS", "").strip()
SEC_13F_TARGET_ISSUERS = os.getenv("SEC_13F_TARGET_ISSUERS", "").strip()
SEC_13F_ASSUME_VALUE_THOUSANDS = _env_bool("SEC_13F_ASSUME_VALUE_THOUSANDS", False)
INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT = _env_bool("INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT", False)
SEC_13F_PRICE_REFERENCE_MAX_TICKERS = int(os.getenv("SEC_13F_PRICE_REFERENCE_MAX_TICKERS", "20") or "20")
SEC_13F_PRICE_REFERENCE_TOTAL_BUDGET_SECONDS = float(os.getenv("SEC_13F_PRICE_REFERENCE_TOTAL_BUDGET_SECONDS", "10") or "10")
SEC_13F_CANDIDATE_CONTEXT_TOP_HOLDINGS_LIMIT = int(os.getenv("SEC_13F_CANDIDATE_CONTEXT_TOP_HOLDINGS_LIMIT", "5") or "5")

ALLOW_LIVE_FETCH_ON_REPORT_REQUEST = _env_bool("ALLOW_LIVE_FETCH_ON_REPORT_REQUEST", False)
ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST = _env_bool("ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST", False)
DAILY_REPORT_FAST_MODE = _env_bool("DAILY_REPORT_FAST_MODE", True)
INCLUDE_PERFORMANCE_DIAGNOSTICS = _env_bool("INCLUDE_PERFORMANCE_DIAGNOSTICS", False)
PRICE_REFERENCE_CACHE_WARMUP_ON_STARTUP = _env_bool("PRICE_REFERENCE_CACHE_WARMUP_ON_STARTUP", False)
PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT = _env_bool("PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT", False)
PRICE_REFERENCE_CACHE_WARMUP_MAX_TICKERS = int(os.getenv("PRICE_REFERENCE_CACHE_WARMUP_MAX_TICKERS", "20") or "20")

DAILY_REPORT_READ_MODE = os.getenv("DAILY_REPORT_READ_MODE", "snapshot_first").strip().lower() or "snapshot_first"
DAILY_BATCH_ALLOW_LIVE_FETCH = _env_bool("DAILY_BATCH_ALLOW_LIVE_FETCH", True)
DAILY_BATCH_PRICE_REFERENCE_WARMUP = _env_bool("DAILY_BATCH_PRICE_REFERENCE_WARMUP", True)
DAILY_BATCH_MAX_RUNTIME_SECONDS = float(os.getenv("DAILY_BATCH_MAX_RUNTIME_SECONDS", "180") or "180")
DAILY_BATCH_PRICE_REFERENCE_WARMED = False

SEC_FORM4_MAX_FILINGS_PER_TICKER = int(os.getenv("SEC_FORM4_MAX_FILINGS_PER_TICKER", "10") or "10")
SEC_FORM4_MAX_XML_DISCOVERY_PER_REPORT = int(os.getenv("SEC_FORM4_MAX_XML_DISCOVERY_PER_REPORT", "20") or "20")
SEC_FORM4_NETWORK_TIMEOUT_SECONDS = float(os.getenv("SEC_FORM4_NETWORK_TIMEOUT_SECONDS", "10") or "10")
SEC_FORM4_TOTAL_BUDGET_SECONDS = float(os.getenv("SEC_FORM4_TOTAL_BUDGET_SECONDS", "20") or "20")
