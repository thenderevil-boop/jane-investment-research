from __future__ import annotations

from backend.app import config
from backend.app.engines.sec_13f_aggregation import summarize_13f_portfolio
from backend.app.engines.sec_13f_target_matching import build_candidate_13f_evidence, match_13f_targets, normalize_target_security_map
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.pipelines import mock_pipeline
from backend.app.schemas.common import DataSourceStatus


def holding_row(issuer_name: str, cusip: str, value_usd: float, shares: float, *, confidence: str = "high") -> dict:
    return {
        "manager_cik": "0001067983",
        "accession_number": "0001067983-2026-03-31",
        "filing_date": "2026-05-15",
        "report_date": "2026-03-31",
        "issuer_name": issuer_name,
        "title_of_class": "COM",
        "cusip": cusip,
        "reported_value_raw": value_usd,
        "reported_value_unit": "as_reported",
        "value_usd": value_usd,
        "value_unit_confidence": confidence,
        "value_normalization_note": "fixture value",
        "shares_or_principal_amount": shares,
        "share_type": "SH",
        "put_call": "",
        "investment_discretion": "SOLE",
        "other_manager": "",
        "voting_authority_sole": 10,
        "voting_authority_shared": 0,
        "voting_authority_none": 0,
        "source": ["SEC EDGAR"],
        "source_status": {
            "source_type": "cached_live",
            "provider": "SEC EDGAR",
            "source_date": "2026-03-31",
            "fetched_at": "2026-05-15T00:00:00+00:00",
            "is_fresh": True,
            "freshness_window": "quarterly_filing_delay",
            "fallback_used": False,
            "limitations": [],
            "missing_data": [],
        },
    }


def berkshire_portfolio_summary() -> dict:
    summary = summarize_13f_portfolio(
        [
            holding_row("APPLE INC", "037833100", 100_000_000, 1_000_000),
            holding_row("AMERICAN EXPRESS CO", "025816109", 50_000_000, 500_000),
            holding_row("BANK OF AMERICA CORP", "060505104", 45_000_000, 450_000),
            holding_row("COCA COLA CO", "191216100", 40_000_000, 400_000),
            holding_row("CHEVRON CORP", "166764100", 35_000_000, 350_000),
        ]
    )
    summary["provider"] = "derived_from_SEC_EDGAR_13F"
    summary["underlying_source_type"] = "cached_live"
    summary["manager_cik"] = "0001067983"
    summary["manager_name"] = "Berkshire Hathaway Inc."
    summary["source_status"] = {
        "source_type": "cached_live",
        "provider": "SEC EDGAR",
        "source_date": "2026-03-31",
        "is_fresh": True,
        "freshness_window": "quarterly_filing_delay",
        "fallback_used": False,
        "limitations": [],
        "missing_data": [],
    }
    return summary


def target_matches_for(summary: dict, tickers: str) -> dict:
    return match_13f_targets(summary["grouped_holdings"], normalize_target_security_map({"tickers": tickers}))


def test_nvda_resolves_but_is_not_matched_when_berkshire_lacks_nvda_cusip():
    summary = berkshire_portfolio_summary()
    evidence = build_candidate_13f_evidence("NVDA", summary, target_matches_for(summary, "NVDA"))
    specific = evidence["candidate_specific_evidence"]
    assert specific["resolved_cusip"] == "67066G104"
    assert specific["matched_in_13f"] is False
    assert specific["match_confidence"] == "none"
    assert specific["interpretation_label"] == "no_reported_13f_position_observed"
    assert specific["position_value_usd"] is None
    assert "No reported 13F position was observed for this candidate in the configured manager portfolio." in evidence["limitations"]


def test_tsla_resolves_but_is_not_matched_when_berkshire_lacks_tsla_cusip():
    summary = berkshire_portfolio_summary()
    evidence = build_candidate_13f_evidence("TSLA", summary, target_matches_for(summary, "TSLA"))
    specific = evidence["candidate_specific_evidence"]
    assert specific["resolved_cusip"] == "88160R101"
    assert specific["matched_in_13f"] is False
    assert specific["interpretation_label"] == "no_reported_13f_position_observed"


def test_aapl_is_candidate_match_when_portfolio_contains_aapl_cusip():
    summary = berkshire_portfolio_summary()
    evidence = build_candidate_13f_evidence("AAPL", summary, target_matches_for(summary, "AAPL"))
    specific = evidence["candidate_specific_evidence"]
    assert specific["resolved_cusip"] == "037833100"
    assert specific["matched_in_13f"] is True
    assert specific["match_confidence"] == "high"
    assert specific["position_value_usd"] == 100_000_000
    assert specific["portfolio_weight_pct"] is not None
    assert specific["interpretation_label"] == "reported_13f_position_observed"


def test_portfolio_top_holdings_do_not_count_as_unrelated_candidate_support():
    summary = berkshire_portfolio_summary()
    evidence = build_candidate_13f_evidence("NVDA", summary, target_matches_for(summary, "NVDA,AAPL"))
    specific = evidence["candidate_specific_evidence"]
    assert specific["matched_in_13f"] is False
    assert all(match.get("resolved_ticker") == "NVDA" or match.get("target_value") == "NVDA" for match in evidence["target_matches"])
    assert any(item["mapped_ticker"] == "AAPL" for item in evidence["portfolio_context"]["top_holdings_by_value"])


