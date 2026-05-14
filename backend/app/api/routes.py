from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app import config
from backend.app.data_sources.mock_data import DEFAULT_STOCK, MOCK_SOURCE, MOCK_SOURCE_DATE, STOCK_FIXTURES
from backend.app.engines.jane_criteria_canonical import JANE_CRITERIA
from backend.app.jobs.daily_research_refresh import refresh_daily_research_snapshot
from backend.app.middleware.safety_filter import SafetyViolationError, check_safety
from backend.app.pipelines.research_pipeline import build_daily_report
from backend.app.raw_store.repository import (
    create_manual_evidence,
    delete_manual_evidence,
    get_company_fundamentals,
    get_company_profile,
    get_market_data,
    get_manual_evidence,
    is_daily_report_snapshot_fresh,
    list_manual_evidence,
    read_daily_report_snapshot,
    read_sec_filings,
    update_manual_evidence,
    warm_price_reference_cache,
)
from backend.app.reports.stock_analysis import analyze_stock
from backend.app.schemas.daily_report import DailyReportMetadata, DailyResearchReport
from backend.app.schemas.health import HealthResponse
from backend.app.schemas.jane_criteria import JaneCriteriaResponse
from backend.app.schemas.macro_regime import MacroRegimeOutput
from backend.app.schemas.manual_evidence import ManualEvidenceQualityLabel, ManualEvidenceReviewStatus, ManualEvidenceCriterion, ManualQualitativeEvidence, ManualQualitativeEvidenceCreate, ManualQualitativeEvidencePatch
from backend.app.schemas.manual_evidence_dashboard import ManualEvidenceDashboardFilters, ManualEvidenceDashboardResponse
from backend.app.schemas.candidate_workspace import CandidateAnalysisHistoryItem, CandidateAnalyzeRequest, CandidateAnalyzeResponse, CandidateDashboardResponse, CandidatePriority, CandidateResearchItem, CandidateResearchItemCreate, CandidateResearchItemPatch, CandidateReviewNote, CandidateReviewNoteCreate, CandidateStatus
from backend.app.schemas.export import AnalyzeStockExportRequest, AnalyzeStockExportResponse, LocalBackupExportResponse
from backend.app.schemas.stock_analysis import AnalyzeStockRequest, AnalyzeStockResponse
from backend.app.schemas.supplemental import DataHealthResponse, PriceReferenceWarmupRequest, RawDataResponse, ThemesLatestResponse, TickerSignalsResponse
from backend.app.raw_store.candidate_workspace import CandidateWorkspaceStoreError
from backend.app.services.candidate_workspace import (
    add_candidate_note,
    analyze_candidate,
    archive_candidate_item,
    build_candidate_dashboard,
    create_candidate_item,
    get_candidate_item,
    list_candidate_analysis_history,
    list_candidate_items,
    list_candidate_notes,
    refresh_candidate_evidence_summary,
    restore_candidate_item,
    update_candidate_item,
)
from backend.app.services.daily_report_service import latest_daily_report_response
from backend.app.services.export_service import export_analyze_stock_report, export_local_backup
from backend.app.services.manual_evidence_dashboard import summarize_manual_evidence_dashboard
from backend.app.services.snapshot_metadata import (
    ensure_macro_score_explanation as _ensure_macro_score_explanation,
    metadata_from_snapshot as _metadata_from_snapshot,
    with_daily_report_metadata as _with_daily_report_metadata,
)
from backend.app.utils.freshness import build_source_status

router = APIRouter(prefix="/api")


def _model_dict(model: Any):
    if isinstance(model, BaseModel):
        return model.model_dump(mode="json")
    if isinstance(model, list):
        return [item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in model]
    return model


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
    return _ensure_safe_response(HealthResponse())


@router.get("/jane-criteria", response_model=JaneCriteriaResponse)
def jane_criteria() -> JaneCriteriaResponse:
    return _ensure_safe_response(JaneCriteriaResponse(criteria=JANE_CRITERIA, count=len(JANE_CRITERIA)))


