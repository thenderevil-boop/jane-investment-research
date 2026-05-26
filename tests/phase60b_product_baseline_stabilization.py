from __future__ import annotations

from pathlib import Path

from backend.app import config
from backend.app.engines.smart_money_engine import _sec_13f_target_manager_config_warning
from backend.app.pipelines.research_pipeline import build_daily_report
from backend.app.utils.forbidden_language import detect_forbidden_language

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase60b_daily_report_has_5_minute_research_actions() -> None:
    report = build_daily_report()

    assert len(report.today_research_actions) >= 2
    action_types = {action.action_type for action in report.today_research_actions}
    assert action_types & {"source_setup", "evidence_review", "coverage_gap", "watchlist_change"}
    assert any(action.priority in {"high", "medium"} for action in report.today_research_actions)
    assert all(action.source == "existing_data" for action in report.today_research_actions)
    assert all(action.affects_score is False for action in report.today_research_actions)
    assert all(action.not_investment_advice is True for action in report.today_research_actions)
    assert detect_forbidden_language([action.model_dump(mode="json") for action in report.today_research_actions]) == []


def test_phase60b_13f_manager_warning_is_runtime_universe_health_not_hard_requirement(monkeypatch) -> None:
    monkeypatch.setattr(config, "SEC_13F_TARGET_MANAGERS", "0001067983")

    warning = _sec_13f_target_manager_config_warning()

    assert warning is not None
    assert "runtime universe" in warning
    assert "starter universe" in warning
    assert "comparable with prior runs" in warning
    assert "missing default managers" not in warning
    assert "required" not in warning.lower()


def test_phase60b_baseline_docs_and_language_policy_are_present() -> None:
    product = _read("docs/PRODUCT_BASELINE.md")
    architecture = _read("docs/ARCHITECTURE_BASELINE.md")
    language = _read("docs/LANGUAGE_POLICY.md")
    roadmap = _read("docs/ROADMAP.md")
    readme = _read("README.md")

    assert "5-minute Daily Report workflow" in product
    assert "today_research_actions" in product
    assert "hard gates" in product
    assert "backend/app/reports/stock_analysis.py" in architecture
    assert "Coverage Matrix" in product
    assert "Forbidden" in language
    assert "researchable" in language
    assert "today_research_actions" in roadmap
    assert "Phase 61" in roadmap
    assert "PRODUCT_BASELINE.md" in readme


def test_phase60b_language_policy_gate_scans_key_surfaces() -> None:
    policy = _read("docs/LANGUAGE_POLICY.md")
    assert "Forbidden and restricted terms" in policy

    paths = [
        "frontend/src/pages/DailyReport.tsx",
        "frontend/src/pages/StockResearch.tsx",
        "backend/app/pipelines/research_pipeline.py",
        "backend/app/reports/stock_analysis.py",
        "docs/PRODUCT_BASELINE.md",
        "docs/ROADMAP.md",
    ]
    allowlist = {
        "holdings",  # SEC 13F factual noun, not a recommendation.
        "stockholder",  # Filing/legal noun.
    }
    allowed_occurrences = {
        ("backend/app/reports/stock_analysis.py", "buy"),
        ("backend/app/reports/stock_analysis.py", "sell"),
        ("backend/app/reports/stock_analysis.py", "hold"),
        ("backend/app/reports/stock_analysis.py", "liquidate"),
    }
    detected = []
    for path in paths:
        text = _read(path)
        for term in detect_forbidden_language(text):
            if term in allowlist or (path, term) in allowed_occurrences:
                continue
            detected.append((path, term))
    assert detected == []
