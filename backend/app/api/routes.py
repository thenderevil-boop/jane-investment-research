from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app import config
from backend.app.data_sources.mock_data import DEFAULT_STOCK, MOCK_SOURCE, MOCK_SOURCE_DATE, STOCK_FIXTURES
from backend.app.middleware.safety_filter import SafetyViolationError, check_safety
from backend.app.pipelines.mock_pipeline import build_daily_report
from backend.app.raw_store.repository import get_market_data, read_sec_filings
from backend.app.reports.stock_analysis import analyze_stock
from backend.app.schemas.daily_report import DailyResearchReport
from backend.app.schemas.health import HealthResponse
from backend.app.schemas.macro_regime import MacroRegimeOutput
from backend.app.schemas.stock_analysis import AnalyzeStockRequest, AnalyzeStockResponse
from backend.app.schemas.supplemental import DataHealthResponse, RawDataResponse, ThemesLatestResponse, TickerSignalsResponse
from backend.app.utils.freshness import build_source_status

router = APIRouter(prefix="/api")


def _model_dict(model):
    return model.model_dump(mode="json")


def _ensure_safe_response(model):
    try:
        check_safety(_model_dict(model))
    except SafetyViolationError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_safety_filter_blocked_response",
                "not_investment_advice": True,
            },
        ) from exc
    return model


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/data-health", response_model=DataHealthResponse)
def data_health() -> DataHealthResponse:
    return DataHealthResponse(
        providers={
            "yfinance": {
                "enabled": config.USE_LIVE_MARKET_DATA,
                "provider": config.MARKET_DATA_PROVIDER,
                "source_type": "live" if config.USE_LIVE_MARKET_DATA else "mock",
                "requires_secret": False,
            },
            "FRED": {
                "enabled": config.USE_LIVE_MACRO_DATA,
                "provider": config.MACRO_DATA_PROVIDER,
                "source_type": "live" if config.USE_LIVE_MACRO_DATA and bool(config.FRED_API_KEY) else "mock",
                "requires_secret": True,
                "credential_configured": bool(config.FRED_API_KEY),
            },
            "SEC EDGAR": {
                "enabled": config.USE_LIVE_SEC_FORM4,
                "provider": config.SEC_FORM4_PROVIDER,
                "source_type": "live" if config.USE_LIVE_SEC_FORM4 and bool(config.SEC_EDGAR_USER_AGENT) else "mock",
                "requires_secret": False,
                "user_agent_configured": bool(config.SEC_EDGAR_USER_AGENT),
                "cache_ttl_hours": config.SEC_FORM4_CACHE_TTL_HOURS,
                "lookback_days": config.SEC_FORM4_LOOKBACK_DAYS,
            },
            "mock sources": {
                "enabled": True,
                "provider": "phase1_mock_dataset",
                "source_type": "mock",
                "requires_secret": False,
            },
        },
        limitations=[
            "Provider health is configuration-level and does not expose credentials or SEC EDGAR User-Agent values.",
            "Daily reports are cache-first for SEC EDGAR Form 4 unless live fetch on report request is explicitly enabled.",
        ],
        missing_data=[],
    )


@router.get("/daily-report/latest", response_model=DailyResearchReport)
def latest_daily_report(use_live_market_data: bool | None = Query(default=None)) -> DailyResearchReport:
    if use_live_market_data is None:
        return _ensure_safe_response(build_daily_report())
    return _ensure_safe_response(build_daily_report(use_live_market_data=use_live_market_data))


@router.get("/daily-report/{report_date}", response_model=DailyResearchReport)
def daily_report_by_date(report_date: str) -> DailyResearchReport:
    report = build_daily_report()
    if report_date != report.date:
        raise HTTPException(status_code=404, detail="Mock report date is unavailable.")
    return report


@router.post("/analyze-stock", response_model=AnalyzeStockResponse)
def analyze_stock_endpoint(request: AnalyzeStockRequest) -> AnalyzeStockResponse:
    return _ensure_safe_response(analyze_stock(request))


@router.get("/themes/latest", response_model=ThemesLatestResponse)
def latest_themes() -> ThemesLatestResponse:
    report = build_daily_report()
    return ThemesLatestResponse(
        themes=report.future_themes,
        limitations=["Mock-only theme radar; live theme evidence is not connected."],
        missing_data=sorted({item for theme in report.future_themes for item in theme.missing_data}),
    )


@router.get("/macro-regime/latest", response_model=MacroRegimeOutput)
def latest_macro_regime() -> MacroRegimeOutput:
    return build_daily_report().macro_regime


@router.get("/raw-data/{ticker}", response_model=RawDataResponse)
def raw_data_by_ticker(ticker: str) -> RawDataResponse:
    normalized_ticker = ticker.strip().upper()
    fixture = STOCK_FIXTURES.get(normalized_ticker, DEFAULT_STOCK)
    market_snapshot = get_market_data(normalized_ticker)
    sec_filings = read_sec_filings(normalized_ticker)
    source_status = build_source_status(market_snapshot)
    form4_live = sec_filings.get("form4_source_status", {}).get("source_type") in {"live", "cached_live"}
    return RawDataResponse(
        ticker=normalized_ticker,
        raw_data={
            "company_fixture": fixture,
            "market_price_snapshot": market_snapshot,
            "sec_form4_snapshot": sec_filings.get("form4_snapshot", {}),
            "note": "Company fixture remains mock-only; market price and SEC Form 4 snapshots may be live when enabled.",
        },
        source=MOCK_SOURCE,
        source_date=MOCK_SOURCE_DATE,
        limitations=["Company fundamentals remain mock fixtures; live integrations currently cover market prices, FRED macro data, and opt-in SEC Form 4 only."],
        missing_data=[*([] if form4_live else ["live SEC filings"]), "live options feed"],
        source_status=source_status,
    )


@router.get("/signals/{ticker}", response_model=TickerSignalsResponse)
def ticker_signals(ticker: str) -> TickerSignalsResponse:
    analysis = analyze_stock(AnalyzeStockRequest(ticker=ticker))
    return TickerSignalsResponse(
        ticker=analysis.ticker,
        leadership_score=analysis.leadership_score,
        market_timing_context=analysis.market_timing_context,
        overheat_risk=analysis.overheat_risk,
        smart_money=analysis.smart_money,
        financial_quality=analysis.financial_quality,
        valuation_context=analysis.valuation_context,
        risk_flags=analysis.risk_flags,
        limitations=sorted(
            {
                *analysis.leadership_score.limitations,
                *analysis.market_timing_context.limitations,
                *analysis.overheat_risk.limitations,
                *analysis.smart_money.limitations,
                *analysis.financial_quality.limitations,
                *analysis.valuation_context.limitations,
            }
        ),
        missing_data=analysis.missing_data,
    )
