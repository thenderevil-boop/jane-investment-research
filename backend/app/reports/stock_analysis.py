from __future__ import annotations

from backend.app.data_sources.mock_data import DEFAULT_STOCK, MOCK_SOURCE_DATE, STOCK_FIXTURES
from backend.app.engines.leadership_engine import evaluate_leadership
from backend.app.engines.macro_regime_engine import evaluate_macro_regime
from backend.app.engines.market_timing_engine import evaluate_market_timing
from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.pipelines.mock_pipeline import _build_jane_reference_conditions, _enrich_source_status, score_object
from backend.app.raw_store.repository import read_macro_data, read_market_data, read_sec_filings
from backend.app.schemas.common import ScoreObject
from backend.app.schemas.stock_analysis import AnalyzeStockRequest, AnalyzeStockResponse, ResearchVerdict
from backend.app.utils.freshness import build_source_status, summarize_data_quality

MOCK_LEADERSHIP_CONFIDENCE_CAP = 0.72
MOCK_EVIDENCE_LIMITATION = "Mock evidence limits analyze-stock confidence; treat mock-based components as preliminary validation only."


def _research_verdict(
    *,
    leadership_percent: float,
    smart_money_score: float,
    macro_score: float,
    overheat_score: float,
    missing_data_count: int,
    confidence_inputs: list[float],
    mock_evidence_present: bool = False,
) -> ResearchVerdict:
    raw_score = leadership_percent * 0.45 + smart_money_score * 0.25 + macro_score * 0.20 + max(0, 100 - overheat_score) * 0.10
    missing_penalty = min(25, missing_data_count * 3)
    score = round(max(0, min(100, raw_score - missing_penalty)), 2)
    confidence = max(0.15, min(1, (sum(confidence_inputs) / len(confidence_inputs)) - min(0.35, missing_data_count * 0.03)))
    if mock_evidence_present:
        confidence = min(confidence, MOCK_LEADERSHIP_CONFIDENCE_CAP)
    confidence = round(confidence, 2)
    if missing_data_count >= 7 or confidence < 0.35:
        label = "insufficient_data"
        summary = "Research reference only. Evidence is incomplete, so this ticker needs human verification before deeper research priority is raised."
    elif overheat_score >= 75:
        label = "high_risk_context"
        summary = "Research reference only. The ticker has elevated risk context, so deeper review should focus on evidence quality and downside scenarios."
    elif score >= 70 and macro_score >= 50:
        label = "worth_deep_research"
        summary = "Research reference only. The ticker is worth deeper research under Jane methodology, with current environment context included."
    elif score >= 45:
        label = "watchlist_candidate"
        summary = "Research reference only. The ticker merits watchlist-level validation while missing or weaker evidence is checked."
    else:
        label = "insufficient_data"
        summary = "Research reference only. Current structured evidence is not strong enough to raise research priority."
    if mock_evidence_present:
        summary = f"{summary} Mock evidence limits confidence."
    return ResearchVerdict(label=label, score=score, confidence=confidence, summary=summary)


