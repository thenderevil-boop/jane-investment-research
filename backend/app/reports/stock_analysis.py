from __future__ import annotations

from backend.app.data_sources.mock_data import DEFAULT_STOCK, MOCK_SOURCE_DATE, STOCK_FIXTURES
from backend.app.engines.leadership_engine import evaluate_leadership
from backend.app.engines.market_timing_engine import evaluate_market_timing
from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.pipelines.mock_pipeline import _enrich_source_status, score_object
from backend.app.raw_store.repository import read_market_data
from backend.app.schemas.stock_analysis import AnalyzeStockRequest, AnalyzeStockResponse
from backend.app.utils.freshness import build_source_status, summarize_data_quality


def analyze_stock(request: AnalyzeStockRequest) -> AnalyzeStockResponse:
    fixture = STOCK_FIXTURES.get(request.ticker, DEFAULT_STOCK)
    market_context = read_market_data()
    engine_context = {
        **fixture,
        **market_context,
        "user_reported_social_heat": request.user_context.social_discussion_level,
        "friends_asking_about_stock": request.user_context.friends_asking_about_stock,
    }
    missing_data = list(fixture["missing_data"])
    if market_context.get("source_type") != "live":
        missing_data.append("live price history")
    missing_data.append("live SEC filing details")

    response = AnalyzeStockResponse(
        ticker=request.ticker,
        company_profile={
            "company_name": fixture["company_name"],
            "sector": fixture["sector"],
            "market": "US",
            "themes": fixture["themes"],
            "source": ["phase1_mock_company_profile"],
            "source_date": MOCK_SOURCE_DATE,
            "market_price_source_type": market_context.get("source_type", "mock"),
        },
        leadership_score=evaluate_leadership({"ticker": request.ticker, **fixture}),
        market_timing_context=evaluate_market_timing(engine_context),
        overheat_risk=evaluate_overheat(engine_context),
        smart_money=evaluate_smart_money(fixture["smart_money"]),
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
            }.items()
            if present
        ],
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
    if response.data_quality.fallback_components:
        response.human_verification_queue.append("Review fallback market data status because live price data was unavailable.")
    if response.data_quality.stale_components:
        response.human_verification_queue.append("Review stale live or derived data source status before interpreting scores.")
    if response.data_quality.missing_source_date_components:
        response.human_verification_queue.append("Review components with missing source dates before interpreting scores.")
    return response
