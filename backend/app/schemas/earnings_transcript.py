from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.schemas.common import DataSourceStatus


class TranscriptTheme(BaseModel):
    theme: str
    label: str
    evidence_snippets: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)
    affects_score: bool = False


class EarningsTranscriptDimension(BaseModel):
    label: str = "insufficient_data"
    confidence: float = Field(default=0, ge=0, le=1)
    evidence_snippets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    affects_score: bool = False


class EarningsTranscriptAnalysis(BaseModel):
    ticker: str
    provider: str = "fmp"
    source_status: DataSourceStatus = Field(default_factory=lambda: DataSourceStatus(provider="fmp", missing_data=["fmp_earnings_transcripts"]))
    quarters_analyzed: int = 0
    management_consistency: EarningsTranscriptDimension = Field(default_factory=EarningsTranscriptDimension)
    strategy_clarity: EarningsTranscriptDimension = Field(default_factory=EarningsTranscriptDimension)
    risk_acknowledgement: EarningsTranscriptDimension = Field(default_factory=EarningsTranscriptDimension)
    customer_demand_signal: EarningsTranscriptDimension = Field(default_factory=EarningsTranscriptDimension)
    margin_pressure_signal: EarningsTranscriptDimension = Field(default_factory=EarningsTranscriptDimension)
    capital_allocation_focus: EarningsTranscriptDimension = Field(default_factory=EarningsTranscriptDimension)
    positive_themes: list[TranscriptTheme] = Field(default_factory=list)
    risk_themes: list[TranscriptTheme] = Field(default_factory=list)
    manual_checks: list[str] = Field(default_factory=lambda: ["Review full transcript context before interpreting management claims."])
    limitations: list[str] = Field(default_factory=lambda: ["Earnings transcript analysis is research context only and may reflect management's own statements."])
    affects_score: bool = False
    not_investment_advice: bool = True


def disabled_earnings_transcript_analysis(ticker: str, reason: str = "FMP transcript provider is disabled.") -> EarningsTranscriptAnalysis:
    return EarningsTranscriptAnalysis(
        ticker=ticker.strip().upper(),
        source_status=DataSourceStatus(
            source_type="unknown",
            provider="fmp",
            source_date="",
            is_fresh=False,
            freshness_window="external_provider_cache",
            fallback_used=False,
            limitations=[reason],
            missing_data=["fmp_earnings_transcripts"],
        ),
        limitations=[reason, "Earnings transcript analysis is research context only and may reflect management's own statements."],
    )
