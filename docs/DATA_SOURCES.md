# DATA_SOURCES.md

## MVP Rule

Mock fixtures remain the default. Phase 8 added opt-in live market prices, and Phase 9 adds opt-in live FRED-compatible macro data for selected US macro fields. Phase 8.1 makes source status, freshness, and fallback state visible in API responses and the frontend.

## Phase 9 Live Macro / FRED

Default:

- `USE_LIVE_MACRO_DATA=false`
- no FRED request is made
- repository functions return mock macro snapshots with `source_type: "mock"`

Opt-in:

```powershell
$env:USE_LIVE_MACRO_DATA="true"
$env:FRED_API_KEY="your_key_here"
$env:MACRO_DATA_PROVIDER="fred"
uvicorn backend.app.main:app --reload
```

Implemented FRED series:

- `FEDFUNDS`: Effective Federal Funds Rate
- `DGS10`: 10-Year Treasury Constant Maturity Rate
- `DGS2`: 2-Year Treasury Constant Maturity Rate
- `CPIAUCSL`: CPI
- `PPIACO`: PPI
- `UNRATE`: unemployment rate

Derived fields:

- `ten_year_minus_two_year_spread_bps = (DGS10 - DGS2) * 100`
- `cpi_yoy`
- `ppi_yoy`
- `unemployment_trend`
- `fed_policy_trend`

Still mock in Phase 9:

- ISM Manufacturing PMI
- DXY trend
- gold trend
- oil trend
- Fear & Greed
- SEC filings, options, news, YouTube, 13F, Form 4, and theme APIs

Repository behavior:

- live FRED fetches are made only through `backend.app.raw_store.repository`
- successful live macro snapshots are cached under `backend/raw_store/cache/macro` unless `MACRO_DATA_CACHE_DIR` overrides it
- missing API key, unsupported provider, or fetch failures return mock fallback macro data with `source_type: "fallback"`
- engines consume normalized macro snapshots from the raw store and do not call FRED directly
- FRED-backed components use `provider: "FRED"` and the yield spread uses `provider: "derived_from_FRED"`
- daily reports expose compact FRED raw summaries, not full historical observation arrays

FRED freshness windows:

- `DGS10` and `DGS2`: `daily_rate_5_business_days`
- `FEDFUNDS`, `CPIAUCSL`, `PPIACO`, and `UNRATE`: `monthly_macro_latest_observation`
- derived FRED values use `derived_from_FRED` and inherit the strictest freshness decision from their input series

Limitations:

- FRED macro series may be delayed depending on release schedule
- Monthly FRED `source_date` is the observation month being measured, not the report generation date or the public release timestamp
- Monthly FRED freshness uses observation-month semantics; for the MVP, a latest observation within 70 calendar days of report generation is considered fresh
- CPI, PPI, unemployment, and rate series update on different calendars
- unavailable FRED fields are marked in `missing_data`
- full FRED history is intentionally not included in `/api/daily-report/latest`; a future endpoint may expose `GET /api/raw-data/macro/{series_id}` for audited raw series access

## Phase 8 Live Market Prices

Phase 8 adds an opt-in live market price adapter for US market research reference data only.

Default:

- `USE_LIVE_MARKET_DATA=false`
- no network market price request is made
- repository functions return mock market snapshots with `source_type: "mock"`

Opt-in:

```powershell
$env:USE_LIVE_MARKET_DATA="true"
$env:MARKET_DATA_PROVIDER="yfinance"
uvicorn backend.app.main:app --reload
```

Implemented source:

- yfinance

Implemented symbols:

- `SPY`
- `QQQ`
- `^VIX`
- requested US watchlist tickers

Normalized OHLCV snapshots include:

- ticker
- source
- source date
- period
- interval
- rows with date, open, high, low, close, volume
- limitations
- missing data

Repository behavior:

- live fetches are made only through `backend.app.raw_store.repository`
- successful live snapshots are cached under `backend/raw_store/cache` unless `MARKET_DATA_CACHE_DIR` overrides it
- failed live fetches fall back to mock market data, set `source_type: "fallback"`, set `fallback_used: true`, and mark missing live market price data
- engines do not call yfinance directly

## Phase 8.1 Source Status

Every source-aware response can include:

- `source_type`: `live`, `mock`, `fallback`, `derived`, or `unknown`
- `provider`: data provider or fixture identifier
- `source_date`: date of the underlying source observation
- `fetched_at`: cache/write timestamp when available
- `is_fresh`: freshness decision; mock reference data does not count as stale solely because it is mock
- `freshness_window`: rule used for freshness
- `fallback_used`: whether a fallback was used
- `fallback_reason`: safe summarized reason, without stack traces
- `limitations`
- `missing_data`

