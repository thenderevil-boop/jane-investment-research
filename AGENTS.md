# AGENTS.md

## Project

Build a US-market-only daily investment research automation system based on Jane's investing framework extracted from the uploaded Markdown source files.

This project must not use the old `龍頭股智能篩選服務規格書.docx` as the source of truth.

## Product Positioning

This is an investment research assistance system, not an investment advisory, trading, or portfolio execution system.

The system helps the user answer:

1. What is the current market regime?
2. Is the market closer to fear, recovery, normal, or overheat?
3. Which future investment themes are heating up?
4. Which US-listed companies deserve deeper research under Jane's framework?
5. Are smart money, insiders, or sentiment signals changing?
6. Which items require human verification because data is incomplete or uncertain?

## Hard Safety Rules

The system must not output direct investment instructions.

Forbidden language:

- buy
- sell
- hold
- liquidate
- exit all
- sell half
- must invest
- guaranteed return
- target price as instruction

Allowed labels:

- worth_deep_research
- watchlist_candidate
- weak_candidate
- favorable_research_environment
- watch_for_confirmation
- neutral
- insufficient_data_or_unfavorable
- normal
- elevated_heat
- overheated
- high_risk_warning
- positive_signal
- weak_positive_signal
- negative_signal
- needs_human_verification

Every output must include:

- `not_investment_advice: true`
- raw data
- data source
- source date
- derived metrics
- benchmark
- trend
- confidence
- limitations
- missing data

## Market Scope

MVP supports US-listed stocks only.

Do not build Taiwan stock support.

Remove or ignore:

- MOPS
- TEJ
- Taiwan exchange data
- Taiwan insider reports
- Taiwan-specific funds or filings

## Development Environment

Target user environment:

- Windows 11
- Visual Studio Code
- Codex IDE extension
- PowerShell terminal
- Git repo workspace

MVP can run natively on Windows. Avoid Linux-only shell assumptions in app code. When writing README commands, include PowerShell examples.

## MVP Scope

Build in phases.

### Phase 1: Mock Daily Research System

Implement:

1. FastAPI backend
2. Pydantic schemas
3. Mock data store
4. Daily research pipeline using mock data
5. `GET /api/daily-report/latest`
6. `POST /api/analyze-stock`
7. Unit tests

Do not connect to live APIs in Phase 1.

### Phase 2: Engines

Implement deterministic rule engines:

1. Macro Regime Engine
2. Market Timing Engine
3. Overheat Risk Engine
4. Future Industry Radar
5. Leadership Stock Engine
6. Smart Money Engine
7. Risk & Allocation Reference Engine

### Phase 3: UI

Implement a dashboard with expandable evidence panels.

### Phase 4: Live Data Integrations

Connect live APIs only after mock pipeline and tests are stable.

## Required Architecture

Use this structure unless there is a strong reason to change it:

```text
backend/
  app/
    main.py
    pipelines/
    data_sources/
    raw_store/
    features/
    engines/
    reports/
    api/
    schemas/
frontend/
  src/
    pages/
    components/
tests/
```

## Schema Contract Rules

Before implementing or modifying any endpoint, Codex must verify response shapes against:

- `schemas/daily_report.schema.json`
- `schemas/analyze_stock.schema.json`
- `docs/API_SPEC.md`

If Pydantic models, JSON schema files, frontend TypeScript types, and API docs disagree, update them together in the same task. Do not let backend responses, frontend assumptions, and documented contracts drift apart.

## raw_store Contract

In mock phases, `backend/app/raw_store` contains repository interfaces over JSON-like mock fixtures.

In live phases, `raw_store` becomes a SQLite-backed cache for raw source snapshots.

Engines must not call external APIs directly. Engines must read data through repository interfaces so live integrations can be audited, cached, and tested independently from deterministic rule evaluation.

## Frontend Proxy Requirement

During local development, Vite must proxy `/api` requests to:

```text
http://localhost:8000
```

Keep `frontend/vite.config.ts` aligned with this requirement.

## Required Backend Endpoints

Minimum endpoints:

- `GET /api/health`
- `GET /api/daily-report/latest`
- `GET /api/daily-report/{date}`
- `POST /api/analyze-stock`
- `GET /api/themes/latest`
- `GET /api/macro-regime/latest`
- `GET /api/raw-data/{ticker}`
- `GET /api/signals/{ticker}`

## Daily Research Pipeline

The pipeline must produce one daily report object with:

1. macro regime
2. market timing environment
3. overheat risk
4. crisis risk
5. future industry radar
6. leadership stock candidates
7. smart money signals
8. risk and allocation reference
9. missing data
10. human verification queue

## Testing Requirements

Before marking a task complete:

1. Run unit tests.
2. Run type checks if configured.
3. Confirm API response matches schema.
4. Confirm no output contains direct buy/sell/hold/liquidate language.
5. Confirm every score contains raw data, source, benchmark, trend, confidence, limitations, and missing data.

## Definition of Done

A task is done only when:

1. Code runs locally.
2. Tests pass.
3. API schemas are documented.
4. Mock daily report works.
5. No prohibited investment instruction language appears in API responses.
6. All rule engines are deterministic unless explicitly marked qualitative.
