from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

from backend.app import config
from backend.app.utils.performance import add_timing, increment_metric

_REFERENCE_CACHE: dict[str, "PriceReference | None"] = {}
_LIVE_REFERENCE_TICKERS: set[str] = set()
_BUDGET_STARTED_AT: float | None = None


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


def _primary_cache_path(ticker: str) -> Path:
    return config.MARKET_DATA_CACHE_DIR / f"{_cache_key(ticker)}.json"


def clear_price_reference_cache(ticker: str | None = None) -> None:
    if ticker is None:
        _REFERENCE_CACHE.clear()
        return
    normalized = str(ticker or "").strip().upper()
    for key in list(_REFERENCE_CACHE):
        if key == normalized or key.startswith(f"{normalized}|"):
            _REFERENCE_CACHE.pop(key, None)


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
    started_at = perf_counter()
    try:
        normalized = str(ticker or "").strip().upper()
        if not normalized or not config.USE_LIVE_MARKET_DATA:
            return None
        cache_key = normalized
        if cache_key in _REFERENCE_CACHE:
            increment_metric("cache_hit_count")
            return _REFERENCE_CACHE[cache_key]
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
            reference = PriceReference(
                ticker=normalized,
                price=price,
                source_date=source_date or as_of_date or "",
                provider=str(payload.get("provider") or "yfinance_cache"),
                confidence="medium",
            )
            _REFERENCE_CACHE[cache_key] = reference
            increment_metric("cache_hit_count")
            return reference
        increment_metric("cache_miss_count")
        if not config.ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST:
            increment_metric("bounded_fetch_skipped_count")
            _REFERENCE_CACHE[cache_key] = None
            return None
        global _BUDGET_STARTED_AT
        if _BUDGET_STARTED_AT is None:
            _BUDGET_STARTED_AT = perf_counter()
        if len(_LIVE_REFERENCE_TICKERS) >= config.SEC_13F_PRICE_REFERENCE_MAX_TICKERS:
            increment_metric("bounded_fetch_skipped_count")
            _REFERENCE_CACHE[cache_key] = None
            return None
        if perf_counter() - _BUDGET_STARTED_AT > config.SEC_13F_PRICE_REFERENCE_TOTAL_BUDGET_SECONDS:
            increment_metric("bounded_fetch_skipped_count")
            _REFERENCE_CACHE[cache_key] = None
            return None
        _LIVE_REFERENCE_TICKERS.add(normalized)
        increment_metric("network_call_count")
        try:
            from backend.app.data_sources.live_market_prices import fetch_ohlcv

            payload = fetch_ohlcv(normalized, period="5d", interval="1d")
            price, source_date = _extract_price(payload)
            if price is None or price <= 0:
                _REFERENCE_CACHE[cache_key] = None
                return None
            reference = PriceReference(
                ticker=normalized,
                price=price,
                source_date=source_date or payload.get("source_date") or as_of_date or "",
                provider=str(payload.get("provider") or "yfinance"),
                confidence="medium",
            )
            _REFERENCE_CACHE[cache_key] = reference
            return reference
        except Exception:
            _REFERENCE_CACHE[cache_key] = None
            return None
    finally:
        add_timing("sec_13f_price_reference_ms", started_at)


def warm_price_reference_cache(tickers: list[str], max_tickers: int | None = None, allow_live_fetch: bool = False) -> dict[str, object]:
    unique_tickers: list[str] = []
    seen: set[str] = set()
    for ticker in tickers or []:
        normalized = str(ticker or "").strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_tickers.append(normalized)
    limit = max(0, min(max_tickers or config.PRICE_REFERENCE_CACHE_WARMUP_MAX_TICKERS, config.SEC_13F_PRICE_REFERENCE_MAX_TICKERS))
    selected = unique_tickers[:limit]
    skipped = max(0, len(unique_tickers) - len(selected))
    warmed: list[str] = []
    cache_hits: list[str] = []
    failed: list[str] = []
    live_fetch_count = 0
    if skipped:
        increment_metric("bounded_fetch_skipped_count", skipped)
    for ticker in selected:
        clear_price_reference_cache(ticker)
        cached = get_price_reference(ticker)
        if cached is not None:
            cache_hits.append(ticker)
            continue
        if not allow_live_fetch:
            failed.append(ticker)
            continue
        clear_price_reference_cache(ticker)
        previous_allow = config.ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST
        try:
            config.ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST = True
            reference = get_price_reference(ticker)
        finally:
            config.ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST = previous_allow
        if reference is None:
            failed.append(ticker)
            continue
        live_fetch_count += 1
        warmed.append(ticker)
        path = _primary_cache_path(ticker)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "latest_close": reference.price,
                    "source_date": reference.source_date,
                    "provider": "yfinance_cache" if "cache" not in reference.provider.casefold() else reference.provider,
                    "ticker": ticker,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        clear_price_reference_cache(ticker)
    return {
        "requested_ticker_count": len(unique_tickers),
        "selected_ticker_count": len(selected),
        "cache_hit_count": len(cache_hits),
        "live_fetch_count": live_fetch_count,
        "warmed_tickers": warmed,
        "cache_hit_tickers": cache_hits,
        "failed_tickers": failed,
        "skipped_ticker_count": skipped,
        "mode": "cache_with_bounded_warmup" if allow_live_fetch else "cache_only",
    }
