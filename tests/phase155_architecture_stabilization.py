from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from backend.app import config
from backend.app.jobs.daily_research_refresh import refresh_daily_research_snapshot
from backend.app.pipelines import mock_pipeline, research_pipeline
from backend.app.raw_store import company_cache, macro_cache, market_cache, price_reference_cache, repository, sec_cache, snapshot
from backend.app.schemas.common import DataSourceStatus
from backend.app.services.daily_candidates import parse_daily_report_candidates


def _isolate_store(monkeypatch) -> Path:
    cache_dir = Path("backend/raw_store/cache/test_phase155") / uuid4().hex
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MARKET_DATA_CACHE_DIR", cache_dir)
    monkeypatch.setattr(config, "MACRO_DATA_CACHE_DIR", cache_dir / "macro")
    monkeypatch.setattr(config, "SEC_FORM4_CACHE_DIR", cache_dir / "sec")
    monkeypatch.setattr(config, "SEC_13F_CACHE_DIR", cache_dir / "sec_13f")
    monkeypatch.setattr(config, "DAILY_REPORT_READ_MODE", "snapshot_first")
    monkeypatch.setattr(config, "DAILY_BATCH_ALLOW_LIVE_FETCH", True)
    monkeypatch.setattr(config, "DAILY_BATCH_PRICE_REFERENCE_WARMUP", False)
    monkeypatch.setattr(config, "DAILY_BATCH_MAX_RUNTIME_SECONDS", 180)
    monkeypatch.setattr(config, "USE_LIVE_MARKET_DATA", False)
    monkeypatch.setattr(config, "USE_LIVE_MACRO_DATA", False)
    monkeypatch.setattr(config, "USE_LIVE_SEC_FORM4", False)
    monkeypatch.setattr(config, "USE_LIVE_SEC_13F", False)
    monkeypatch.setattr(config, "DEFAULT_DAILY_REPORT_CANDIDATES", "NVDA:AI energy infrastructure,TSLA:humanoid robotics")
    return cache_dir


def test_daily_batch_does_not_mutate_report_fetch_config(monkeypatch):
    _isolate_store(monkeypatch)
    monkeypatch.setattr(config, "ALLOW_LIVE_FETCH_ON_REPORT_REQUEST", True)
    monkeypatch.setattr(config, "PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT", True)
    before = (
        config.ALLOW_LIVE_FETCH_ON_REPORT_REQUEST,
        config.PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT,
    )

    result = refresh_daily_research_snapshot()

    assert (
        config.ALLOW_LIVE_FETCH_ON_REPORT_REQUEST,
        config.PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT,
    ) == before
    assert result["status"] == "completed"
    assert "price_reference_warmup" in result
    stored = repository.read_daily_report_snapshot()
    assert stored["daily_report_metadata"]["snapshot_used"] is True
    assert "price_reference_warmup" in stored["daily_report_metadata"]


def test_research_pipeline_and_mock_pipeline_compatibility_imports():
    assert research_pipeline.build_daily_report is mock_pipeline.build_daily_report
    assert research_pipeline.build_daily_report().not_investment_advice is True


def test_raw_store_facade_and_split_modules_import_public_api():
    assert repository.get_market_data is market_cache.get_market_data
    assert repository.read_macro_data is macro_cache.read_macro_data
    assert repository.read_sec_filings is sec_cache.read_sec_filings
    assert repository.get_company_profile is company_cache.get_company_profile
    assert repository.write_daily_report_snapshot is snapshot.write_daily_report_snapshot
    assert repository.warm_price_reference_cache is price_reference_cache.warm_price_reference_cache


def test_daily_candidates_default_override_and_invalid_fallback():
    defaults, default_warnings = parse_daily_report_candidates(None)
    assert [(item.ticker, item.theme) for item in defaults] == [
        ("NVDA", "AI energy infrastructure"),
        ("TSLA", "humanoid robotics"),
    ]
    assert default_warnings == []

    override, warnings = parse_daily_report_candidates("MSFT:AI platform,AMD:accelerators")
    assert [(item.ticker, item.theme) for item in override] == [("MSFT", "AI platform"), ("AMD", "accelerators")]
    assert warnings == []

    fallback, fallback_warnings = parse_daily_report_candidates("broken")
    assert fallback[0].ticker == "NVDA"
    assert fallback_warnings == ["Daily report candidate configuration was invalid; safe defaults were used."]


class _SourceModel(BaseModel):
    source_status: DataSourceStatus | None = None
    source: list[str] | None = None
    source_date: str | None = None
    raw_data: dict = {}
    child: object | None = None


def test_enrich_source_status_preserves_existing_status_and_handles_depth():
    existing = DataSourceStatus(source_type="live", provider="unit_test", source_date="2026-05-05")
    model = _SourceModel(source_status=existing, source=["mock"], source_date="2026-04-24")
    statuses: list[DataSourceStatus] = []

    research_pipeline._enrich_source_status(model, statuses, max_depth=1)

    assert model.source_status is existing
    assert statuses[0].provider == "unit_test"


def test_enrich_source_status_handles_cycles_without_crashing():
    cyclic: dict[str, object] = {"source": ["unit"], "source_date": datetime.now(timezone.utc).date().isoformat()}
    cyclic["self"] = cyclic
    statuses: list[DataSourceStatus] = []

    research_pipeline._enrich_source_status(cyclic, statuses, max_depth=4)

    assert cyclic["source_status"]["provider"] == "unit"
    assert statuses


def test_smart_money_summary_remains_backward_compatible():
    report = research_pipeline.build_daily_report()
    assert report.smart_money is not None
    assert report.smart_money_summary == report.smart_money
