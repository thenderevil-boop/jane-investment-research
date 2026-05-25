from __future__ import annotations

from tests.phase55_coverage_matrix_auto_evidence_expansion import _analyze


def test_phase57_analyze_stock_exposes_non_scoring_macro_flow_breakdown(monkeypatch) -> None:
    payload = _analyze(monkeypatch, smart_money_label="institutional_target_match_observed")

    breakdown = payload["macro_flow_signal_breakdown"]

    assert breakdown["version"] == "phase57_macro_flow_signal_breakdown_v1"
    assert breakdown["affects_score"] is False
    assert breakdown["not_investment_advice"] is True
    assert breakdown["final_score_unchanged"] is True
    assert breakdown["research_verdict_label"] == payload["research_verdict"]["label"]
    assert breakdown["macro_regime_label"] == payload["macro_regime"]["label"]
    assert breakdown["smart_money_label"] == payload["smart_money"]["label"]
    assert "not a trading signal" in " ".join(breakdown["limitations"]).lower()

    assert breakdown["macro_signal_count"] >= 3
    assert breakdown["flow_signal_count"] >= 3
    assert breakdown["manual_review_required"] is True

    macro_names = {item["name"] for item in breakdown["macro_signals"]}
    assert {"fed_policy_trend", "vix", "equity_drawdown"} & macro_names
    for item in breakdown["macro_signals"]:
        assert item["category"] == "macro"
        assert item["affects_score"] is False
        assert item["source_quality"] in {"live", "cached_live", "derived", "mock", "fallback", "unknown"}
        assert item["interpretation"]

    flow_names = {item["name"] for item in breakdown["flow_signals"]}
    assert {"insider_form4_signal", "institutional_support_13f", "options_abnormal_activity"} <= flow_names
    delayed_13f = next(item for item in breakdown["flow_signals"] if item["name"] == "institutional_support_13f")
    assert delayed_13f["category"] == "flow"
    assert delayed_13f["is_real_time_signal"] is False
    assert "delayed" in " ".join(delayed_13f["limitations"]).lower()


def test_phase57_breakdown_is_explainability_only_and_does_not_change_score(monkeypatch) -> None:
    payload = _analyze(monkeypatch)
    breakdown = payload["macro_flow_signal_breakdown"]

    assert breakdown["affects_score"] is False
    assert payload["score_driver_breakdown"]["final_score"] == payload["research_verdict"]["score"]
    assert breakdown["final_score"] == payload["research_verdict"]["score"]
    assert breakdown["manual_checks"]
    forbidden = " ".join([breakdown["summary"], *breakdown["manual_checks"], *breakdown["limitations"]]).lower()
    for phrase in ["buy", "sell", "hold", "must invest", "target price"]:
        assert phrase not in forbidden
