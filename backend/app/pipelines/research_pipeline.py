# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from backend.app import config
from backend.app.data_sources.mock_crisis import MOCK_CRISIS_SCENARIOS
from backend.app.data_sources.mock_data import MOCK_SMART_MONEY_SUMMARY, MOCK_SOURCE, MOCK_SOURCE_DATE, STOCK_FIXTURES
from backend.app.engines.crisis_engine import crisis_to_score_object, evaluate_crisis
from backend.app.engines.future_industry_engine import evaluate_future_industry_radar
from backend.app.engines.leadership_engine import evaluate_leadership
from backend.app.engines.macro_regime_engine import evaluate_macro_regime
from backend.app.engines.market_timing_engine import evaluate_market_timing
from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.engines.risk_allocation_engine import evaluate_risk_allocation
from backend.app.engines.sec_13f_target_matching import build_candidate_13f_evidence
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.raw_store.repository import read_daily_report_snapshot, read_macro_data, read_market_data, read_sec_filings
from backend.app.services.daily_candidates import configured_daily_report_candidates
from backend.app.schemas.candidate import StockCandidate
from backend.app.schemas.common import DataSourceStatus, ScoreObject
from backend.app.schemas.daily_report import (
    DailyActionRouteHint,
    DailyCommandCenter,
    DailyCommandCenterMacroSnapshot,
    DailyCommandCenterSourceAlert,
    DailyCommandCenterWatchlistFocus,
    DailyMacroDelta,
    DailyResearchReport,
    DailyWatchlistDelta,
    DailyWatchlistDeltaItem,
    JaneReferenceCondition,
    JaneReferenceConditions,
    TodayResearchAction,
)
from backend.app.utils.freshness import build_source_status, summarize_data_quality
from backend.app.utils.human_verification import append_jane_social_heat_check
from backend.app.utils.performance import add_timing, finalize_performance_context, reset_performance_context

JANE_REFERENCE_CONDITIONS_PATH = Path(__file__).resolve().parents[1] / "data" / "jane_reference_conditions.json"


def score_object(
    name: str,
    score: float,
    label: str,
    raw_data: dict,
    derived_metrics: dict,
    benchmark: dict,
    trend: dict,
    confidence: float,
    limitations: list[str] | None = None,
    missing_data: list[str] | None = None,
) -> ScoreObject:
    return ScoreObject(
        name=name,
        score=round(score, 2),
        label=label,
        raw_data=raw_data,
        derived_metrics=derived_metrics,
        benchmark=benchmark,
        trend=trend,
        source=MOCK_SOURCE,
        source_date=MOCK_SOURCE_DATE,
        confidence=confidence,
        limitations=limitations or ["Phase 1 mock data only; no live source connection."],
        missing_data=missing_data or [],
    )


def _macro_scenario_name(scenario: str) -> str:
    return {"fearful": "fear_crisis"}.get(scenario, scenario)


def _crisis_scenario_name(scenario: str) -> str:
    return {"fearful": "high", "fear_crisis": "high", "overheated": "normal"}.get(scenario, scenario)


