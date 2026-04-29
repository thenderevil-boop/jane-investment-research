from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel

from backend.app.data_sources.mock_crisis import MOCK_CRISIS_SCENARIOS
from backend.app.data_sources.mock_data import MOCK_SMART_MONEY_SUMMARY, MOCK_SOURCE, MOCK_SOURCE_DATE, STOCK_FIXTURES
from backend.app.engines.crisis_engine import crisis_to_score_object, evaluate_crisis
from backend.app.engines.future_industry_engine import evaluate_future_industry_radar
from backend.app.engines.leadership_engine import evaluate_leadership
from backend.app.engines.macro_regime_engine import evaluate_macro_regime
from backend.app.engines.market_timing_engine import evaluate_market_timing
from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.engines.risk_allocation_engine import evaluate_risk_allocation
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.raw_store.repository import read_macro_data, read_market_data, read_sec_filings
from backend.app.schemas.candidate import StockCandidate
from backend.app.schemas.common import DataSourceStatus, ScoreObject
from backend.app.schemas.daily_report import DailyResearchReport
from backend.app.utils.freshness import build_source_status, summarize_data_quality


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
        missing_data=sorted(
            {
                *fixture.get("missing_data", []),
                *leadership.missing_data,
                *smart_money.missing_data,
                *market_timing.missing_data,
                *overheat.missing_data,
            }
            - (
                {"live SEC Form 4 data", "live SEC 13F data", "live SEC filings"}
                if sec_filings.get("form4_source_status", {}).get("source_type") in {"live", "cached_live"}
                and sec_filings.get("institutional_13f_source_status", {}).get("source_type") in {"live", "cached_live"}
                else set()
            )
        ),
    )
    thirteen_f_raw = smart_money.raw_data.get("institutional_13f", {})
    candidate.institutional_13f = {
        "portfolio_summary": thirteen_f_raw.get("portfolio_summary"),
        "target_matches": thirteen_f_raw.get("target_matches", []),
        "top_holdings_by_value": (thirteen_f_raw.get("top_holdings_by_value") or [])[:5],
        "limitations": [
            "13F is delayed quarterly evidence.",
            "13F may lag up to 45 days after quarter end.",
            "13F may not show shorts, many derivatives, or current positions.",
            "Local security mapping is bounded and not authoritative.",
            "Issuer-name matches are low confidence unless CUSIP or local ticker mapping confirms.",
            *(["Price reference may not match the 13F report date exactly."] if thirteen_f_raw.get("portfolio_summary", {}).get("price_reference_used_count") else []),
        ],
    }
    form4_status = sec_filings.get("form4_source_status", {})
    thirteen_f_status = sec_filings.get("institutional_13f_source_status", {})
    form4_source_type = form4_status.get("source_type", "mock")
    thirteen_f_source_type = thirteen_f_status.get("source_type", "mock")
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


def _enrich_source_status(value, statuses: list | None = None) -> None:
    statuses = statuses if statuses is not None else []
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
            _enrich_source_status(getattr(value, field_name), statuses)
        return
    if isinstance(value, dict):
        if isinstance(value.get("source_status"), dict):
            statuses.append(DataSourceStatus.model_validate(value["source_status"]))
        if {"source", "source_date"}.issubset(value.keys()) and value.get("source_status") is None:
            status = build_source_status(_payload_for_source_status(value))
            value["source_status"] = status.model_dump(mode="json")
            statuses.append(status)
        for child in value.values():
            _enrich_source_status(child, statuses)
        return
    if isinstance(value, list):
        for child in value:
            _enrich_source_status(child, statuses)


def _source_statuses(report: DailyResearchReport) -> list:
    statuses: list = []
    _enrich_source_status(report, statuses)
    return statuses


def build_daily_report(
    scenario: str = "normal",
    use_live_market_data: bool | None = None,
    report_clock: datetime | None = None,
) -> DailyResearchReport:
    snapshot = read_market_data(scenario, use_live=use_live_market_data)
    macro_snapshot = read_macro_data(_macro_scenario_name(scenario))
    crisis_snapshot = MOCK_CRISIS_SCENARIOS.get(_crisis_scenario_name(scenario), MOCK_CRISIS_SCENARIOS["normal"])
    macro_regime = evaluate_macro_regime(macro_snapshot)
    crisis = evaluate_crisis(crisis_snapshot)
    market_timing = evaluate_market_timing(snapshot)
    overheat_risk = evaluate_overheat(snapshot)
    sec_filings = read_sec_filings("NVDA")
    smart_money = evaluate_smart_money({**MOCK_SMART_MONEY_SUMMARY, **sec_filings})
    future_themes = evaluate_future_industry_radar()
    risk_allocation = evaluate_risk_allocation(macro_regime, market_timing, overheat_risk, crisis, snapshot)
    generated_at = report_clock or datetime.now(timezone.utc)
    today = generated_at.date().isoformat()
    stock_candidates = [
        _candidate("NVDA", "AI energy infrastructure", snapshot),
        _candidate("TSLA", "humanoid robotics", snapshot),
    ]
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
                "FRED-backed macro data is enabled for selected macro fields only." if macro_snapshot.get("provider") == "mixed_FRED_and_mock_macro" else "Mock macro data is used unless USE_LIVE_MACRO_DATA=true and FRED_API_KEY is configured.",
                *macro_regime.limitations,
                *crisis.limitations,
                *smart_money.limitations,
                *risk_allocation.limitations,
                "SEC Form 4 interpretation is limited by transaction-code context and reporting timing.",
                *sec_filings.get("form4_snapshot", {}).get("limitations", []),
                *(item for theme in future_themes for item in theme.limitations),
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
        limitations=limitations,
        missing_data=missing_data,
        human_verification_queue=[
            "Verify current macro releases before relying on regime label.",
            "Review theme news manually because Phase 1 uses mock mentions.",
        ],
    )
    report.data_quality = summarize_data_quality(_source_statuses(report))
    if report.data_quality.stale_components:
        report.human_verification_queue.append("Review stale live or derived data source status before interpreting scores.")
    if report.data_quality.missing_source_date_components:
        report.human_verification_queue.append("Review components with missing source dates before interpreting scores.")
    if report.data_quality.fallback_components:
        report.human_verification_queue.append("Review fallback source status because one or more live data sources were unavailable.")
    return report
