from __future__ import annotations

from typing import Any

from backend.app.utils.freshness import DAILY_MARKET_FRESHNESS_WINDOW, build_source_status

YFINANCE_LIMITATION = "Yfinance data is suitable for MVP research reference only."
MOCK_CONTEXT_UNAVAILABLE_LIMITATION = "This field remains mock context because live market context was unavailable."


def _rows(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((snapshot or {}).get("rows") or [])


def _close_values(rows: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        close = row.get("close")
        if close is None:
            continue
        try:
            values.append(float(close))
        except (TypeError, ValueError):
            continue
    return values


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in {None, 0}:
        return None
    return (current / prior - 1) * 100


def _latest_source_date(snapshots: list[dict[str, Any]]) -> str:
    return max((str(snapshot.get("source_date") or "") for snapshot in snapshots if snapshot.get("source_date")), default="")


def _provider_status(payload: dict[str, Any], *, source_type: str = "derived", provider: str = "derived_from_yfinance") -> dict[str, Any]:
    return build_source_status(
        {
            **payload,
            "source_type": source_type,
            "provider": provider,
            "limitations": sorted(set([*payload.get("limitations", []), YFINANCE_LIMITATION])),
            "missing_data": payload.get("missing_data", []),
            "fallback_used": False,
        },
        freshness_window=DAILY_MARKET_FRESHNESS_WINDOW,
    ).model_dump(mode="json")


def _mock_status(field: str) -> dict[str, Any]:
    return build_source_status(
        {
            "source_type": "mock",
            "provider": "phase5_mock_macro_dataset",
            "source": ["phase5_mock_macro_dataset"],
            "source_date": "",
            "fallback_used": False,
            "limitations": [MOCK_CONTEXT_UNAVAILABLE_LIMITATION],
            "missing_data": [field],
        },
        freshness_window="phase9_mock_context",
    ).model_dump(mode="json")


def classify_trend(snapshot: dict[str, Any], *, threshold_pct: float = 3.0) -> dict[str, Any]:
    rows = _rows(snapshot)
    closes = _close_values(rows)
    latest = closes[-1] if closes else None
    prior_5d = closes[-6] if len(closes) >= 6 else None
    prior_20d = closes[-21] if len(closes) >= 21 else None
    change_5d = _pct_change(latest, prior_5d)
    change_20d = _pct_change(latest, prior_20d)
    if change_20d is None:
        trend = "stable"
    elif change_20d >= threshold_pct:
        trend = "rising"
    elif change_20d <= -threshold_pct:
        trend = "falling"
    else:
        trend = "stable"
    payload = {
        "ticker": snapshot.get("ticker"),
        "latest_close": _round(latest),
        "change_5d_pct": _round(change_5d),
        "change_20d_pct": _round(change_20d),
        "trend": trend,
        "source": ["yfinance"],
        "source_date": snapshot.get("source_date", ""),
        "limitations": snapshot.get("limitations", []),
        "missing_data": snapshot.get("missing_data", []),
    }
    payload["source_status"] = _provider_status(payload)
    return payload


def vix_metrics(snapshot: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(snapshot)
    closes = _close_values(rows)
    latest = closes[-1] if closes else None
    prior_5d = closes[-6] if len(closes) >= 6 else None
    change_5d = _pct_change(latest, prior_5d)
    high_20d = max(closes[-20:]) if closes else None
    if latest is not None and latest >= 30:
        trend = "elevated"
    elif change_5d is not None and change_5d >= 20:
        trend = "rising"
    elif change_5d is not None and change_5d <= -20:
        trend = "falling"
    else:
        trend = "stable"
    payload = {
        "latest_value": _round(latest),
        "change_5d_pct": _round(change_5d),
        "high_20d": _round(high_20d),
        "recent_spike": bool(latest is not None and (latest >= 30 or (change_5d is not None and change_5d >= 20))),
        "trend": trend,
        "source": ["yfinance"],
        "source_date": snapshot.get("source_date", ""),
        "limitations": snapshot.get("limitations", []),
        "missing_data": snapshot.get("missing_data", []),
    }
    payload["source_status"] = _provider_status(payload)
    return payload


def equity_metrics(spy_snapshot: dict[str, Any], qqq_snapshot: dict[str, Any]) -> dict[str, Any]:
    snapshots = {"SPY": spy_snapshot, "QQQ": qqq_snapshot}
    indexes: dict[str, Any] = {}
    drawdowns: list[float] = []
    gains: list[float] = []
    for symbol, snapshot in snapshots.items():
        closes = _close_values(_rows(snapshot))
        latest = closes[-1] if closes else None
        high_52w = max(closes[-252:]) if closes else None
        low_52w = min(closes[-252:]) if closes else None
        drawdown = _pct_change(latest, high_52w)
        gain = _pct_change(latest, low_52w)
        if drawdown is not None:
            drawdowns.append(drawdown)
        if gain is not None:
            gains.append(gain)
        indexes[symbol] = {
            "latest_close": _round(latest),
            "high_52w": _round(high_52w),
            "drawdown_from_52w_high_pct": _round(drawdown),
            "low_52w": _round(low_52w),
            "gain_from_52w_low_pct": _round(gain),
            "source_date": snapshot.get("source_date", ""),
        }
    max_drawdown = min(drawdowns) if drawdowns else None
    max_gain = max(gains) if gains else None
    drawdown_state = "deep_drawdown" if max_drawdown is not None and max_drawdown <= -20 else "correction" if max_drawdown is not None and max_drawdown <= -10 else "normal"
    rebound_state = "strong_rebound" if max_gain is not None and max_gain >= 30 else "normal_rebound"
    payload = {
        "index_metrics": indexes,
        "max_index_drawdown_pct": _round(max_drawdown),
        "max_gain_from_recent_trough_pct": _round(max_gain),
        "drawdown_state": drawdown_state,
        "rebound_state": rebound_state,
        "source": ["yfinance"],
        "source_date": _latest_source_date([spy_snapshot, qqq_snapshot]),
        "limitations": sorted(set([*spy_snapshot.get("limitations", []), *qqq_snapshot.get("limitations", [])])),
        "missing_data": sorted(set([*spy_snapshot.get("missing_data", []), *qqq_snapshot.get("missing_data", [])])),
    }
    payload["source_status"] = _provider_status(payload)
    return payload


def missing_context_status(field: str) -> dict[str, Any]:
    return _mock_status(field)
