from __future__ import annotations

from backend.app.pipelines import research_pipeline
from backend.app.reports import stock_analysis
from backend.app.schemas.common import ScoreObject


JANE_SOCIAL_HEAT_ITEM = {
    "item": "jane_social_heat_check",
    "question": "Have non-investor friends or family recently asked you about this stock or theme unprompted?",
    "jane_reference": "Jane handbook: widespread non-investor discussion is a late-cycle overheat signal",
    "action": "If yes, treat as additional overheat evidence. Not a scoring input — human judgment required.",
    "needs_human_verification": True,
}


def _overheat_score(score: float) -> ScoreObject:
    return ScoreObject(
        name="overheat_score",
        score=score,
        max_score=100,
        label="overheated" if score >= 60 else "normal",
        raw_data={},
        derived_metrics={"components": {}},
        benchmark={},
        trend={},
        source=["test"],
        source_date="2026-05-16",
        confidence=0.8,
        limitations=[],
        missing_data=[],
    )


def _contains_jane_social_heat_item(queue: list[object]) -> bool:
    return any(isinstance(item, dict) and item == JANE_SOCIAL_HEAT_ITEM for item in queue)


def test_daily_report_adds_jane_social_heat_check_when_overheat_score_is_elevated(monkeypatch) -> None:
    monkeypatch.setattr(research_pipeline, "evaluate_overheat", lambda _snapshot: _overheat_score(60))

    report = research_pipeline.build_daily_report()

    assert _contains_jane_social_heat_item(report.model_dump(mode="json")["human_verification_queue"])


def test_analyze_stock_adds_jane_social_heat_check_when_overheat_score_is_elevated(monkeypatch) -> None:
    monkeypatch.setattr(stock_analysis, "evaluate_overheat", lambda _context: _overheat_score(60))

    response = stock_analysis.analyze_stock(stock_analysis.AnalyzeStockRequest(ticker="NVDA", market="US"))

    assert _contains_jane_social_heat_item(response.model_dump(mode="json")["human_verification_queue"])
