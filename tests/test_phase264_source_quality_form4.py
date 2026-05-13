from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.reports import stock_analysis


def _macro_status(source_type: str, provider: str) -> dict:
    return {
        "source_type": source_type,
        "provider": provider,
        "source_date": "2026-05-04",
        "is_fresh": True,
        "fallback_used": False,
        "limitations": [],
        "missing_data": [],
    }


def _derived_live_macro_payload() -> dict:
    return {
        "fed_funds_rate": 4.25,
        "fed_policy_trend": "easing",
        "ten_year_yield": 4.3,
        "two_year_yield": 4.05,
        "ten_year_minus_two_year_spread_bps": 25,
        "cpi_yoy": 3.0,
        "ppi_yoy": 2.8,
        "unemployment_rate": 4.2,
        "unemployment_trend": "stable",
        "vix": 18.5,
        "vix_trend": "stable",
        "dxy_trend": "stable",
        "gold_trend": "stable",
        "oil_trend": "stable",
        "sp500_drawdown_pct": -4.0,
        "nasdaq_drawdown_pct": -6.0,
        "sp500_gain_from_trough_pct": 14.0,
        "nasdaq_gain_from_trough_pct": 18.0,
        "equity_trend": "stable",
        "source_type": "derived",
        "provider": "mixed_FRED_and_yfinance_macro",
        "source": ["FRED", "yfinance"],
        "source_date": "2026-05-04",
        "fallback_used": False,
        "limitations": ["FRED release lag may apply."],
        "missing_data": [],
        "component_source_status": {
            "fed_funds_rate": _macro_status("live", "FRED"),
            "fed_policy_trend": _macro_status("derived", "derived_from_FRED"),
            "ten_year_minus_two_year_spread_bps": _macro_status("derived", "derived_from_FRED"),
            "cpi_yoy": _macro_status("derived", "derived_from_FRED"),
            "ppi_yoy": _macro_status("derived", "derived_from_FRED"),
            "unemployment_rate": _macro_status("live", "FRED"),
            "unemployment_trend": _macro_status("derived", "derived_from_FRED"),
            "vix": _macro_status("live", "yfinance"),
            "equity_drawdown": _macro_status("derived", "derived_from_yfinance"),
            "dxy_trend": _macro_status("derived", "derived_from_yfinance"),
            "gold_trend": _macro_status("derived", "derived_from_yfinance"),
            "oil_trend": _macro_status("derived", "derived_from_yfinance"),
            "gain_from_recent_trough": _macro_status("derived", "derived_from_yfinance"),
        },
    }

client = TestClient(app)


def _use_tmp_stores(monkeypatch):
    root = Path("backend/raw_store/cache/test_phase264") / uuid4().hex
    manual = root / "manual"
    candidates = root / "candidates"
    manual.mkdir(parents=True, exist_ok=True)
    candidates.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MANUAL_EVIDENCE_DIR", manual)
    monkeypatch.setattr(config, "CANDIDATE_WORKSPACE_DIR", candidates)


def _analyze() -> dict:
    response = client.post(
        "/api/analyze-stock",
        json={
            "ticker": "NVDA",
            "market": "US",
            "research_context": {
                "theme": "AI infrastructure",
                "user_reason": "External trend research",
            },
        },
    )
    assert response.status_code == 200
    return response.json()


def _manual_payload(**overrides) -> dict:
    payload = {
        "ticker": "NVDA",
        "criterion": "network_effect",
        "evidence_type": "platform_ecosystem",
        "summary": "CUDA developer ecosystem and software stack are tracked as manual network effect evidence requiring review.",
        "source_label": "User research note",
        "source_url": None,
        "source_date": "2026-05-06",
        "confidence": 0.65,
        "review_status": "unreviewed",
        "limitations": ["Requires manual verification against official filings or independent sources."],
        "tags": ["CUDA"],
    }
    payload.update(overrides)
    return payload


def test_phase264_mock_form4_limits_smart_money_and_insider_source_quality(monkeypatch):
    _use_tmp_stores(monkeypatch)
    payload = _analyze()
    matrix = {item["category"]: item for item in payload["evidence_matrix"]}
    breakdown = payload["smart_money"]["source_quality_breakdown"]
    data_quality = payload["data_quality_summary"]

    assert matrix["smart_money"]["source_quality"] == "mixed_with_fallback"
    assert matrix["insider_activity"]["source_quality"] == "mixed_with_fallback"
    assert payload["insider_activity"]["source_quality"] == "mixed_with_fallback"
    assert breakdown["form4"]["source_type"] in {"mock", "fallback"}
    assert breakdown["form4"]["fallback_used"] is True
    assert "fallback" in breakdown["form4"]["interpretation"].lower() or "mock" in breakdown["form4"]["interpretation"].lower()
    assert "smart_money" in data_quality["fallback_evidence_categories"]
    assert "insider_activity" in data_quality["fallback_evidence_categories"]
    assert payload["not_investment_advice"] is True
    assert '"source_type": "mixed"' not in json.dumps(payload)


def test_phase264_macro_environment_excluded_context_does_not_become_mock_only(monkeypatch):
    _use_tmp_stores(monkeypatch)
    monkeypatch.setattr(stock_analysis, "read_macro_data", lambda *args, **kwargs: _derived_live_macro_payload())
    payload = _analyze()
    matrix = {item["category"]: item for item in payload["evidence_matrix"]}
    data_quality = payload["data_quality_summary"]
    excluded = payload["macro_regime"]["macro_score_explanation"]["excluded_indicators"]

    assert matrix["macro_environment"]["source_quality"] == "derived_live"
    assert "macro_environment" not in data_quality["mock_evidence_categories"]
    assert "macro_environment" not in data_quality["fallback_evidence_categories"]
    assert all(item["affects_score"] is False and item["weight"] == 0 for item in excluded)


def test_phase264_archived_rejected_manual_evidence_excluded_from_active_counts(monkeypatch):
    _use_tmp_stores(monkeypatch)
    active_one = client.post("/api/manual-evidence", json=_manual_payload()).json()
    active_two = client.post(
        "/api/manual-evidence",
        json=_manual_payload(
            criterion="visionary_founder_ceo",
            evidence_type="founder_operator",
            summary="Founder operator notes are tracked as qualitative evidence requiring manual verification.",
        ),
    ).json()
    archived = client.post("/api/manual-evidence", json=_manual_payload(review_status="archived")).json()
    rejected = client.post(
        "/api/manual-evidence",
        json=_manual_payload(
            criterion="continuous_r_and_d",
            evidence_type="r_and_d_intensity",
            summary="R and D intensity note requires manual verification before use.",
            review_status="rejected",
        ),
    ).json()

    payload = _analyze()
    assessment = payload["qualitative_evidence_assessment"]
    accepted_ids = {item["evidence_id"] for item in assessment["evidence_items"] if item["accepted"]}
    criteria = {item["name"]: item for item in payload["jane_company_quality"]["criteria"]}
    qualitative_row = next(item for item in payload["evidence_matrix"] if item["category"] == "qualitative_evidence")

    assert assessment["evidence_count"] == 2
    assert assessment["accepted_evidence_count"] == 2
    assert assessment["archived_or_rejected_ignored_count"] == 2
    assert accepted_ids == {active_one["evidence_id"], active_two["evidence_id"]}
    assert archived["evidence_id"] not in accepted_ids
    assert rejected["evidence_id"] not in accepted_ids
    assert "continuous_r_and_d" not in assessment["criteria_covered"]
    assert criteria["continuous_r_and_d"]["status"] == "insufficient"
    assert "Accepted evidence items: 2" in qualitative_row["key_evidence"]