@router.get("/data-health", response_model=DataHealthResponse)
def data_health() -> DataHealthResponse:
    return _ensure_safe_response(DataHealthResponse(
        providers={
            "yfinance": {
                "enabled": config.USE_LIVE_MARKET_DATA,
                "provider": config.MARKET_DATA_PROVIDER,
                "source_type": "live" if config.USE_LIVE_MARKET_DATA else "mock",
                "requires_secret": False,
            },
            "yfinance company data": {
                "enabled": config.USE_LIVE_COMPANY_DATA,
                "provider": config.COMPANY_DATA_PROVIDER,
                "source_type": "live" if config.USE_LIVE_COMPANY_DATA else "mock",
                "requires_secret": False,
            },
            "FRED": {
                "enabled": config.USE_LIVE_MACRO_DATA,
                "provider": config.MACRO_DATA_PROVIDER,
                "source_type": "live" if config.USE_LIVE_MACRO_DATA and config.is_fred_api_key_configured() else "mock",
                "requires_secret": True,
                "credential_configured": config.is_fred_api_key_configured(),
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
            "SEC EDGAR 13F": {
                "enabled": config.USE_LIVE_SEC_13F,
                "provider": config.SEC_13F_PROVIDER,
                "source_type": "live" if config.USE_LIVE_SEC_13F and bool(config.SEC_EDGAR_USER_AGENT) else "mock",
                "requires_secret": False,
                "user_agent_configured": bool(config.SEC_EDGAR_USER_AGENT),
                "cache_ttl_days": config.SEC_13F_CACHE_TTL_DAYS,
                "lookback_quarters": config.SEC_13F_LOOKBACK_QUARTERS,
                "freshness_window": "quarterly_filing_delay",
            },
            "SEC EDGAR Companyfacts": {
                "enabled": config.USE_LIVE_SEC_COMPANYFACTS,
                "provider": "SEC EDGAR companyfacts",
                "source_type": "live" if config.USE_LIVE_SEC_COMPANYFACTS and bool(config.SEC_EDGAR_USER_AGENT) else "mock",
                "requires_secret": False,
                "user_agent_configured": bool(config.SEC_EDGAR_USER_AGENT),
                "cache_ttl_days": config.SEC_COMPANYFACTS_CACHE_TTL_DAYS,
                "freshness_window": "latest_company_filing",
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
            "Daily reports are cache-first for SEC EDGAR Form 4 and 13F unless live fetch on report request is explicitly enabled.",
        ],
        missing_data=[],
    ))


@router.get("/daily-report/latest", response_model=DailyResearchReport)
def latest_daily_report(use_live_market_data: bool | None = Query(default=None)) -> DailyResearchReport:
    return _ensure_safe_response(latest_daily_report_response(use_live_market_data=use_live_market_data, build_report=build_daily_report))


@router.post("/jobs/daily-research-refresh")
def daily_research_refresh_job() -> dict:
    return _ensure_safe_response(refresh_daily_research_snapshot())


@router.post("/price-reference/warmup")
def price_reference_warmup(payload: PriceReferenceWarmupRequest) -> dict:
    max_tickers = payload.max_tickers or config.PRICE_REFERENCE_CACHE_WARMUP_MAX_TICKERS
    result = warm_price_reference_cache(payload.tickers, max_tickers=max_tickers, allow_live_fetch=payload.allow_live_fetch)
    return _ensure_safe_response({"not_investment_advice": True, **result})


@router.get("/daily-report/{report_date}", response_model=DailyResearchReport)
def daily_report_by_date(report_date: str) -> DailyResearchReport:
    snapshot = read_daily_report_snapshot(report_date)
    if snapshot:
        return _ensure_safe_response(
            _with_daily_report_metadata(
                DailyResearchReport.model_validate(snapshot),
                _metadata_from_snapshot(
                    snapshot,
                    snapshot_used=True,
                    snapshot_is_fresh=is_daily_report_snapshot_fresh(snapshot),
                    status="completed",
                ),
            )
        )
    report = build_daily_report()
    if report_date != report.date:
        raise HTTPException(status_code=404, detail="Mock report date is unavailable.")
    return _ensure_safe_response(report)


@router.post("/analyze-stock", response_model=AnalyzeStockResponse)
def analyze_stock_endpoint(request: AnalyzeStockRequest) -> AnalyzeStockResponse:
    return _ensure_safe_response(analyze_stock(request))


@router.post("/analyze-stock/export", response_model=AnalyzeStockExportResponse)
def analyze_stock_export_endpoint(request: AnalyzeStockExportRequest) -> AnalyzeStockExportResponse:
    return _ensure_safe_response(export_analyze_stock_report(request))


@router.get("/local-backup/export", response_model=LocalBackupExportResponse)
def local_backup_export_endpoint(
    include_manual_evidence: bool = Query(default=True),
    include_candidate_workspace: bool = Query(default=True),
    include_evidence_dashboard: bool = Query(default=True),
    include_archived: bool = Query(default=True),
    include_rejected: bool = Query(default=True),
    format: str = Query(default="json"),
) -> LocalBackupExportResponse:
    if format != "json":
        raise HTTPException(status_code=422, detail={"error": "Only json backup export format is supported.", "not_investment_advice": True})
    return _ensure_safe_response(export_local_backup(
        include_manual_evidence=include_manual_evidence,
        include_candidate_workspace=include_candidate_workspace,
        include_evidence_dashboard=include_evidence_dashboard,
        include_archived=include_archived,
        include_rejected=include_rejected,
    ))


@router.get("/candidates/dashboard", response_model=CandidateDashboardResponse)
def candidates_dashboard(include_archived: bool = Query(default=False)) -> CandidateDashboardResponse:
    try:
        return _ensure_safe_response(build_candidate_dashboard(include_archived=include_archived))
    except CandidateWorkspaceStoreError as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc), "not_investment_advice": True}) from exc