def _candidate(ticker: str, theme: str, market_context: dict | None = None) -> StockCandidate:
    fixture = STOCK_FIXTURES[ticker]
    sec_filings = read_sec_filings(ticker)
    smart_money_data = {**fixture["smart_money"], **sec_filings}
    engine_context = {**fixture, **(market_context or {})}
    source = market_context.get("source", MOCK_SOURCE) if market_context else MOCK_SOURCE
    source_date = market_context.get("source_date", MOCK_SOURCE_DATE) if market_context else MOCK_SOURCE_DATE
    if isinstance(source, str):
        source = [source]
    leadership = evaluate_leadership({"ticker": ticker, **fixture})
    smart_money = evaluate_smart_money(smart_money_data)
    market_timing = evaluate_market_timing(engine_context)
    overheat = evaluate_overheat(engine_context)
    leadership_percent = leadership.score / leadership.max_score * 100
    risk_score = round(overheat.score * 0.60 + max(0, 100 - leadership_percent) * 0.40, 2)
    confidence = round((leadership.confidence + smart_money.confidence + market_timing.confidence + overheat.confidence) / 4, 2)
    form4_status = sec_filings.get("form4_source_status", {})
    thirteen_f_status = sec_filings.get("institutional_13f_source_status", {})
    form4_source_type = form4_status.get("source_type", "mock")
    thirteen_f_source_type = thirteen_f_status.get("source_type", "mock")
    missing_items = {
        *fixture.get("missing_data", []),
        *leadership.missing_data,
        *smart_money.missing_data,
        *market_timing.missing_data,
        *overheat.missing_data,
    }
    if form4_source_type in {"live", "cached_live"}:
        missing_items.discard("live SEC Form 4 data")
        missing_items.discard("live SEC filings")
    if thirteen_f_source_type in {"live", "cached_live"}:
        missing_items.discard("live SEC 13F data")
        missing_items.discard("live SEC filings")
    candidate = StockCandidate(
        ticker=ticker,
        company_name=fixture["company_name"],
        theme=theme,
        leadership_score=leadership.score,
        smart_money_score=smart_money.score,
        market_timing_score=market_timing.score,
        overheat_score=overheat.score,
        risk_score=risk_score,
        label=leadership.label,
        source=source,
        source_date=source_date,
        confidence=confidence,
        limitations=sorted({*leadership.limitations, *smart_money.limitations, *market_timing.limitations, *overheat.limitations}),
        missing_data=sorted(missing_items),
    )
    thirteen_f_raw = smart_money.raw_data.get("institutional_13f", {})
    candidate.institutional_13f = build_candidate_13f_evidence(
        ticker,
        sec_filings.get("institutional_13f_summary") or thirteen_f_raw.get("portfolio_summary") or {},
        sec_filings.get("institutional_13f_target_matches") or {"target_matches": thirteen_f_raw.get("target_matches", [])},
    )
    component_source_types = {
        item
        for item in [
            market_context.get("source_type") if market_context else None,
            form4_source_type,
            thirteen_f_source_type,
            "mock",
        ]
        if item
    }
    has_mixed_sources = len(component_source_types) > 1
    candidate_fallback_used = (
        (market_context.get("fallback_used") if market_context else False)
        or form4_source_type == "fallback"
        or thirteen_f_source_type == "fallback"
    )
    market_status = (market_context or {}).get("source_status") or {}
    candidate_is_fresh = (
        (form4_status.get("is_fresh", True) is not False)
        and (thirteen_f_status.get("is_fresh", True) is not False)
        and (market_status.get("is_fresh", True) is not False)
    )
    candidate.source_status = build_source_status(
        {
            "source_type": "derived" if has_mixed_sources else form4_source_type,
            "provider": "mixed_sources" if has_mixed_sources else form4_status.get("provider"),
            "source": sorted(set([*candidate.source, *(form4_status.get("source") or []), *(thirteen_f_status.get("source") or [])])),
            "source_date": max(
                [
                    item
                    for item in [
                        candidate.source_date,
                        form4_status.get("source_date", "") if form4_source_type in {"live", "cached_live"} else "",
                        thirteen_f_status.get("source_date", "") if thirteen_f_source_type in {"live", "cached_live"} else "",
                    ]
                    if item
                ],
                default=candidate.source_date,
            ),
            "is_fresh": candidate_is_fresh,
            "limitations": candidate.limitations,
            "missing_data": candidate.missing_data,
            "fallback_used": candidate_fallback_used,
            "fallback_reason": (market_context.get("fallback_reason") if market_context else None) or form4_status.get("fallback_reason") or thirteen_f_status.get("fallback_reason"),
        }
    )
    return candidate


