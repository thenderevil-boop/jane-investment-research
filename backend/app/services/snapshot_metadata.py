from __future__ import annotations

from copy import deepcopy

from backend.app import config
from backend.app.engines.macro_regime_engine import evaluate_macro_regime
from backend.app.schemas.daily_report import DailyReportMetadata, DailyResearchReport


def metadata_from_snapshot(snapshot: dict | None, *, snapshot_used: bool, snapshot_is_fresh: bool, status: str) -> DailyReportMetadata:
    existing = snapshot.get("daily_report_metadata") if isinstance(snapshot, dict) and isinstance(snapshot.get("daily_report_metadata"), dict) else {}
    return DailyReportMetadata(
        read_mode=config.DAILY_REPORT_READ_MODE,
        snapshot_used=snapshot_used,
        snapshot_id=(snapshot or {}).get("snapshot_id") or existing.get("snapshot_id"),
        snapshot_generated_at=(snapshot or {}).get("report_generated_at") or existing.get("snapshot_generated_at"),
        snapshot_is_fresh=snapshot_is_fresh,
        batch_refresh_status=(existing.get("batch_refresh_status") if snapshot_used else None) or status,
        batch_refresh_started_at=existing.get("batch_refresh_started_at"),
        batch_refresh_completed_at=existing.get("batch_refresh_completed_at") or (snapshot or {}).get("cached_at"),
        batch_duration_ms=existing.get("batch_duration_ms"),
        price_reference_warmup=existing.get("price_reference_warmup"),
    )


def ensure_macro_score_explanation(report: DailyResearchReport) -> None:
    macro = report.macro_regime
    if macro is None or macro.macro_score_explanation is not None:
        return
    try:
        refreshed = evaluate_macro_regime(macro.raw_data or {})
    except Exception:
        return
    if refreshed.macro_score_explanation is None:
        return
    explanation = deepcopy(refreshed.macro_score_explanation)
    explanation["score"] = macro.score
    explanation["label"] = macro.label
    explanation["confidence"] = macro.confidence
    if "confidence_explanation" in explanation:
        explanation["confidence_explanation"]["confidence"] = macro.confidence
    weighted_sum = float(explanation.get("weighted_contribution_sum") or 0)
    explanation["rounding_difference"] = round(float(macro.score) - weighted_sum, 4)
    macro.macro_score_explanation = explanation


def with_daily_report_metadata(report: DailyResearchReport, metadata: DailyReportMetadata) -> DailyResearchReport:
    ensure_macro_score_explanation(report)
    report.daily_report_metadata = metadata
    return report
