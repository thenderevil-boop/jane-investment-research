# API_SPEC.md

## Base URL

MVP local:

```text
http://localhost:8000
```

## Endpoints

### GET /api/health

Response:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "not_investment_advice": true
}
```

### GET /api/daily-report/latest

Returns latest daily research report.

Optional query parameter:

- `use_live_market_data`: boolean. Defaults to environment configuration. When `true`, the backend attempts repository-backed yfinance OHLCV fetches for market price fields and falls back to mock market data if the fetch fails.

Response shape:

```json
{
  "date": "2026-04-24",
  "market": "US",
  "report_generated_at": "2026-04-24T08:00:00+08:00",
  "macro_regime": {},
  "market_timing": {},
  "overheat_risk": {},
  "crisis_risk": {},
  "crisis": {},
  "future_themes": [],
  "stock_candidates": [],
  "smart_money_summary": {},
  "smart_money": {},
  "risk_allocation": {},
  "risk_notes": [],
  "limitations": [],
  "missing_data": [],
  "human_verification_queue": [],
  "not_investment_advice": true
}
```

### GET /api/daily-report/{date}

Returns daily report by date.

### POST /api/analyze-stock

Request:

```json
{
  "ticker": "NVDA",
  "market": "US",
  "period": "3Y",
  "user_context": {
    "friends_asking_about_stock": false,
    "social_discussion_level": "low"
  }
}
```

Response:

```json
{
  "ticker": "NVDA",
  "market": "US",
  "company_profile": {},
  "leadership_score": {},
  "market_timing_context": {},
  "overheat_risk": {},
  "smart_money": {},
  "financial_quality": {},
  "valuation_context": {},
  "risk_flags": [],
  "missing_data": [],
  "human_verification_queue": [],
  "not_investment_advice": true
}
```

### GET /api/themes/latest

Returns latest Future Industry Radar.

Response:

```json
{
  "market": "US",
  "themes": [],
  "limitations": [],
  "missing_data": [],
  "not_investment_advice": true
}
```

Each item in `themes` follows the `FutureTheme` contract.

### GET /api/macro-regime/latest

Returns latest macro regime object.

Response:

```json
{
  "name": "macro_regime_score",
  "score": 58,
  "max_score": 100,
  "label": "normal",
  "raw_data": {},
  "derived_metrics": {},
  "benchmark": {},
  "trend": {},
  "source": [],
  "source_date": "2026-04-24",
  "confidence": 0.76,
  "components": [],
  "limitations": [],
  "missing_data": []
}
```

### GET /api/raw-data/{ticker}

Returns raw data snapshots available for a ticker.

Response:

```json
{
  "ticker": "NVDA",
  "market": "US",
  "raw_data": {},
  "source": [],
  "source_date": "2026-04-24",
  "limitations": [],
  "missing_data": [],
  "not_investment_advice": true
}
```

This endpoint returns mock company fixture snapshots plus the repository market price snapshot. In Phase 8, market price snapshots may be live when `USE_LIVE_MARKET_DATA=true`; company fundamentals remain mock-only.

### GET /api/signals/{ticker}

Returns signal summary for a ticker.

Response:

```json
{
  "ticker": "NVDA",
  "market": "US",
  "leadership_score": {},
  "market_timing_context": {},
  "overheat_risk": {},
  "smart_money": {},
  "financial_quality": {},
  "valuation_context": {},
  "risk_flags": [],
  "limitations": [],
  "missing_data": [],
  "not_investment_advice": true
}
```

All score-like fields follow the shared `ScoreComponent` contract, except `leadership_score`, which includes the 20-criterion leadership detail.

## Response Requirements

All responses must include:

```json
{
  "not_investment_advice": true
}
```

All scoring subobjects must include:

- raw_data
- source
- source_date
- derived_metrics
- benchmark
- trend
- confidence
- limitations
- missing_data

Endpoint implementers must keep Pydantic response models, JSON schemas in `schemas/`, frontend TypeScript types, and this API spec aligned in the same change.

`GET /api/daily-report/latest` and `POST /api/analyze-stock` run a safety filter before returning responses. If a direct trading instruction phrase is detected during development or tests, the API returns an internal-safe error payload instead of the unsafe response.

## raw_store Boundary

Mock phases use `backend/app/raw_store/repository.py` as a repository interface over mock JSON-like fixtures. Live phases will replace the implementation with a SQLite-backed cache.

Rule engines must not call external APIs directly. Engines should receive raw snapshots through repository interfaces so data collection, caching, and deterministic scoring remain separate.

## Shared Schema Contracts

### ScoreComponent

All score-like objects share this contract:

```json
{
  "name": "entry_environment_score",
  "score": 72,
  "max_score": 100,
  "label": "watch_for_confirmation",
  "raw_data": {},
  "derived_metrics": {},
  "benchmark": {},
  "trend": {},
  "source": [],
  "source_date": "2026-04-24",
  "confidence": 0.82,
  "limitations": [],
  "missing_data": []
}
```

### Evidence

Evidence is represented by:

- `source`
- `source_date`
- `confidence`
- `limitations`
- `missing_data`

### RawData

Raw data is always an object under `raw_data`. It contains mock source snapshots in the MVP.

### Benchmark

Benchmark is always an object under `benchmark`. It contains thresholds, peer references, or rule cutoffs.

### Trend

Trend is always an object under `trend`. It contains direction, state, or comparison labels.

### Limitation

Limitations are arrays of strings under `limitations`.

### MissingData

Missing data is an array of strings under `missing_data`.

## DailyReport Schema

`GET /api/daily-report/latest` returns:

```json
{
  "date": "2026-04-24",
  "market": "US",
  "report_generated_at": "2026-04-24T08:00:00+00:00",
  "macro_regime": {},
  "market_timing": {},
  "overheat_risk": {},
  "crisis_risk": {},
  "crisis": {},
  "future_themes": [],
  "stock_candidates": [],
  "smart_money_summary": {},
  "smart_money": {},
  "risk_allocation": {},
  "risk_notes": [],
  "limitations": [],
  "missing_data": [],
  "human_verification_queue": [],
  "not_investment_advice": true
}
```

`smart_money_summary` and `smart_money` currently contain the same score object. `smart_money` is the stable frontend-facing field; `smart_money_summary` is retained for backwards compatibility.

### FutureTheme

Items in `future_themes` include:

```json
{
  "name": "theme_score",
  "theme": "AI energy infrastructure",
  "score": 84,
  "max_score": 100,
  "label": "heating_up",
  "raw_data": {},
  "derived_metrics": {
    "components": {
      "news_momentum_score": 0,
      "capital_flow_score": 0,
      "policy_support_score": 0,
      "technology_progress_score": 0,
      "commercialization_score": 0,
      "strategic_relevance_score": 0
    }
  },
  "benchmark": {},
  "trend": {},
  "source": [],
  "source_date": "2026-04-24",
  "confidence": 0.82,
  "limitations": [],
  "missing_data": [],
  "candidate_companies": []
}
```

### StockCandidate

Items in `stock_candidates` are typed objects:

```json
{
  "ticker": "NVDA",
  "company_name": "NVIDIA Corporation",
  "theme": "AI energy infrastructure",
  "leadership_score": 16.5,
  "smart_money_score": 72,
  "market_timing_score": 35,
  "overheat_score": 28,
  "risk_score": 40,
  "label": "worth_deep_research",
  "source": [],
  "source_date": "2026-04-24",
  "confidence": 0.82,
  "limitations": [],
  "missing_data": []
}
```

### RiskAllocation

`risk_allocation` returns reference labels only:

```json
{
  "risk_posture": "balanced_watch",
  "score": 50,
  "reference": {
    "market_risk": "balanced_watch",
    "volatility": "balanced_watch",
    "theme_research": "balanced_watch",
    "quality_filter": "balanced_watch"
  },
  "risk_flags": [],
  "raw_data": {},
  "derived_metrics": {},
  "benchmark": {},
  "trend": {},
  "source": [],
  "source_date": "2026-04-24",
  "confidence": 0.82,
  "limitations": [],
  "missing_data": []
}
```

Allowed `risk_posture` and `reference` labels:

- `risk_on_watch`
- `balanced_watch`
- `defensive_watch`
- `crisis_watch`
- `overheat_warning`
- `insufficient_data`

## StockAnalysis Schema

`POST /api/analyze-stock` returns:

```json
{
  "ticker": "NVDA",
  "market": "US",
  "company_profile": {},
  "leadership_score": {},
  "market_timing_context": {},
  "overheat_risk": {},
  "smart_money": {},
  "financial_quality": {},
  "valuation_context": {},
  "risk_flags": [],
  "missing_data": [],
  "human_verification_queue": [],
  "not_investment_advice": true
}
```

## Phase 5 Additions

`GET /api/daily-report/latest` includes:

- `macro_regime`: structured Macro Regime Engine output with components.
- `crisis`: structured Crisis Playbook Engine output with reference labels.
- `crisis_risk`: compatibility score object derived from `crisis`.

All Phase 5 data is mock-only. No live API integrations are used.

## Phase 6 Frontend Notes

The frontend uses relative API URLs:

- `/api/daily-report/latest`
- `/api/analyze-stock`

During Vite development, `/api` is proxied to the FastAPI backend at `http://localhost:8000`.

