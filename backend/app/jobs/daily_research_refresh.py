from __future__ import annotations

import time
from datetime import datetime, timezone

from backend.app import config
from backend.app.data_sources.mock_data import MOCK_SMART_MONEY_SUMMARY, STOCK_FIXTURES
from backend.app.middleware.safety_filter import SafetyViolationError, check_safety
from backend.app.pipelines.research_pipeline import build_daily_report
from backend.app.raw_store import repository
from backend.app.services.daily_batch_context import DailyBatchContext, use_daily_batch_context
from backend.app.services.daily_candidates import configured_daily_report_candidates


def _daily_research_tickers() -> list[str]:
    tickers: list[str] = []
    configured_candidates, _warnings = configured_daily_report_candidates()
    for ticker in [*(candidate.ticker for candidate in configured_candidates), *STOCK_FIXTURES.keys()]:
        normalized = str(ticker or "").strip().upper()
        if normalized and normalized not in tickers:
            tickers.append(normalized)
    return tickers


def _target_managers(ticker: str) -> list[str]:
    configured = [item.strip() for item in config.SEC_13F_TARGET_MANAGERS.split(",") if item.strip()]
    if configured:
        return configured[:5]
    fixture = repository.read_company_fundamentals(ticker)
    smart_money = fixture.get("smart_money", MOCK_SMART_MONEY_SUMMARY)
    institution = str(smart_money.get("institutional_13f", {}).get("institution_name") or "").strip()
    return [institution or "mock_manager"]


def _over_budget(started_at: float) -> bool:
    return time.monotonic() - started_at >= config.DAILY_BATCH_MAX_RUNTIME_SECONDS


def refresh_daily_research_snapshot() -> dict[str, object]:
    started_at = time.monotonic()
    batch_refresh_started_at = datetime.now(timezone.utc)
    generated_at = datetime.now(timezone.utc)
    tickers = _daily_research_tickers()
    market_symbols = ["SPY", "QQQ", "^VIX", *tickers]
    refreshed: dict[str, object] = {
        "market_tickers": [],
        "form4_tickers": [],
        "thirteen_f_managers": [],
        "price_reference_warmup": {},
    }
    warnings: list[str] = []

    for symbol in market_symbols:
        if _over_budget(started_at):
            warnings.append("Daily batch runtime budget reached during market data refresh.")
            break
        repository.get_market_data(symbol, use_live=config.USE_LIVE_MARKET_DATA and config.DAILY_BATCH_ALLOW_LIVE_FETCH)
        refreshed["market_tickers"].append(symbol)

    if not _over_budget(started_at):
        repository.get_macro_snapshot(use_live=config.USE_LIVE_MACRO_DATA and config.DAILY_BATCH_ALLOW_LIVE_FETCH)
        refreshed["macro"] = True
    else:
        warnings.append("Daily batch runtime budget reached before FRED refresh.")

    mapped_tickers: list[str] = []
    for ticker in tickers:
        if _over_budget(started_at):
            warnings.append("Daily batch runtime budget reached during SEC refresh.")
            break
        repository.get_sec_form4_transactions(ticker, allow_live_fetch=config.DAILY_BATCH_ALLOW_LIVE_FETCH)
        refreshed["form4_tickers"].append(ticker)
        for manager in _target_managers(ticker):
            if _over_budget(started_at):
                break
            snapshot = repository.get_sec_13f_holdings(manager, allow_live_fetch=config.DAILY_BATCH_ALLOW_LIVE_FETCH, ticker=ticker)
            refreshed["thirteen_f_managers"].append(manager)
            for mapped in repository.mapped_13f_tickers_from_snapshot(snapshot):
                if mapped not in mapped_tickers:
                    mapped_tickers.append(mapped)

    if config.DAILY_BATCH_PRICE_REFERENCE_WARMUP and mapped_tickers and not _over_budget(started_at):
        refreshed["price_reference_warmup"] = repository.warm_price_reference_cache(
            mapped_tickers,
            max_tickers=config.PRICE_REFERENCE_CACHE_WARMUP_MAX_TICKERS,
            allow_live_fetch=config.DAILY_BATCH_ALLOW_LIVE_FETCH,
        )

    batch_context = DailyBatchContext(
        allow_live_fetch_on_report_request=False,
        price_reference_cache_warmup_on_report=False,
        daily_batch_price_reference_warmed=bool(
            config.DAILY_BATCH_PRICE_REFERENCE_WARMUP
            and (refreshed.get("price_reference_warmup") or {}).get("selected_ticker_count", 0)
        ),
        batch_started_at=batch_refresh_started_at,
    )
    with use_daily_batch_context(batch_context):
        report = build_daily_report(report_clock=generated_at)

    batch_refresh_completed_at = datetime.now(timezone.utc)
    batch_duration_ms = int(round((time.monotonic() - started_at) * 1000))
    payload = report.model_dump(mode="json")
    payload["daily_report_metadata"] = {
        "read_mode": config.DAILY_REPORT_READ_MODE,
        "snapshot_used": True,
        "snapshot_id": None,
        "snapshot_generated_at": report.report_generated_at,
        "snapshot_is_fresh": True,
        "batch_refresh_status": "completed_with_warnings" if warnings else "completed",
        "batch_refresh_started_at": batch_refresh_started_at.isoformat(),
        "batch_refresh_completed_at": batch_refresh_completed_at.isoformat(),
        "batch_duration_ms": batch_duration_ms,
        "price_reference_warmup": refreshed.get("price_reference_warmup", {}),
    }
    if warnings:
        payload["limitations"] = sorted(set([*payload.get("limitations", []), *warnings]))
        payload["human_verification_queue"] = sorted(set([*payload.get("human_verification_queue", []), *warnings]))
    check_safety(payload)
    snapshot = repository.write_daily_report_snapshot(payload)
    elapsed_seconds = round(time.monotonic() - started_at, 3)
    return {
        "not_investment_advice": True,
        "status": payload["daily_report_metadata"]["batch_refresh_status"],
        "snapshot_id": snapshot.get("snapshot_id"),
        "snapshot_date": snapshot.get("date"),
        "cached_at": snapshot.get("cached_at"),
        "elapsed_seconds": elapsed_seconds,
        "batch_duration_ms": batch_duration_ms,
        "batch_refresh_started_at": batch_refresh_started_at.isoformat(),
        "batch_refresh_completed_at": batch_refresh_completed_at.isoformat(),
        "runtime_budget_seconds": config.DAILY_BATCH_MAX_RUNTIME_SECONDS,
        "price_reference_warmup": refreshed.get("price_reference_warmup", {}),
        "refreshed": refreshed,
        "warnings": warnings,
    }


def main() -> None:
    try:
        result = refresh_daily_research_snapshot()
    except SafetyViolationError as exc:
        raise SystemExit(f"daily research refresh blocked by safety filter: {exc}") from exc
    print(result)


if __name__ == "__main__":
    main()
