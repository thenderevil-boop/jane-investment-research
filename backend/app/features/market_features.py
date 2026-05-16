from __future__ import annotations

import math
from typing import Any

from backend.app.utils.freshness import build_source_status


TRADING_DAYS_PER_YEAR = 252


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None or math.isnan(value):
        return None
    return round(value, digits)


def _pct_change(current: float | None, reference: float | None) -> float | None:
    if current is None or reference in {None, 0}:
        return None
    return (current / reference - 1) * 100


def _rows(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((snapshot or {}).get("rows") or [])


def _closes(rows: list[dict[str, Any]]) -> list[float]:
    closes: list[float] = []
    for row in rows:
        close = row.get("close")
        if close is not None:
            closes.append(float(close))
    return closes


def _realized_vol(closes: list[float], days: int) -> float | None:
    if len(closes) < days + 1:
        return None
    window = closes[-(days + 1) :]
    returns = [math.log(window[index] / window[index - 1]) for index in range(1, len(window)) if window[index - 1] > 0]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100


def _range_pct(rows: list[dict[str, Any]], days: int = 20) -> float | None:
    window = rows[-days:]
    highs = [float(row["high"]) for row in window if row.get("high") is not None]
    lows = [float(row["low"]) for row in window if row.get("low") is not None]
    latest_close = window[-1].get("close") if window else None
    if not highs or not lows or latest_close in {None, 0}:
        return None
    return (max(highs) - min(lows)) / float(latest_close) * 100


def _average_volume(rows: list[dict[str, Any]], days: int = 20) -> float | None:
    volumes = [float(row.get("volume") or 0) for row in rows[-days:]]
    if not volumes:
        return None
    return sum(volumes) / len(volumes)


def _moving_average(values: list[float], days: int) -> float | None:
    window = values[-days:]
    if len(window) < days:
        return None
    return sum(window) / len(window)


def _days_since_low(rows: list[dict[str, Any]], days: int = 252) -> int | None:
    window = rows[-days:]
    if not window:
        return None
    lows = [float(row.get("low") or row.get("close") or 0) for row in window]
    if not lows:
        return None
    low_index = lows.index(min(lows))
    return len(window) - low_index - 1


def build_price_features(snapshot: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(snapshot)
    closes = _closes(rows)
    latest = rows[-1] if rows else {}
    latest_close = float(latest["close"]) if latest.get("close") is not None else None
    latest_volume = int(latest.get("volume") or 0) if rows else None
    high_52w = max(closes[-252:]) if closes else None
    all_time_high = max(closes) if closes else None
    recent_trough = min(closes[-252:]) if closes else None
    prior_cycle_high = max(closes[:-63]) if len(closes) > 63 else None
    realized_vol_20d = _realized_vol(closes, 20)
    previous_realized_vol_20d = _realized_vol(closes[:-20], 20) if len(closes) >= 41 else None
    range_20d = _range_pct(rows, 20)
    average_volume_20d = _average_volume(rows, 20)
    average_volume_52w = _average_volume(rows, 252)
    ma_200d = _moving_average(closes, 200)
    vol_falling = realized_vol_20d is not None and previous_realized_vol_20d is not None and realized_vol_20d < previous_realized_vol_20d
    range_stable = range_20d is not None and range_20d <= 8
    source = snapshot.get("source", "unknown")
    source_type = "live" if source == "yfinance" else str(snapshot.get("source_type") or "mock")
    provider = snapshot.get("provider") or ("yfinance" if source == "yfinance" else "mock")
    payload = {
        "ticker": snapshot.get("ticker"),
        "source": [source],
        "source_date": snapshot.get("source_date"),
        "source_type": source_type,
        "provider": provider,
        "latest_close": _round(latest_close),
        "latest_volume": latest_volume,
        "current_price": _round(latest_close),
        "current_volume": latest_volume,
        "average_volume_20d": _round(average_volume_20d, 0),
        "avg_volume_52w": _round(average_volume_52w, 0),
        "ma_200d": _round(ma_200d),
        "drawdown_from_52w_high": _round(_pct_change(latest_close, high_52w)),
        "drawdown_from_all_time_high": _round(_pct_change(latest_close, all_time_high)),
        "distance_from_52w_high": _round(_pct_change(latest_close, high_52w)),
        "index_gain_from_recent_trough": _round(_pct_change(latest_close, recent_trough)),
        "index_gain_vs_prior_cycle_high": _round(_pct_change(latest_close, prior_cycle_high)),
        "index_range_20d_pct": _round(range_20d),
        "realized_vol_20d": _round(realized_vol_20d),
        "previous_realized_vol_20d": _round(previous_realized_vol_20d),
        "realized_vol_60d": _round(_realized_vol(closes, 60)),
        "days_since_low": _days_since_low(rows),
        "stabilization_status": "stabilizing" if range_stable and vol_falling else "not_confirmed",
        "limitations": snapshot.get("limitations", []),
        "missing_data": snapshot.get("missing_data", []),
    }
    payload["source_status"] = build_source_status(payload).model_dump(mode="json")
    return payload


def build_market_snapshot_features(
    spy_snapshot: dict[str, Any],
    qqq_snapshot: dict[str, Any],
    vix_snapshot: dict[str, Any],
) -> dict[str, Any]:
    spy = build_price_features(spy_snapshot)
    qqq = build_price_features(qqq_snapshot)
    vix_rows = _rows(vix_snapshot)
    vix_closes = _closes(vix_rows)
    latest_vix = vix_closes[-1] if vix_closes else None
    prior_vix = vix_closes[-6] if len(vix_closes) >= 6 else None
    recent_vix_high = max(vix_closes[-20:]) if vix_closes else None
    vix_recent_spike = bool(recent_vix_high is not None and recent_vix_high >= 25 and latest_vix is not None)
    vix_falling = latest_vix is not None and recent_vix_high is not None and latest_vix < recent_vix_high * 0.9
    source_type = "live" if spy.get("source_type") == "live" and qqq.get("source_type") == "live" else "mock"
    aggregate_source_date = max([value for value in [spy.get("source_date"), qqq.get("source_date"), vix_snapshot.get("source_date")] if value] or ["unknown"])
    for index_features in [spy, qqq]:
        if source_type == "live":
            index_features["source_date"] = aggregate_source_date
            index_features["source_status"] = build_source_status(index_features).model_dump(mode="json")
    missing = sorted({*spy.get("missing_data", []), *qqq.get("missing_data", []), *vix_snapshot.get("missing_data", [])})
    limitations = sorted({*spy.get("limitations", []), *qqq.get("limitations", []), *vix_snapshot.get("limitations", [])})
    return {
        "source_type": source_type,
        "source": sorted({*spy.get("source", []), *qqq.get("source", []), vix_snapshot.get("source", "unknown")}),
        "source_date": aggregate_source_date,
        "sp500_drawdown_pct": spy["drawdown_from_52w_high"],
        "nasdaq_drawdown_pct": qqq["drawdown_from_52w_high"],
        "drawdown_from_52w_high": spy["drawdown_from_52w_high"],
        "drawdown_from_all_time_high": spy["drawdown_from_all_time_high"],
        "index_gain_from_recent_trough": spy["index_gain_from_recent_trough"],
        "index_gain_vs_prior_cycle_high": spy["index_gain_vs_prior_cycle_high"],
        "distance_from_52w_high": spy["distance_from_52w_high"],
        "index_range_20d_pct": spy["index_range_20d_pct"],
        "realized_vol_20d": spy["realized_vol_20d"],
        "previous_realized_vol_20d": spy["previous_realized_vol_20d"],
        "realized_vol_60d": spy["realized_vol_60d"],
        "stabilization_status": spy["stabilization_status"],
        "latest_close": spy["latest_close"],
        "latest_volume": spy["latest_volume"],
        "current_price": spy["current_price"],
        "current_volume": spy["current_volume"],
        "average_volume_20d": spy["average_volume_20d"],
        "avg_volume_52w": spy["avg_volume_52w"],
        "ma_200d": spy["ma_200d"],
        "days_since_low": spy["days_since_low"],
        "vix": _round(latest_vix),
        "vix_recent_spike": vix_recent_spike,
        "vix_trend": "falling" if latest_vix is not None and prior_vix is not None and latest_vix < prior_vix else "rising" if latest_vix is not None and prior_vix is not None and latest_vix > prior_vix else "stable",
        "vix_falling_from_spike": vix_falling,
        "index_market_data": {"SPY": spy, "QQQ": qqq},
        "vix_market_data": build_price_features(vix_snapshot),
        "limitations": limitations,
        "missing_data": missing,
    }