def _payload_for_source_status(value) -> dict:
    if hasattr(value, "model_dump"):
        data = value.model_dump(mode="json")
    elif isinstance(value, dict):
        data = value
    else:
        return {}
    raw_data = data.get("raw_data") if isinstance(data.get("raw_data"), dict) else {}
    payload = {
        "source_type": data.get("source_type") or raw_data.get("source_type"),
        "source": data.get("source") or raw_data.get("source"),
        "source_date": data.get("source_date") or raw_data.get("source_date"),
        "cached_at": data.get("cached_at") or raw_data.get("cached_at"),
        "fetched_at": data.get("fetched_at") or raw_data.get("fetched_at"),
        "provider": data.get("provider") or raw_data.get("provider"),
        "fallback_used": data.get("fallback_used") or raw_data.get("fallback_used"),
        "fallback_reason": data.get("fallback_reason") or raw_data.get("fallback_reason") or raw_data.get("live_market_data_error"),
        "limitations": data.get("limitations"),
        "missing_data": data.get("missing_data"),
    }
    return payload


def _has_source_status_payload(payload: dict) -> bool:
    return any(payload.get(key) for key in ["source_type", "source", "source_date", "provider", "fallback_used", "fallback_reason"])


def _enrich_source_status(value, statuses: list | None = None, *, max_depth: int = 10, _depth: int = 0, _visited: set[int] | None = None) -> None:
    # Legacy compatibility. New engines must emit source_status directly.
    statuses = statuses if statuses is not None else []
    _visited = _visited if _visited is not None else set()
    if _depth > max_depth:
        return
    if isinstance(value, (BaseModel, dict, list)):
        value_id = id(value)
        if value_id in _visited:
            return
        _visited.add(value_id)
    if isinstance(value, BaseModel):
        model_fields = value.__class__.model_fields
        if "source_status" in model_fields and getattr(value, "source_status", None) is None:
            payload = _payload_for_source_status(value)
            if _has_source_status_payload(payload):
                status = build_source_status(payload)
                value.source_status = status
                statuses.append(status)
        elif "source_status" in model_fields and getattr(value, "source_status", None) is not None:
            statuses.append(getattr(value, "source_status"))
        for field_name in model_fields:
            if field_name == "source_status":
                continue
            _enrich_source_status(getattr(value, field_name), statuses, max_depth=max_depth, _depth=_depth + 1, _visited=_visited)
        return
    if isinstance(value, dict):
        if isinstance(value.get("source_status"), dict):
            statuses.append(DataSourceStatus.model_validate(value["source_status"]))
        if {"source", "source_date"}.issubset(value.keys()) and not value.get("source_status"):
            status = build_source_status(_payload_for_source_status(value))
            value["source_status"] = status.model_dump(mode="json")
            statuses.append(status)
        for child in value.values():
            _enrich_source_status(child, statuses, max_depth=max_depth, _depth=_depth + 1, _visited=_visited)
        return
    if isinstance(value, list):
        for child in value:
            _enrich_source_status(child, statuses, max_depth=max_depth, _depth=_depth + 1, _visited=_visited)


def _source_statuses(report: DailyResearchReport) -> list:
    statuses: list = []
    _enrich_source_status(report, statuses)
    return statuses


