from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_data import MOCK_SOURCE, MOCK_SOURCE_DATE
from backend.app.schemas.common import ScoreObject
from backend.app.utils.confidence import source_confidence_weights

LIMITATION = "Phase 2 deterministic mock engine; no live source connection."
LIVE_LIMITATION = "Deterministic engine using repository-backed live market price features where available."


def _confidence(missing_data: list[str], source_type: str | None = "mock") -> float:
    completeness = max(0.35, 1 - len(missing_data) * 0.12)
    recency, reliability = source_confidence_weights(source_type)
    return round(completeness * 0.40 + recency * 0.30 + reliability * 0.30, 2)


def _score(
    name: str,
    score: float,
    label: str,
    raw_data: dict[str, Any],
    derived_metrics: dict[str, Any],
    benchmark: dict[str, Any],
    trend: dict[str, Any],
    missing_data: list[str] | None = None,
) -> ScoreObject:
    missing = missing_data or []
    return ScoreObject(
        name=name,
        score=round(score, 2),
        label=label,
        raw_data=raw_data,
        derived_metrics=derived_metrics,
        benchmark=benchmark,
        trend=trend,
        source=MOCK_SOURCE,
        source_date=MOCK_SOURCE_DATE,
        confidence=_confidence(missing, "mock"),
        limitations=[LIMITATION],
        missing_data=missing,
    )


def _source(data: dict[str, Any]) -> list[str]:
    value = data.get("source")
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return MOCK_SOURCE


def _source_date(data: dict[str, Any]) -> str:
    value = data.get("source_date")
    return str(value) if value else MOCK_SOURCE_DATE


def _limitations(data: dict[str, Any]) -> list[str]:
    existing = data.get("limitations")
    if isinstance(existing, list) and existing:
        return existing
    return [LIVE_LIMITATION if data.get("source_type") == "live" else LIMITATION]


def _mark_live_derived(component: ScoreObject, data: dict[str, Any]) -> ScoreObject:
    if data.get("source_type") != "live":
        return component
    component.source = _source(data)
    component.source_date = _source_date(data)
    component.limitations = _limitations(data)
    component.raw_data = {
        **component.raw_data,
        "source_type": "derived",
        "provider": "derived_from_yfinance",
        "source": _source(data),
        "source_date": _source_date(data),
    }
    return component


def _overheat_explanation(data: dict[str, Any], index_component: ScoreObject) -> dict[str, Any]:
    qqq_drawdown = data.get("nasdaq_drawdown_pct")
    spy_distance = data.get("distance_from_52w_high")
    supporting_conditions: list[str] = []
    unmet_conditions: list[str] = []
    metrics = index_component.derived_metrics
    for condition, present in {
        "primary index gain versus prior cycle high is elevated": bool(metrics.get("gain_vs_prior_cycle_high_above_30pct")),
        "primary index gain from recent trough is elevated": bool(metrics.get("gain_from_recent_trough_above_30pct")),
        "primary index is near its 52-week high": bool(metrics.get("near_52w_high")),
    }.items():
        (supporting_conditions if present else unmet_conditions).append(condition)
    if qqq_drawdown is not None and qqq_drawdown >= -3 and (spy_distance is None or spy_distance < -3):
        supporting_conditions.append("secondary index is elevated")
        unmet_conditions.append("primary index confirmation is not strong enough for overall overheat by itself")
    return {
        "primary_index_used": "SPY",
        "secondary_index_used": "QQQ",
        "supporting_conditions": supporting_conditions,
        "unmet_conditions": unmet_conditions,
    }


def index_overextension_component(data: dict[str, Any]) -> ScoreObject:
    gain_vs_prior_high = data.get("index_gain_vs_prior_cycle_high")
    gain_from_trough = data.get("index_gain_from_recent_trough")
    distance_from_52w_high = data.get("distance_from_52w_high")
    extension = data.get("index_extension_from_200d_pct")
    missing = [
        field
        for field, value in {
            "index_gain_vs_prior_cycle_high": gain_vs_prior_high,
            "index_gain_from_recent_trough": gain_from_trough,
            "distance_from_52w_high": distance_from_52w_high,
        }.items()
        if value is None
    ]
    gain_vs_prior_high = gain_vs_prior_high or 0
    gain_from_trough = gain_from_trough or 0
    distance_from_52w_high = distance_from_52w_high or -100
    near_high = distance_from_52w_high >= -3
    if (gain_vs_prior_high >= 30 or gain_from_trough >= 45) and near_high:
        score = 100
    elif gain_vs_prior_high >= 30 or gain_from_trough >= 30:
        score = 80
    elif gain_vs_prior_high >= 20 or gain_from_trough >= 20 or distance_from_52w_high >= -5:
        score = 40
    else:
        score = 0
    label = "high_risk_warning" if score >= 80 else "overheated" if score >= 60 else "elevated_heat" if score >= 40 else "normal"
    return _score(
        "index_overextension_score",
        score,
        label,
        {
            "index_gain_vs_prior_cycle_high": gain_vs_prior_high,
            "index_gain_from_recent_trough": gain_from_trough,
            "distance_from_52w_high": distance_from_52w_high,
            "index_extension_from_200d_pct": extension,
        },
        {
            "gain_vs_prior_cycle_high_above_30pct": gain_vs_prior_high >= 30,
            "gain_from_recent_trough_above_30pct": gain_from_trough >= 30,
            "near_52w_high": near_high,
            "supplemental_200d_extension": extension,
        },
        {
            "gain_vs_prior_cycle_high_high_pct": 30,
            "gain_from_recent_trough_high_pct": 30,
            "near_52w_high_distance_pct": -3,
        },
        {"index_heat": "up" if score >= 80 else "elevated" if score >= 40 else "stable"},
        missing,
    )


