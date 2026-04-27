# DATA_SOURCES.md

## MVP Rule

Phase 1 uses mock data only.

Live data integrations come later.

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