def test_candidate_context_is_capped_and_full_holdings_are_not_exposed(monkeypatch):
    monkeypatch.setattr(config, "SEC_13F_CANDIDATE_CONTEXT_TOP_HOLDINGS_LIMIT", 2)
    summary = berkshire_portfolio_summary()
    evidence = build_candidate_13f_evidence("NVDA", summary, target_matches_for(summary, "NVDA"))
    assert len(evidence["portfolio_context"]["top_holdings_by_value"]) == 2
    assert "grouped_holdings" not in evidence
    assert "holdings" not in evidence
    assert "rows" not in evidence["portfolio_context"]["top_holdings_by_value"][0]


def test_issuer_name_only_match_returns_low_confidence_and_limitation():
    summary = summarize_13f_portfolio([holding_row("NVIDIA CORPORATION", "999999999", 10_000_000, 10_000)])
    summary["manager_cik"] = "0001067983"
    evidence = build_candidate_13f_evidence("NVDA", summary, target_matches_for(summary, "NVDA"))
    specific = evidence["candidate_specific_evidence"]
    assert specific["matched_in_13f"] is True
    assert specific["match_confidence"] == "low"
    assert specific["match_method"] == "issuer_name_string_match"
    assert specific["interpretation_label"] == "low_confidence_issuer_name_match"
    assert "Issuer-name-only 13F match is low confidence without CUSIP confirmation." in evidence["limitations"]


def test_unresolved_ticker_returns_insufficient_identifier_mapping():
    summary = berkshire_portfolio_summary()
    evidence = build_candidate_13f_evidence("ZZZZ", summary, [])
    specific = evidence["candidate_specific_evidence"]
    assert specific["matched_in_13f"] is False
    assert specific["match_confidence"] == "unknown"
    assert specific["match_method"] == "unresolved_ticker"
    assert specific["interpretation_label"] == "insufficient_identifier_mapping"
    assert "local security mapping unavailable for candidate ticker" in evidence["missing_data"]


def test_unmatched_candidate_does_not_receive_positive_13f_score_contribution():
    summary = berkshire_portfolio_summary()
    result = evaluate_smart_money(
        {
            "institutional_13f": {"cusip": "67066G104"},
            "institutional_13f_summary": summary,
            "institutional_13f_snapshot": {
                "manager": "0001067983",
                "manager_cik": "0001067983",
                "holdings": [row for holding in summary["grouped_holdings"] for row in holding["rows"]],
                "source_type": "cached_live",
                "provider": "SEC EDGAR",
                "source": ["SEC EDGAR"],
                "source_date": "2026-03-31",
                "limitations": [],
                "missing_data": [],
            },
            "institutional_13f_source_status": summary["source_status"],
            "institutional_13f_target_matches": target_matches_for(summary, "NVDA"),
            "form4_transactions": [],
            "options_activity": {},
        }
    )
    institutional = result.derived_metrics["components"]["institutional_support_13f"]
    assert institutional["score"] <= 40
    assert institutional["label"] in {"institutional_evidence_limited", "insufficient_data"}
    assert institutional["derived_metrics"]["high_confidence_target_match_count"] == 0


def test_mock_fallback_13f_target_matches_do_not_boost_score():
    summary = berkshire_portfolio_summary()
    summary["source_status"] = {
        **summary["source_status"],
        "source_type": "fallback",
        "provider": "mock",
        "fallback_used": True,
    }
    result = evaluate_smart_money(
        {
            "institutional_13f": {"cusip": "037833100"},
            "institutional_13f_summary": summary,
            "institutional_13f_snapshot": {
                "manager": "mock_manager",
                "holdings": [row for holding in summary["grouped_holdings"] for row in holding["rows"]],
                "source_type": "fallback",
                "provider": "mock",
                "source_status": summary["source_status"],
            },
            "institutional_13f_source_status": summary["source_status"],
            "institutional_13f_target_matches": target_matches_for(summary, "AAPL"),
            "form4_transactions": [],
            "options_activity": {},
        }
    )
    institutional = result.derived_metrics["components"]["institutional_support_13f"]
    assert institutional["score"] <= 40
    assert institutional["derived_metrics"]["target_match_count"] == 0
    assert institutional["derived_metrics"]["diagnostic_target_match_count"] >= 1


def test_stock_candidate_output_contains_candidate_specific_13f(monkeypatch):
    summary = berkshire_portfolio_summary()
    filings = {
        "institutional_13f": {"cusip": "67066G104"},
        "institutional_13f_summary": summary,
        "institutional_13f_target_matches": target_matches_for(summary, "NVDA,AAPL"),
        "institutional_13f_source_status": summary["source_status"],
        "form4_transactions": [],
        "form4_source_status": {"source_type": "mock", "provider": "mock", "source_date": "2025-01-01", "is_fresh": True},
        "options_activity": {},
    }
    monkeypatch.setattr(mock_pipeline, "read_sec_filings", lambda ticker: filings)
    candidate = mock_pipeline._candidate("NVDA", "AI energy infrastructure").model_dump(mode="json")
    thirteen_f = candidate["institutional_13f"]
    assert "candidate_specific_evidence" in thirteen_f
    assert "portfolio_context" in thirteen_f
    assert thirteen_f["candidate_specific_evidence"]["resolved_cusip"] == "67066G104"
    assert thirteen_f["candidate_specific_evidence"]["matched_in_13f"] is False
    assert "portfolio_summary" not in thirteen_f
    assert "grouped_holdings" not in thirteen_f["portfolio_context"]


def test_source_type_enum_rejects_mixed():
    try:
        DataSourceStatus(source_type="mixed")
    except Exception as exc:
        assert "source_type" in str(exc)
    else:
        raise AssertionError("source_type must not accept mixed")