def build_daily_report(
    scenario: str = "normal",
    use_live_market_data: bool | None = None,
    report_clock: datetime | None = None,
) -> DailyResearchReport:
    performance_started_at = reset_performance_context()
    section_started_at = time.monotonic()
    snapshot = read_market_data(scenario, use_live=use_live_market_data)
    add_timing("market_data_ms", section_started_at)
    section_started_at = time.monotonic()
    macro_snapshot = read_macro_data(_macro_scenario_name(scenario), market_context_seed=snapshot)
    add_timing("macro_ms", section_started_at)
    crisis_snapshot = MOCK_CRISIS_SCENARIOS.get(_crisis_scenario_name(scenario), MOCK_CRISIS_SCENARIOS["normal"])
    macro_regime = evaluate_macro_regime(macro_snapshot)
    crisis = evaluate_crisis(crisis_snapshot)
    market_timing = evaluate_market_timing(snapshot)
    overheat_risk = evaluate_overheat(snapshot)
    configured_candidates, candidate_warnings = configured_daily_report_candidates()
    primary_ticker = configured_candidates[0].ticker if configured_candidates else "NVDA"
    sec_filings = read_sec_filings(primary_ticker)
    section_started_at = time.monotonic()
    smart_money = evaluate_smart_money({**MOCK_SMART_MONEY_SUMMARY, **sec_filings})
    add_timing("smart_money_ms", section_started_at)
    future_themes = evaluate_future_industry_radar()
    risk_allocation = evaluate_risk_allocation(macro_regime, market_timing, overheat_risk, crisis, snapshot)
    generated_at = report_clock or datetime.now(timezone.utc)
    today = generated_at.date().isoformat()
    section_started_at = time.monotonic()
    stock_candidates = [
        _candidate(candidate.ticker, candidate.theme, snapshot)
        for candidate in configured_candidates
        if candidate.ticker in STOCK_FIXTURES
    ]
    add_timing("candidate_generation_ms", section_started_at)
    jane_reference_conditions = _build_jane_reference_conditions(macro_snapshot)
    missing_data = sorted(
        set(
            [
                *(["live SEC filings"] if sec_filings.get("form4_source_status", {}).get("source_type") not in {"live", "cached_live"} else []),
                *(["live SEC 13F data"] if sec_filings.get("institutional_13f_source_status", {}).get("source_type") not in {"live", "cached_live"} else []),
                "live options feed",
                *(["live market prices"] if snapshot.get("source_type") != "live" else []),
                *(
                    ["live FRED macro data"]
                    if macro_snapshot.get("source_type") in {"mock", "fallback"}
                    and macro_snapshot.get("provider") != "mixed_FRED_and_mock_macro"
                    else []
                ),
                *macro_regime.missing_data,
                *crisis.missing_data,
                *risk_allocation.missing_data,
                *(item for theme in future_themes for item in theme.missing_data),
            ]
        )
    )
    limitations = sorted(
        set(
            [
                "Live market price data is enabled for price-derived fields only." if snapshot.get("source_type") == "live" else "Mock-only validation report; live market data APIs are not connected.",
                "FRED-backed macro data is enabled for selected macro fields only." if macro_snapshot.get("provider") == "mixed_FRED_and_mock_macro" else "Mock macro data is used unless live FRED macro data is configured.",
                *macro_regime.limitations,
                *crisis.limitations,
                *smart_money.limitations,
                *risk_allocation.limitations,
                "SEC Form 4 interpretation is limited by transaction-code context and reporting timing.",
                *(["Daily report fast mode uses fresh cached live data when available."] if config.DAILY_REPORT_FAST_MODE else []),
                *sec_filings.get("form4_snapshot", {}).get("limitations", []),
                *(item for theme in future_themes for item in theme.limitations),
                *candidate_warnings,
            ]
        )
    )
    report = DailyResearchReport(
        date=today,
        report_generated_at=generated_at.isoformat(),
        macro_regime=macro_regime,
        market_timing=market_timing,
        overheat_risk=overheat_risk,
        crisis_risk=crisis_to_score_object(crisis),
        crisis=crisis,
        future_themes=future_themes,
        stock_candidates=stock_candidates,
        smart_money_summary=smart_money,
        smart_money=smart_money,
        risk_allocation=risk_allocation,
        risk_notes=[
            f"Macro regime signal is {macro_regime.label} with confidence {macro_regime.confidence}.",
            f"Crisis playbook level is {crisis.level}; reference labels are research context only.",
            f"Risk reference posture is {risk_allocation.risk_posture}.",
            "Theme attention can change quickly when live data is enabled.",
        ],
        jane_reference_conditions=jane_reference_conditions,
        limitations=limitations,
        missing_data=missing_data,
        human_verification_queue=[
            "Verify current macro releases before relying on regime label.",
            "Review theme news manually because Phase 1 uses mock mentions.",
            *(["Review daily report candidate configuration; one or more entries were invalid."] if candidate_warnings else []),
        ],
    )
    report.data_quality = summarize_data_quality(_source_statuses(report))
    if macro_regime.macro_data_quality:
        report.data_quality.macro = {
            "provider": macro_regime.source_status.provider if macro_regime.source_status else macro_snapshot.get("provider", "unknown"),
            "live_macro_fields_count": macro_regime.macro_data_quality.live_macro_fields_count,
            "derived_macro_fields_count": macro_regime.macro_data_quality.derived_macro_fields_count,
            "mock_macro_fields_count": macro_regime.macro_data_quality.mock_macro_fields_count,
            "yfinance_macro_fields_count": macro_regime.macro_data_quality.yfinance_macro_fields_count,
            "has_mock_macro_context": macro_regime.macro_data_quality.has_mock_macro_context,
            "mock_context_fields": macro_regime.macro_data_quality.mock_context_fields,
            "fred_backed_fields": macro_regime.macro_data_quality.fred_backed_fields,
            "derived_from_fred_fields": macro_regime.macro_data_quality.derived_from_fred_fields,
            "yfinance_backed_fields": macro_regime.macro_data_quality.yfinance_backed_fields,
            "derived_from_yfinance_fields": macro_regime.macro_data_quality.derived_from_yfinance_fields,
            "context_only_fred_fields": macro_regime.macro_data_quality.context_only_fred_fields,
            "excluded_indicators": macro_regime.macro_data_quality.excluded_indicators,
            "scoring": macro_regime.macro_data_quality.scoring,
            "market_context_reused_from_daily_market_data": (macro_regime.raw_data.get("raw_market_context") or {}).get("diagnostics", {}).get("market_context_reused_from_daily_market_data"),
            "confidence_adjustment_applied": macro_regime.macro_data_quality.confidence_adjustment_applied,
        }
    append_jane_social_heat_check(report.human_verification_queue, overheat_risk.score)
    if report.data_quality.stale_components:
        report.human_verification_queue.append("Review stale live or derived data source status before interpreting scores.")
    if report.data_quality.missing_source_date_components:
        report.human_verification_queue.append("Review components with missing source dates before interpreting scores.")
    if report.data_quality.fallback_components:
        report.human_verification_queue.append("Review fallback source status because one or more live data sources were unavailable.")
    previous_snapshot = read_daily_report_snapshot()
    report.macro_delta = _build_macro_delta(report, previous_snapshot)
    report.watchlist_delta = _build_watchlist_delta(report, previous_snapshot)
    report.today_research_actions = _build_today_research_actions(report)
    report.command_center = _build_command_center(report)
    if config.INCLUDE_PERFORMANCE_DIAGNOSTICS:
        report.performance_diagnostics = finalize_performance_context(performance_started_at)
    return report


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _nested_number(payload: dict | None, *path: str) -> float | None:
    cursor: object = payload or {}
    for key in path:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return _number(cursor)


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return round(current - previous, 2)


