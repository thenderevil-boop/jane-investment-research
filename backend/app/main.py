from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app import config
from backend.app.api.routes import router
from backend.app.raw_store.repository import warm_price_reference_cache

def _warm_price_references_on_startup() -> None:
    if not config.PRICE_REFERENCE_CACHE_WARMUP_ON_STARTUP:
        return
    tickers = [item.strip() for item in config.SEC_13F_TARGET_TICKERS.split(",") if item.strip()]
    if tickers:
        warm_price_reference_cache(tickers, max_tickers=config.PRICE_REFERENCE_CACHE_WARMUP_MAX_TICKERS, allow_live_fetch=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warm_price_references_on_startup()
    yield


app = FastAPI(
    title="Jane Framework Daily Investment Research Assistant",
    version="0.1.0",
    description="Phase 1 mock-data backend for US-market research assistance.",
    lifespan=lifespan,
)
app.include_router(router)
