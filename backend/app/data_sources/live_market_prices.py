from __future__ import annotations

from datetime import date
from typing import Any


LIMITATION = "Data source is suitable for MVP research reference only."


class MarketPriceFetchError(RuntimeError):
    """Raised when the live market price adapter cannot return normalized data."""


def _load_yfinance():
    try:
        import yfinance as yf  # type: ignore
    except ImportError as exc:
        raise MarketPriceFetchError("yfinance is not installed.") from exc
    return yf


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if hasattr(value, "item"):
            value = value.item()
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int:
    try:
        if hasattr(value, "item"):
            value = value.item()
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _date_string(value: Any) -> str:
    if hasattr(value, "date"):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _normalize_history(ticker: str, history: Any, period: str, interval: str) -> dict[str, Any]:
    if history is None or getattr(history, "empty", False):
        raise MarketPriceFetchError(f"No market price rows returned for {ticker}.")

    rows: list[dict[str, Any]] = []
    for index, row in history.iterrows():
        close = _as_float(row.get("Close"))
        if close is None:
            continue
        rows.append(
            {
                "date": _date_string(index),
                "open": _as_float(row.get("Open")),
                "high": _as_float(row.get("High")),
                "low": _as_float(row.get("Low")),
                "close": close,
                "volume": _as_int(row.get("Volume")),
            }
        )

    if not rows:
        raise MarketPriceFetchError(f"No usable market price rows returned for {ticker}.")

    return {
        "ticker": ticker.strip().upper(),
        "source": "yfinance",
        "source_date": rows[-1]["date"],
        "period": period,
        "interval": interval,
        "rows": rows,
        "limitations": [LIMITATION],
        "missing_data": [],
    }


def fetch_ohlcv(ticker: str, period: str = "1y", interval: str = "1d") -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise MarketPriceFetchError("Ticker is required.")
    yf = _load_yfinance()
    history = yf.Ticker(normalized_ticker).history(period=period, interval=interval, auto_adjust=False)
    return _normalize_history(normalized_ticker, history, period, interval)


def fetch_latest_price(ticker: str) -> dict[str, Any]:
    snapshot = fetch_ohlcv(ticker, period="5d", interval="1d")
    latest = snapshot["rows"][-1]
    return {
        "ticker": snapshot["ticker"],
        "source": snapshot["source"],
        "source_date": snapshot["source_date"],
        "latest_price": latest["close"],
        "latest_volume": latest["volume"],
        "raw_data": latest,
        "limitations": snapshot["limitations"],
        "missing_data": snapshot["missing_data"],
    }


def fetch_index_data(symbols: list[str]) -> dict[str, dict[str, Any]]:
    return {symbol.strip().upper(): fetch_ohlcv(symbol) for symbol in symbols}


def fetch_vix_data() -> dict[str, Any]:
    return fetch_ohlcv("^VIX")