def _build_macro_delta(report: DailyResearchReport, previous_snapshot: dict | None) -> DailyMacroDelta | None:
    if not previous_snapshot:
        return None
    current_raw = report.macro_regime.raw_data if report.macro_regime else {}
    previous_raw = previous_snapshot.get("macro_regime", {}).get("raw_data", {}) if isinstance(previous_snapshot.get("macro_regime"), dict) else {}
    latest_inflation = []
    for key, label in [("cpi_yoy", "CPI YoY"), ("ppi_yoy", "PPI YoY")]:
        current = _number(current_raw.get(key))
        previous = _number(previous_raw.get(key))
        if current is not None or previous is not None:
            latest_inflation.append({"name": label, "current": current, "previous": previous, "change": _delta(current, previous)})
    return DailyMacroDelta(
        previous_report_date=str(previous_snapshot.get("date") or "") or None,
        macro_score_change=_delta(_number(report.macro_regime.score), _nested_number(previous_snapshot, "macro_regime", "score")),
        vix_change=_delta(_number(current_raw.get("vix")), _number(previous_raw.get("vix"))),
        yield_curve_10y2y_spread_change_bps=_delta(_number(current_raw.get("ten_year_minus_two_year_spread_bps")), _number(previous_raw.get("ten_year_minus_two_year_spread_bps"))),
        latest_inflation_observations=latest_inflation,
        limitations=["Delta compares the current Daily Report with the latest stored snapshot and is research workflow context only."],
    )


def _candidate_by_ticker(snapshot: dict | None) -> dict[str, dict]:
    candidates = snapshot.get("stock_candidates") if isinstance(snapshot, dict) else []
    if not isinstance(candidates, list):
        return {}
    return {str(item.get("ticker") or "").upper(): item for item in candidates if isinstance(item, dict) and item.get("ticker")}


