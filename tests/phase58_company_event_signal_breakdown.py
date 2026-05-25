from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_phase58_analyze_stock_exposes_non_scoring_company_event_breakdown() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200
    payload = response.json()

    breakdown = payload["company_event_signal_breakdown"]
    assert breakdown["version"] == "phase58_company_event_signal_breakdown_v1"
    assert breakdown["affects_score"] is False
    assert breakdown["final_score_unchanged"] is True
    assert breakdown["not_investment_advice"] is True
    assert "not a trading signal" in breakdown["summary"]

    names = {item["name"] for item in breakdown["event_signals"]}
    assert {
        "form4_insider_accumulation_disposition",
        "systematic_insider_plan_risk",
        "delayed_13f_institutional_positioning",
        "options_attention_abnormality",
        "ipo_lockup_expiration",
    } <= names

    lockup = next(item for item in breakdown["event_signals"] if item["name"] == "ipo_lockup_expiration")
    assert lockup["category"] == "lockup"
    assert lockup["label"] == "lockup_data_not_available"
    assert lockup["source_quality"] == "unknown"
    assert lockup["affects_score"] is False
    assert "prospectus lock-up" in lockup["manual_check"]

    thirteen_f = next(item for item in breakdown["event_signals"] if item["name"] == "delayed_13f_institutional_positioning")
    assert thirteen_f["is_real_time_signal"] is False
    assert "delayed quarterly" in thirteen_f["interpretation"]

    form4 = next(item for item in breakdown["event_signals"] if item["name"] == "form4_insider_accumulation_disposition")
    assert "code P" in form4["interpretation"]
    assert "code S" in form4["interpretation"]


def test_phase58_breakdown_does_not_change_existing_scores_or_verdict() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200
    payload = response.json()

    breakdown = payload["company_event_signal_breakdown"]
    assert payload["research_verdict"]["score"] == payload["score_driver_breakdown"]["final_score"]
    assert payload["macro_flow_signal_breakdown"]["final_score_unchanged"] is True
    assert breakdown["final_score_unchanged"] is True
    assert all(item["affects_score"] is False for item in breakdown["event_signals"])
    forbidden_fragments = [" buy ", " sell ", " hold ", " liquidate ", "exit all", "sell half", "must invest", "guaranteed return"]
    rendered = f" {str(breakdown).lower()} "
    for fragment in forbidden_fragments:
        assert fragment not in rendered
