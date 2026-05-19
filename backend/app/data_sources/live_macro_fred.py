from __future__ import annotations

import re
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
FRED_SERIES_METADATA_URL = "https://api.stlouisfed.org/fred/series"
FRED_SERIES_SEARCH_URL = "https://api.stlouisfed.org/fred/series/search"
LIMITATION = "FRED macro series may be delayed depending on release schedule."
PMI_UNAVAILABLE_ERROR = "Configured FRED PMI series is unavailable or invalid."
PMI_PROXY_LIMITATION = "This series is used as a manufacturing PMI proxy and may not exactly match official ISM Manufacturing PMI."
FRED_REQUEST_TIMEOUT_SECONDS = 20
FRED_MAX_ATTEMPTS = 2
TRANSIENT_FRED_STATUS_CODES = {500, 502, 503, 504}

FRED_SERIES = {
    "fed_funds_rate": "FEDFUNDS",
    "ten_year_yield": "DGS10",
    "two_year_yield": "DGS2",
    "cpi": "CPIAUCSL",
    "ppi": "PPIACO",
    "unemployment_rate": "UNRATE",
}
FRED_CONTEXT_SERIES = {"consumer_sentiment": "UMCSENT"}

DAILY_RATE_SERIES = {"DGS10", "DGS2"}


class FredFetchError(RuntimeError):
    """Raised when FRED cannot return normalized macro observations."""


class FredInvalidSeriesError(FredFetchError):
    """Raised when FRED reports that a configured series id is invalid."""


def redact_fred_error_text(value: Any) -> str:
    text = str(value or "")
    api_key = config.FRED_API_KEY
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    text = re.sub(r"(?i)(api_key=)[^&\s'\")]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(api_key%3D)[^&\s'\")]+", r"\1[REDACTED]", text)
    return text


def _safe_fred_error_message(exc: Exception, *, series_id: str, attempts: int) -> str:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    if status_code:
        if status_code == 400:
            return PMI_UNAVAILABLE_ERROR
        return f"FRED request failed for {series_id} after {attempts} attempts: HTTP {status_code}."
    if isinstance(exc, httpx.TimeoutException):
        return f"FRED request timed out for {series_id} after {attempts} attempts."
    if isinstance(exc, httpx.RequestError):
        return f"FRED request failed for {series_id} after {attempts} attempts."
    text = redact_fred_error_text(str(exc).splitlines()[0])[:180]
    if "api_key" in text.lower() or "stlouisfed.org" in text.lower():
        return f"FRED request failed for {series_id} after {attempts} attempts."
    return text or f"FRED request failed for {series_id} after {attempts} attempts."


def _is_retryable_fred_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    return status_code in TRANSIENT_FRED_STATUS_CODES