def _candidate_13f_status(candidate: StockCandidate, previous: dict | None) -> str:
    current_status = None
    if isinstance(candidate.institutional_13f, dict):
        current_status = (candidate.institutional_13f.get("source_status") or {}).get("source_type")
    previous_status = ((previous or {}).get("institutional_13f") or {}).get("source_status", {}).get("source_type") if isinstance((previous or {}).get("institutional_13f"), dict) else None
    if current_status and previous_status and current_status != previous_status:
        return f"changed:{previous_status}_to_{current_status}"
    if current_status:
        return str(current_status)
    return "unknown"


def _build_watchlist_delta(report: DailyResearchReport, previous_snapshot: dict | None) -> DailyWatchlistDelta | None:
    if not previous_snapshot:
        return None
    previous_by_ticker = _candidate_by_ticker(previous_snapshot)
    items: list[DailyWatchlistDeltaItem] = []
    for candidate in report.stock_candidates:
        previous = previous_by_ticker.get(candidate.ticker.upper())
        items.append(
            DailyWatchlistDeltaItem(
                ticker=candidate.ticker,
                price_change_pct=None,
                overheat_score_change=_delta(_number(candidate.overheat_score), _number((previous or {}).get("overheat_score"))),
                new_form4_count=None,
                institutional_13f_status=_candidate_13f_status(candidate, previous),
                data_issue=", ".join(candidate.missing_data[:2]) if candidate.missing_data else None,
            )
        )
    return DailyWatchlistDelta(
        previous_report_date=str(previous_snapshot.get("date") or "") or None,
        items=items,
        limitations=["Watchlist delta compares configured Daily Report candidates with the latest stored snapshot; price delta remains null unless a stable prior/current price field is available."],
    )

def _route_for_action(action: TodayResearchAction) -> DailyActionRouteHint:
    routes: dict[str, DailyActionRouteHint] = {
        "source_setup": "operations",
        "evidence_review": "evidence_library",
        "coverage_gap": "stock_research",
        "watchlist_change": "stock_research",
        "macro_context": "daily_report",
    }
    return routes.get(action.action_type, "daily_report")


def _with_route(action: TodayResearchAction) -> TodayResearchAction:
    action.route_hint = _route_for_action(action)
    return action


def _macro_snapshot_for_command_center(report: DailyResearchReport) -> DailyCommandCenterMacroSnapshot | None:
    delta = report.macro_delta
    if not delta:
        return DailyCommandCenterMacroSnapshot(summary=f"Macro regime is {report.macro_regime.label}; use it as research context before single-name work.")
    parts = []
    if delta.macro_score_change is not None:
        parts.append(f"macro score changed {delta.macro_score_change:+g}")
    if delta.vix_change is not None:
        parts.append(f"VIX changed {delta.vix_change:+g}")
    if delta.yield_curve_10y2y_spread_change_bps is not None:
        parts.append(f"10Y-2Y spread changed {delta.yield_curve_10y2y_spread_change_bps:+g} bps")
    summary = "; ".join(parts) if parts else "Macro delta has no numeric change available versus the previous snapshot."
    return DailyCommandCenterMacroSnapshot(summary=summary)


def _source_alerts_for_command_center(report: DailyResearchReport) -> list[DailyCommandCenterSourceAlert]:
    alerts: list[DailyCommandCenterSourceAlert] = []
    if not report.data_quality:
        return alerts
    if report.data_quality.fallback_components:
        alerts.append(
            DailyCommandCenterSourceAlert(
                severity="high",
                title="Review fallback data sources",
                reason="One or more live or derived data sources are unavailable; check Operations before comparing evidence.",
            )
        )
    if report.data_quality.stale_components:
        alerts.append(
            DailyCommandCenterSourceAlert(
                severity="medium",
                title="Review stale source status",
                reason="At least one component is stale; confirm source freshness before using daily changes as context.",
            )
        )
    if report.data_quality.missing_source_date_components:
        alerts.append(
            DailyCommandCenterSourceAlert(
                severity="medium",
                title="Review missing source dates",
                reason="Some components are missing source dates, which limits daily change interpretation.",
            )
        )
    return alerts[:3]