def analyze_stock(request: AnalyzeStockRequest) -> AnalyzeStockResponse:
    fixture = STOCK_FIXTURES.get(request.ticker, DEFAULT_STOCK)
    market_context = read_market_data()
    macro_snapshot = read_macro_data("normal", market_context_seed=market_context)
    macro_regime = evaluate_macro_regime(macro_snapshot)
    sec_filings = read_sec_filings(request.ticker)
    smart_money_data = {**fixture["smart_money"], **sec_filings}
    engine_context = {
        **fixture,
        **market_context,
        "user_reported_social_heat": request.user_context.social_discussion_level,
        "friends_asking_about_stock": request.user_context.friends_asking_about_stock,
    }
    missing_data = list(fixture["missing_data"])
    if market_context.get("source_type") != "live":
        missing_data.append("live price history")
    if sec_filings.get("form4_source_status", {}).get("source_type") not in {"live", "cached_live"}:
        missing_data.append("live SEC filing details")
    if sec_filings.get("institutional_13f_source_status", {}).get("source_type") not in {"live", "cached_live"}:
        missing_data.append("live SEC 13F data")
    missing_data.extend(macro_regime.missing_data)
    missing_data = sorted(set(missing_data))
    leadership_score = evaluate_leadership({"ticker": request.ticker, **fixture})
    market_timing_context = evaluate_market_timing(engine_context)
    overheat_risk = evaluate_overheat(engine_context)
    smart_money = evaluate_smart_money(smart_money_data)
    insider_activity = smart_money.derived_metrics["components"]["insider_form4_signal"]
    institutional_13f = smart_money.derived_metrics["components"]["institutional_support_13f"]
    if not hasattr(insider_activity, "model_dump"):
        insider_activity = ScoreObject.model_validate(insider_activity)
    if not hasattr(institutional_13f, "model_dump"):
        institutional_13f = ScoreObject.model_validate(institutional_13f)
    leadership_percent = leadership_score.score / leadership_score.max_score * 100
    leadership_status = build_source_status(leadership_score.model_dump(mode="json"))
    mock_evidence_present = leadership_status.source_type == "mock" or market_context.get("source_type") in {"mock", "fallback"}
    research_context = request.research_context.model_dump(exclude_none=True) if request.research_context else {}
    research_verdict = _research_verdict(
        leadership_percent=leadership_percent,
        smart_money_score=smart_money.score,
        macro_score=macro_regime.score,
        overheat_score=overheat_risk.score,
        missing_data_count=len(missing_data),
        confidence_inputs=[leadership_score.confidence, smart_money.confidence, macro_regime.confidence, overheat_risk.confidence],
        mock_evidence_present=mock_evidence_present,
    )

    response = AnalyzeStockResponse(
        ticker=request.ticker,
        analysis_mode="ticker_validation",
        research_verdict=research_verdict,
        company_profile={
            "company_name": fixture["company_name"],
            "sector": fixture["sector"],
            "market": "US",
            "themes": fixture["themes"],
            "source": ["phase1_mock_company_profile"],
            "source_date": MOCK_SOURCE_DATE,
            "market_price_source_type": market_context.get("source_type", "mock"),
            "source_status": build_source_status(
                {
                    "source_type": "mock",
                    "provider": "phase1_mock_company_profile",
                    "source": ["phase1_mock_company_profile"],
                    "source_date": MOCK_SOURCE_DATE,
                    "limitations": ["Company profile remains mock-based preliminary evidence."],
                    "missing_data": [],
                }
            ).model_dump(mode="json"),
            "research_context": research_context,
        },
        macro_regime=macro_regime,
        leadership_score=leadership_score,
        market_timing_context=market_timing_context,
        overheat_risk=overheat_risk,
        smart_money=smart_money,
        insider_activity=insider_activity,
        institutional_13f=institutional_13f,
        financial_quality=score_object(
            "financial_quality_score",
            min(100, 50 + fixture["free_cash_flow_margin_pct"] - max(0, fixture["net_debt_to_ebitda"]) * 5),
            "favorable_research_environment" if fixture["free_cash_flow_margin_pct"] >= 15 else "neutral",
            {
                "free_cash_flow_margin_pct": fixture["free_cash_flow_margin_pct"],
                "net_debt_to_ebitda": fixture["net_debt_to_ebitda"],
            },
            {"cash_generation_proxy": fixture["free_cash_flow_margin_pct"]},
            {"fcf_margin_supportive_pct": 15, "net_debt_to_ebitda_watch": 3},
            {"financial_quality": "up" if fixture["free_cash_flow_margin_pct"] >= 15 else "mixed"},
            0.62,
            missing_data=["live income statement", "live balance sheet"],
        ),
        valuation_context=score_object(
            "valuation_context_score",
            100 - fixture["valuation_percentile_vs_5y"],
            "elevated_heat" if fixture["valuation_percentile_vs_5y"] >= 75 else "neutral",
            {"valuation_percentile_vs_5y": fixture["valuation_percentile_vs_5y"]},
            {"relative_expensiveness_proxy": fixture["valuation_percentile_vs_5y"]},
            {"elevated_heat_percentile": 75},
            {"valuation_pressure": "up" if fixture["valuation_percentile_vs_5y"] >= 75 else "stable"},
            0.60,
            missing_data=["live peer valuation multiples"],
        ),
        risk_flags=[
            flag
            for flag, present in {
                "valuation_context_elevated": fixture["valuation_percentile_vs_5y"] >= 75,
                "social_heat_elevated": request.user_context.social_discussion_level == "high",
                "financial_quality_mixed": fixture["free_cash_flow_margin_pct"] < 5,
                "macro_context_cautious": macro_regime.score < 45,
            }.items()
            if present
        ],
        jane_reference_conditions=_build_jane_reference_conditions(macro_snapshot),
        missing_data=missing_data,
        human_verification_queue=[
            "Verify company fundamentals with current filings.",
            "Review current news and filings before using this research output.",
        ],
    )
    statuses: list = []
    _enrich_source_status(response, statuses)
    response.source_status = build_source_status(market_context)
    statuses.append(response.source_status)
    response.data_quality = summarize_data_quality(statuses)
    if response.data_quality.mock_components and MOCK_EVIDENCE_LIMITATION not in response.data_quality.limitations:
        response.data_quality.limitations.append(MOCK_EVIDENCE_LIMITATION)
    if macro_regime.macro_data_quality:
        response.data_quality.macro = {
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
            "excluded_indicators": macro_regime.macro_data_quality.excluded_indicators,
            "scoring": macro_regime.macro_data_quality.scoring,
            "market_context_reused_from_daily_market_data": (macro_regime.raw_data.get("raw_market_context") or {}).get("diagnostics", {}).get("market_context_reused_from_daily_market_data"),
            "confidence_adjustment_applied": macro_regime.macro_data_quality.confidence_adjustment_applied,
        }
    if response.data_quality.fallback_components:
        response.human_verification_queue.append("Review fallback source status because one or more live data sources were unavailable.")
    if response.data_quality.stale_components:
        response.human_verification_queue.append("Review stale live or derived data source status before interpreting scores.")
    if response.data_quality.missing_source_date_components:
        response.human_verification_queue.append("Review components with missing source dates before interpreting scores.")
    return response
