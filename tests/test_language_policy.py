from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.policies.vocabulary import (
    NON_SCORING_FLAGS,
    RESEARCH_STATUS_VOCABULARY,
    ROUTE_VOCABULARY,
)
from backend.app.utils.forbidden_language import detect_forbidden_language


client = TestClient(app)
DIRECTIVE_LANGUAGE = ("buy", "sell", "hold", "liquidate", "must invest", "guaranteed")


def _contains_directive_language(payload: object) -> list[str]:
    text = " ".join(str(item) for item in payload) if isinstance(payload, list) else str(payload)
    lowered = text.lower()
    return [phrase for phrase in DIRECTIVE_LANGUAGE if phrase in lowered]


def test_research_workflow_status_uses_allowed_vocabulary() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200

    summary = response.json()["research_workflow_summary"]

    assert summary["research_status"] in RESEARCH_STATUS_VOCABULARY


def test_daily_report_actions_use_allowed_route_vocabulary() -> None:
    response = client.get("/api/daily-report/latest")
    assert response.status_code == 200

    command_center = response.json()["command_center"]
    actions = command_center["top_actions"]
    routes = [action["route_hint"] for action in actions]
    action_target_surfaces = [action["action_target"]["surface"] for action in actions if action.get("action_target")]

    assert routes
    assert all(route in ROUTE_VOCABULARY for route in routes)
    assert action_target_surfaces
    assert all(surface in ROUTE_VOCABULARY for surface in action_target_surfaces)


def test_no_directive_language_in_workflow_summaries() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200

    summary = response.json()["research_workflow_summary"]

    assert detect_forbidden_language(summary["one_line_summary"]) == []
    assert detect_forbidden_language(summary["next_3_research_actions"]) == []
    assert _contains_directive_language(summary["one_line_summary"]) == []
    assert _contains_directive_language(summary["next_3_research_actions"]) == []


def test_non_scoring_flags_present() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200

    summary = response.json()["research_workflow_summary"]

    assert "not_investment_advice" in NON_SCORING_FLAGS
    assert "final_score_unchanged" in NON_SCORING_FLAGS
    assert summary["not_investment_advice"] is True
    assert summary["final_score_unchanged"] is True
