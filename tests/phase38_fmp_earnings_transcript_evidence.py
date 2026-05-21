from __future__ import annotations

import importlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from backend.app.schemas.common import DataSourceStatus

FORBIDDEN_PATTERNS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"target price",
    r"must invest",
    r"liquidate",
    r"position size",
]


def assert_no_forbidden_language(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False).lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert not re.search(pattern, text), pattern


def sample_transcripts() -> list[dict]:
    return [
        {
            "ticker": "MSFT",
            "quarter": 1,
            "year": 2026,
            "date": "2026-04-24",
            "transcript": (
                "CEO: Our cloud and AI strategy remains consistent. Customer demand is strong, "
                "pipeline expanded, and retention improved. We continue reinvestment in R&D and capex. "
                "CFO: We acknowledge macro uncertainty and margin pressure from compute costs, but pricing "
                "and operating leverage remain priorities."
            ),
        },
        {
            "symbol": "MSFT",
            "quarter": "4",
            "year": "2025",
            "date": "2026-01-25",
            "content": (
                "CEO: The same cloud and AI platform strategy continues. Enterprise customers are adopting "
                "the product suite and usage is expanding. CFO: We are watching competition, regulation, "
                "cost inflation, and gross margin pressure while preserving free cash flow."
            ),
        },
    ]


def test_earnings_transcript_schema_is_non_scoring_and_safe() -> None:
    from backend.app.schemas.earnings_transcript import EarningsTranscriptAnalysis, EarningsTranscriptDimension, TranscriptTheme

    status = DataSourceStatus(source_type="live", provider="fmp", source_date="2026-04-24", is_fresh=True)
    dimension = EarningsTranscriptDimension(
        label="clear",
        confidence=0.7,
        evidence_snippets=["Management repeatedly described cloud demand."],
        limitations=["Transcript evidence reflects management statements and requires review."],
    )
    payload = EarningsTranscriptAnalysis(
        ticker="MSFT",
        source_status=status,
        quarters_analyzed=2,
        management_consistency=dimension,
        strategy_clarity=dimension,
        risk_acknowledgement=dimension,
        customer_demand_signal=dimension,
        margin_pressure_signal=dimension,
        capital_allocation_focus=dimension,
        positive_themes=[TranscriptTheme(theme="customer_demand", label="supportive_context", evidence_snippets=["Customer demand is strong."], confidence=0.6)],
        risk_themes=[TranscriptTheme(theme="margin_pressure", label="review_context", evidence_snippets=["Compute costs remain a margin pressure."], confidence=0.6)],
        manual_checks=["Review full transcript context before interpreting management claims."],
        limitations=["Transcript analysis is research context only."],
    )

    dumped = payload.model_dump(mode="json")
    assert dumped["provider"] == "fmp"
    assert dumped["affects_score"] is False
    assert dumped["not_investment_advice"] is True
    assert dumped["management_consistency"]["affects_score"] is False
    assert_no_forbidden_language(dumped)


def test_deterministic_transcript_analyzer_extracts_management_context_without_scoring() -> None:
    from backend.app.features.earnings_transcript_analysis import analyze_earnings_transcripts

    analysis = analyze_earnings_transcripts("MSFT", sample_transcripts())
    dumped = analysis.model_dump(mode="json")

    assert dumped["ticker"] == "MSFT"
    assert dumped["quarters_analyzed"] == 2
    assert dumped["management_consistency"]["label"] == "consistent"
    assert dumped["strategy_clarity"]["label"] in {"clear", "mixed"}
    assert dumped["risk_acknowledgement"]["label"] in {"transparent", "partial"}
    assert dumped["customer_demand_signal"]["label"] in {"strong_positive", "mixed"}
    assert dumped["margin_pressure_signal"]["label"] in {"manageable_pressure", "elevated_pressure"}
    assert dumped["capital_allocation_focus"]["label"] in {"reinvestment_focused", "mixed"}
    assert dumped["affects_score"] is False
    assert dumped["not_investment_advice"] is True
    assert dumped["manual_checks"]
    assert_no_forbidden_language(dumped)


def test_transcript_adapter_uses_phase37_provider_status_and_redacts_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_LIVE_FMP_DATA", "true")
    monkeypatch.setenv("FMP_API_KEY", "dummy_fmp_key_for_test")
    import backend.app.config as config
    import backend.app.data_sources.provider_registry as registry
    import backend.app.data_sources.fmp_transcripts as fmp_transcripts

    importlib.reload(config)
    importlib.reload(registry)
    importlib.reload(fmp_transcripts)

    requested_urls: list[str] = []

    class DummyResponse:
        status_code = 200

        def json(self) -> list[dict]:
            return sample_transcripts()

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int = 15):
        requested_urls.append(url)
        return DummyResponse()

    result = fmp_transcripts.fetch_fmp_earnings_transcripts("msft", limit=2, http_get=fake_get)
    dumped = result.model_dump(mode="json")

    assert requested_urls and "dummy_fmp_key_for_test" in requested_urls[0]
    parsed_url = urlparse(requested_urls[0])
    parsed_query = parse_qs(parsed_url.query)
    assert parsed_url.path == "/api/v4/batch_earning_call_transcript/MSFT"
    assert parsed_query["apikey"] == ["dummy_fmp_key_for_test"]
    assert "year" in parsed_query
    assert "quarter" not in parsed_query
    assert dumped["ticker"] == "MSFT"
    assert dumped["source_status"]["provider"] == "fmp"
    assert dumped["source_status"]["source_type"] == "live"
    assert dumped["quarters_analyzed"] == 2
    assert "dummy_fmp_key_for_test" not in json.dumps(dumped)
    assert_no_forbidden_language(dumped)


