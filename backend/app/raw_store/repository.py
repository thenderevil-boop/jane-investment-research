from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.app.data_sources.mock_crisis import MOCK_CRISIS_SCENARIOS
from backend.app.data_sources.mock_data import MARKET_SNAPSHOTS, MOCK_SMART_MONEY_SUMMARY, STOCK_FIXTURES, THEMES
from backend.app.data_sources.mock_macro import MOCK_MACRO_SCENARIOS


def read_market_data(scenario: str = "normal") -> dict[str, Any]:
    return deepcopy(MARKET_SNAPSHOTS.get(scenario, MARKET_SNAPSHOTS["normal"]))


def read_macro_data(scenario: str = "normal") -> dict[str, Any]:
    return deepcopy(MOCK_MACRO_SCENARIOS.get(scenario, MOCK_MACRO_SCENARIOS["normal"]))


def read_company_fundamentals(ticker: str = "NVDA") -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    fixture = STOCK_FIXTURES.get(normalized_ticker, STOCK_FIXTURES["NVDA"])
    return deepcopy(fixture)


def read_sec_filings(ticker: str = "NVDA") -> dict[str, Any]:
    fixture = read_company_fundamentals(ticker)
    smart_money = fixture.get("smart_money", MOCK_SMART_MONEY_SUMMARY)
    return deepcopy(
        {
            "institutional_13f": smart_money.get("institutional_13f", {}),
            "form4_transactions": smart_money.get("form4_transactions", []),
            "crisis_scenarios": MOCK_CRISIS_SCENARIOS,
        }
    )


def read_news_mentions() -> list[dict[str, Any]]:
    return deepcopy(
        [
            {
                "theme": theme["theme"],
                "theme_mentions_7d": theme["theme_mentions_7d"],
                "theme_mentions_30d_avg": theme["theme_mentions_30d_avg"],
            }
            for theme in THEMES
        ]
    )


def read_theme_data() -> list[dict[str, Any]]:
    return deepcopy(THEMES)
