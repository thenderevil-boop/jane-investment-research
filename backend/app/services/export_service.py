from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.raw_store.candidate_workspace import list_candidate_items as list_candidate_store_items
from backend.app.raw_store.manual_evidence import list_all_manual_evidence
from backend.app.reports.stock_analysis import analyze_stock
from backend.app.schemas.common import DataSourceStatus
from backend.app.schemas.export import (
    AnalyzeStockExportRequest,
    AnalyzeStockExportResponse,
    LocalBackupExportResponse,
    LocalBackupMetadata,
)
from backend.app.schemas.manual_evidence_dashboard import ManualEvidenceDashboardFilters
from backend.app.services.candidate_workspace import build_candidate_dashboard, list_candidate_items
from backend.app.services.manual_evidence_dashboard import summarize_manual_evidence_dashboard
from backend.app.utils.redaction import redact_sensitive_fields


EXPORT_LIMITATIONS = [
    "Research reference only. Not investment advice.",
    "User-provided qualitative evidence is not independently verified.",
    "Candidate Workspace metadata does not affect scoring.",
    "Export does not change analyze-stock scoring.",
    "Request-scoped qualitative evidence is not persisted by export.",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(now: datetime) -> str:
    return now.isoformat().replace("+00:00", "Z")


def _filename_timestamp(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H%M%SZ")


def _safe_filename_part(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.upper())
    return cleaned.strip("-")[:24] or "UNKNOWN"


def _as_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _manual_assessment(analysis: dict[str, Any], include_manual_evidence: bool) -> dict[str, Any]:
    assessment = dict(analysis.get("qualitative_evidence_assessment") or {})
    if not include_manual_evidence:
        assessment["evidence_items"] = []
        assessment["limitations"] = sorted({
            *assessment.get("limitations", []),
            "Manual evidence item details omitted by export option.",
        })
    return assessment


def _raw_evidence(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_profile": analysis.get("company_profile"),
        "macro_regime": analysis.get("macro_regime"),
        "leadership_score": analysis.get("leadership_score"),
        "jane_company_quality": analysis.get("jane_company_quality"),
        "financial_statement_signals": analysis.get("financial_statement_signals"),
        "sec_financial_facts": analysis.get("sec_financial_facts"),
        "fundamentals_cross_check": analysis.get("fundamentals_cross_check"),
        "smart_money": analysis.get("smart_money"),
        "insider_activity": analysis.get("insider_activity"),
        "institutional_13f": analysis.get("institutional_13f"),
        "financial_quality": analysis.get("financial_quality"),
        "valuation_context": analysis.get("valuation_context"),
        "data_quality": analysis.get("data_quality"),
        "source_status": analysis.get("source_status"),
    }


def _candidate_metadata_for_ticker(ticker: str) -> list[dict[str, Any]]:
    try:
        return [
            item.model_dump(mode="json")
            for item in list_candidate_items(include_archived=True, ticker=ticker)
        ]
    except Exception:
        return []


def _build_json_report(request: AnalyzeStockExportRequest, analysis: dict[str, Any], generated_at: str) -> dict[str, Any]:
    summary = analysis.get("candidate_validation_summary") or {}
    verdict = analysis.get("research_verdict") or {}
    report: dict[str, Any] = {
        "export_metadata": {
            "export_id": "",
            "generated_at": generated_at,
            "format": "json",
            "schema_version": "phase25_validation_export_v1",
            "ticker": analysis.get("ticker"),
            "market": analysis.get("market", "US"),
            "not_investment_advice": True,
            "limitations": EXPORT_LIMITATIONS,
        },
        "validation_summary": {
            "ticker": analysis.get("ticker"),
            "score": verdict.get("score"),
            "max_score": 100,
            "label": verdict.get("label"),
            "confidence": verdict.get("confidence"),
            "data_quality_grade": (analysis.get("data_quality_summary") or {}).get("source_quality_grade"),
            "validation_summary": summary.get("overall_summary") or verdict.get("summary"),
            "primary_strengths": summary.get("primary_strengths", []),
            "primary_risks": summary.get("primary_risks", []),
        },
        "data_quality_summary": analysis.get("data_quality_summary"),
        "macro_context": analysis.get("macro_regime"),
        "company_quality": analysis.get("jane_company_quality"),
        "financial_statement_signals": analysis.get("financial_statement_signals"),
        "sec_financial_facts": analysis.get("sec_financial_facts"),
        "fundamentals_cross_check": analysis.get("fundamentals_cross_check"),
        "smart_money": analysis.get("smart_money"),
        "qualitative_evidence_assessment": _manual_assessment(analysis, request.include_manual_evidence),
        "comparison_evidence_assessment": analysis.get("comparison_evidence_assessment"),
        "evidence_matrix": analysis.get("evidence_matrix", []),
        "score_driver_breakdown": analysis.get("score_driver_breakdown"),
        "next_manual_checks": analysis.get("next_manual_checks", []),
        "risk_flags": analysis.get("risk_flags", []),
        "missing_data": analysis.get("missing_data", []),
        "source_limitations": sorted({
            *analysis.get("missing_data", []),
            *sum([row.get("limitations", []) for row in analysis.get("evidence_matrix", []) if isinstance(row, dict)], []),
        }),
    }
    if request.include_candidate_metadata:
        report["candidate_metadata"] = _candidate_metadata_for_ticker(str(analysis.get("ticker") or request.ticker))
    if request.include_raw_evidence:
        report["raw_evidence"] = _raw_evidence(analysis)
    return report


def _bullet_list(values: list[Any]) -> str:
    if not values:
        return "- None listed"
    lines = []
    for value in values:
        if isinstance(value, dict):
            text = value.get("check") or value.get("summary") or value.get("name") or str(value)
        else:
            text = str(value)
        lines.append(f"- {text}")
    return "\n".join(lines)


def _markdown_report(request: AnalyzeStockExportRequest, analysis: dict[str, Any], generated_at: str) -> str:
    ticker = str(analysis.get("ticker") or request.ticker).upper()
    verdict = analysis.get("research_verdict") or {}
    summary = analysis.get("candidate_validation_summary") or {}
    dq = analysis.get("data_quality_summary") or {}
    context = request.research_context.model_dump(mode="json") if request.research_context else {}
    evidence_rows = analysis.get("evidence_matrix") or []
    drivers = analysis.get("score_driver_breakdown") or {}
    positive = drivers.get("positive_drivers", [])
    limiting = drivers.get("negative_or_limiting_drivers", [])
    neutral = drivers.get("neutral_drivers", [])
    return "\n\n".join([
        f"# Ticker Validation Report: {ticker}",
        f"Generated at: {generated_at}\n\nResearch reference only. Not investment advice.",
        "## Validation Summary\n"
        f"- Score: {verdict.get('score', 'N/A')} / 100\n"
        f"- Label: {verdict.get('label', 'N/A')}\n"
        f"- Confidence: {verdict.get('confidence', 'N/A')}\n"
        f"- Data quality grade: {dq.get('source_quality_grade', 'N/A')}\n"
        f"- Summary: {summary.get('overall_summary') or verdict.get('summary', 'N/A')}",
        "## Thesis Context\n"
        f"- Theme: {context.get('theme') or 'N/A'}\n"
        f"- User reason: {context.get('user_reason') or 'N/A'}",
        "## Primary Strengths\n" + _bullet_list(summary.get("primary_strengths", [])),
        "## Primary Risks / Limits\n" + _bullet_list(summary.get("primary_risks", [])),
        "## Data Quality\n"
        f"- Grade: {dq.get('source_quality_grade', 'N/A')}\n"
        f"- Mode: {dq.get('mode', 'N/A')}\n"
        f"- Summary: {dq.get('source_quality_summary', 'N/A')}\n"
        f"- Missing or insufficient categories: {', '.join(dq.get('insufficient_evidence_categories', []) or []) or 'None listed'}",
        "## Macro Context\n"
        f"- Label: {(analysis.get('macro_regime') or {}).get('label', 'N/A')}\n"
        f"- Score: {(analysis.get('macro_regime') or {}).get('score', 'N/A')}\n"
        f"- Limitations: {' '.join((analysis.get('macro_regime') or {}).get('limitations', []) or []) or 'None listed'}",
        "## Jane Company Quality\n"
        f"- Label: {(analysis.get('jane_company_quality') or {}).get('label', 'N/A')}\n"
        f"- Score: {(analysis.get('jane_company_quality') or {}).get('score', 'N/A')}\n"
        f"- Missing data: {', '.join((analysis.get('jane_company_quality') or {}).get('missing_data', []) or []) or 'None listed'}",
        "## Financial Statement Signals\n"
        f"- Label: {(analysis.get('financial_statement_signals') or {}).get('label', 'N/A')}\n"
        f"- Score: {(analysis.get('financial_statement_signals') or {}).get('score', 'N/A')}\n"
        f"- Missing data: {', '.join((analysis.get('financial_statement_signals') or {}).get('missing_data', []) or []) or 'None listed'}",
        "## SEC Financial Facts\n"
        f"- Source type: {(((analysis.get('sec_financial_facts') or {}).get('source_status') or {}).get('source_type')) or 'N/A'}\n"
        f"- Missing data: {', '.join((analysis.get('sec_financial_facts') or {}).get('missing_data', []) or []) or 'None listed'}",
        "## Fundamentals Cross-Check\n"
        f"- Agreement: {(analysis.get('fundamentals_cross_check') or {}).get('agreement_level', 'N/A')}\n"
        f"- Summary: {(analysis.get('fundamentals_cross_check') or {}).get('summary', 'N/A')}",
        "## Smart Money\n"
        f"- Label: {(analysis.get('smart_money') or {}).get('label', 'N/A')}\n"
        f"- Score: {(analysis.get('smart_money') or {}).get('score', 'N/A')}\n"
        f"- Limitations: {' '.join((analysis.get('smart_money') or {}).get('limitations', []) or []) or 'None listed'}",
        "## Qualitative Evidence\n"
        f"- Accepted: {(analysis.get('qualitative_evidence_assessment') or {}).get('accepted_evidence_count', 0)}\n"
        "- Manual evidence remains user_provided and is not independently verified.",
        "## Comparison Evidence\n"
        f"- Accepted: {(analysis.get('comparison_evidence_assessment') or {}).get('accepted_comparison_count', 0)}\n"
        "- Peer and advantage claims are user_provided metadata requiring manual validation.",
        "## Evidence Matrix\n" + _bullet_list([
            f"{row.get('category')}: {row.get('status')} ({row.get('source_quality')}) - {row.get('summary')}"
            for row in evidence_rows
        ]),
        "## Score Driver Breakdown\n"
        "Positive drivers:\n" + _bullet_list([item.get("summary") for item in positive]) + "\n\n"
        "Limiting drivers:\n" + _bullet_list([item.get("summary") for item in limiting]) + "\n\n"
        "Neutral drivers:\n" + _bullet_list([item.get("summary") for item in neutral]),
        "## Next Manual Checks\n" + _bullet_list(analysis.get("next_manual_checks", [])),
        "## Limitations\n" + _bullet_list(EXPORT_LIMITATIONS + (analysis.get("missing_data") or [])),
    ])


def export_analyze_stock_report(request: AnalyzeStockExportRequest) -> AnalyzeStockExportResponse:
    now = _utc_now()
    generated_at = _utc_iso(now)
    analysis_model = analyze_stock(request)
    analysis = analysis_model.model_dump(mode="json")
    report: dict[str, Any] | str
    content_type = "application/json" if request.format == "json" else "text/markdown"
    ext = "json" if request.format == "json" else "md"
    filename = f"jane-validation-{_safe_filename_part(analysis_model.ticker)}-{_filename_timestamp(now)}.{ext}"
    if request.format == "json":
        report = _build_json_report(request, analysis, generated_at)
    else:
        report = _markdown_report(request, analysis, generated_at)
    response = AnalyzeStockExportResponse(
        generated_at=generated_at,
        ticker=analysis_model.ticker,
        format=request.format,
        filename=filename,
        content_type=content_type,
        report=report,
        source_status=DataSourceStatus(
            source_type="derived",
            provider="analyze_stock_export",
            source_date=generated_at,
            fetched_at=generated_at,
            is_fresh=True,
            freshness_window="export_generated_at",
            fallback_used=False,
            limitations=EXPORT_LIMITATIONS,
            missing_data=[],
        ),
    )
    if isinstance(response.report, dict):
        response.report["export_metadata"]["export_id"] = response.export_id
    payload = response.model_dump(mode="json")
    if request.redact_sensitive_fields:
        payload = redact_sensitive_fields(payload)
    return AnalyzeStockExportResponse.model_validate(payload)


def export_local_backup(
    *,
    include_manual_evidence: bool = True,
    include_candidate_workspace: bool = True,
    include_evidence_dashboard: bool = True,
    include_archived: bool = True,
    include_rejected: bool = True,
) -> LocalBackupExportResponse:
    now = _utc_now()
    generated_at = _utc_iso(now)
    response = LocalBackupExportResponse(
        backup_metadata=LocalBackupMetadata(generated_at=generated_at),
        source_status=DataSourceStatus(
            source_type="derived",
            provider="local_backup_export",
            source_date=generated_at,
            fetched_at=generated_at,
            is_fresh=True,
            freshness_window="local_export_generated_at",
            fallback_used=False,
            limitations=[
                "Local backup reads local stores only.",
                "Provider caches and runtime files are not included.",
                "Import or restore is not implemented in Phase 25.",
            ],
            missing_data=[],
        ),
    )
    if include_manual_evidence:
        manual_items = list_all_manual_evidence(include_archived=include_archived, include_rejected=include_rejected)
        manual_payload: dict[str, Any] = {"items": manual_items}
        if include_evidence_dashboard:
            manual_payload["dashboard_summary"] = summarize_manual_evidence_dashboard(
                ManualEvidenceDashboardFilters(
                    include_archived=include_archived,
                    include_rejected=include_rejected,
                )
            ).model_dump(mode="json")
        response.manual_evidence = manual_payload
    if include_candidate_workspace:
        candidate_items = list_candidate_store_items(include_archived=include_archived)
        candidate_payload: dict[str, Any] = {"items": candidate_items}
        if include_evidence_dashboard:
            candidate_payload["dashboard_summary"] = build_candidate_dashboard(include_archived=include_archived).model_dump(mode="json")
        response.candidate_workspace = candidate_payload
    return LocalBackupExportResponse.model_validate(redact_sensitive_fields(response.model_dump(mode="json")))