def _fred_get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    if not config.is_fred_api_key_configured():
        raise FredFetchError("FRED API key is missing.")
    safe_params = {**params, "api_key": config.FRED_API_KEY, "file_type": "json"}
    try:
        response = httpx.get(url, params=safe_params, timeout=FRED_REQUEST_TIMEOUT_SECONDS)
    except Exception as exc:
        raise FredFetchError(_safe_fred_error_message(exc, series_id=str(params.get("series_id") or params.get("search_text") or "FRED"), attempts=1)) from None
    try:
        response.raise_for_status()
    except Exception as exc:
        if getattr(response, "status_code", None) == 400:
            raise FredInvalidSeriesError(PMI_UNAVAILABLE_ERROR) from None
        raise FredFetchError(_safe_fred_error_message(exc, series_id=str(params.get("series_id") or params.get("search_text") or "FRED"), attempts=1)) from None
    return response.json()


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
    series_id = str(series_id or "").strip().upper()
    if not series_id:
        raise FredInvalidSeriesError(PMI_UNAVAILABLE_ERROR)
    api_key = config.FRED_API_KEY
    if not config.is_fred_api_key_configured():
        raise FredFetchError("FRED API key is missing.")
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "asc",
    }
    if observation_start:
        params["observation_start"] = observation_start
    last_error: Exception | None = None
    for attempt in range(1, FRED_MAX_ATTEMPTS + 1):
        try:
            response = httpx.get(FRED_BASE_URL, params=params, timeout=FRED_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            break
        except Exception as exc:
            last_error = exc
            if getattr(getattr(exc, "response", None), "status_code", None) == 400:
                raise FredInvalidSeriesError(PMI_UNAVAILABLE_ERROR) from None
            if attempt >= FRED_MAX_ATTEMPTS or not _is_retryable_fred_error(exc):
                raise FredFetchError(_safe_fred_error_message(exc, series_id=series_id, attempts=attempt)) from None
    else:
        raise FredFetchError(_safe_fred_error_message(last_error or RuntimeError("unknown FRED error"), series_id=series_id, attempts=FRED_MAX_ATTEMPTS))
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


def fred_series_map() -> dict[str, str]:
    return {**FRED_SERIES}


def _safe_series_metadata(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "series_id": item.get("id") or item.get("series_id"),
        "title": item.get("title"),
        "frequency": item.get("frequency"),
        "units": item.get("units"),
        "seasonal_adjustment": item.get("seasonal_adjustment"),
        "observation_start": item.get("observation_start"),
        "observation_end": item.get("observation_end"),
        "popularity": item.get("popularity"),
        "last_updated": item.get("last_updated"),
        "notes": item.get("notes"),
    }


def validate_fred_series(series_id: str) -> dict[str, Any]:
    series_id = str(series_id or "").strip().upper()
    if not config.is_fred_api_key_configured():
        return {
            "series_id": series_id,
            "is_valid": False,
            "title": None,
            "frequency": None,
            "observation_start": None,
            "observation_end": None,
            "last_updated": None,
            "notes": None,
            "error_type": "missing_api_key",
            "sanitized_error": "FRED API key is missing.",
        }
    if not series_id:
        return {
            "series_id": series_id,
            "is_valid": False,
            "title": None,
            "frequency": None,
            "observation_start": None,
            "observation_end": None,
            "last_updated": None,
            "notes": None,
            "error_type": "invalid_series",
            "sanitized_error": PMI_UNAVAILABLE_ERROR,
        }
    try:
        payload = _fred_get_json(FRED_SERIES_METADATA_URL, {"series_id": series_id})
        series = payload.get("seriess") or []
        item = series[0] if series else {}
        if not item:
            raise FredInvalidSeriesError(PMI_UNAVAILABLE_ERROR)
        safe = _safe_series_metadata(item)
        return {
            "series_id": series_id,
            "is_valid": True,
            "title": safe.get("title"),
            "frequency": safe.get("frequency"),
            "observation_start": safe.get("observation_start"),
            "observation_end": safe.get("observation_end"),
            "last_updated": safe.get("last_updated"),
            "notes": safe.get("notes"),
            "error_type": None,
            "sanitized_error": None,
        }
    except FredInvalidSeriesError:
        error_type = "invalid_series"
    except FredFetchError:
        error_type = "provider_error"
    except Exception:
        error_type = "provider_error"
    return {
        "series_id": series_id,
        "is_valid": False,
        "title": None,
        "frequency": None,
        "observation_start": None,
        "observation_end": None,
        "last_updated": None,
        "notes": None,
        "error_type": error_type,
        "sanitized_error": PMI_UNAVAILABLE_ERROR,
    }


def search_fred_series(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    payload = _fred_get_json(
        FRED_SERIES_SEARCH_URL,
        {
            "search_text": str(query or "").strip(),
            "limit": max(1, min(int(limit), 25)),
            "order_by": "search_rank",
        },
    )
    results = []
    for item in payload.get("seriess", []):
        safe = _safe_series_metadata(item)
        notes = str(safe.get("notes") or "")
        safe["notes"] = notes[:240] if notes else None
        results.append(safe)
    return results


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
    context_series: dict[str, dict[str, Any]] = {}
    missing_data: list[str] = []
    limitations = [LIMITATION]
    for name, series_id in FRED_CONTEXT_SERIES.items():
        try:
            context_series[name] = fetch_fred_series(series_id)
        except FredFetchError:
            missing_data.append(name)
            limitations.append(f"Optional FRED context series {series_id} unavailable; active macro scoring continues without it.")
    series.update(context_series)
    limitations.append("ISM Manufacturing PMI is excluded from scoring because no valid licensed/live source is configured.")
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
    if cpi_yoy is None:
        missing_data.append("cpi_yoy")
    if ppi_yoy is None:
        missing_data.append("ppi_yoy")
    source_date = max(item["date"] for item in latest.values())
    indicators = {
        "fed_funds_rate": latest["fed_funds_rate"]["value"],
        "fed_policy_trend": calculate_fed_policy_trend(observations["fed_funds_rate"]),
        "ten_year_yield": ten_year,
        "two_year_yield": two_year,
        "ten_year_minus_two_year_spread_bps": round((ten_year - two_year) * 100, 2),
        "cpi_yoy": cpi_yoy,
        "ppi_yoy": ppi_yoy,
        "unemployment_rate": latest["unemployment_rate"]["value"],
        "unemployment_trend": calculate_trend(observations["unemployment_rate"]),
    }
    if "consumer_sentiment" in latest:
        indicators["consumer_sentiment"] = latest["consumer_sentiment"]["value"]
        indicators["consumer_sentiment_trend"] = calculate_trend(observations["consumer_sentiment"])
    payload = {
        "source_type": "live",
        "provider": "FRED",
        "source": ["FRED"],
        "source_date": source_date,
        "fetched_at": fetched_at,
        "indicators": indicators,
        "excluded_indicators": [
            {
                "name": "ism_manufacturing_pmi",
                "reason": "Excluded because no valid licensed/live source is configured. NAPM is invalid and IPMAN is not PMI.",
                "affects_score": False,
            }
        ],
        "raw_series": series,
        "limitations": limitations,
        "missing_data": missing_data,
    }
    return payload
