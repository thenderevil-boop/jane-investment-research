from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_crisis import MOCK_CRISIS_SOURCE_DATE
from backend.app.features.crisis_features import build_crisis_components
from backend.app.schemas.common import ScoreObject
from backend.app.schemas.crisis import CrisisOutput

LIMITATION = "Phase 5 deterministic mock crisis playbook engine; no live source connection."
REQUIRED_FIELDS = [
    "vix",
    "oil_price_spike_5d_pct",
    "gold_price_spike_5d_pct",
    "dxy_spike_5d_pct",
    "treasury_yield_movement",
    "geopolitical_news_count",
    "geopolitical_news_count_benchmark",
    "geopolitical_news_severity",
]


def _missing_required(data: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if data.get(field) is None]


def _level_score(level: str) -> float:
    return {"normal": 15, "elevated": 55, "high": 78, "severe": 95, "insufficient_data": 0}[level]


def _classify(data: dict[str, Any]) -> str:
    if len(_missing_required(data)) > 4:
        return "insufficient_data"
    vix = data.get("vix")
    oil_spike = data.get("oil_price_spike_5d_pct")
    gold_spike = data.get("gold_price_spike_5d_pct")
    dxy_spike = data.get("dxy_spike_5d_pct")
    news_count = data.get("geopolitical_news_count")
    news_benchmark = data.get("geopolitical_news_count_benchmark")
    severity = data.get("geopolitical_news_severity")
    if vix is not None and vix >= 40 and severity == "high" and oil_spike is not None and oil_spike >= 10:
        return "severe"
    if vix is not None and vix >= 30 and severity in {"medium", "high"} and ((gold_spike is not None and gold_spike >= 3) or (dxy_spike is not None and dxy_spike >= 3)):
        return "high"
    if (
        (vix is not None and vix >= 25)
        or (news_count is not None and news_benchmark is not None and news_count > news_benchmark)
        or (oil_spike is not None and oil_spike >= 5)
    ):
        return "elevated"
    return "normal"


def _reference(level: str) -> dict[str, str]:
    if level == "insufficient_data":
        return {
            "cash_usd": "insufficient_data",
            "gold": "insufficient_data",
            "treasury": "insufficient_data",
            "energy": "insufficient_data",
            "defense": "insufficient_data",
            "growth_stocks": "insufficient_data",
        }
    if level == "normal":
        return {
            "cash_usd": "no_crisis_signal",
            "gold": "no_crisis_signal",
            "treasury": "no_crisis_signal",
            "energy": "no_crisis_signal",
            "defense": "no_crisis_signal",
            "growth_stocks": "no_crisis_signal",
        }
    return {
        "cash_usd": "defensive_assets_positive",
        "gold": "defensive_assets_positive",
        "treasury": "defensive_assets_positive",
        "energy": "monitor_energy_and_defense",
        "defense": "monitor_energy_and_defense",
        "growth_stocks": "risk_assets_under_pressure",
    }


def evaluate_crisis(data: dict[str, Any]) -> CrisisOutput:
    components = build_crisis_components(data)
    level = _classify(data)
    missing = sorted(set(_missing_required(data) + [item for component in components for item in component.missing_data]))
    confidence = 0.35 if level == "insufficient_data" else round(sum(component.confidence for component in components) / len(components), 2)
    return CrisisOutput(
        level=level,
        confidence=confidence,
        reference=_reference(level),
        components=components,
        limitations=[LIMITATION, "Reference labels describe research context only."],
        missing_data=missing,
    )


def crisis_to_score_object(crisis: CrisisOutput) -> ScoreObject:
    score = _level_score(crisis.level)
    label = "high_risk_warning" if crisis.level in {"high", "severe"} else "elevated_heat" if crisis.level == "elevated" else "insufficient_data_or_unfavorable" if crisis.level == "insufficient_data" else "normal"
    return ScoreObject(
        name="crisis_score",
        score=score,
        max_score=100,
        label=label,
        raw_data={"level": crisis.level, "reference": crisis.reference},
        derived_metrics={"components": [component.model_dump() for component in crisis.components]},
        benchmark={"elevated_minimum": 25, "high_vix": 30, "severe_vix": 40},
        trend={"crisis_level": crisis.level},
        source=["phase5_mock_crisis_dataset"],
        source_date=MOCK_CRISIS_SOURCE_DATE,
        confidence=crisis.confidence,
        limitations=crisis.limitations,
        missing_data=crisis.missing_data,
    )
