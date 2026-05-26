from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.pipelines import research_pipeline
from backend.app.pipelines.research_pipeline import build_daily_report
from backend.app.reports.stock_analysis import _build_jane_criteria_coverage
from backend.app.schemas.common import DataSourceStatus, ScoreObject
from backend.app.schemas.patent_ip import PatentIPEvidence, PatentRecord
from backend.app.schemas.jane_external_evidence import JaneCriteriaExternalEvidenceItem


class _EmptyAssessment:
    def model_dump(self, *args, **kwargs) -> dict:
        return {}


def _external_evidence_empty():
    return SimpleNamespace(criteria=[])


def _coverage_row(payload: dict, criterion_id: int) -> dict:
    return next(row for row in payload["criteria"] if row["criterion_id"] == criterion_id)


def _minimal_response(**overrides):
    base = SimpleNamespace(
        qualitative_evidence_assessment=_EmptyAssessment(),
        financial_quality=SimpleNamespace(raw_data={}),
        jane_criteria_external_evidence=_external_evidence_empty(),
        government_relationship_evidence=_external_evidence_empty(),
        patent_ip_evidence=PatentIPEvidence(ticker="NVDA"),
        institutional_13f={},
        company_profile={},
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_c19_live_13f_target_match_reaches_coverage_matrix_from_analyze_stock_payload() -> None:
    institutional = {
        "label": "institutional_target_match_observed",
        "source_status": {"source_type": "live", "provider": "SEC EDGAR 13F", "source_date": "2026-03-31"},
        "candidate_specific_evidence": {"matched_in_13f": True, "manager_name": "Vanguard"},
    }
    response = _minimal_response(institutional_13f=institutional)

    payload = _build_jane_criteria_coverage(response)  # type: ignore[arg-type]
    c19 = _coverage_row(payload, 19)

    assert c19["coverage_status"] == "partial"
    assert "institutional_support" in c19["covered_submetrics"]
    assert "fund_support" in c19["covered_submetrics"]
    assert c19["financial_proxy_source"] == "sec_13f"
    assert any("delayed" in item.lower() for item in c19["limitations"])
    assert payload["not_investment_advice"] is True


def test_c19_fallback_13f_does_not_false_cover_and_surfaces_source_setup() -> None:
    institutional = {
        "label": "insufficient_data",
        "source_status": {"source_type": "fallback", "provider": "SEC EDGAR 13F", "fallback_used": True, "source_date": ""},
        "candidate_specific_evidence": {"matched_in_13f": False},
    }
    response = _minimal_response(institutional_13f=institutional)

    payload = _build_jane_criteria_coverage(response)  # type: ignore[arg-type]
    c19 = _coverage_row(payload, 19)

    assert c19["coverage_status"] == "insufficient"
    assert "institutional_support" not in c19["covered_submetrics"]
    assert "fund_support" not in c19["covered_submetrics"]
    assert c19["requires_human_verification"] is True


def test_c18_default_uspto_patent_count_reaches_coverage_matrix_from_analyze_stock_payload() -> None:
    patent = PatentIPEvidence(
        ticker="NVDA",
        query_name="NVIDIA Corporation",
        patent_count=237,
        source_status=DataSourceStatus(provider="uspto_patentsview", source_type="live", source_date="2026-05-01", is_fresh=True),
        criteria=[
            JaneCriteriaExternalEvidenceItem(
                criterion_id=18,
                criterion_name="patents_ip",
                support_level="partial",
                source_quality="provider_backed",
                confidence=0.55,
                covered_submetrics=["patent_count"],
                evidence_snippets=["PatentsView found 237 patent(s) assigned to NVIDIA Corporation."],
                manual_checks=["Confirm assignee/entity matching."],
                limitations=["Patent count is an auto-derived proxy and does not prove patent quality."],
            )
        ],
        patents=[PatentRecord(patent_id="US123", patent_title="GPU system", patent_date="2025-01-01", assignee="NVIDIA Corporation")],
        limitations=["Patent count is an auto-derived proxy and does not prove patent quality."],
        affects_score=False,
        not_investment_advice=True,
    )
    response = _minimal_response(patent_ip_evidence=patent)

    payload = _build_jane_criteria_coverage(response)  # type: ignore[arg-type]
    c18 = _coverage_row(payload, 18)

    assert c18["coverage_status"] == "partial"
    assert "patent_count" in c18["covered_submetrics"]
    assert c18["source_quality"] == "provider_backed"
    assert any("Patent count" in item for item in c18["limitations"])


def test_overheat_exposes_source_backing_and_mock_weight_share_without_score_change() -> None:
    data = {
        "source_type": "live",
        "source": ["yfinance"],
        "source_date": "2026-05-26",
        "index_gain_vs_prior_cycle_high": 35,
        "index_gain_from_recent_trough": 50,
        "distance_from_52w_high": -1,
        "current_volume": 200,
        "avg_volume_52w": 100,
        "current_price": 130,
        "ma_200d": 100,
    }
    result = evaluate_overheat(data)
    weights = result.derived_metrics["weights"]
    expected_score = round(sum(component["score"] * weights[name] for name, component in result.derived_metrics["components"].items()), 2)

    backing = result.derived_metrics["source_backing"]
    assert result.score == expected_score
    assert backing["total_configured_weight"] == 1.0
    assert backing["live_backed_weight"] > 0
    assert backing["mock_or_fallback_weight"] > 0
    assert backing["final_score_unchanged"] is True
    assert any(item["component"] == "media_hype_score" and item["source_type"] == "mock" for item in backing["components"])


def test_daily_report_builds_macro_and_watchlist_delta_from_previous_snapshot(monkeypatch) -> None:
    previous_snapshot = {
        "date": "2026-05-25",
        "macro_regime": {"score": 55, "raw_data": {"vix": 18, "ten_year_minus_two_year_spread_bps": -20, "cpi_yoy": 3.1, "ppi_yoy": 2.5}},
        "overheat_risk": {"score": 40},
        "stock_candidates": [
            {"ticker": "NVDA", "overheat_score": 35, "institutional_13f": {"source_status": {"source_type": "cached_live"}}, "missing_data": []}
        ],
    }
    monkeypatch.setattr(research_pipeline, "read_daily_report_snapshot", lambda *args, **kwargs: previous_snapshot, raising=False)

    report = build_daily_report(report_clock=datetime(2026, 5, 26, tzinfo=timezone.utc))

    assert report.macro_delta is not None
    assert report.macro_delta.version == "phase61_macro_delta_v1"
    assert report.macro_delta.macro_score_change == round(report.macro_regime.score - 55, 2)
    assert report.macro_delta.vix_change is not None
    assert report.watchlist_delta is not None
    assert report.watchlist_delta.version == "phase61_watchlist_delta_v1"
    assert report.watchlist_delta.items
    assert report.watchlist_delta.items[0].ticker == "NVDA"
    assert any(action.action_type in {"watchlist_change", "source_setup"} for action in report.today_research_actions)
