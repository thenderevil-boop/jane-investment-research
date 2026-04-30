# DAILY_AUTOMATION_SPEC.md

## Purpose

The daily automation pipeline generates a daily investment research report based on Jane's framework.

It should not wait for a user to enter a ticker. It should run on a watchlist, theme list, and market data.

## Suggested Schedule

For a Taiwan-based user following US markets:

```text
Daily after US market close
Preferred local report time: 06:30 to 08:00 Asia/Taipei
```

## Daily Pipeline Steps

```text
1. Update market prices
2. Update VIX, DXY, yields, gold, oil, major ETFs
3. Update macro data when available
4. Keep CNN Fear & Greed excluded unless a licensed/stable provider is selected
5. Update news and theme mentions
6. Update YouTube hype metrics if available
7. Update SEC Form 4 insider transactions
8. Update options abnormal activity if available
9. Update 13F only when new quarterly filings are available
10. Recalculate features
11. Run rule engines
12. Generate daily report
13. Store report
14. Expose report through API
```

## Daily Report Sections

The daily report must include:

1. Market Status
   - macro regime
   - market timing environment
   - overheat risk
   - crisis risk

2. Key Market Changes
   - S&P 500 / Nasdaq trend
   - drawdown or overextension
   - VIX
   - DXY
   - 10Y-2Y spread
   - Fed policy state
   - Jane methodology reference conditions

3. Smart Money Signals
   - insider Form 4 changes
   - options abnormal activity
   - latest 13F institutional updates if available

4. Future Industry Radar
   - heating themes
   - cooling themes
   - new theme evidence

5. Candidate Stock Radar
   - newly added candidates
   - score increases
   - score decreases
   - high-risk names

6. Risk Notes
   - overheat
   - leverage risk
   - high debt
   - insider selling
   - media hype
   - missing data

7. Human Verification Queue
   - important but unverified news
   - incomplete source data
   - conflicting indicators

## Report Storage

For MVP, store daily reports in SQLite or JSON files.

Required fields:

- date
- market
- report_generated_at
- macro_regime
- market_timing
- overheat_risk
- crisis_risk
- future_themes
- stock_candidates
- smart_money_summary
- risk_notes
- missing_data
- human_verification_queue
- not_investment_advice

## Failure Handling

If data is missing:

- do not fail silently
- set confidence lower
- add item to `missing_data`
- add item to `human_verification_queue` if important

## MVP Rule

Phase 1 must use mock data only.
Do not connect live APIs before schemas, engines, and tests are stable.
