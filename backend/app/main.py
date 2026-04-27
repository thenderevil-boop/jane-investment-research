from __future__ import annotations

from fastapi import FastAPI

from backend.app.api.routes import router

app = FastAPI(
    title="Jane Framework Daily Investment Research Assistant",
    version="0.1.0",
    description="Phase 1 mock-data backend for US-market research assistance.",
)
app.include_router(router)
