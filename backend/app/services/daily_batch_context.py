from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator


@dataclass(frozen=True)
class DailyBatchContext:
    allow_live_fetch_on_report_request: bool = False
    price_reference_cache_warmup_on_report: bool = False
    daily_batch_price_reference_warmed: bool = False
    batch_started_at: datetime | None = None
    batch_job_id: str | None = None


_CURRENT_DAILY_BATCH_CONTEXT: ContextVar[DailyBatchContext | None] = ContextVar(
    "current_daily_batch_context",
    default=None,
)


def get_daily_batch_context() -> DailyBatchContext | None:
    return _CURRENT_DAILY_BATCH_CONTEXT.get()


@contextmanager
def use_daily_batch_context(context: DailyBatchContext | None) -> Iterator[None]:
    token = _CURRENT_DAILY_BATCH_CONTEXT.set(context)
    try:
        yield
    finally:
        _CURRENT_DAILY_BATCH_CONTEXT.reset(token)
