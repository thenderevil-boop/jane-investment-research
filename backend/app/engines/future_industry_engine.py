from __future__ import annotations

from typing import Any

from backend.app.data_sources.mock_data import MOCK_SOURCE, MOCK_SOURCE_DATE, THEMES
from backend.app.features.theme_features import THEME_WEIGHTS, normalize_theme_fixture, theme_component_scores, theme_label, weighted_theme_score
from backend.app.schemas.future_theme import FutureTheme

LIMITATION = "Phase 7.1 deterministic mock future industry engine; live theme sources are not connected."


def _confidence(missing_data: list[str]) -> float:
    completeness = max(0.35, 1 - len(missing_data) * 0.10)
    return round(completeness * 0.40 + 0.90 * 0.30 + 0.80 * 0.30, 2)


def evaluate_future_theme(theme_fixture: dict[str, Any] | tuple) -> FutureTheme:
    theme = normalize_theme_fixture(theme_fixture)
    components = theme_component_scores(theme)
    score = weighted_theme_score(components)
    missing_data = list(theme.get("missing_data", ["live theme evidence source"]))
    mentions_30d = theme.get("theme_mentions_30d_avg") or 0
    mentions_7d = theme.get("theme_mentions_7d") or 0
    hype_ratio = round(mentions_7d / mentions_30d, 2) if mentions_30d else None
    return FutureTheme(
        theme=theme["theme"],
        score=score,
        label=theme.get("label") or theme_label(score, missing_data),
        raw_data={
            "theme": theme["theme"],
            "theme_mentions_7d": mentions_7d,
            "theme_mentions_30d_avg": mentions_30d,
            "candidate_companies": theme.get("candidate_companies", []),
        },
        derived_metrics={
            "components": components,
            "weights": THEME_WEIGHTS,
            "theme_hype_ratio": hype_ratio,
        },
        benchmark={
            "heating_up_minimum": 70,
            "stable_minimum": 50,
            "theme_hype_ratio_watch": 1.2,
        },
        trend={
            "theme_momentum": "up" if score >= 70 else "stable" if score >= 50 else "down",
            "news_momentum": "up" if components["news_momentum_score"] >= 70 else "stable",
        },
        source=theme.get("source", MOCK_SOURCE),
        source_date=theme.get("source_date", MOCK_SOURCE_DATE),
        confidence=_confidence(missing_data),
        limitations=theme.get("limitations", [LIMITATION]),
        missing_data=missing_data,
        candidate_companies=theme.get("candidate_companies", []),
    )


def evaluate_future_industry_radar(themes: list[dict[str, Any] | tuple] | None = None) -> list[FutureTheme]:
    return [evaluate_future_theme(theme) for theme in themes or THEMES]
