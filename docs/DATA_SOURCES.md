# DATA_SOURCES.md

## MVP Rule

Mock fixtures remain the default. Phase 8 added opt-in live market prices only; Phase 8.1 makes source status, freshness, and fallback state visible in API responses and the frontend.

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
- Mock data is never treated as fully fresh.
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
