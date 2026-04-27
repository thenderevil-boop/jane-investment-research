# Jane Framework Daily Investment Research Assistant

This repo specification pack is designed to be copied into a new VSCode project and used with Codex.

## Purpose

Build a US-market-only daily investment research automation system based on Jane's Markdown investment framework.

This is not a trading system. It produces research signals, evidence, benchmarks, trends, confidence, and missing-data warnings.

## Files

```text
AGENTS.md
README.md
docs/
  PRODUCT_SPEC.md
  DAILY_AUTOMATION_SPEC.md
  JANE_FRAMEWORK_MAPPING.md
  SCORING_RUBRIC.md
  MARKET_TIMING_SPEC.md
  MACRO_REGIME_SPEC.md
  FUTURE_INDUSTRY_SPEC.md
  SMART_MONEY_SPEC.md
  RISK_ALLOCATION_SPEC.md
  DATA_SOURCES.md
  API_SPEC.md
  ACCEPTANCE_CRITERIA.md
codex_prompts/
  01_phase1_scaffold.md
  02_market_timing_engine.md
  03_leadership_engine.md
  04_smart_money_engine.md
  05_macro_future_industry_engines.md
  06_frontend_dashboard.md
schemas/
  daily_report.schema.json
  analyze_stock.schema.json
```

## How to use with Codex in VSCode

1. Create a new local folder, for example:

```powershell
mkdir jane-investment-research
cd jane-investment-research
git init
```

2. Copy all files from this spec pack into that folder.

3. Open the folder in Visual Studio Code.

4. Install and open the Codex extension in VSCode.

5. Start with this prompt:

```text
Read AGENTS.md and all docs under /docs. Build Phase 1 only using the prompt in codex_prompts/01_phase1_scaffold.md. Do not connect to live APIs yet.
```

6. After each phase, run tests and commit.

## MVP Tech Stack

Backend:

- Python 3.11+
- FastAPI
- Pydantic
- SQLite for MVP
- pytest

Frontend:

- React
- TypeScript
- Vite

## Product Rule

Leadership Score tells us what to research.
Market Timing and Macro Regime tell us whether the current environment is favorable, neutral, fearful, or overheated.
Neither is a direct investment recommendation.

## Windows VSCode Runbook

Open this folder in VSCode:

```powershell
cd D:\jane-investment-research
code .
```

### Backend Setup

```powershell
cd D:\jane-investment-research
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Run Backend Tests

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
python -m pytest -p no:cacheprovider
```

### Run Backend

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload
```

Backend URL:

```text
http://localhost:8000
```

### Frontend Setup

```powershell
cd D:\jane-investment-research\frontend
npm install
```

Do not commit `frontend\node_modules`; dependencies are restored with `npm install`. If the frontend build fails after extracting or moving an archive, run `npm install` again from `D:\jane-investment-research\frontend` because `node_modules` is intentionally not part of the repo.

### Run Frontend Tests

```powershell
cd D:\jane-investment-research\frontend
npm test
```

### Build Frontend

```powershell
cd D:\jane-investment-research\frontend
npm run build
```

### Run Frontend

```powershell
cd D:\jane-investment-research\frontend
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

The Vite dev server proxies `/api` requests to `http://localhost:8000`.

Proxy configuration lives in `frontend\vite.config.ts`. Keep the backend running at `http://localhost:8000` in a second PowerShell terminal when using the Vite dev server.

## Phase 1 Backend

Phase 1 adds a mock-data FastAPI backend under `backend/` with:

- `GET /api/health`
- `GET /api/daily-report/latest`
- `GET /api/daily-report/{date}`
- `POST /api/analyze-stock`

The Phase 1 implementation uses mock US-market data only. It does not connect to live APIs.

### Windows PowerShell Commands

```powershell
cd D:\jane-investment-research
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -p no:cacheprovider
uvicorn backend.app.main:app --reload
```

Local API base URL:

```text
http://localhost:8000
```

## Phase 6 Frontend

The MVP frontend lives under `frontend/` and uses React, TypeScript, and Vite.

Windows PowerShell commands:

```powershell
cd D:\jane-investment-research\frontend
npm install
npm run dev
```

Frontend local URL:

```text
http://localhost:5173
```

The Vite dev server proxies `/api` requests to `http://localhost:8000`, so run the FastAPI backend in a second terminal.

Build and test:

```powershell
cd D:\jane-investment-research\frontend
npm run build
npm test
```

## Next Phase: Live Market Data

Live market, macro, SEC, options, news, and theme APIs are not connected yet. The current system is fully mock-based so schemas, report quality checks, and UI flows can stabilize before live integrations are added.

## Project Guardrails

Before changing an endpoint, verify Pydantic models, JSON schemas under `schemas\`, frontend TypeScript types, and `docs\API_SPEC.md` together. Mock raw data should be accessed through `backend.app.raw_store.repository`; live API clients should not be called from engines directly.
