from __future__ import annotations

import json
import re

from backend.app.engines.smart_money_engine import (
    evaluate_13f_institutional_support,
    evaluate_form4_insider_signal,
    evaluate_options_abnormal_activity,
    evaluate_smart_money,
)

PROHIBITED_PATTERNS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\bliquidate\b",
    r"\bexit all\b",
    r"\bsell half\b",
    r"\bmust invest\b",
    r"\bguaranteed\b",
]

SCORE_FIELDS = {
    "raw_data",
    "source",
    "source_date",
    "derived_metrics",
    "benchmark",
    "trend",
    "confidence",
    "limitations",
    "missing_data",
}


def assert_score_contract(payload: dict) -> None:
    assert SCORE_FIELDS.issubset(payload.keys())
    assert 0 <= payload["confidence"] <= 1


def assert_no_prohibited_language(payload: dict) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    for pattern in PROHIBITED_PATTERNS:
        assert not re.search(pattern, text), pattern


def test_13f_delay_limitation_and_required_dates() -> None:
    result = evaluate_13f_institutional_support(
        {
            "institutional_13f": {
                "institution_name": "Mock Fund",
                "issuer_name": "Mock Issuer",
                "cusip": "123456789",
                "shares": 100000,
                "market_value": 12000000,
                "quarter": "2026-Q1",
                "filing_date": "2026-05-15",
                "holder_count": 85,
                "holder_count_change": 8,
                "top_10_holder_concentration": 0.30,
                "quarterly_position_change_pct": 6.0,
                "institutional_ownership_proxy": 0.62,
                "peer_average_institutional_ownership": 0.54,
                "peer_average_quarterly_position_change_pct": 2.0,
                "sector_median_institutional_ownership": 0.55,
            }
        }
    )
    payload = result.model_dump()
    assert result.score == 40
    assert payload["raw_data"]["quarter"] == "2026-Q1"
    assert payload["raw_data"]["filing_date"] == "2026-05-15"
    assert payload["derived_metrics"]["is_real_time_signal"] is False
    assert payload["derived_metrics"]["institutional_support_label"] == "institutional_evidence_limited"
    assert any("45 days" in item for item in payload["limitations"])
    assert any("not used to boost" in item for item in payload["limitations"])
    assert_score_contract(payload)
    assert_no_prohibited_language(payload)


def test_insider_net_buying_equivalent_accumulation_is_positive() -> None:
    result = evaluate_form4_insider_signal(
        {
            "form4_transactions": [
                {
                    "insider_name": "Mock CEO",
                    "role": "Founder CEO",
                    "transaction_code": "P",
                    "transaction_type": "accumulation",
                    "shares": 1000,
                    "price": 100.0,
                    "value": 100000,
                    "transaction_date": "2026-04-01",
                    "filing_date": "2026-04-03",
                },
                {
                    "insider_name": "Mock Director",
                    "role": "Director",
                    "transaction_code": "P",
                    "transaction_type": "accumulation",
                    "shares": 500,
                    "price": 101.0,
                    "value": 50500,
                    "transaction_date": "2026-04-06",
                    "filing_date": "2026-04-08",
                },
            ]
        }
    )
    payload = result.model_dump()
    assert result.score == 100
    assert result.label == "insider_accumulation_observed"
    assert payload["derived_metrics"]["net_insider_accumulation_value_180d"] > 0
    assert_no_prohibited_language(payload)


def test_insider_selling_equivalent_disposition_is_risk_signal() -> None:
    result = evaluate_form4_insider_signal(
        {
            "form4_transactions": [
                {
                    "insider_name": "Mock Officer A",
                    "role": "Officer",
                    "transaction_code": "S",
                    "transaction_type": "disposition",
                    "shares": 1200,
                    "price": 90.0,
                    "value": 108000,
                    "transaction_date": "2026-04-01",
                    "filing_date": "2026-04-03",
                },
                {
                    "insider_name": "Mock Officer B",
                    "role": "Officer",
                    "transaction_code": "S",
                    "transaction_type": "disposition",
                    "shares": 800,
                    "price": 91.0,
                    "value": 72800,
                    "transaction_date": "2026-04-10",
                    "filing_date": "2026-04-12",
                },
            ]
        }
    )
    payload = result.model_dump()
    assert result.score == 20
    assert result.label == "insider_distribution_risk"
    assert payload["derived_metrics"]["disposition_count_180d"] == 2
    assert_no_prohibited_language(payload)


def test_abnormal_options_activity_includes_ambiguity_limitation() -> None:
    result = evaluate_options_abnormal_activity(
        {
            "options_activity": {
                "option_volume": 60000,
                "open_interest": 12000,
                "call_put_ratio": 2.6,
                "implied_volatility": 0.58,
                "expiration_date": "2026-06-19",
                "abnormal_volume_ratio": 4.0,
                "direction_consistent_with_price_action": True,
            }
        }
    )
    payload = result.model_dump()
    assert result.score == 80
    assert payload["derived_metrics"]["volume_to_open_interest"] == 5.0
    assert any("ambiguous" in item for item in result.limitations)
    assert_score_contract(payload)
    assert_no_prohibited_language(payload)


def test_final_smart_money_score_weights_components() -> None:
    result = evaluate_smart_money(
        {
            "institutional_13f": {
                "quarter": "2026-Q1",
                "filing_date": "2026-05-15",
                "holder_count_change": 4,
                "quarterly_position_change_pct": 4.0,
                "peer_average_quarterly_position_change_pct": 2.0,
            },
            "form4_transactions": [
                {
                    "insider_name": "Mock CEO",
                    "role": "Founder CEO",
                    "transaction_code": "P",
                    "transaction_type": "accumulation",
                    "shares": 100,
                    "price": 50.0,
                    "value": 5000,
                    "transaction_date": "2026-04-02",
                    "filing_date": "2026-04-04",
                }
            ],
            "options_activity": {
                "option_volume": 30000,
                "open_interest": 10000,
                "abnormal_volume_ratio": 3.0,
                "direction_consistent_with_price_action": True,
            },
        }
    )
    payload = result.model_dump()
    assert result.score == 72.5
    assert result.label == "smart_money_mixed"
    assert set(payload["derived_metrics"]["components"]) == {
        "institutional_support_13f",
        "insider_form4_signal",
        "options_abnormal_activity",
    }
    assert_no_prohibited_language(payload)
