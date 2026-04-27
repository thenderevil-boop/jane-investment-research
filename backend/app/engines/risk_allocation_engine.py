from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_data import MOCK_SOURCE, MOCK_SOURCE_DATE
from backend.app.schemas.crisis import CrisisOutput
from backend.app.schemas.common import ScoreObject
from backend.app.schemas.macro_regime import MacroRegimeOutput
from backend.app.schemas.risk_allocation import RiskAllocationReference, RiskPostureLabel

LIMITATION = "Phase 7.1 deterministic mock risk reference engine; no live source connection."


def _confidence(missing_data: list[str]) -> float:
    completeness = max(0.35, 1 - len(missing_data) * 0.10)
    return round(completeness * 0.40 + 0.90 * 0.30 + 0.80 * 0.30, 2)


def _reference(posture: RiskPostureLabel) -> dict[str, RiskPostureLabel]:
    return {
        "market_risk": posture,
        "volatility": "crisis_watch" if posture == "crisis_watch" else posture,
        "theme_research": "overheat_warning" if posture == "overheat_warning" else "balanced_watch",
        "quality_filter": "defensive_watch" if posture in {"defensive_watch", "crisis_watch"} else "balanced_watch",
    }


def evaluate_risk_allocation(
    macro_regime: MacroRegimeOutput,
    market_timing: ScoreObject,
    overheat_risk: ScoreObject,
    crisis: CrisisOutput,
    market_snapshot: dict[str, Any],
) -> RiskAllocationReference:
    missing_data = sorted(
        {
            *macro_regime.missing_data,
            *market_timing.missing_data,
            *overheat_risk.missing_data,
            *crisis.missing_data,
        }
    )
    risk_flags: list[str] = []
    if crisis.level in {"high", "severe"}:
        risk_flags.append("crisis_pressure")
    if overheat_risk.score >= 60:
        risk_flags.append("overheat_pressure")
    if macro_regime.label in {"recession_warning", "recession_confirmed", "fear_crisis"}:
        risk_flags.append("macro_stress")
    if market_snapshot.get("vix", 0) >= 25:
        risk_flags.append("volatility_elevated")

    if len(missing_data) >= 8:
        posture: RiskPostureLabel = "insufficient_data"
        score = 0
    elif crisis.level in {"high", "severe"}:
        posture = "crisis_watch"
        score = 90 if crisis.level == "severe" else 80
    elif overheat_risk.score >= 60:
        posture = "overheat_warning"
        score = overheat_risk.score
    elif macro_regime.label in {"recession_warning", "recession_confirmed", "fear_crisis"}:
        posture = "defensive_watch"
        score = max(60, macro_regime.score)
    elif market_timing.score >= 60 and overheat_risk.score < 40 and crisis.level == "normal":
        posture = "risk_on_watch"
        score = market_timing.score
    else:
        posture = "balanced_watch"
        score = max(40, min(65, (market_timing.score + (100 - overheat_risk.score)) / 2))

    return RiskAllocationReference(
        risk_posture=posture,
        score=round(score, 2),
        reference=_reference(posture),
        risk_flags=risk_flags,
        raw_data={
            "macro_regime_label": macro_regime.label,
            "market_timing_score": market_timing.score,
            "overheat_score": overheat_risk.score,
            "crisis_level": crisis.level,
            "vix": market_snapshot.get("vix"),
        },
        derived_metrics={
            "risk_flag_count": len(risk_flags),
            "missing_data_count": len(missing_data),
        },
        benchmark={
            "overheat_warning_minimum": 60,
            "vix_elevated": 25,
            "market_timing_constructive_minimum": 60,
        },
        trend={
            "risk_posture": posture,
            "volatility": "up" if market_snapshot.get("vix", 0) >= 25 else "stable",
        },
        source=MOCK_SOURCE,
        source_date=MOCK_SOURCE_DATE,
        confidence=_confidence(missing_data),
        limitations=[LIMITATION, "Reference labels are research context only and contain no allocation percentages."],
        missing_data=missing_data,
    )
