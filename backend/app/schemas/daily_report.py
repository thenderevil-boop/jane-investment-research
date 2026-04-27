from __future__ import annotations

from pydantic import BaseModel

from backend.app.schemas.candidate import StockCandidate
from backend.app.schemas.common import DataQualitySummary, ScoreObject
from backend.app.schemas.crisis import CrisisOutput
from backend.app.schemas.future_theme import FutureTheme
from backend.app.schemas.macro_regime import MacroRegimeOutput
from backend.app.schemas.risk_allocation import RiskAllocationReference


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
    not_investment_advice: bool = True
