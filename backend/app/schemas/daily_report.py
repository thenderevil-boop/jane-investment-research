from __future__ import annotations

from pydantic import BaseModel

from backend.app.schemas.candidate import StockCandidate
from backend.app.schemas.common import DataQualitySummary, DataSourceStatus, ScoreObject
from backend.app.schemas.crisis import CrisisOutput
from backend.app.schemas.future_theme import FutureTheme
from backend.app.schemas.macro_regime import MacroRegimeOutput
from backend.app.schemas.risk_allocation import RiskAllocationReference


class DailyReportMetadata(BaseModel):
    read_mode: str = "snapshot_first"
    snapshot_used: bool = False
    snapshot_id: str | None = None
    snapshot_generated_at: str | None = None
    snapshot_is_fresh: bool = False
    batch_refresh_status: str = "unknown"
    batch_refresh_started_at: str | None = None
    batch_refresh_completed_at: str | None = None
    batch_duration_ms: int | None = None


class DailyResearchReport(BaseModel):
    date: str
    market: str = "US"
    report_generated_at: str
    macro_regime: MacroRegimeOutput
    market_timing: ScoreObject
    overheat_risk: ScoreObject
    crisis_risk: ScoreObject
    crisis: CrisisOutput
    future_themes: list[FutureTheme]
    stock_candidates: list[StockCandidate]
    smart_money_summary: ScoreObject
    smart_money: ScoreObject
    risk_allocation: RiskAllocationReference
    risk_notes: list[str]
    limitations: list[str]
    missing_data: list[str]
    human_verification_queue: list[str]
    data_quality: DataQualitySummary | None = None
    source_status: DataSourceStatus | None = None
    daily_report_metadata: DailyReportMetadata | None = None
    performance_diagnostics: dict[str, int | float] | None = None
    not_investment_advice: bool = True
