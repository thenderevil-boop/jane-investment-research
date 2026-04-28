from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from backend.app import config
from backend.app.utils.freshness import (
    DAILY_RATE_FRESHNESS_WINDOW,
    MONTHLY_MACRO_FRESHNESS_WINDOW,
    build_source_status,
)

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
LIMITATION = "FRED macro series may be delayed depending on release schedule."

FRED_SERIES = {
    "fed_funds_rate": "FEDFUNDS",
    "ten_year_yield": "DGS10",
    "two_year_yield": "DGS2",
    "cpi": "CPIAUCSL",
    "ppi": "PPIACO",
    "unemployment_rate": "UNRATE",
}

DAILY_RATE_SERIES = {"DGS10", "DGS2"}


class FredFetchError(RuntimeError):
    """Raised when FRED cannot return normalized macro observations."""


def _as_float(value: Any) -> float | None:
    if value in {None, "", "."}:
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _valid_observations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload.get("observations", []):
        value = _as_float(item.get("value"))
        date = str(item.get("date") or "")
        if value is None or not date:
            continue
        rows.append({"date": date, "value": value})
    rows.sort(key=lambda row: row["date"])
    return rows


def fetch_fred_series(series_id: str, observation_start: str | None = None) -> dict[str, Any]:
    api_key = config.FRED_API_KEY
    if not config.is_fred_api_key_configured():
        raise FredFetchError("FRED_API_KEY is missing.")
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "asc",
    }
    if observation_start:
        params["observation_start"] = observation_start
    response = httpx.get(FRED_BASE_URL, params=params, timeout=20)
    response.raise_for_status()
    rows = _valid_observations(response.json())
    if not rows:
        raise FredFetchError(f"No usable FRED observations returned for {series_id}.")
    previous = rows[-2] if len(rows) >= 2 else None
    freshness_window = DAILY_RATE_FRESHNESS_WINDOW if series_id in DAILY_RATE_SERIES else MONTHLY_MACRO_FRESHNESS_WINDOW
    payload = {
        "series_id": series_id,
        "source_type": "live",
        "provider": "FRED",
        "source": "FRED",
        "source_date": rows[-1]["date"],
        "latest_date": rows[-1]["date"],
        "latest_value": rows[-1]["value"],
        "previous_value": previous["value"] if previous else None,
        "observations": rows,
        "limitations": [LIMITATION],
        "missing_data": [],
    }
    payload["source_status"] = build_source_status(payload, freshness_window=freshness_window).model_dump(mode="json")
    return payload


def fetch_latest_fred_value(series_id: str) -> dict[str, Any]:
    snapshot = fetch_fred_series(series_id)
    latest = snapshot["observations"][-1]
    return {
        "series_id": series_id,
        "source": "FRED",
        "source_date": latest["date"],
        "value": latest["value"],
        "limitations": snapshot["limitations"],
        "missing_data": snapshot["missing_data"],
    }


def calculate_yoy(observations: list[dict[str, Any]]) -> float | None:
    if len(observations) < 13:
        return None
    latest = observations[-1]
    latest_date = datetime.fromisoformat(latest["date"])
    prior_candidates = [
        row
        for row in observations
        if datetime.fromisoformat(row["date"]).year == latest_date.year - 1
        and datetime.fromisoformat(row["date"]).month == latest_date.month
    ]
    if not prior_candidates:
        return None
    latest_value = _as_float(latest["value"])
    prior_value = _as_float(prior_candidates[-1]["value"])
    if latest_value is None or prior_value in {None, 0}:
        return None
    return round((latest_value / prior_value - 1) * 100, 2)


def calculate_trend(observations: list[dict[str, Any]], *, threshold: float = 0.05) -> str:
    recent = observations[-3:]
    if len(recent) < 3:
        return "stable"
    latest = _as_float(recent[-1]["value"])
    earliest = _as_float(recent[0]["value"])
    if latest is None or earliest is None:
        return "stable"
    delta = latest - earliest
    if delta > threshold:
        return "rising"
    if delta < -threshold:
        return "falling"
    return "stable"


def calculate_fed_policy_trend(observations: list[dict[str, Any]]) -> str:
    trend = calculate_trend(observations, threshold=0.05)
    if trend == "rising":
        return "tightening"
    if trend == "falling":
        return "easing"
    return "neutral"


def fetch_macro_snapshot() -> dict[str, Any]:
    series = {name: fetch_fred_series(series_id) for name, series_id in FRED_SERIES.items()}
    fetched_at = datetime.now(timezone.utc).isoformat()
    for payload in series.values():
        payload["fetched_at"] = fetched_at
        freshness_window = DAILY_RATE_FRESHNESS_WINDOW if payload.get("series_id") in DAILY_RATE_SERIES else MONTHLY_MACRO_FRESHNESS_WINDOW
        payload["source_status"] = build_source_status(payload, freshness_window=freshness_window).model_dump(mode="json")
    observations = {name: payload["observations"] for name, payload in series.items()}
    latest = {name: rows[-1] for name, rows in observations.items()}
    ten_year = latest["ten_year_yield"]["value"]
    two_year = latest["two_year_yield"]["value"]
    cpi_yoy = calculate_yoy(observations["cpi"])
    ppi_yoy = calculate_yoy(observations["ppi"])
    missing_data: list[str] = []
    if cpi_yoy is None:
        missing_data.append("cpi_yoy")
    if ppi_yoy is None:
        missing_data.append("ppi_yoy")
    source_date = max(item["date"] for item in latest.values())
    return {
        "source_type": "live",
        "provider": "FRED",
        "source": ["FRED"],
        "source_date": source_date,
        "fetched_at": fetched_at,
        "indicators": {
            "fed_funds_rate": latest["fed_funds_rate"]["value"],
            "fed_policy_trend": calculate_fed_policy_trend(observations["fed_funds_rate"]),
            "ten_year_yield": ten_year,
            "two_year_yield": two_year,
            "ten_year_minus_two_year_spread_bps": round((ten_year - two_year) * 100, 2),
            "cpi_yoy": cpi_yoy,
            "ppi_yoy": ppi_yoy,
            "unemployment_rate": latest["unemployment_rate"]["value"],
            "unemployment_trend": calculate_trend(observations["unemployment_rate"]),
        },
        "raw_series": series,
        "limitations": [LIMITATION],
        "missing_data": missing_data,
    }