Freshness semantics:

- live/fallback/derived components are stale only when `source_date` is older than the latest expected trading day
- FRED macro components use series-aware freshness windows instead of the market trading-day rule
- mock components are counted as mock components, not stale components
- components with no source date are counted separately as missing-source-date components
- nested SPY and QQQ live market feature snapshots inherit the aggregate market snapshot date for source-status consistency
- crisis aggregate source status is derived from its component source dates

Cache behavior:

- live mode fetches fresh yfinance data through the adapter and writes a cache snapshot
- stale cache files are not used as the source of truth when live fetch is requested
- if live fetch fails, repository fallback metadata explicitly marks fallback usage

Freshness rules:

- Daily market data is fresh if `source_date` is within the latest expected trading-day window.
- FRED daily rate data is fresh if `source_date` is within 5 business days.
- FRED monthly macro data uses `monthly_macro_latest_observation`: the observation date represents the month measured, and the MVP treats observations within 70 calendar days of report generation as fresh to account for FRED release delay.
- Derived FRED data is fresh only when the relevant input series are fresh; if an input is stale, the derived status records the stale input in `missing_data`.
- Mock data is counted as mock reference data and is excluded from stale-live counts.
- Fallback data is not treated as fully fresh and must disclose the fallback reason.
- Missing `source_date` adds `source_date` to `missing_data`.

Fallback behavior:

- yfinance failures do not reach engines directly.
- The raw store returns deterministic mock fallback data.
- API users see `source_type: "fallback"`, `provider: "mock"`, and the limitation `Live market data unavailable; mock fallback used.`
- Stack traces are not exposed.

Interpretation:

- `live` means live market-price data was available for price-derived fields only.
- `mock` means deterministic fixtures are being used.
- `fallback` means the system attempted live market data and used mock data after an unavailable fetch.
- `derived` means the status summarizes multiple component statuses.

Limitations:

- yfinance is acceptable for MVP research reference only
- it is not an official exchange feed
- data can be delayed, unavailable, adjusted, or incomplete
- Phase 8 does not connect macro, SEC filings, options, news, YouTube, or live theme evidence

## Target Data Sources by Module

### Market Prices

Purpose:

- S&P 500 / Nasdaq drawdown
- individual stock price and volume
- overextension
- consolidation

Potential sources:

- Polygon.io
- Alpha Vantage
- Tiingo
- Yahoo Finance unofficial packages for prototype only

### Macro

Purpose:

- Fed policy
- yield curve
- recession risk
- inflation pressure

Potential sources:

- FRED
- Federal Reserve official data
- BLS for CPI / unemployment
- ISM data if licensed or manually updated

### Market Sentiment

Purpose:

- CNN Fear & Greed
- VIX
- news sentiment

Potential sources:

- CNN Fear & Greed page or vendor API where available
- CBOE / market data vendor for VIX
- News API providers

### SEC Filings

Purpose:

- 13F institutional holdings
- Form 4 insider transactions
- 10-K / 10-Q fundamentals

Potential sources:

- SEC EDGAR APIs
- sec-companyfacts
- SEC submissions API

### Options Flow

Purpose:

- abnormal options volume
- call/put ratio
- open interest

Potential sources:

- market data vendors
- Polygon options data
- CBOE data if available

### News and Hype

Purpose:

- media hype ratio
- future theme momentum
- geopolitical crisis detection

Potential sources:

- NewsAPI
- GDELT
- Reuters / AP if licensed
- RSS feeds

### YouTube Hype

Purpose:

- YouTube hype ratio

Potential sources:

- YouTube Data API

Limitations:

- API quotas
- incomplete coverage
- noisy titles
- potential false positives

### Stablecoin / Digital Money

Purpose:

- USDC / USDT supply
- stablecoin market share
- digital asset rails

Potential sources:

- DeFiLlama stablecoins
- issuer transparency pages
- CoinMetrics if licensed

## Data Quality Rules

Every source integration must return:

- source name
- source URL or identifier
- source date
- retrieved_at
- raw data snapshot
- transformation status
- error status if any

## Missing Data Rules

If a source is unavailable:

1. Do not fabricate.
2. Mark missing data explicitly.
3. Lower confidence.
4. Add to human verification queue when material.
