from __future__ import annotations

from datetime import datetime, timezone

from backend.app.data_sources.mock_crisis import MOCK_CRISIS_SCENARIOS
from backend.app.data_sources.mock_macro import MOCK_MACRO_SCENARIOS
from backend.app.data_sources.mock_data import MOCK_SMART_MONEY_SUMMARY, MOCK_SOURCE, MOCK_SOURCE_DATE, STOCK_FIXTURES
from backend.app.engines.crisis_engine import crisis_to_score_object, evaluate_crisis
from backend.app.engines.future_industry_engine import evaluate_future_industry_radar
from backend.app.engines.leadership_engine import evaluate_leadership
from backend.app.engines.macro_regime_engine import evaluate_macro_regime
from backend.app.engines.market_timing_engine import evaluate_market_timing
from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.engines.risk_allocation_engine import evaluate_risk_allocation
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.raw_store.repository import read_market_data
from backend.app.schemas.candidate import StockCandidate
from backend.app.schemas.common import ScoreObject
from backend.app.schemas.daily_report import DailyResearchReport


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
    engine_context = {**fixture, **(market_context or {})}
    source = market_context.get("source", MOCK_SOURCE) if market_context else MOCK_SOURCE
    source_date = market_context.get("source_date", MOCK_SOURCE_DATE) if market_context else MOCK_SOURCE_DATE
    if isinstance(source, str):
        source = [source]
    leadership = evaluate_leadership({"ticker": ticker, **fixture})
    smart_money = evaluate_smart_money(fixture["smart_money"])
    market_timing = evaluate_market_timing(engine_context)
    overheat = evaluate_overheat(engine_context)
    leadership_percent = leadership.score / leadership.max_score * 100
    risk_score = round(overheat.score * 0.60 + max(0, 100 - leadership_percent) * 0.40, 2)
    confidence = round((leadership.confidence + smart_money.confidence + market_timing.confidence + overheat.confidence) / 4, 2)
    return StockCandidate(
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
        missing_data=sorted({*fixture.get("missing_data", []), *leadership.missing_data, *smart_money.missing_data, *market_timing.missing_data, *overheat.missing_data}),
    )


def build_daily_report(scenario: str = "normal", use_live_market_data: bool | None = None) -> DailyResearchReport:
    snapshot = read_market_data(scenario, use_live=use_live_market_data)
    macro_snapshot = MOCK_MACRO_SCENARIOS.get(_macro_scenario_name(scenario), MOCK_MACRO_SCENARIOS["normal"])
    crisis_snapshot = MOCK_CRISIS_SCENARIOS.get(_crisis_scenario_name(scenario), MOCK_CRISIS_SCENARIOS["normal"])
    macro_regime = evaluate_macro_regime(macro_snapshot)
    crisis = evaluate_crisis(crisis_snapshot)
    market_timing = evaluate_market_timing(snapshot)
    overheat_risk = evaluate_overheat(snapshot)
    smart_money = evaluate_smart_money(MOCK_SMART_MONEY_SUMMARY)
    future_themes = evaluate_future_industry_radar()
    risk_allocation = evaluate_risk_allocation(macro_regime, market_timing, overheat_risk, crisis, snapshot)
    today = MOCK_SOURCE_DATE
    stock_candidates = [
        _candidate("NVDA", "AI energy infrastructure", snapshot),
        _candidate("TSLA", "humanoid robotics", snapshot),
    ]
    missing_data = sorted(
        set(
            [
                "live SEC filings",
                "live options feed",
                *(["live market prices"] if snapshot.get("source_type") != "live" else []),
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
                *macro_regime.limitations,
                *crisis.limitations,
                *smart_money.limitations,
                *risk_allocation.limitations,
                *(item for theme in future_themes for item in theme.limitations),
            ]
        )
    )
    return DailyResearchReport(
        date=today,
        report_generated_at=datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc).isoformat(),
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
