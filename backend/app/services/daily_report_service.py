from __future__ import annotations

from fastapi import HTTPException

from backend.app import config
from backend.app.raw_store.repository import is_daily_report_snapshot_fresh, read_daily_report_snapshot
from backend.app.schemas.daily_report import DailyReportMetadata, DailyResearchReport
from backend.app.services.snapshot_metadata import metadata_from_snapshot, with_daily_report_metadata


def latest_daily_report_response(
    *,
    use_live_market_data: bool | None,
    build_report,
) -> DailyResearchReport:
    if use_live_market_data is None and config.DAILY_REPORT_READ_MODE == "snapshot_first":
        snapshot = read_daily_report_snapshot()
        snapshot_fresh = is_daily_report_snapshot_fresh(snapshot)
        if snapshot_fresh:
            return with_daily_report_metadata(
                DailyResearchReport.model_validate(snapshot),
                metadata_from_snapshot(snapshot, snapshot_used=True, snapshot_is_fresh=True, status="completed"),
            )
        if not config.DAILY_BATCH_ALLOW_LIVE_FETCH:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "daily_report_snapshot_missing_or_stale",
                    "not_investment_advice": True,
                    "daily_report_metadata": metadata_from_snapshot(
                        snapshot,
                        snapshot_used=False,
                        snapshot_is_fresh=False,
                        status="fallback_compute_disabled",
                    ).model_dump(mode="json"),
                },
            )
        return with_daily_report_metadata(
            build_report(),
            metadata_from_snapshot(
                snapshot,
                snapshot_used=False,
                snapshot_is_fresh=False,
                status="computed_without_fresh_snapshot",
            ),
        )
    if use_live_market_data is None:
        return with_daily_report_metadata(
            build_report(),
            DailyReportMetadata(read_mode=config.DAILY_REPORT_READ_MODE, snapshot_used=False, batch_refresh_status="computed_without_snapshot_mode"),
        )
    return with_daily_report_metadata(
        build_report(use_live_market_data=use_live_market_data),
        DailyReportMetadata(read_mode="explicit_query", snapshot_used=False, batch_refresh_status="computed_from_explicit_query"),
    )
