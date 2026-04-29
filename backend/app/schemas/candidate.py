from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.common import DataSourceStatus


class Candidate13FSpecificEvidence(BaseModel):
    ticker: str | None = None
    resolved_ticker: str | None = None
    resolved_cusip: str | None = None
    resolved_issuer_name: str | None = None
    local_security_map_used: bool | None = None
    matched_in_13f: bool | None = None
    match_confidence: str | None = None
    match_method: str | None = None
    position_value_usd: float | None = None
    position_shares_or_principal_amount: float | None = None
    portfolio_weight_pct: float | None = None
    latest_report_date: str | None = None
    latest_filing_date: str | None = None
    manager_cik: str | None = None
    manager_name: str | None = None
    interpretation_label: str | None = None


class Candidate13FPortfolioContext(BaseModel):
    manager_cik: str | None = None
    manager_name: str | None = None
    latest_report_date: str | None = None
    latest_filing_date: str | None = None
    holding_count_grouped: int | None = None
    mapped_holding_count: int | None = None
    top_holdings_by_value: list[dict[str, Any]] = Field(default_factory=list)
    source_status: DataSourceStatus | dict[str, Any] | None = None


class Candidate13FEvidence(BaseModel):
    source_status: DataSourceStatus | dict[str, Any] | None = None
    candidate_specific_evidence: Candidate13FSpecificEvidence | dict[str, Any] | None = None
    target_matches: list[dict[str, Any]] = Field(default_factory=list)
    portfolio_context: Candidate13FPortfolioContext | dict[str, Any] | None = None
    limitations: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)


class StockCandidate(BaseModel):
    ticker: str
    company_name: str
    theme: str
    leadership_score: float = Field(ge=0)
    smart_money_score: float = Field(ge=0, le=100)
    market_timing_score: float = Field(ge=0, le=100)
    overheat_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    label: str
    source: list[str]
    source_date: str
    confidence: float = Field(ge=0, le=1)
    limitations: list[str]
    missing_data: list[str]
    source_status: DataSourceStatus | None = None
    institutional_13f: Candidate13FEvidence | dict[str, Any] | None = None