def test_transcript_adapter_queries_previous_year_when_current_year_has_no_records(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_LIVE_FMP_DATA", "true")
    monkeypatch.setenv("FMP_API_KEY", "dummy_fmp_key_for_test")
    import backend.app.config as config
    import backend.app.data_sources.provider_registry as registry
    import backend.app.data_sources.fmp_transcripts as fmp_transcripts

    importlib.reload(config)
    importlib.reload(registry)
    importlib.reload(fmp_transcripts)

    requested_urls: list[str] = []

    class DummyResponse:
        status_code = 200

        def __init__(self, payload: list[dict]) -> None:
            self._payload = payload

        def json(self) -> list[dict]:
            return self._payload

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int = 15):
        requested_urls.append(url)
        return DummyResponse([] if len(requested_urls) == 1 else sample_transcripts())

    result = fmp_transcripts.fetch_fmp_earnings_transcripts("msft", limit=2, http_get=fake_get)
    dumped = result.model_dump(mode="json")

    assert len(requested_urls) == 2
    years = [int(parse_qs(urlparse(url).query)["year"][0]) for url in requested_urls]
    assert years == [datetime.now(timezone.utc).year, datetime.now(timezone.utc).year - 1]
    assert all(urlparse(url).path == "/api/v4/batch_earning_call_transcript/MSFT" for url in requested_urls)
    assert dumped["source_status"]["source_type"] == "live"
    assert dumped["quarters_analyzed"] == 2
    assert "dummy_fmp_key_for_test" not in json.dumps(dumped)


def test_fmp_transcript_cache_ttl_and_cached_after_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.raw_store import fmp_transcripts_cache

    monkeypatch.setattr(fmp_transcripts_cache, "_cache_dir", lambda: tmp_path)
    now = datetime.now(timezone.utc)
    fmp_transcripts_cache.save_fmp_transcripts_snapshot("MSFT", {"records": sample_transcripts()}, fetched_at=now)

    fresh = fmp_transcripts_cache.load_cached_fmp_transcripts("MSFT", ttl_days=7, now=now + timedelta(days=1))
    stale = fmp_transcripts_cache.load_cached_fmp_transcripts("MSFT", ttl_days=1, now=now + timedelta(days=2))

    assert fresh is not None
    assert fresh["cache_hit"] is True
    assert fresh["ticker"] == "MSFT"
    assert stale is None


def test_analyze_stock_includes_disabled_transcript_context_without_changing_score(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_LIVE_FMP_DATA", "false")
    import backend.app.config as config
    import backend.app.data_sources.provider_registry as registry
    import backend.app.reports.stock_analysis as stock_analysis

    importlib.reload(config)
    importlib.reload(registry)
    importlib.reload(stock_analysis)

    request = stock_analysis.AnalyzeStockRequest(ticker="NVDA")
    response = stock_analysis.analyze_stock(request)
    dumped = response.model_dump(mode="json")

    assert "earnings_transcript_analysis" in dumped
    transcript = dumped["earnings_transcript_analysis"]
    assert transcript["source_status"]["provider"] == "fmp"
    assert transcript["source_status"]["source_type"] == "unknown"
    assert transcript["quarters_analyzed"] == 0
    assert transcript["affects_score"] is False
    assert transcript["not_investment_advice"] is True
    assert "fmp_earnings_transcripts" in transcript["source_status"]["missing_data"]
    assert dumped["score_driver_breakdown"]["final_score"] == dumped["research_verdict"]["score"]
    assert_no_forbidden_language(transcript)


def test_analyze_stock_uses_fmp_transcript_analysis_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.features.earnings_transcript_analysis import analyze_earnings_transcripts
    import backend.app.reports.stock_analysis as stock_analysis

    analysis = analyze_earnings_transcripts("NVDA", sample_transcripts())
    monkeypatch.setattr(stock_analysis, "get_earnings_transcript_analysis", lambda ticker: analysis)

    response = stock_analysis.analyze_stock(stock_analysis.AnalyzeStockRequest(ticker="NVDA"))
    dumped = response.model_dump(mode="json")
    transcript = dumped["earnings_transcript_analysis"]

    assert transcript["quarters_analyzed"] == 2
    assert transcript["management_consistency"]["label"] == "consistent"
    assert transcript["affects_score"] is False
    assert transcript["not_investment_advice"] is True
    assert "earnings_transcript_analysis" in dumped["data_quality_summary"].get("excluded_from_scoring", [])
    assert_no_forbidden_language(transcript)
