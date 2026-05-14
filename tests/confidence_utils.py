from __future__ import annotations

from backend.app.utils.confidence import source_confidence_weights


def test_source_confidence_weights_are_source_type_aware() -> None:
    assert source_confidence_weights("live") == (0.95, 0.95)
    assert source_confidence_weights("cached_live") == (0.85, 0.90)
    assert source_confidence_weights("derived") == (0.80, 0.80)
    assert source_confidence_weights("mock") == (0.60, 0.70)
    assert source_confidence_weights("fallback") == (0.50, 0.60)
    assert source_confidence_weights(None) == (0.70, 0.70)
    assert source_confidence_weights("unexpected") == (0.70, 0.70)