@router.get("/candidates", response_model=list[CandidateResearchItem])
def candidates_list(
    include_archived: bool = Query(default=False),
    ticker: str | None = Query(default=None),
    status: CandidateStatus | None = Query(default=None),
    priority: CandidatePriority | None = Query(default=None),
    tag: str | None = Query(default=None),
    stale_evidence_only: bool = Query(default=False),
    needs_review_only: bool = Query(default=False),
    has_comparison_evidence: bool | None = Query(default=None),
    missing_criterion: str | None = Query(default=None),
    data_quality_grade: str | None = Query(default=None),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
) -> list[CandidateResearchItem]:
    try:
        return _ensure_safe_response(list_candidate_items(
            include_archived=include_archived,
            ticker=ticker,
            status=status,
            priority=priority,
            tag=tag,
            stale_evidence_only=stale_evidence_only,
            needs_review_only=needs_review_only,
            has_comparison_evidence=has_comparison_evidence,
            missing_criterion=missing_criterion,
            data_quality_grade=data_quality_grade,
            sort_by=sort_by,
            sort_order=sort_order,
        ))
    except CandidateWorkspaceStoreError as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc), "not_investment_advice": True}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc), "not_investment_advice": True}) from exc


@router.get("/candidates/{candidate_id}", response_model=CandidateResearchItem)
def candidates_get(candidate_id: str) -> CandidateResearchItem:
    item = get_candidate_item(candidate_id)
    if not item:
        raise HTTPException(status_code=404, detail="Candidate item not found")
    return _ensure_safe_response(item)


@router.post("/candidates", response_model=CandidateResearchItem)
def candidates_create(payload: CandidateResearchItemCreate) -> CandidateResearchItem:
    try:
        return _ensure_safe_response(create_candidate_item(payload))
    except CandidateWorkspaceStoreError as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc), "not_investment_advice": True}) from exc


@router.patch("/candidates/{candidate_id}", response_model=CandidateResearchItem)
def candidates_patch(candidate_id: str, payload: CandidateResearchItemPatch) -> CandidateResearchItem:
    try:
        item = update_candidate_item(candidate_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc), "not_investment_advice": True}) from exc
    if not item:
        raise HTTPException(status_code=404, detail="Candidate item not found")
    return _ensure_safe_response(item)


@router.delete("/candidates/{candidate_id}", response_model=CandidateResearchItem)
def candidates_archive(candidate_id: str) -> CandidateResearchItem:
    item = archive_candidate_item(candidate_id)
    if not item:
        raise HTTPException(status_code=404, detail="Candidate item not found")
    return _ensure_safe_response(item)


@router.post("/candidates/{candidate_id}/restore", response_model=CandidateResearchItem)
def candidates_restore(candidate_id: str) -> CandidateResearchItem:
    item = restore_candidate_item(candidate_id)
    if not item:
        raise HTTPException(status_code=404, detail="Candidate item not found")
    return _ensure_safe_response(item)


@router.post("/candidates/{candidate_id}/notes", response_model=CandidateReviewNote)
def candidates_add_note(candidate_id: str, payload: CandidateReviewNoteCreate) -> CandidateReviewNote:
    note = add_candidate_note(candidate_id, payload)
    if not note:
        raise HTTPException(status_code=404, detail="Candidate item not found")
    return _ensure_safe_response(note)