## Phase 7.5 Mock Endpoint Stabilization

The following originally planned endpoints are implemented with mock data:

- `/api/themes/latest`
- `/api/macro-regime/latest`
- `/api/raw-data/{ticker}`
- `/api/signals/{ticker}`

They are read-only validation endpoints. They do not connect to live market data APIs.

## Phase 7.1 Architecture Corrections

Before live data integrations, Phase 7.1 stabilizes:

- `stock_candidates` as typed `StockCandidate` objects.
- `future_themes` as `FutureTheme` objects from the Future Industry Radar engine.
- `risk_allocation` as a research-reference object without allocation percentages.
- Market Timing VIX confirmation: high VIX alone is not treated as favorable; full confirmation requires recent spike, falling VIX, and index stabilization.
- Overheat benchmark: primary index heat uses prior-cycle high gain, recent-trough gain, and distance from 52-week high. The 200-day extension field remains supplemental only.

## Phase 8 Live Market Price Data

Phase 8 adds a yfinance market price adapter behind the raw store boundary.

Configuration:

```powershell
$env:USE_LIVE_MARKET_DATA="true"
$env:MARKET_DATA_PROVIDER="yfinance"
uvicorn backend.app.main:app --reload
```

Mock mode remains the default. Live market data can also be requested for `GET /api/daily-report/latest` with `?use_live_market_data=true`.

Public response schemas remain stable. Live-vs-mock status is carried inside existing raw-data evidence fields such as `source`, `source_date`, and `raw_data.source_type`. Phase 8 does not connect 13F, Form 4, FRED, news, YouTube, options, or live theme data.