def media_hype_component(data: dict[str, Any]) -> ScoreObject:
    ratio = data.get("media_hype_ratio")
    if ratio is None:
        return _score(
            "media_hype_score",
            0,
            "normal",
            {"media_hype_ratio": None},
            {"media_hype_ratio": None},
            {"overheated_ratio": 3.0},
            {"media_hype": "unknown"},
            ["media_hype_ratio"],
        )
    score = 100 if ratio >= 3 else 70 if ratio >= 2 else 40 if ratio >= 1.5 else 0
    label = "high_risk_warning" if score >= 80 else "overheated" if score >= 60 else "elevated_heat" if score >= 40 else "normal"
    return _score(
        "media_hype_score",
        score,
        label,
        {"media_hype_ratio": ratio},
        {"media_hype_ratio": ratio},
        {"overheated_ratio": 3.0, "elevated_ratio": 1.5},
        {"media_hype": "up" if ratio >= 2 else "stable"},
    )


def youtube_hype_component(data: dict[str, Any]) -> ScoreObject:
    ratio = data.get("youtube_hype_ratio")
    if ratio is None:
        return _score(
            "youtube_hype_score",
            0,
            "normal",
            {"youtube_hype_ratio": None},
            {"youtube_hype_ratio": None},
            {"overheated_ratio": 3.0},
            {"video_attention": "unknown"},
            ["youtube_hype_ratio"],
        )
    score = 100 if ratio >= 3 else 70 if ratio >= 2 else 40 if ratio >= 1.5 else 0
    label = "high_risk_warning" if score >= 80 else "overheated" if score >= 60 else "elevated_heat" if score >= 40 else "normal"
    return _score(
        "youtube_hype_score",
        score,
        label,
        {"youtube_hype_ratio": ratio},
        {"youtube_hype_ratio": ratio},
        {"overheated_ratio": 3.0, "elevated_ratio": 1.5},
        {"video_attention": "up" if ratio >= 2 else "stable"},
    )


def user_social_heat_component(data: dict[str, Any]) -> ScoreObject:
    level = data.get("user_reported_social_heat", "low")
    friends_asking = bool(data.get("friends_asking_about_stock", False))
    base = {"low": 0, "medium": 45, "high": 75}.get(level, 0)
    score = min(100, base + (15 if friends_asking else 0))
    label = "high_risk_warning" if score >= 80 else "overheated" if score >= 60 else "elevated_heat" if score >= 40 else "normal"
    return _score(
        "user_reported_social_heat_score",
        score,
        label,
        {"user_reported_social_heat": level, "friends_asking_about_stock": friends_asking},
        {"social_heat_score": score},
        {"high_social_heat_score": 75, "friends_discussion_additive": 15},
        {"social_attention": "up" if score >= 60 else "stable"},
    )


def overheat_label(score: float) -> str:
    if score >= 80:
        return "high_risk_warning"
    if score >= 60:
        return "overheated"
    if score >= 40:
        return "elevated_heat"
    return "normal"


def evaluate_overheat(data: dict[str, Any]) -> ScoreObject:
    components = [
        index_overextension_component(data),
        media_hype_component(data),
        youtube_hype_component(data),
        user_social_heat_component(data),
    ]
    _mark_live_derived(components[0], data)
    weights = {
        "index_overextension_score": 0.38,
        "media_hype_score": 0.32,
        "youtube_hype_score": 0.18,
        "user_reported_social_heat_score": 0.12,
    }
    total = sum(component.score * weights[component.name] for component in components)
    missing = sorted({item for component in components for item in component.missing_data})
    component_payload = {component.name: component.model_dump() for component in components}
    explanation = _overheat_explanation(data, components[0])
    return ScoreObject(
        name="overheat_score",
        score=round(total, 2),
        label=overheat_label(total),
        raw_data={key: data.get(key) for key in sorted(data.keys()) if key != "fear_greed"},
        derived_metrics={"components": component_payload, "weights": weights, **explanation},
        benchmark={
            "high_risk_warning_minimum": 80,
            "overheated_minimum": 60,
            "elevated_heat_minimum": 40,
        },
        trend={
            "speculative_attention": "up" if total >= 60 else "stable",
            "component_count": len(components),
        },
        source=_source(data),
        source_date=_source_date(data),
        confidence=_confidence(missing, data.get("source_type") or "mock"),
        limitations=_limitations(data),
        missing_data=missing,
    )
