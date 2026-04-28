# DATA_SOURCES.md

## MVP Rule

Mock fixtures remain the default. Phase 8 added opt-in live market prices, Phase 9 adds opt-in live FRED-compatible macro data for selected US macro fields, Phase 10.5 adds opt-in official SEC EDGAR Form 4 insider transactions, and Phase 11 adds opt-in official SEC EDGAR 13F institutional holdings. Phase 8.1 makes source status, freshness, and fallback state visible in API responses and the frontend.

## Phase 11 Official SEC EDGAR 13F

Default:

- `USE_LIVE_SEC_13F=false`
- no SEC 13F request is made
- repository functions return mock 13F snapshots with `source_type: "mock"`

Opt-in:

```powershell
$env:USE_LIVE_SEC_13F="true"
$env:SEC_13F_PROVIDER="sec_edgar"
$env:SEC_EDGAR_USER_AGENT="Your Name your.email@example.com"
$env:SEC_13F_TARGET_MANAGERS="0001067983"
uvicorn backend.app.main:app --reload
```

Implemented SEC endpoints:

- `https://data.sec.gov/submissions/CIK##########.json` for institutional manager filing discovery
- SEC EDGAR Archives filing indexes and XML information table documents

URL strategy:

- The submissions API is only for filing discovery and requires a 10-digit zero-padded CIK.
- The Archives filing directory uses CIK without leading zeros and accession numbers without dashes.
- The Archives `index.json` is the primary source for actual filing document names.
- If `index.json` is unavailable, `{accession-number}-index.html` is used as the bounded HTML fallback. The accession number keeps dashes in this filename.
- The XML download URL uses the actual XML filename discovered from `index.json` or the HTML index.
- The integration must not hardcode `form13fInfoTable.xml`; if a candidate XML returns 404, the next ranked candidate is tried.

No API key is required. SEC requests must include a proper `SEC_EDGAR_USER_AGENT`, and User-Agent values must never be returned by API responses or logs. `sec-api.io` is not a runtime provider.

Normalized holding fields include manager CIK, accession number, filing date, report date, issuer name, title of class, CUSIP, `reported_value_raw`, `reported_value_unit`, best-effort `value_usd`, `value_unit_confidence`, `value_normalization_note`, shares or principal amount, share type, put/call, investment discretion, other manager, voting authority, source status, limitations, and missing data.

13F value normalization:

- SEC 13F XML `<value>` is preserved as `reported_value_raw`.
- `value_usd` is the normalized value used by smart-money totals and top-holding rankings.
- Modern XML filings are not blindly multiplied by 1000. If no reliable price reference is available, the value is preserved as reported with `reported_value_unit: "as_reported"` and a low-confidence note.
- If a reliable price reference is available, the parser compares raw value and raw value times 1000 against shares times the reference price, then chooses `reported_value_unit: "usd"` or `reported_value_unit: "thousands_usd"` accordingly.
- `SEC_13F_ASSUME_VALUE_THOUSANDS=false` by default. Setting it true is a legacy override and should be used only when the source context requires that assumption.

Repository behavior:

- live SEC 13F fetches are made only through `backend.app.raw_store.repository`
- successful snapshots are cached under `backend/raw_store/cache/sec_13f` unless `SEC_13F_CACHE_DIR` overrides it
- cached live EDGAR data within `SEC_13F_CACHE_TTL_DAYS` returns `source_type: "cached_live"` with `provider: "SEC EDGAR"`
- daily reports are cache-first and do not perform live SEC 13F fetches unless `ALLOW_LIVE_FETCH_ON_REPORT_REQUEST=true`
- missing `SEC_EDGAR_USER_AGENT` or fetch failures return cached live data when available, otherwise mock fallback 13F data with `source_type: "fallback"`
- fallback metadata includes a safe summarized `fallback_reason` and does not expose stack traces or `SEC_EDGAR_USER_AGENT`
- smart-money engines consume normalized 13F snapshots from the raw store and do not call SEC directly
- fallback mock 13F does not boost smart-money score and is labeled insufficient data

Freshness:

- 13F source status uses `freshness_window: "quarterly_filing_delay"`
- `source_date` is the filing report date when available, otherwise filing date
- `fetched_at` is the cache/write or retrieval timestamp
- `report_generated_at` is only the daily report assembly timestamp
- 13F does not use `latest_expected_trading_day` or `form4_recent_180_days`

Limitations:

- 13F is delayed quarterly evidence and should not be interpreted as real-time institutional flow
- 13F may lag up to 45 days after quarter end
- 13F may not show shorts, many derivatives, or current positions
- manager-name discovery is limited to a small local mapping in v1; numeric CIKs are preferred
- SEC Form 13F Data Sets can be considered as a future batch optimization but are not required for Phase 11

## Phase 10.5 Official SEC EDGAR Form 4

Default:

- `USE_LIVE_SEC_FORM4=false`
- no SEC request is made
- repository functions return mock Form 4 snapshots with `source_type: "mock"`

Opt-in:

```powershell
$env:USE_LIVE_SEC_FORM4="true"
$env:SEC_FORM4_PROVIDER="sec_edgar"
$env:SEC_EDGAR_USER_AGENT="Your Name your.email@example.com"
uvicorn backend.app.main:app --reload
```

Implemented SEC endpoints:

- `https://www.sec.gov/files/company_tickers.json` for ticker to CIK mapping
- `https://data.sec.gov/submissions/CIK##########.json` for recent filing metadata
- SEC EDGAR Archives filing XML documents for Form 4 transaction details

