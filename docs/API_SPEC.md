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

Environment-controlled live macro behavior:

- `USE_LIVE_MACRO_DATA=false` by default keeps macro data on deterministic mock fixtures.
- `USE_LIVE_MACRO_DATA=true` with `FRED_API_KEY` attempts repository-backed FRED fetches for selected macro fields.
- Missing `FRED_API_KEY`, unsupported provider, or FRED fetch failure falls back to mock macro data with `source_type="fallback"`.

Environment-controlled live SEC Form 4 behavior:

- `USE_LIVE_SEC_FORM4=false` by default keeps insider Form 4 data on deterministic mock fixtures.
- `USE_LIVE_SEC_FORM4=true` with `SEC_FORM4_PROVIDER=sec_edgar` and `SEC_EDGAR_USER_AGENT` attempts repository-backed official SEC EDGAR fetches for Form 4 insider transactions.
- Missing required credentials or fetch failures fall back to mock Form 4 data with `source_type="fallback"`.
- `SEC_EDGAR_USER_AGENT` is never exposed in API responses.

Response shape:

```json
{
  "date": "2026-04-27",
  "market": "US",
  "report_generated_at": "2026-04-27T08:00:00+00:00",
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
  "data_quality": {
    "mode": "mixed",
    "live_components": 4,
    "mock_components": 8,
    "fallback_components": 1,
    "stale_components": 2,
    "missing_source_date_components": 0,
    "limitations": []
  },
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
In Phase 10.5, `raw_data.sec_form4_snapshot` may contain SEC EDGAR-backed Form 4 transactions when `USE_LIVE_SEC_FORM4=true` and `SEC_EDGAR_USER_AGENT` is configured.

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

### GET /api/data-health

Returns safe provider configuration status for yfinance, FRED, SEC EDGAR, and mock sources. The response does not expose secrets or SEC EDGAR User-Agent values.

`source_type` values may include `live`, `cached_live`, `fallback`, `mock`, and `derived`.

## Phase 8.1 Data Source Visibility

Phase 8.1 adds non-breaking metadata fields:

- `source_status`: optional object on score-like components, stock candidates, raw-data responses, and stock analysis responses.
- `data_quality`: optional summary on daily report and stock analysis responses.

`source_status` shape:

```json
{
  "source_type": "live",
  "provider": "yfinance",
  "source_date": "2026-04-24",
  "fetched_at": "2026-04-24T20:30:00+00:00",
  "is_fresh": true,
  "freshness_window": "latest_expected_trading_day",
  "fallback_used": false,
  "fallback_reason": null,
  "limitations": [],
  "missing_data": []
}
```

Allowed `source_type` values:

- `live`: repository-backed live market price data.
- `cached_live`: cached repository-backed live data that remains within the configured cache freshness window.
- `mock`: deterministic mock fixture data.
- `fallback`: mock data used because a live market price fetch was unavailable.
- `derived`: summary metadata derived from multiple components.
- `unknown`: source metadata could not be classified.

Freshness rules:

- Daily market data is fresh when `source_date` matches the latest expected trading day.
- FRED daily rate series use `freshness_window="daily_rate_5_business_days"`.
- FRED monthly macro series use `freshness_window="monthly_macro_latest_observation"`.
- FRED-derived fields use `freshness_window="derived_from_FRED"` and inherit freshness from their input series. If an input series is stale, the derived field is stale and includes the stale input in `missing_data`.
- For monthly FRED series, `source_date` is the observation month being measured, not the report generation date or the FRED release timestamp. The MVP treats monthly observations within 70 calendar days of report generation as fresh to account for normal release delay.
- Mock data is classified as mock reference data and does not count as stale solely because it is not live.
- Stale applies only to live, fallback, or derived components with outdated `source_date`.
- Fallback data sets `fallback_used=true` and includes a safe `fallback_reason`.
- Missing `source_date` sets `is_fresh=false`, adds `source_date` to `missing_data`, and increments `missing_source_date_components`.
- Nested live market snapshots under `index_market_data` use the same aggregate market snapshot source date for SPY and QQQ freshness checks.
- `crisis.source_status` is derived from crisis components with `provider="derived_from_crisis_components"`.

`data_quality` shape:

```json
{
  "mode": "live_with_fallback",
  "live_components": 4,
  "mock_components": 8,
  "fallback_components": 1,
  "stale_components": 2,
  "missing_source_date_components": 0,
  "limitations": [
    "Some components use fallback data because live data was unavailable."
  ]
}
```

Allowed `mode` values are `all_mock`, `mixed`, `mostly_live`, and `live_with_fallback`.

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

For live FRED macro data, `/api/daily-report/latest` includes compact `raw_fred_snapshot.raw_series` summaries instead of full historical observations. Each series summary includes `series_id`, `latest_date`, `latest_value`, `previous_value`, a bounded `recent_observations` array, `source_status`, `limitations`, and `missing_data`. Full macro raw-series access is reserved for a future `GET /api/raw-data/macro/{series_id}` endpoint.

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

`date` is the report date. `report_generated_at` is the actual generation timestamp. `source_date` remains source-specific on each score, component, candidate, and source-status object.

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

Public response schemas remain stable. Phase 8.1 adds `source_status` and `data_quality` as additive metadata so clients can distinguish live, mock, fallback, stale, and missing-source-date components. Phase 8.2 clarifies that mock components are mock reference data, not stale live data, and that market timing / overheat subcomponents derived from yfinance carry `source_type="derived"` with `provider="derived_from_yfinance"`. Phase 8 does not connect 13F, Form 4, FRED, news, YouTube, options, or live theme data.

Phase 8.3 keeps nested SPY / QQQ market snapshots aligned with the aggregate live market snapshot date and ensures crisis aggregate source status is always present as derived component metadata.

## Phase 9 Live Macro / FRED Data

Phase 9 adds an opt-in FRED-compatible macro adapter behind the raw store boundary. Public response schemas remain stable; live/fallback/mixed state is exposed through existing `source_status`, `raw_data`, `limitations`, `missing_data`, and `data_quality` fields.

PowerShell:

```powershell
$env:USE_LIVE_MACRO_DATA="true"
$env:FRED_API_KEY="your_key_here"
$env:MACRO_DATA_PROVIDER="fred"
uvicorn backend.app.main:app --reload
```

Live FRED-backed fields in `macro_regime`:

- `fed_policy_trend` from `FEDFUNDS`
- `ten_year_minus_two_year_spread_bps` derived from `DGS10` and `DGS2`
- `cpi_yoy` from `CPIAUCSL`
- `ppi_yoy` from `PPIACO`
- `unemployment_rate` and `unemployment_trend` from `UNRATE`

Still mock in Phase 9:

- `ism_manufacturing_pmi`
- `dxy_trend`
- `gold_trend`
- `oil_trend`
- `fear_greed`

FRED release schedules may lag the current date. When live macro is enabled, `data_quality.live_components` counts FRED-backed macro components, while mock-only macro components remain visible as mock. If live macro fetch fails, macro source metadata is marked as fallback and the report adds macro missing-data and limitation notes.

Phase 9.1 cleanup:

- FRED freshness is series-aware: Treasury yield series use `daily_rate_5_business_days`; monthly macro releases use `monthly_macro_latest_observation`; derived FRED values use `derived_from_FRED`.
- `/api/daily-report/latest` exposes compact FRED raw-series summaries and does not include full historical FRED observations.
- `date` reflects the current report date, while `report_generated_at` is the actual report generation timestamp.

Phase 9.2 monthly FRED freshness:

- Monthly series (`FEDFUNDS`, `CPIAUCSL`, `PPIACO`, and `UNRATE`) are evaluated using observation-month freshness rather than latest-trading-day freshness.
- A March 2026 monthly observation can be fresh in an April 27, 2026 report because the observation date is the measured month, while release schedules can lag.
- Every live FRED component source status should propagate the macro snapshot `fetched_at` timestamp when available.

## Phase 10.5 Official SEC EDGAR Form 4

Phase 10.5 uses official SEC EDGAR Form 4 insider transactions behind the raw-store boundary. Public response schemas remain stable; live, cached, fallback, mock, and mixed state is exposed through existing `source_status`, `raw_data`, `limitations`, `missing_data`, and `data_quality` fields.

PowerShell:

```powershell
$env:USE_LIVE_SEC_FORM4="true"
$env:SEC_FORM4_PROVIDER="sec_edgar"
$env:SEC_EDGAR_USER_AGENT="Your Name your.email@example.com"
uvicorn backend.app.main:app --reload
```

`SEC_EDGAR_USER_AGENT` is required by official SEC endpoints. No API key is required.

Live SEC-backed fields in `smart_money_summary.raw_data.form4.transactions`:

- `ticker`
- `cik`
- `accession_number`
- `filing_date`
- `transaction_date`
- `insider_name`
- `role`
- `is_director`
- `is_officer`
- `officer_title`
- `security_title`
- `transaction_code`
- `transaction_category`
- `shares`
- `price`
- `acquired_disposed_code`
- `value`
- `ownership_type`
- `direct_or_indirect_ownership`
- `source`
- `source_date`
- `source_status`

Smart-money derived metrics include:

- `net_insider_accumulation_value_180d`
- `total_transactions_180d`
- `accumulation_count_180d`
- `disposition_count_180d`
- `officer_accumulation_count`
- `director_accumulation_count`
- `founder_or_ceo_accumulation`
- `largest_accumulation_value`
- `latest_transaction_date`
- `latest_filing_date`

Transaction-code treatment:

- `P` counts as insider accumulation.
- `S` counts as insider disposition.
- `M` is option exercise, `A` is award, `F` is tax withholding, `G` is gift, and `J` or unknown/missing codes are other.
- Only `P` counts toward accumulation. Only `S` counts toward disposition.

Parsing and quality controls:

- Official SEC EDGAR mode uses `company_tickers.json` for ticker-to-CIK mapping, company submissions JSON for recent Form 4 filing metadata, and SEC Archives XML documents for transaction rows.
- XML parsing reads `nonDerivativeTable.nonDerivativeTransaction` and `derivativeTable.derivativeTransaction`.
- Holdings-only rows are not emitted as transactions.
- Duplicate rows are removed using ticker, CIK, accession number, insider name, transaction date, transaction code, security title, shares, price, ownership type, and acquired/disposed code.
- Form 4 source status uses `freshness_window="form4_recent_180_days"` based on latest filing date within the 180-day lookback by default.
- Cached live EDGAR data within `SEC_FORM4_CACHE_TTL_HOURS` returns `source_type="cached_live"` and `provider="SEC EDGAR"`.
- Daily report raw Form 4 transactions are capped at the latest 25 rows. Derived summary metrics use all rows in the lookback window.
- Mock fallback Form 4 data is not used to boost the smart-money score.
- If all live Form 4 rows are missing transaction codes, `transaction_code` appears in `missing_data` and the Form 4 component does not boost the smart-money score.

Still mock after Phase 10:

- 13F institutional data
- options activity
- news, YouTube, and live theme evidence

If SEC EDGAR is unavailable or `SEC_EDGAR_USER_AGENT` is missing, API responses mark the Form 4 component with `source_type="fallback"`, include a safe `fallback_reason`, and use deterministic mock fallback transactions unless usable cached live data is available. Form 4 evidence is research context only and is not a trading instruction.
