from __future__ import annotations


def source_confidence_weights(source_type: str | None) -> tuple[float, float]:
    """
    Returns (data_recency_weight, source_reliability_weight) based on source_type.
    Used in the confidence formula:
      completeness * 0.40 + data_recency * 0.30 + source_reliability * 0.30
    """
    return {
        "live": (0.95, 0.95),
        "cached_live": (0.85, 0.90),
        "derived": (0.80, 0.80),
        "mock": (0.60, 0.70),
        "fallback": (0.50, 0.60),
        "unknown": (0.70, 0.70),
    }.get(str(source_type or "unknown"), (0.70, 0.70))
