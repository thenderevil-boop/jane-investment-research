from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

FORBIDDEN_PATTERNS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\bliquidate\b",
    r"\bexit\b",
    r"\benter position\b",
    r"\bmust invest\b",
]


def test_daily_report_includes_macro_regime_and_crisis() -> None:
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200
    payload = response.json()
    assert "macro_regime" in payload
    assert "crisis" in payload
    assert payload["macro_regime"]["label"] in {
        "normal",
        "fear_crisis",
        "inflation_pressure",
        "recession_warning",
        "recession_confirmed",
        "recovery",
        "overheated",
        "restrictive_or_stress",
        "cautious",
        "neutral_to_constructive",
        "supportive_macro_backdrop",
        "insufficient_data",
    }
    assert payload["macro_regime"]["macro_score_explanation"]["scoring_model_version"] == "macro_v12_5"
    assert payload["crisis"]["level"] in {"normal", "elevated", "high", "severe", "insufficient_data"}
    assert payload["macro_regime"]["components"]
    assert payload["crisis"]["components"]


def test_daily_report_has_no_forbidden_instruction_language() -> None:
    response = client.get("/api/daily-report/latest")
    payload = response.json()
    text = json.dumps(payload, sort_keys=True).lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert not re.search(pattern, text), pattern
