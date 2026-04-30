from __future__ import annotations

import argparse
import json

from backend.app.data_sources.live_macro_fred import fetch_fred_series, validate_fred_series


def _safe_invalid(series_id: str, validation: dict) -> dict:
    return {
        "series_id": series_id,
        "is_valid": False,
        "error_type": validation.get("error_type") or "invalid_series",
        "sanitized_error": validation.get("sanitized_error") or "Configured FRED series is unavailable or invalid.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate one FRED series without printing secrets.")
    parser.add_argument("series_id")
    args = parser.parse_args(argv)
    series_id = args.series_id.strip().upper()
    validation = validate_fred_series(series_id)
    if not validation.get("is_valid"):
        print(json.dumps(_safe_invalid(series_id, validation), indent=2, sort_keys=True))
        return 1
    try:
        payload = fetch_fred_series(series_id)
        observations = payload.get("observations", [])[-5:]
        latest = observations[-1] if observations else {}
        result = {
            "series_id": series_id,
            "is_valid": True,
            "title": validation.get("title"),
            "frequency": validation.get("frequency"),
            "latest_observation_date": latest.get("date"),
            "latest_value": latest.get("value"),
            "observation_count_checked": len(observations),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception:
        print(json.dumps(_safe_invalid(series_id, {"error_type": "provider_error"}), indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
