from __future__ import annotations

from dataclasses import dataclass

from backend.app import config


SAFE_DEFAULT_DAILY_CANDIDATES = "NVDA:AI energy infrastructure,TSLA:humanoid robotics"


@dataclass(frozen=True)
class DailyReportCandidate:
    ticker: str
    theme: str


def parse_daily_report_candidates(raw_value: str | None) -> tuple[list[DailyReportCandidate], list[str]]:
    raw = (raw_value or "").strip()
    if not raw:
        raw = SAFE_DEFAULT_DAILY_CANDIDATES
    candidates: list[DailyReportCandidate] = []
    warnings: list[str] = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        if ":" not in text:
            warnings.append("Invalid daily candidate entry omitted; expected TICKER:theme.")
            continue
        ticker, theme = [part.strip() for part in text.split(":", 1)]
        normalized = ticker.upper()
        if not normalized or not theme:
            warnings.append("Invalid daily candidate entry omitted; expected non-empty ticker and theme.")
            continue
        if not normalized.replace(".", "").replace("-", "").isalnum():
            warnings.append("Invalid daily candidate ticker omitted.")
            continue
        if normalized not in [candidate.ticker for candidate in candidates]:
            candidates.append(DailyReportCandidate(ticker=normalized, theme=theme))
    if not candidates:
        return parse_daily_report_candidates(SAFE_DEFAULT_DAILY_CANDIDATES)[0], [
            "Daily report candidate configuration was invalid; safe defaults were used."
        ]
    return candidates, warnings


def configured_daily_report_candidates() -> tuple[list[DailyReportCandidate], list[str]]:
    return parse_daily_report_candidates(config.DEFAULT_DAILY_REPORT_CANDIDATES)
