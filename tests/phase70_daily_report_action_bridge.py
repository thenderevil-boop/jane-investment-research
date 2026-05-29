from backend.app.pipelines.research_pipeline import _with_route
from backend.app.schemas.daily_report import TodayResearchAction


def test_stock_research_top_action_carries_url_action_target():
    action = _with_route(
        TodayResearchAction(
            priority="high",
            ticker="NVDA",
            action_type="watchlist_change",
            title="Review NVDA watchlist delta",
            reason="Daily Watchlist Delta shows a changed score, source status, or data issue versus the previous snapshot.",
        )
    )

    dumped = action.model_dump(mode="json")

    assert dumped["route_hint"] == "stock_research"
    assert dumped["action_target"] == {
        "ticker": "NVDA",
        "surface": "stock_research",
        "url_params": {
            "ticker": "NVDA",
            "source": "daily_action",
            "blocker": "manual_evidence_gap",
        },
        "open_in_new_tab": False,
    }
    assert dumped["affects_score"] is False
    assert dumped["not_investment_advice"] is True


def test_operations_top_action_carries_operations_action_target_without_ticker():
    action = _with_route(
        TodayResearchAction(
            priority="high",
            action_type="source_setup",
            title="Review fallback data sources",
            reason="Confirm SEC EDGAR setup before comparing daily source changes.",
        )
    )

    dumped = action.model_dump(mode="json")

    assert dumped["route_hint"] == "operations"
    assert dumped["action_target"] == {
        "ticker": None,
        "surface": "operations",
        "url_params": {"provider": "sec_edgar"},
        "open_in_new_tab": False,
    }
    assert dumped["affects_score"] is False
    assert dumped["not_investment_advice"] is True