No API key is required. SEC requests must include a proper `SEC_EDGAR_USER_AGENT`. Official SEC EDGAR is the runtime Form 4 provider. `sec-api.io` is no longer a runtime provider for this project. SEC EDGAR uses `SEC_EDGAR_USER_AGENT`, not an API key, and User-Agent values must never be returned by API responses.

Normalized fields include:

- ticker, CIK, accession number, filing date, and transaction date
- insider name, role, director/officer flags, and officer title
- transaction code and transaction category
- security title, shares, price, acquired/disposed code, value, ownership type, and direct/indirect ownership code
- source, source date, source status, limitations, and missing data

SEC EDGAR transaction rows are parsed from `nonDerivativeTable.nonDerivativeTransaction` and `derivativeTable.derivativeTransaction`. Holdings-only rows are not emitted as transactions. When source data does not provide transaction value directly, value is calculated as `shares * price`.

Transaction-code interpretation:

- `P` is counted as insider accumulation.
- `S` is counted as insider disposition.
- `M` is option exercise activity and is not counted as accumulation by default.
- `A` is grant or award activity and is not counted as accumulation by default.
- `F` is tax withholding activity and is not counted as accumulation by default.
- `G` is gift activity and is not counted as accumulation or disposition by default.
- `J`, unknown, and missing codes are classified as other unless later rule revisions add context-specific treatment.

Quality controls:

- Form 4 source freshness uses `freshness_window: "form4_recent_180_days"` and compares the latest filing date to the configured lookback window. It does not use latest expected trading day freshness.
- Duplicate transaction rows are removed using ticker, CIK, accession number, insider name, transaction date, transaction code, security title, shares, price, ownership type, and acquired/disposed code.
- Cached live EDGAR data within `SEC_FORM4_CACHE_TTL_HOURS` returns `source_type: "cached_live"` with `provider: "SEC EDGAR"`.
- Daily report raw Form 4 rows are capped at the latest 25 transactions by filing date and transaction date. Summary metrics still use all rows in the lookback window.
- Mock fallback Form 4 data is not used to boost smart-money score.
- If all live rows are missing transaction codes, the smart-money Form 4 component remains neutral or insufficient and reports `transaction_code` in `missing_data`.

Repository behavior:

- live SEC fetches are made only through `backend.app.raw_store.repository`
- successful snapshots are cached under `backend/raw_store/cache/sec` unless `SEC_FORM4_CACHE_DIR` overrides it
- daily reports are cache-first and do not perform live EDGAR fetches unless `ALLOW_LIVE_FETCH_ON_REPORT_REQUEST=true`
- missing `SEC_EDGAR_USER_AGENT` or fetch failures return cached live data when available, otherwise mock fallback Form 4 data with `source_type: "fallback"`
- fallback metadata includes a safe summarized `fallback_reason` and does not expose stack traces or `SEC_EDGAR_USER_AGENT`
- smart-money engines consume normalized Form 4 snapshots from the raw store and do not call SEC directly
- Phase 10.5 does not connect 13F, options, news, YouTube, or live theme APIs

Limitations:

- Form 4 transaction codes require context from compensation plans, ownership type, and reporting notes
- SEC submissions recent filings pagination is documented as a limitation when not followed
- awards, option exercises, tax withholding, gifts, and other non-open-market codes are not treated as accumulation by default
- Form 4 evidence is research context only and is not a trading instruction

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
- 13F, options, news, YouTube, and theme APIs

Repository behavior:

- live FRED fetches are made only through `backend.app.raw_store.repository`
- successful live macro snapshots are cached under `backend/raw_store/cache/macro` unless `MACRO_DATA_CACHE_DIR` overrides it
- missing API key, unsupported provider, or fetch failures return mock fallback macro data with `source_type: "fallback"`
- engines consume normalized macro snapshots from the raw store and do not call FRED directly
- FRED-backed components use `provider: "FRED"` and the yield spread uses `provider: "derived_from_FRED"`
- Macro snapshots that combine FRED-backed fields with Phase 9 mock-only fields use `source_type: "derived"` and `provider: "mixed_FRED_and_mock_macro"`
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

- `source_type`: `live`, `cached_live`, `mock`, `fallback`, `derived`, or `unknown`
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
- Mixed live/mock sources use `source_type: "derived"` with a provider such as `mixed_FRED_and_mock_macro` or `mixed_smart_money_sources`; do not use `mixed` as a `source_type`.

## Data Freshness Contract

- Market prices: latest expected US trading day.
- FRED daily rates: `daily_rate_5_business_days`.
- FRED monthly macro: `monthly_macro_latest_observation`.
- Form 4: `form4_recent_180_days`.
- 13F: `quarterly_filing_delay`, not daily freshness.
- Options future: requires an explicit provider-specific timestamp and should not use stale mock data.
- News/sentiment future: source timestamp and deduplication are required.
- Mock data is excluded from stale-data counts but must be disclosed as mock.

### 13F Freshness Rules

- 13F is quarterly batch data, not daily market data.
- 13F is delayed and must not use `latest_expected_trading_day`.
- 13F source status uses `quarterly_filing_delay`.
- 13F cache TTL should be measured in days, not hours.
- 13F should be refreshed around expected filing windows, not on every daily report request.
- 13F remains research evidence only and must not be treated as real-time smart-money confirmation.

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
