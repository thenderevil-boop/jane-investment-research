# Jane Framework Daily Investment Research Assistant

This repo specification pack is designed to be copied into a new VSCode project and used with Codex.

## Purpose

Build a US-market-only daily investment research automation system based on Jane's Markdown investment framework.

This is not a trading system. It produces research signals, evidence, benchmarks, trends, confidence, and missing-data warnings.

## Current Implementation Status

`AGENTS.md` originally defined early planning phases for the MVP. The actual implementation has advanced to Phase 10.5 / 10.6.

Completed live integrations now documented in this README:

- Phase 8: yfinance market data
- Phase 9: FRED macro data
- Phase 10: official SEC EDGAR Form 4
- Phase 11: official SEC EDGAR 13F

Future phases should use README current status, JSON schemas, and tests as the implementation reference, while keeping AGENTS.md safety rules in force.

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

## Environment Variables Reference

| Variable | Default | Required for | Notes |
|---|---|---|---|
| USE_LIVE_MARKET_DATA | false | yfinance live prices | |
| MARKET_DATA_PROVIDER | yfinance | yfinance live prices | |
| USE_LIVE_MACRO_DATA | false | FRED live macro | |
| MACRO_DATA_PROVIDER | fred | FRED live macro | |
| FRED_API_KEY | none | FRED live macro | secret; never expose |
| USE_LIVE_SEC_FORM4 | false | SEC EDGAR Form 4 | |
| SEC_FORM4_PROVIDER | sec_edgar | SEC EDGAR Form 4 | |
| SEC_EDGAR_USER_AGENT | none | SEC EDGAR Form 4 | required; never expose |
| SEC_EDGAR_REQUEST_DELAY_SECONDS | 0.2 | SEC EDGAR Form 4 | |
| SEC_FORM4_CACHE_TTL_HOURS | 24 | SEC EDGAR Form 4 cache | |
| SEC_FORM4_LOOKBACK_DAYS | 180 | SEC EDGAR Form 4 | |
| USE_LIVE_SEC_13F | false | SEC EDGAR 13F | |
| SEC_13F_PROVIDER | sec_edgar | SEC EDGAR 13F | official SEC EDGAR only |
| SEC_13F_CACHE_TTL_DAYS | 7 | SEC EDGAR 13F cache | TTL is days, not hours |
| SEC_13F_LOOKBACK_QUARTERS | 4 | SEC EDGAR 13F | |
| SEC_13F_TARGET_MANAGERS | none | SEC EDGAR 13F | optional comma-separated manager names or CIKs |
| SEC_13F_TARGET_TICKERS | none | SEC EDGAR 13F | optional comma-separated tickers for future mapping support |
| SEC_13F_ASSUME_VALUE_THOUSANDS | false | SEC EDGAR 13F | legacy fallback only; modern XML values are preserved unless disambiguated |
| ALLOW_LIVE_FETCH_ON_REPORT_REQUEST | false | quota guard | default should remain false |

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

## Phase 8 Live Market Price Data

Market price data can now be enabled for US-listed tickers and index proxies through the repository-backed yfinance adapter. Mock mode remains the default.

Keep mock mode:

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
$env:USE_LIVE_MARKET_DATA="false"
uvicorn backend.app.main:app --reload
```

Enable live market prices:

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
$env:USE_LIVE_MARKET_DATA="true"
$env:MARKET_DATA_PROVIDER="yfinance"
uvicorn backend.app.main:app --reload
```

You can also request a live-backed daily report for one call:

```powershell
Invoke-RestMethod "http://localhost:8000/api/daily-report/latest?use_live_market_data=true"
```

Phase 8 only covers OHLCV market prices for `SPY`, `QQQ`, `^VIX`, and requested watchlist tickers. Macro, SEC, options, news, YouTube, and theme evidence are still mock or manually verified placeholders. yfinance is suitable for MVP research reference only; it is not an official exchange feed and may have delays, gaps, adjustments, or availability limits.

## Phase 8.1 Data Source Visibility

Daily report, stock analysis, and raw-data responses now expose additive source metadata:

- `source_status` on source-aware components
- `data_quality` summary on daily report and stock analysis

`source_type` meanings:

- `live`: repository-backed live market price data
- `cached_live`: cached repository-backed live data within the configured cache window
- `mock`: deterministic fixture data
- `fallback`: mock data used after live market price data was unavailable
- `derived`: summary across multiple components
- `unknown`: source could not be classified

Freshness rules:

- Daily market data is fresh when `source_date` is within the latest expected trading-day window.
- FRED Treasury yield series are fresh within `daily_rate_5_business_days`.
- FRED monthly macro series use `monthly_macro_latest_observation`.
- Derived FRED fields use `derived_from_FRED` and inherit the strictest relevant input freshness.
- Mock data is counted as mock reference data, not stale live data.
- Missing source dates are marked in `missing_data`.
- Fallbacks include a safe summarized `fallback_reason` and do not expose stack traces.

Enable live market data with:

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
$env:USE_LIVE_MARKET_DATA="true"
$env:MARKET_DATA_PROVIDER="yfinance"
uvicorn backend.app.main:app --reload
```

Live market data remains limited to US market prices. FRED, SEC filings, news, YouTube, options, and 13F integrations are not connected yet.

## Phase 9 Live Macro / FRED Data

Selected US macro indicators can now be enabled through the repository-backed FRED adapter. Mock macro mode remains the default.

Keep mock macro mode:

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
$env:USE_LIVE_MACRO_DATA="false"
uvicorn backend.app.main:app --reload
```

Enable live FRED-backed macro fields:

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
$env:USE_LIVE_MACRO_DATA="true"
$env:FRED_API_KEY="your_key_here"
$env:MACRO_DATA_PROVIDER="fred"
uvicorn backend.app.main:app --reload
```

Live Phase 9 fields:

- Effective Federal Funds Rate and `fed_policy_trend`
- 10-year Treasury yield and 2-year Treasury yield
- `ten_year_minus_two_year_spread_bps`, derived from FRED yields
- CPI YoY
- PPI YoY
- unemployment rate and `unemployment_trend`

Still mock in Phase 9:

- ISM Manufacturing PMI
- DXY trend
- gold trend
- oil trend
- Fear & Greed
- macro equity drawdown context unless live market prices are separately enabled

If `USE_LIVE_MACRO_DATA=true` but `FRED_API_KEY` is missing, FRED is unavailable, or the provider is unsupported, the raw store returns deterministic mock fallback macro data with `source_type="fallback"`. FRED release schedules can lag the current date, so live macro components include release-delay limitations and may require human verification.

Phase 9.1 keeps `/api/daily-report/latest` compact: FRED raw payloads include latest/previous values and bounded recent observations instead of full historical series. The report `date` is the current report date, `report_generated_at` is the actual generation timestamp, and each data source keeps its own `source_date`.

## Phase 10 Live SEC Form 4 Insider Transactions

SEC Form 4 insider transactions can now be enabled through the repository-backed SEC EDGAR adapter. Mock Form 4 remains the default.

Keep mock Form 4 mode:

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
$env:USE_LIVE_SEC_FORM4="false"
uvicorn backend.app.main:app --reload
```

Enable live SEC Form 4:

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
$env:USE_LIVE_SEC_FORM4="true"
$env:SEC_FORM4_PROVIDER="sec_edgar"
$env:SEC_EDGAR_USER_AGENT="Your Name your.email@example.com"
uvicorn backend.app.main:app --reload
```

`SEC_EDGAR_USER_AGENT` is required for official SEC EDGAR public endpoints. No API key is required. If the User-Agent is missing or a fetch fails, the raw store returns deterministic mock fallback Form 4 data with `source_type="fallback"` and a safe `fallback_reason`. User-Agent values are never returned by API responses.

Phase 10 only connects SEC Form 4 insider transactions. Phase 11 separately connects SEC 13F institutional holdings. Options, news, YouTube, and live theme APIs remain mock or manually verified placeholders.

Form 4 transaction-code handling:

- `P` is counted as insider accumulation.
- `S` is counted as insider disposition.
- `M`, `A`, `F`, `G`, `J`, and unknown or missing codes are not counted as accumulation by default.
- Official SEC EDGAR mode parses Form 4 XML transaction rows from the SEC Archives.
- Form 4 freshness uses `form4_recent_180_days` based on latest filing date.
- Duplicate transaction rows are removed by ticker, accession number, insider name, transaction date, code, security title, shares, price, and ownership type.
- Daily report raw Form 4 transactions are capped at the latest 25 rows while summary metrics use all rows in the lookback window.
- Mock fallback Form 4 data is not used to boost smart-money score.
- Form 4 output is research evidence only and is not a trading instruction.

## Phase 11 Official SEC EDGAR 13F

SEC 13F institutional holdings can now be enabled through the repository-backed official SEC EDGAR adapter. Mock 13F remains the default.

Keep mock 13F mode:

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
$env:USE_LIVE_SEC_13F="false"
uvicorn backend.app.main:app --reload
```

