from __future__ import annotations

from typing import Any


THEME_COMPONENTS = [
    "news_momentum_score",
    "capital_flow_score",
    "policy_support_score",
    "technology_progress_score",
    "commercialization_score",
    "strategic_relevance_score",
]

THEME_WEIGHTS = {
    "news_momentum_score": 0.20,
    "capital_flow_score": 0.20,
    "policy_support_score": 0.15,
    "technology_progress_score": 0.15,
    "commercialization_score": 0.15,
    "strategic_relevance_score": 0.15,
}


def normalize_theme_fixture(theme: dict[str, Any] | tuple) -> dict[str, Any]:
    if isinstance(theme, dict):
        return theme
    name, score, label, companies = theme
    return {
        "theme": name,
        "label": label,
        "candidate_companies": companies,
        "theme_mentions_7d": score,
        "theme_mentions_30d_avg": max(1, score - 20),
        "news_momentum_score": max(0, min(100, score - 4)),
        "capital_flow_score": max(0, min(100, score - 8)),
        "policy_support_score": max(0, min(100, score - 12)),
        "technology_progress_score": max(0, min(100, score - 6)),
        "commercialization_score": max(0, min(100, score - 10)),
        "strategic_relevance_score": max(0, min(100, score + 3)),
        "missing_data": ["live theme evidence source"],
    }


def theme_component_scores(theme: dict[str, Any]) -> dict[str, float]:
    return {component: float(theme.get(component, 0) or 0) for component in THEME_COMPONENTS}


def weighted_theme_score(components: dict[str, float]) -> float:
    return round(sum(components[name] * THEME_WEIGHTS[name] for name in THEME_COMPONENTS), 2)


def theme_label(score: float, missing_data: list[str]) -> str:
    if len(missing_data) >= 4:
        return "insufficient_data"
    if score >= 70:
        return "heating_up"
    if score >= 50:
        return "stable"
    return "cooling_down"