@router.get("/candidates/{candidate_id}/notes", response_model=list[CandidateReviewNote])
def candidates_notes(candidate_id: str) -> list[CandidateReviewNote]:
    notes = list_candidate_notes(candidate_id)
    if notes is None:
        raise HTTPException(status_code=404, detail="Candidate item not found")
    return _ensure_safe_response(notes)


@router.get("/candidates/{candidate_id}/analysis-history", response_model=list[CandidateAnalysisHistoryItem])
def candidates_analysis_history(candidate_id: str) -> list[CandidateAnalysisHistoryItem]:
    history = list_candidate_analysis_history(candidate_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Candidate item not found")
    return _ensure_safe_response(history)


@router.post("/candidates/{candidate_id}/refresh-evidence-summary", response_model=CandidateResearchItem)
def candidates_refresh_evidence(candidate_id: str) -> CandidateResearchItem:
    item = refresh_candidate_evidence_summary(candidate_id)
    if not item:
        raise HTTPException(status_code=404, detail="Candidate item not found")
    return _ensure_safe_response(item)


@router.post("/candidates/{candidate_id}/analyze", response_model=CandidateAnalyzeResponse)
def candidates_analyze(candidate_id: str, payload: CandidateAnalyzeRequest) -> CandidateAnalyzeResponse:
    result = analyze_candidate(candidate_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Candidate item not found")
    return _ensure_safe_response(result)


def _filter_manual_evidence_rows(rows: list[dict], review_status: str | None = None, criterion: str | None = None, stale: bool | None = None) -> list[dict]:
    filtered = rows
    if review_status:
        filtered = [item for item in filtered if item.get("review_status") == review_status]
    if criterion:
        filtered = [item for item in filtered if item.get("criterion") == criterion]
    if stale is not None:
        filtered = [item for item in filtered if bool(item.get("is_stale")) is stale]
    return filtered


@router.get("/manual-evidence/dashboard", response_model=ManualEvidenceDashboardResponse)
def manual_evidence_dashboard(
    ticker: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    include_rejected: bool = Query(default=False),
    review_status: ManualEvidenceReviewStatus | None = Query(default=None),
    criterion: ManualEvidenceCriterion | None = Query(default=None),
    stale_only: bool = Query(default=False),
    review_due_only: bool = Query(default=False),
    has_comparison_context: bool | None = Query(default=None),
    min_quality_label: ManualEvidenceQualityLabel | None = Query(default=None),
) -> ManualEvidenceDashboardResponse:
    filters = ManualEvidenceDashboardFilters(
        ticker=ticker.strip().upper() if ticker else None,
        include_archived=include_archived,
        include_rejected=include_rejected,
        review_status=review_status,
        criterion=criterion,
        stale_only=stale_only,
        review_due_only=review_due_only,
        has_comparison_context=has_comparison_context,
        min_quality_label=min_quality_label,
    )
    return _ensure_safe_response(summarize_manual_evidence_dashboard(filters))


@router.get("/manual-evidence", response_model=list[ManualQualitativeEvidence])
def manual_evidence_list(
    ticker: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    criterion: str | None = Query(default=None),
    stale: bool | None = Query(default=None),
) -> list[ManualQualitativeEvidence]:
    rows = list_manual_evidence(ticker.strip().upper() if ticker else None)
    rows = _filter_manual_evidence_rows(rows, review_status=review_status, criterion=criterion, stale=stale)
    return _ensure_safe_response([ManualQualitativeEvidence.model_validate(row) for row in rows])


@router.get("/manual-evidence/by-ticker/{ticker}", response_model=list[ManualQualitativeEvidence])
def manual_evidence_by_ticker(ticker: str) -> list[ManualQualitativeEvidence]:
    rows = list_manual_evidence(ticker.strip().upper())
    return _ensure_safe_response([ManualQualitativeEvidence.model_validate(row) for row in rows])


@router.get("/manual-evidence/{evidence_id}", response_model=ManualQualitativeEvidence)
def manual_evidence_get(evidence_id: str) -> ManualQualitativeEvidence:
    row = get_manual_evidence(evidence_id)
    if not row:
        raise HTTPException(status_code=404, detail="Manual evidence item not found")
    return _ensure_safe_response(ManualQualitativeEvidence.model_validate(row))


@router.post("/manual-evidence", response_model=ManualQualitativeEvidence)
def manual_evidence_create(payload: ManualQualitativeEvidenceCreate) -> ManualQualitativeEvidence:
    created = ManualQualitativeEvidence.model_validate(payload.model_dump(mode="json"))
    row = create_manual_evidence(created)
    return _ensure_safe_response(ManualQualitativeEvidence.model_validate(row))


@router.patch("/manual-evidence", include_in_schema=False)
def manual_evidence_patch_missing_id() -> None:
    raise HTTPException(status_code=400, detail="evidence_id path segment is required for manual evidence PATCH")


@router.patch("/manual-evidence/{evidence_id}", response_model=ManualQualitativeEvidence)
def manual_evidence_patch(evidence_id: str, payload: ManualQualitativeEvidencePatch) -> ManualQualitativeEvidence:
    row = update_manual_evidence(evidence_id, payload)
    if not row:
        raise HTTPException(status_code=404, detail="Manual evidence item not found")
    return _ensure_safe_response(ManualQualitativeEvidence.model_validate(row))


@router.delete("/manual-evidence/{evidence_id}", response_model=ManualQualitativeEvidence)
def manual_evidence_delete(evidence_id: str) -> ManualQualitativeEvidence:
    row = delete_manual_evidence(evidence_id)
    if not row:
        raise HTTPException(status_code=404, detail="Manual evidence item not found")
    return _ensure_safe_response(ManualQualitativeEvidence.model_validate(row))


@router.get("/themes/latest", response_model=ThemesLatestResponse)
def latest_themes() -> ThemesLatestResponse:
    report = latest_daily_report_response(use_live_market_data=None, build_report=build_daily_report)
    return _ensure_safe_response(ThemesLatestResponse(
        themes=report.future_themes,
        limitations=["Mock-only theme radar; live theme evidence is not connected."],
        missing_data=sorted({item for theme in report.future_themes for item in theme.missing_data}),
    ))


@router.get("/macro-regime/latest", response_model=MacroRegimeOutput)
def latest_macro_regime() -> MacroRegimeOutput:
    report = latest_daily_report_response(use_live_market_data=None, build_report=build_daily_report)
    return _ensure_safe_response(report.macro_regime)


@router.get("/raw-data/{ticker}", response_model=RawDataResponse)
def raw_data_by_ticker(ticker: str) -> RawDataResponse:
    normalized_ticker = ticker.strip().upper()
    fixture = STOCK_FIXTURES.get(normalized_ticker, DEFAULT_STOCK)
    market_snapshot = get_market_data(normalized_ticker)
    company_profile = get_company_profile(normalized_ticker)
    company_fundamentals = get_company_fundamentals(normalized_ticker)
    from backend.app.raw_store.repository import get_sec_companyfacts
    sec_companyfacts = get_sec_companyfacts(normalized_ticker)
    sec_filings = read_sec_filings(normalized_ticker)
    source_status = build_source_status(market_snapshot)
    form4_live = sec_filings.get("form4_source_status", {}).get("source_type") in {"live", "cached_live"}
    thirteen_f_live = sec_filings.get("institutional_13f_source_status", {}).get("source_type") in {"live", "cached_live"}
    return _ensure_safe_response(RawDataResponse(
        ticker=normalized_ticker,
        raw_data={
            "company_fixture": fixture,
            "company_profile_snapshot": company_profile,
            "company_fundamentals_snapshot": company_fundamentals,
            "sec_companyfacts_snapshot": sec_companyfacts,
            "market_price_snapshot": market_snapshot,
            "sec_form4_snapshot": sec_filings.get("form4_snapshot", {}),
            "sec_13f_snapshot": sec_filings.get("institutional_13f_snapshot", {}),
            "note": "Company profile, company fundamentals, SEC Companyfacts, market price, SEC Form 4, and SEC 13F snapshots may be live when enabled.",
        },
        source=MOCK_SOURCE,
        source_date=MOCK_SOURCE_DATE,
        limitations=["Company profile and fundamentals may use yfinance when enabled; live integrations also cover market prices, FRED macro data, opt-in SEC Form 4, and opt-in SEC 13F."],
        missing_data=[*([] if form4_live and thirteen_f_live else ["live SEC filings"]), "live options feed"],
        source_status=source_status,
    ))


@router.get("/signals/{ticker}", response_model=TickerSignalsResponse)
def ticker_signals(ticker: str) -> TickerSignalsResponse:
    analysis = analyze_stock(AnalyzeStockRequest(ticker=ticker))
    return _ensure_safe_response(TickerSignalsResponse(
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
    ))