def _watchlist_focus_for_command_center(report: DailyResearchReport) -> list[DailyCommandCenterWatchlistFocus]:
    items: list[DailyCommandCenterWatchlistFocus] = []
    if not report.watchlist_delta:
        return items
    for item in report.watchlist_delta.items:
        reasons = []
        if item.overheat_score_change is not None:
            reasons.append(f"overheat changed {item.overheat_score_change:+g}")
        if item.institutional_13f_status not in {"unknown", "live", "cached_live"}:
            reasons.append(f"13F status is {item.institutional_13f_status}")
        if item.data_issue:
            reasons.append(f"data issue: {item.data_issue}")
        if reasons:
            items.append(DailyCommandCenterWatchlistFocus(ticker=item.ticker, summary="; ".join(reasons)))
    return items[:3]


def _workflow_focus(source_alerts: list[DailyCommandCenterSourceAlert], watchlist_focus: list[DailyCommandCenterWatchlistFocus], actions: list[TodayResearchAction]) -> str:
    if any(alert.severity == "high" for alert in source_alerts):
        return "source_health_first"
    if any(action.action_type == "coverage_gap" for action in actions):
        return "evidence_gap_first"
    if watchlist_focus:
        return "watchlist_first"
    return "macro_first"


def _build_command_center(report: DailyResearchReport) -> DailyCommandCenter:
    top_actions = [_with_route(action) for action in report.today_research_actions[:3]]
    source_alerts = _source_alerts_for_command_center(report)
    watchlist_focus = _watchlist_focus_for_command_center(report)
    macro_snapshot = _macro_snapshot_for_command_center(report)
    workflow_focus = _workflow_focus(source_alerts, watchlist_focus, top_actions)
    if workflow_focus == "source_health_first":
        headline = "Start with source-health review, then use Daily Report changes as research context."
    elif workflow_focus == "evidence_gap_first":
        headline = "Start with the top evidence gap before opening deeper single-name research."
    elif workflow_focus == "watchlist_first":
        headline = "Start with watchlist changes, then review source context and evidence gaps."
    else:
        headline = "Start with macro context, then confirm whether any source or evidence gap needs attention."
    return DailyCommandCenter(
        headline=headline,
        workflow_focus=workflow_focus,  # type: ignore[arg-type]
        top_actions=top_actions,
        source_health_alerts=source_alerts,
        watchlist_focus=watchlist_focus,
        macro_snapshot=macro_snapshot,
    )


def _build_today_research_actions(report: DailyResearchReport) -> list[TodayResearchAction]:
    actions: list[TodayResearchAction] = []
    macro_label = report.macro_regime.label if report.macro_regime else "unknown"
    actions.append(
        TodayResearchAction(
            priority="medium",
            action_type="macro_context",
            title="Start with macro context",
            reason=f"Daily macro regime is {macro_label}; use it as context before single-name research, not as a timing directive.",
        )
    )
    if report.data_quality and report.data_quality.fallback_components:
        actions.append(
            TodayResearchAction(
                priority="high",
                action_type="source_setup",
                title="Review fallback data sources",
                reason="One or more live or derived data sources are unavailable; confirm provider settings before comparing today with prior runs.",
            )
        )
    if report.watchlist_delta and report.watchlist_delta.items:
        changed = [item for item in report.watchlist_delta.items if item.overheat_score_change is not None or item.data_issue]
        if changed:
            first = changed[0]
            actions.append(
                TodayResearchAction(
                    priority="high" if first.data_issue else "medium",
                    ticker=first.ticker,
                    action_type="watchlist_change",
                    title=f"Review {first.ticker} watchlist delta",
                    reason="Daily Watchlist Delta shows a changed score, source status, or data issue versus the previous snapshot.",
                )
            )
    for candidate in report.stock_candidates[:3]:
        if candidate.missing_data:
            actions.append(
                TodayResearchAction(
                    priority="high",
                    ticker=candidate.ticker,
                    action_type="coverage_gap",
                    title=f"Resolve {candidate.ticker} evidence gap",
                    reason=f"Candidate radar still lists missing data: {', '.join(candidate.missing_data[:2])}.",
                )
            )
            break
    if report.human_verification_queue:
        actions.append(
            TodayResearchAction(
                priority="medium",
                action_type="evidence_review",
                title="Complete manual evidence review queue",
                reason=f"Daily report has {len(report.human_verification_queue)} review item(s) that can clarify evidence quality before deeper analysis.",
            )
        )
    if not any(action.action_type == "coverage_gap" for action in actions):
        actions.append(
            TodayResearchAction(
                priority="medium",
                action_type="coverage_gap",
                title="Check top Coverage Matrix gaps before adding new signals",
                reason="Use existing Jane Coverage Matrix and manual evidence status to choose the next evidence item, rather than adding another explanation card.",
            )
        )
    return actions[:3]


