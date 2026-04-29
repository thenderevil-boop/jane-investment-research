from __future__ import annotations

from contextvars import ContextVar
from time import perf_counter
from typing import Any


_DEFAULT = {
    "macro_ms": 0.0,
    "market_data_ms": 0.0,
    "sec_form4_ms": 0.0,
    "sec_13f_ms": 0.0,
    "sec_13f_price_reference_ms": 0.0,
    "smart_money_ms": 0.0,
    "candidate_generation_ms": 0.0,
    "network_call_count": 0,
    "cache_hit_count": 0,
    "cache_miss_count": 0,
    "bounded_fetch_skipped_count": 0,
}

_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar("performance_context", default=None)


def reset_performance_context() -> float:
    _CONTEXT.set(dict(_DEFAULT))
    return perf_counter()


def get_performance_context() -> dict[str, Any] | None:
    return _CONTEXT.get()


def increment_metric(name: str, amount: int = 1) -> None:
    context = _CONTEXT.get()
    if context is None:
        return
    context[name] = int(context.get(name, 0) or 0) + amount


def add_timing(name: str, started_at: float) -> None:
    context = _CONTEXT.get()
    if context is None:
        return
    context[name] = round(float(context.get(name, 0.0) or 0.0) + (perf_counter() - started_at) * 1000, 3)


def finalize_performance_context(started_at: float) -> dict[str, Any]:
    context = dict(_CONTEXT.get() or _DEFAULT)
    context["total_ms"] = round((perf_counter() - started_at) * 1000, 3)
    return context
