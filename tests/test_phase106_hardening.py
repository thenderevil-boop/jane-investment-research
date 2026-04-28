from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app import config
from backend.app.engines.smart_money_engine import evaluate_form4_insider_signal, evaluate_smart_money
from backend.app.raw_store import repository
from backend.app.schemas.common import DataSourceStatus
from backend.app.utils.forbidden_language import detect_forbidden_language


SOURCE_TYPE_ENUM = ["live", "cached_live", "mock", "fallback", "derived", "unknown"]


def test_source_type_schema_enum_is_exact_and_excludes_mixed():
    for schema_path in [Path("schemas/daily_report.schema.json"), Path("schemas/analyze_stock.schema.json")]:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        enum = schema["$defs"]["DataSourceStatus"]["properties"]["source_type"]["enum"]

        assert enum == SOURCE_TYPE_ENUM
        assert "mixed" not in enum


def test_pydantic_source_type_rejects_unexpected_value():
    with pytest.raises(ValidationError):
        DataSourceStatus(source_type="mixed")


def test_mixed_macro_uses_derived_source_type_not_mixed(monkeypatch):
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "MACRO_DATA_PROVIDER", "fred")

    snapshot = {
        "source_type": "live",
        "provider": "FRED",
        "source": ["FRED"],
        "source_date": "2026-04-24",
        "fetched_at": "2026-04-24T20:30:00+00:00",
        "indicators": {
            "fed_funds_rate": 4.25,
            "fed_policy_trend": "easing",
            "ten_year_yield": 4.3,
            "two_year_yield": 4.05,
            "ten_year_minus_two_year_spread_bps": 25.0,
            "cpi_yoy": 3.0,
            "ppi_yoy": 3.0,
            "unemployment_rate": 4.2,
            "unemployment_trend": "rising",
        },
        "raw_series": {},
        "limitations": [],
        "missing_data": [],
    }
    monkeypatch.setattr(repository, "get_macro_snapshot", lambda use_live=None, scenario="normal": snapshot)

    payload = repository.read_macro_data(use_live=True)

    assert payload["source_type"] == "derived"
    assert payload["provider"] == "mixed_FRED_and_mock_macro"


def test_mixed_smart_money_uses_derived_source_type_and_mixed_provider():
    result = evaluate_smart_money(
        {
            "institutional_13f": {},
            "form4_transactions": [
                {
                    "transaction_code": "P",
                    "transaction_category": "accumulation",
                    "value": 1000,
                    "filing_date": "2026-04-11",
                    "transaction_date": "2026-04-10",
                }
            ],
            "form4_source_status": {"source_type": "live", "provider": "SEC EDGAR", "source_date": "2026-04-11"},
            "options_activity": {},
        }
    )

    assert result.source_status is not None
    assert result.source_status.source_type == "derived"
    assert result.source_status.provider == "mixed_smart_money_sources"


def test_form4_p_s_labels_are_research_evidence_not_trading_instructions():
    result = evaluate_form4_insider_signal(
        {
            "form4_transactions": [
                {
                    "transaction_code": "P",
                    "transaction_category": "accumulation",
                    "value": 1000,
                    "filing_date": "2026-04-11",
                    "transaction_date": "2026-04-10",
                },
                {
                    "transaction_code": "S",
                    "transaction_category": "disposition",
                    "value": 400,
                    "filing_date": "2026-04-12",
                    "transaction_date": "2026-04-11",
                },
            ],
            "form4_source_status": {"source_type": "live", "provider": "SEC EDGAR", "source_date": "2026-04-12"},
        }
    )

    assert result.benchmark["accumulation_code"] == "P"
    assert result.benchmark["disposition_code"] == "S"
    assert detect_forbidden_language(result.model_dump(mode="json")) == []


def test_fallback_mock_form4_does_not_boost_component_or_aggregate_score():
    fallback = repository._mock_form4_snapshot("NVDA", "SEC unavailable")
    component = evaluate_form4_insider_signal(
        {
            "form4_transactions": fallback["transactions"],
            "form4_source_status": fallback["source_status"],
        }
    )
    aggregate = evaluate_smart_money(
        {
            "institutional_13f": {},
            "form4_transactions": fallback["transactions"],
            "form4_source_status": fallback["source_status"],
            "options_activity": {},
        }
    )

    assert component.score == 50
    assert component.label == "insider_activity_neutral"
    assert aggregate.derived_metrics["components"]["insider_form4_signal"]["score"] == 50
    assert aggregate.score < 50


def test_fred_placeholder_key_is_not_treated_as_configured(monkeypatch):
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", True)
    monkeypatch.setattr(config, "FRED_API_KEY", "your_key_here")

    payload = repository.read_macro_data(use_live=True)

    assert config.is_fred_api_key_configured() is False
    assert payload["source_type"] == "fallback"
    assert payload["provider"] == "mock"
    assert payload["source_status"]["fallback_used"] is True


def test_readme_documents_phase106_environment_reference():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "## Current Implementation Status" in readme
    assert "| SEC_EDGAR_USER_AGENT | none | SEC EDGAR Form 4 | required; never expose |" in readme
    assert "| ALLOW_LIVE_FETCH_ON_REPORT_REQUEST | false | quota guard | default should remain false |" in readme