def _build_jane_reference_conditions(macro_snapshot: dict[str, object]) -> JaneReferenceConditions:
    definition = _load_jane_reference_condition_text()
    display_text_by_name = {
        str(condition.get("name")): str(condition.get("display_text"))
        for condition in definition.get("conditions", [])
        if isinstance(condition, dict)
    }
    drawdown = min(
        value
        for value in [macro_snapshot.get("sp500_drawdown_pct"), macro_snapshot.get("nasdaq_drawdown_pct")]
        if isinstance(value, (int, float))
    ) if any(isinstance(value, (int, float)) for value in [macro_snapshot.get("sp500_drawdown_pct"), macro_snapshot.get("nasdaq_drawdown_pct")]) else None
    equity_trend = str(macro_snapshot.get("equity_trend") or "")
    base_like = equity_trend in {"stable", "stabilizing", "recovering", "base_building"}
    if drawdown is not None and drawdown <= -20 and base_like:
        index_status = "observed_condition"
    elif drawdown is not None:
        index_status = "not_observed"
    else:
        index_status = "partially_observable"
    return JaneReferenceConditions(
        title=str(definition.get("title") or "Jane methodology reference conditions"),
        conditions=[
            JaneReferenceCondition(
                name="fed_rate_cut_cycle",
                display_text=display_text_by_name.get("fed_rate_cut_cycle", "Fed rate cut cycle reference condition"),
                system_status="observable_not_evaluated",
                mapped_system_fields=["fed_funds_rate", "fed_policy_trend"],
                score_contribution_allowed=False,
            ),
            JaneReferenceCondition(
                name="major_index_drawdown_and_base",
                display_text=display_text_by_name.get("major_index_drawdown_and_base", "Major index drawdown and base reference condition"),
                system_status=index_status,
                mapped_system_fields=["equity_drawdown", "gain_from_recent_trough", "SPY", "QQQ"],
                score_contribution_allowed=False,
            ),
            JaneReferenceCondition(
                name="cnn_fear_greed_extreme_fear",
                display_text=display_text_by_name.get("cnn_fear_greed_extreme_fear", "CNN Fear & Greed extreme fear reference condition"),
                system_status="excluded_unlicensed_source",
                mapped_system_fields=[],
                score_contribution_allowed=False,
                limitation="CNN Fear & Greed is excluded from scoring because no licensed/stable source is configured.",
            ),
        ],
        limitations=[
            "Jane reference conditions are displayed for methodology context only.",
            "CNN Fear & Greed is excluded from scoring because no licensed/stable source is configured.",
            "ISM Manufacturing PMI is excluded from scoring because no valid licensed/live source is configured.",
            "Reference conditions are not system recommendations or investment instructions.",
        ],
    )


@lru_cache(maxsize=1)
def _load_jane_reference_condition_text() -> dict[str, object]:
    if not JANE_REFERENCE_CONDITIONS_PATH.exists():
        return {"title": "Jane methodology reference conditions", "conditions": []}
    with JANE_REFERENCE_CONDITIONS_PATH.open(encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {"title": "Jane methodology reference conditions", "conditions": []}
