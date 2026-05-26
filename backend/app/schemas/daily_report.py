from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.candidate import StockCandidate
from backend.app.schemas.common import DataQualitySummary, DataSourceStatus, HumanVerificationQueueItem, ScoreObject
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
    price_reference_warmup: dict | None = None


class JaneReferenceCondition(BaseModel):
    name: str
    display_text: str
    system_status: str
    mapped_system_fields: list[str]
    score_contribution_allowed: bool = False
    limitation: str | None = None


class JaneReferenceConditions(BaseModel):
    title: str = "Jane methodology reference conditions"
    source_type: str = "methodology_reference"
    affects_score: bool = False
    not_investment_advice: bool = True
    conditions: list[JaneReferenceCondition]
    limitations: list[str]


class TodayResearchAction(BaseModel):
    priority: Literal["high", "medium", "low"]
    ticker: str | None = None
    action_type: Literal["source_setup", "evidence_review", "coverage_gap", "watchlist_change", "macro_context"]
    title: str
    reason: str
    source: Literal["existing_data"] = "existing_data"
    affects_score: bool = False
    not_investment_advice: bool = True


class DailyMacroDelta(BaseModel):
    version: Literal["phase61_macro_delta_v1"] = "phase61_macro_delta_v1"
    previous_report_date: str | None = None
    macro_score_change: float | None = None
    vix_change: float | None = None
    yield_curve_10y2y_spread_change_bps: float | None = None
    latest_inflation_observations: list[dict[str, float | str | None]] = Field(default_factory=list)
    source: Literal["daily_report_snapshot_compare"] = "daily_report_snapshot_compare"
    limitations: list[str] = Field(default_factory=list)
    not_investment_advice: bool = True


class DailyWatchlistDeltaItem(BaseModel):
    ticker: str
    price_change_pct: float | None = None
    overheat_score_change: float | None = None
    new_form4_count: int | None = None
    institutional_13f_status: str = "unknown"
    data_issue: str | None = None
    source: Literal["daily_report_snapshot_compare"] = "daily_report_snapshot_compare"
    not_investment_advice: bool = True


class DailyWatchlistDelta(BaseModel):
    version: Literal["phase61_watchlist_delta_v1"] = "phase61_watchlist_delta_v1"
    previous_report_date: str | None = None
    items: list[DailyWatchlistDeltaItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    not_investment_advice: bool = True


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
    jane_reference_conditions: JaneReferenceConditions | None = None
    limitations: list[str]
    missing_data: list[str]
    human_verification_queue: list[str | HumanVerificationQueueItem]
    today_research_actions: list[TodayResearchAction] = Field(default_factory=list)
    macro_delta: DailyMacroDelta | None = None
    watchlist_delta: DailyWatchlistDelta | None = None
    data_quality: DataQualitySummary | None = None
    source_status: DataSourceStatus | None = None
    daily_report_metadata: DailyReportMetadata | None = None
    performance_diagnostics: dict[str, int | float] | None = None
    not_investment_advice: bool = True
