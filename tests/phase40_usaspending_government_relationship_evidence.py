from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from backend.app.schemas.stock_analysis import AnalyzeStockRequest

FORBIDDEN_PATTERNS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"target price",
    r"price target",
    r"guaranteed",
]


class MockResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _autocomplete_payload():
    return {
        "results": [
            {
                "recipient_name": "NVIDIA CORPORATION",
                "recipient_hash": "recipient-nvda-parent",
                "uei": "NVDAUEI123",
            }
        ]
    }


def _award_payload():
    return {
        "results": [
            {
                "Award ID": "FA0001",
                "Recipient Name": "NVIDIA CORPORATION",
                "Awarding Agency": "Department of Defense",
                "Award Amount": 12500000,
                "Start Date": "2025-02-14",
                "Award Type": "contract",
                "Description": "AI compute platform contract",
            },
            {
                "Award ID": "NN0002",
                "Recipient Name": "NVIDIA CORPORATION",
                "Awarding Agency": "National Aeronautics and Space Administration",
                "Award Amount": 2500000,
                "Start Date": "2024-07-01",
                "Award Type": "contract",
                "Description": "Accelerated computing research support",
            },
        ]
    }


def test_usaspending_adapter_normalizes_awards_and_aggregates_agency_context(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.app.config.USE_LIVE_USASPENDING_DATA", True)
    monkeypatch.setattr("backend.app.config.USASPENDING_CACHE_TTL_DAYS", 30)
    monkeypatch.setattr("backend.app.config.MARKET_DATA_CACHE_DIR", tmp_path)

    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        if url.endswith("/api/v2/autocomplete/recipient/"):
            assert json["search_text"] == "NVIDIA Corporation"
            return MockResponse(_autocomplete_payload())
        if url.endswith("/api/v2/search/spending_by_award/"):
            assert json["filters"]["recipient_search_text"] == ["NVIDIA CORPORATION"]
            return MockResponse(_award_payload())
        raise AssertionError(url)

    from backend.app.data_sources.usaspending_contracts import fetch_usaspending_contracts

    evidence = fetch_usaspending_contracts("NVDA", company_name="NVIDIA Corporation", http_post=fake_post)

    assert evidence.provider == "usaspending"
    assert evidence.source == "usaspending_contract_awards"
    assert evidence.source_status.provider == "usaspending"
    assert evidence.source_status.source_type == "live"
    assert evidence.total_obligated_amount == 15000000
    assert evidence.award_count == 2
    assert evidence.top_awarding_agencies[0].agency == "Department of Defense"
    assert evidence.top_awarding_agencies[0].obligated_amount == 12500000
    assert evidence.recipient_candidates[0].recipient_name == "NVIDIA CORPORATION"
    assert evidence.criteria[0].criterion_id == 15
    assert evidence.criteria[0].criterion_name == "Regulatory / Government Relationship"
    assert evidence.criteria[0].source_quality == "provider_backed"
    assert evidence.criteria[0].support_level == "supportive"
    assert "government_contracts" in evidence.criteria[0].covered_submetrics
    assert "defense_or_infrastructure_status" in evidence.criteria[0].covered_submetrics
    assert evidence.criteria[0].requires_manual_review is True
    assert evidence.affects_score is False
    assert evidence.not_investment_advice is True
    assert not any(re.search(pattern, json.dumps(evidence.model_dump(mode="json")), re.I) for pattern in FORBIDDEN_PATTERNS)
    assert len(calls) == 2


def test_usaspending_disabled_returns_c15_insufficient_data_without_network(monkeypatch):
    monkeypatch.setattr("backend.app.config.USE_LIVE_USASPENDING_DATA", False)

    def fail_post(*args, **kwargs):
        raise AssertionError("disabled provider should not call network")

    from backend.app.data_sources.usaspending_contracts import fetch_usaspending_contracts

    evidence = fetch_usaspending_contracts("NVDA", company_name="NVIDIA Corporation", http_post=fail_post)

    assert evidence.source_status.source_type == "fallback"
    assert evidence.source_status.provider == "usaspending"
    assert evidence.total_obligated_amount == 0
    assert evidence.award_count == 0
    assert evidence.criteria[0].criterion_id == 15
    assert evidence.criteria[0].support_level == "insufficient_data"
    assert evidence.criteria[0].source_quality == "insufficient"
    assert evidence.criteria[0].missing_data == ["usaspending_contract_awards"]
    assert evidence.affects_score is False


def test_usaspending_cached_snapshot_is_used_after_live_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.app.config.USE_LIVE_USASPENDING_DATA", True)
    monkeypatch.setattr("backend.app.config.USASPENDING_CACHE_TTL_DAYS", 30)
    monkeypatch.setattr("backend.app.config.MARKET_DATA_CACHE_DIR", tmp_path)

    from backend.app.data_sources.usaspending_contracts import fetch_usaspending_contracts
    from backend.app.raw_store.usaspending_contracts_cache import save_usaspending_contracts_snapshot

    save_usaspending_contracts_snapshot(
        "NVDA",
        {
            "query_name": "NVIDIA Corporation",
            "recipient_candidates": _autocomplete_payload()["results"],
            "awards": _award_payload()["results"],
        },
        fetched_at=datetime.now(timezone.utc),
    )

    def failing_post(*args, **kwargs):
        raise RuntimeError("provider temporary outage")

    evidence = fetch_usaspending_contracts("NVDA", company_name="NVIDIA Corporation", http_post=failing_post)

    assert evidence.source_status.source_type == "cached_live"
    assert evidence.source_status.fallback_used is True
    assert evidence.total_obligated_amount == 15000000
    assert evidence.criteria[0].source_quality == "cached_live"
    assert evidence.criteria[0].support_level == "supportive"


def test_analyze_stock_exposes_c15_government_relationship_and_coverage_without_scoring_changes(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.app.config.USE_LIVE_USASPENDING_DATA", True)
    monkeypatch.setattr("backend.app.config.MARKET_DATA_CACHE_DIR", tmp_path)

    def fake_post(url, json=None, timeout=None):
        if url.endswith("/api/v2/autocomplete/recipient/"):
            return MockResponse(_autocomplete_payload())
        if url.endswith("/api/v2/search/spending_by_award/"):
            return MockResponse(_award_payload())
        raise AssertionError(url)

    monkeypatch.setattr("backend.app.data_sources.usaspending_contracts.requests.post", fake_post)

    from backend.app.reports import stock_analysis

    response = stock_analysis.analyze_stock(AnalyzeStockRequest(ticker="NVDA"))

    evidence = response.government_relationship_evidence
    assert evidence.provider == "usaspending"
    assert evidence.criteria[0].criterion_id == 15
    assert evidence.criteria[0].support_level == "supportive"
    assert evidence.affects_score is False
    data_quality_summary = response.data_quality_summary.model_dump(mode="json")
    assert data_quality_summary["excluded_from_scoring"]
    assert "government_relationship_evidence" in data_quality_summary["excluded_from_scoring"]

    coverage = response.jane_criteria_coverage.model_dump(mode="json")
    c15 = next(row for row in coverage["criteria"] if row["criterion_id"] == 15)
    assert c15["coverage_status"] == "partial"
    assert c15["source_quality"] == "provider_backed"
    assert "government_contracts" in c15["covered_submetrics"]
    assert "defense_or_infrastructure_status" in c15["covered_submetrics"]
    assert c15["requires_human_verification"] is True

    payload = response.model_dump(mode="json")
    assert payload["candidate_validation_summary"]["score"] == response.research_verdict.score
    assert payload["government_relationship_evidence"]["not_investment_advice"] is True
    assert not any(re.search(pattern, json.dumps(payload["government_relationship_evidence"]), re.I) for pattern in FORBIDDEN_PATTERNS)
