from __future__ import annotations

from tests.phase55_coverage_matrix_auto_evidence_expansion import _analyze, _coverage_row


def test_user_supplied_theme_is_validation_target_not_auto_coverage_or_score(monkeypatch) -> None:
    payload = _analyze(monkeypatch, theme="AI infrastructure")

    context = payload["theme_validation_context"]
    assert context["supplied_theme"] == "AI infrastructure"
    assert context["input_source"] == "user_supplied"
    assert context["boundary_label"] == "user_supplied_validation_target"
    assert context["validation_status"] == "needs_manual_evidence"
    assert context["theme_discovery_enabled"] is False
    assert context["system_generated_theme"] is False
    assert context["affects_score"] is False
    assert context["not_investment_advice"] is True
    assert "automatic theme discovery" in " ".join(context["limitations"])
    assert "revenue exposure" in " ".join(context["manual_checks"])

    c11 = _coverage_row(payload, 11)
    assert c11["coverage_status"] == "insufficient"
    assert "jane_theme_alignment" not in c11["covered_submetrics"]
    assert "jane_theme_alignment" in c11["requires_user_input_submetrics"]
    assert "jane_theme_alignment" not in c11["auto_derivable_submetrics"]
    assert c11["financial_proxy_source"] is None
    assert c11["requires_human_verification"] is True
    assert "User-supplied theme is a validation target" in c11["next_manual_check"]


def test_known_theme_does_not_create_theme_library_rank_or_confidence(monkeypatch) -> None:
    payload = _analyze(monkeypatch, theme="AI infrastructure")

    context = payload["theme_validation_context"]
    forbidden = " ".join(
        [
            context.get("summary", ""),
            context.get("ranking_or_scoring_policy", ""),
            *context.get("limitations", []),
        ]
    ).lower()
    assert "theme mapping score" not in forbidden
    assert "known jane strategic themes" not in forbidden
    assert context["ranking_or_scoring_policy"] == "not_ranked_or_scored"
    assert context["confidence"] == 0.0

    c11 = _coverage_row(payload, 11)
    assert c11["confidence"] == 0.0
    assert c11["source_quality"] == "insufficient"
    assert c11["accepted_evidence_item_count"] == 0