Enable live SEC 13F:

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
$env:USE_LIVE_SEC_13F="true"
$env:SEC_13F_PROVIDER="sec_edgar"
$env:SEC_EDGAR_USER_AGENT="Your Name your.email@example.com"
$env:SEC_13F_TARGET_MANAGERS="0001067983"
uvicorn backend.app.main:app --reload
```

Implemented SEC sources:

- `data.sec.gov/submissions/CIK##########.json` for institutional manager filing discovery.
- `www.sec.gov/Archives/edgar/data/...` filing directories for actual document discovery and XML information tables.

SEC 13F URL strategy:

- The submissions API is only used to discover filing history. Its CIK must be zero-padded to 10 digits.
- The Archives filing path uses CIK without leading zeros and accession numbers without dashes.
- The Archives `index.json` is tried first to discover the actual information table XML filename.
- If `index.json` is unavailable, the filing detail HTML page `{accession-number}-index.html` is used as a fallback.
- The information table filename is not assumed to be `form13fInfoTable.xml`; actual XML filenames are ranked from the filing index.
- The index HTML filename keeps dashes in the accession number.

13F source status uses `freshness_window="quarterly_filing_delay"`. It does not use market latest-trading-day freshness or Form 4 recency rules. 13F is delayed quarterly evidence, may lag up to 45 days after quarter end, and may not show shorts, many derivatives, or current positions.

13F value normalization:

- The raw XML `<value>` is preserved as `reported_value_raw`.
- `value_usd` is a best-effort normalized USD value used for totals and top-holding rankings.
- The backend no longer blindly multiplies every SEC 13F XML value by 1000. When a reliable price reference is not available, modern XML values are preserved as reported with `reported_value_unit="as_reported"`.
- If a reliable price reference is available, the parser can choose between `reported_value_unit="usd"` and `reported_value_unit="thousands_usd"` based on which interpretation is closer to shares times the reference price.
- `value_unit_confidence` and `value_normalization_note` explain the normalization decision. `SEC_13F_ASSUME_VALUE_THOUSANDS=true` is only a legacy override and is false by default.

Repository behavior:

- Daily reports are cache-first and do not repeatedly live-fetch SEC 13F unless `ALLOW_LIVE_FETCH_ON_REPORT_REQUEST=true`.
- Cached live SEC 13F data within `SEC_13F_CACHE_TTL_DAYS` returns `source_type="cached_live"` with `provider="SEC EDGAR"`.
- Missing `SEC_EDGAR_USER_AGENT` returns fallback mock 13F with `fallback_reason="SEC_EDGAR_USER_AGENT missing"` and never exposes the User-Agent value.
- Fallback mock 13F does not boost smart-money score and is labeled insufficient data.
- Manager-name discovery is limited to a small local mapping in v1; numeric CIKs are preferred.
- SEC Form 13F Data Sets may be considered later as a batch optimization, but Phase 11 does not depend on them.

## Project Guardrails

Before changing an endpoint, verify Pydantic models, JSON schemas under `schemas\`, frontend TypeScript types, and `docs\API_SPEC.md` together. Mock raw data should be accessed through `backend.app.raw_store.repository`; live API clients should not be called from engines directly.
