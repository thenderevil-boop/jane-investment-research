from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_phase59_analyze_stock_exposes_non_scoring_platform_business_quality_card() -> None:
    response = client.post(
        "/api/analyze-stock",
        json={
            "ticker": "NVDA",
            "market": "US",
            "qualitative_evidence": [
                {
                    "criterion": "network_effect",
                    "criterion_id": 8,
                    "submetric": "network_effect",
                    "evidence_type": "platform_ecosystem",
                    "summary": "CUDA developer ecosystem and switching costs are user-supplied network-effect evidence requiring manual verification.",
                    "source_label": "User research note",
                    "source_date": "2026-05-25",
                    "confidence": 0.7,
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()

    card = payload["platform_business_quality_card"]
    assert card["version"] == "phase59_platform_business_quality_card_v1"
    assert card["affects_score"] is False
    assert card["final_score_unchanged"] is True
    assert card["not_investment_advice"] is True
    assert "does not change final score" in card["summary"]

    metric_names = {metric["name"] for metric in card["metrics"]}
    assert {
        "gmv_growth",
        "take_rate",
        "net_dollar_retention",
        "burn_rate",
        "runway",
        "marketplace_liquidity",
        "network_effect",
        "ltv_cac",
        "contribution_margin_operating_leverage",
    } <= metric_names

    network_effect = next(metric for metric in card["metrics"] if metric["name"] == "network_effect")
    assert network_effect["status"] == "manual_evidence"
    assert network_effect["source_quality"] == "user_provided"
    assert network_effect["requires_manual_evidence"] is True
    assert network_effect["affects_score"] is False
    assert "switching costs" in network_effect["interpretation"]

    gmv = next(metric for metric in card["metrics"] if metric["name"] == "gmv_growth")
    assert gmv["status"] == "manual_or_disclosed_only"
    assert gmv["observed_value"] is None
    assert "Do not infer GMV" in " ".join(gmv["limitations"])


def test_phase59_platform_card_preserves_score_and_uses_available_financial_proxies_only() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200
    payload = response.json()

    card = payload["platform_business_quality_card"]
    assert payload["research_verdict"]["score"] == payload["score_driver_breakdown"]["final_score"]
    assert card["final_score_unchanged"] is True
    assert all(metric["affects_score"] is False for metric in card["metrics"])

    metric_by_name = {metric["name"]: metric for metric in card["metrics"]}
    contribution = metric_by_name["contribution_margin_operating_leverage"]
    assert contribution["status"] in {"computed_proxy", "unavailable"}
    assert "operating leverage" in contribution["manual_check"]

    unavailable_names = set(card["manual_or_disclosed_metric_names"])
    assert {"gmv_growth", "take_rate", "net_dollar_retention", "marketplace_liquidity", "ltv_cac"} <= unavailable_names
    assert "Platform metrics are unavailable unless disclosed" in " ".join(card["limitations"])
