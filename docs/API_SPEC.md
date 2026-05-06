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

Phase 13 keeps this endpoint as background context, source health, cache warmup, and market-environment snapshot support. It is snapshot-first and is not the primary user workflow. `POST /api/analyze-stock` is the primary workflow for user-provided ticker validation.

Phase 11.5 defaults this endpoint to `DAILY_REPORT_READ_MODE=snapshot_first`. When a fresh daily snapshot exists in raw store, the endpoint returns that snapshot without refreshing live providers. The top-level `source_status` uses schema-compatible `source_type="derived"` and `provider="daily_report_snapshot"` to identify snapshot-served reports. If the snapshot is missing or stale, the endpoint computes the report only when `DAILY_BATCH_ALLOW_LIVE_FETCH=true`; otherwise it returns a safe 503 payload with `not_investment_advice=true`.

Phase 11.5a adds `daily_report_metadata` to `/api/daily-report/latest` responses and stale-snapshot 503 details. Metadata includes `read_mode`, `snapshot_used`, `snapshot_id`, `snapshot_generated_at`, `snapshot_is_fresh`, `batch_refresh_status`, `batch_refresh_started_at`, `batch_refresh_completed_at`, and `batch_duration_ms`. The endpoint must not silently recompute without this metadata.

Phase 15.5 keeps daily reports snapshot-first while stabilizing architecture. Daily batch refresh uses a per-job context instead of mutating global config for report live-fetch or price-reference warmup flags. Daily report candidates are config-driven through `DEFAULT_DAILY_REPORT_CANDIDATES`, with safe defaults matching the existing NVDA and TSLA background candidates. `smart_money` is canonical; `smart_money_summary` is deprecated and retained as an equal backward-compatible alias.

Optional query parameter:

- `use_live_market_data`: boolean. Defaults to environment configuration. When `true`, the backend attempts repository-backed yfinance OHLCV fetches for market price fields and falls back to mock market data if the fetch fails.

Environment-controlled live macro behavior:

- `USE_LIVE_MACRO_DATA=false` by default keeps macro data on deterministic mock fixtures.
- `USE_LIVE_MACRO_DATA=true` with `FRED_API_KEY` attempts repository-backed FRED fetches for selected macro fields.
- FRED transient 5xx/timeout failures are retried with a bounded adapter budget.
- If a FRED live refresh fails and fresh cached-live FRED data exists, the macro report uses cached-live data before mock fallback.
- Missing `FRED_API_KEY`, unsupported provider, or FRED fetch failure without usable cached-live data falls back to mock macro data with `source_type="fallback"`.
- FRED fallback reasons are sanitized and must not expose `FRED_API_KEY` or tokenized FRED request URLs.

Environment-controlled live SEC Form 4 behavior:

- `USE_LIVE_SEC_FORM4=false` by default keeps insider Form 4 data on deterministic mock fixtures.
- `USE_LIVE_SEC_FORM4=true` with `SEC_FORM4_PROVIDER=sec_edgar` and `SEC_EDGAR_USER_AGENT` attempts repository-backed official SEC EDGAR fetches for Form 4 insider transactions.
- Missing required credentials or fetch failures fall back to mock Form 4 data with `source_type="fallback"`.
- `SEC_EDGAR_USER_AGENT` is never exposed in API responses.

Environment-controlled live SEC 13F behavior:

- `USE_LIVE_SEC_13F=false` by default keeps institutional 13F data on deterministic mock fixtures.
- `USE_LIVE_SEC_13F=true` with `SEC_13F_PROVIDER=sec_edgar`, `SEC_EDGAR_USER_AGENT`, and configured target managers attempts repository-backed official SEC EDGAR 13F fetches.
- Missing required SEC User-Agent or fetch failures fall back to mock 13F data with `source_type="fallback"` unless usable cached live SEC 13F data exists.
- 13F uses `freshness_window="quarterly_filing_delay"` and is delayed quarterly evidence, not real-time institutional flow.

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

Primary endpoint. Validates a user-provided US ticker using structured evidence and Jane methodology. Future Industry Radar is not required for this endpoint.

Phase 14 makes the response a candidate validation report rather than a loose bundle of engine outputs. Phase 15 adds live/cached company profile, financial quality, and derived valuation context through repository-backed yfinance data when company data is enabled. Phase 16 adds evidence-based Jane company quality and financial statement signals so mock leadership no longer acts as the primary company-quality driver. The main user-facing fields are:

- `candidate_validation_summary`: concise research-priority summary, strengths, risks, mock/fallback disclosure, and next checks.
- `evidence_matrix`: primary explanation layer for macro environment, company profile, financial quality, valuation context, Jane company quality, financial statement signals, legacy leadership score, smart money, insider activity, institutional 13F, and risk flags.
- `data_quality_summary`: user-facing source-quality grade, confidence-cap reason, mock/fallback categories, and excluded scoring indicators.
- `score_driver_breakdown`: positive, limiting, and neutral score drivers.
- `next_manual_checks`: research-oriented checks for source quality, fundamentals, filings, valuation, and risk.

Raw evidence remains available in the legacy score objects, `raw_data`, and debug/expandable frontend panels for audit. Mock and fallback data reduce confidence. The endpoint must keep `not_investment_advice=true` and must not emit trading instructions.

Phase 15 company data behavior:

- `company_profile` may use `source_type="live"` or `source_type="cached_live"` with `provider="yfinance"` when yfinance profile data is available.
- `financial_quality` may use yfinance fundamentals. SEC companyfacts is a preferred future official source but is not required for this implementation slice.
- `valuation_context` is derived from market cap, enterprise value, revenue, and free cash flow inputs. It is risk context only.
- If live yfinance company data is unavailable, profile and fundamentals fall back to mock fixtures with `fallback_used=true` when a live attempt was made.
- `research_context` remains user-provided context and is not treated as source evidence.
- Leadership score remains mock-only until a later phase.
- `source_type="mixed"` is invalid; derived summaries use `source_type="derived"` with descriptive providers such as `derived_from_yfinance`.

Phase 16 company quality behavior:

- `jane_company_quality` is the primary company-quality model and contains 10 explicit criteria: `monopoly_power`, `mega_trend_fit`, `visionary_founder_ceo`, `disruptive_innovation`, `scalability`, `network_effect`, `continuous_r_and_d`, `financial_statement_quality`, `balance_sheet_strength`, and `cash_flow_quality`.
- User-provided `research_context.theme` is context only. It may appear under `mega_trend_fit` with `source_quality="user_context"` and `affects_score=false`; it is not independently verified evidence.
- Qualitative moat, founder/CEO, disruption, and network-effect criteria are marked `insufficient` unless reliable evidence is available. The system does not fabricate these criteria from mock leadership.
- Financial criteria derive from yfinance fundamentals when available and use `source_type="derived"` with descriptive providers. Yfinance normalization limitations remain visible.
- `financial_statement_signals` includes revenue growth quality, operating margin strength, net income quality, operating cash flow quality, cash safety buffer, debt risk, receivables vs revenue risk, inventory vs revenue risk, CapEx vs OCF risk, and share dilution risk.
- Missing receivables, inventory, operating cash flow, CapEx, dilution, or R&D fields are marked insufficient and listed in `missing_data`.
- `leadership_score` is retained for backward compatibility only, marked `deprecated_by="jane_company_quality"`, `source_quality="mock_only"`, and `affects_score=false`.

Request:

```json
{
  "ticker": "NVDA",
  "market": "US",
  "research_context": {
    "theme": "AI infrastructure",
    "user_reason": "External trend research"
  }
}
```

Response:

```json
{
  "ticker": "NVDA",
  "market": "US",
  "analysis_mode": "ticker_validation",
  "research_verdict": {
    "label": "worth_deep_research",
    "score": 72,
    "confidence": 0.76,
    "summary": "Research reference only.",
    "confidence_factors": {
      "confidence_boosters": [],
      "confidence_limiters": []
    }
  },
  "candidate_validation_summary": {
    "ticker": "NVDA",
    "research_priority": "watchlist_candidate",
    "score": 63,
    "confidence": 0.72,
    "environment_assessment": "Macro environment is neutral-to-constructive.",
    "company_assessment": "Company evidence remains preliminary.",
    "smart_money_assessment": "Smart-money evidence is limited by fallback or cached components.",
    "data_quality_assessment": "Source quality grade C.",
    "overall_summary": "Research validation summary.",
    "primary_strengths": [],
    "primary_risks": [],
    "missing_or_mock_evidence": [],
    "next_manual_checks": []
  },
  "evidence_matrix": [],
  "data_quality_summary": {},
  "score_driver_breakdown": {},
  "next_manual_checks": [],
  "company_profile": {},
  "macro_regime": {},
  "leadership_score": {},
  "jane_company_quality": {
    "name": "jane_company_quality_score",
    "score": 32,
    "max_score": 100,
    "confidence": 0.5,
    "label": "preliminary",
    "criteria": [],
    "source_status": {},
    "limitations": [],
    "missing_data": []
  },
  "financial_statement_signals": {
    "score": 45,
    "confidence": 0.5,
    "label": "adequate",
    "signals": [],
    "source_status": {},
    "limitations": [],
    "missing_data": []
  },
  "market_timing_context": {},
  "overheat_risk": {},
  "smart_money": {},
  "insider_activity": {},
  "institutional_13f": {},
  "financial_quality": {},
  "valuation_context": {},
  "risk_flags": [],
  "data_quality": {},
  "jane_reference_conditions": {},
  "jane_quality_methodology_reference": {
    "framework": "Jane 7-principle company quality framework",
    "principles": [],
    "affects_score": true,
    "limitations": []
  },
  "missing_data": [],
  "human_verification_queue": [],
  "not_investment_advice": true
}
```

Research verdict labels describe research priority only: `worth_deep_research`, `watchlist_candidate`, `insufficient_data`, or `high_risk_context`. Missing data reduces confidence. Mock or excluded indicators must not increase the verdict score. The endpoint must not emit trading instructions.

`institutional_13f` is candidate-focused. It includes `candidate_specific_evidence`, `portfolio_context`, `source_status`, `limitations`, and `missing_data`. A configured manager portfolio is context only unless the candidate has matched 13F evidence with `score_contribution_allowed=true`.

`insider_activity` summarizes SEC Form 4 evidence. Only transaction code `P` counts as accumulation evidence; only code `S` counts as disposition evidence. Cached or fallback evidence is described as limited source context.

`financial_quality.raw_data` may include `revenue_ttm`, `revenue_yoy_growth_pct`, `revenue_3y_cagr_pct`, `gross_margin_pct`, `operating_margin_pct`, `free_cash_flow_ttm`, `free_cash_flow_margin_pct`, `cash_and_equivalents`, `total_debt`, `net_cash_or_debt`, `debt_to_equity`, `shares_outstanding`, and `share_dilution_3y_pct`. Missing fields are listed in `missing_data` and are not fabricated.

`valuation_context.raw_data` may include `market_cap`, `enterprise_value`, `price_to_sales_ttm`, `ev_to_sales_ttm`, `price_to_free_cash_flow_ttm`, `ev_to_free_cash_flow_ttm`, `gross_margin_pct`, `revenue_growth_yoy_pct`, `valuation_risk_label`, and `valuation_summary`. Multiples are null when denominators are missing or non-positive.

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
In Phase 11, `raw_data.sec_13f_snapshot` may contain SEC EDGAR-backed 13F holdings when `USE_LIVE_SEC_13F=true`, `SEC_EDGAR_USER_AGENT` is configured, and manager CIKs or supported manager names are configured.

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

`source_type` values may include `live`, `cached_live`, `fallback`, `mock`, `derived`, and `unknown`.

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

`source_type` is constrained to `live`, `cached_live`, `mock`, `fallback`, `derived`, or `unknown`. Do not use `mixed` as a `source_type`; mixed inputs should use `source_type="derived"` with `provider` set to a mixed provider string such as `mixed_FRED_and_mock_macro` or `mixed_smart_money_sources`.

Freshness rules:

- Daily market data is fresh when `source_date` matches the latest expected trading day.
- FRED daily rate series use `freshness_window="daily_rate_5_business_days"`.
- FRED monthly macro series use `freshness_window="monthly_macro_latest_observation"`.
- FRED-derived fields use `freshness_window="derived_from_FRED"` and inherit freshness from their input series. If an input series is stale, the derived field is stale and includes the stale input in `missing_data`.
- For monthly FRED series, `source_date` is the observation month being measured, not the report generation date or the FRED release timestamp. The MVP treats monthly observations within 70 calendar days of report generation as fresh to account for normal release delay.
- 13F source status uses `freshness_window="quarterly_filing_delay"`. `source_date` is the filing report date when available, otherwise filing date. `fetched_at` is the cache/write or retrieval timestamp. `report_generated_at` remains the daily report assembly timestamp and must not be used as the 13F source date.
- Mock data is classified as mock reference data and does not count as stale solely because it is not live.
- Stale applies only to live, fallback, or derived components with outdated `source_date`.
- Fallback data sets `fallback_used=true` and includes a safe `fallback_reason`.
- `fallback` means a configured live source could not be used and deterministic mock fallback data was returned with limitations and missing-data disclosure.
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
  "macro": {
    "provider": "mixed_FRED_and_mock_macro",
    "live_macro_fields_count": 4,
    "derived_macro_fields_count": 5,
    "mock_macro_fields_count": 8,
    "has_mock_macro_context": true,
    "mock_context_fields": [],
    "fred_backed_fields": [],
    "derived_from_fred_fields": [],
    "yfinance_backed_fields": [],
    "derived_from_yfinance_fields": [],
    "yfinance_macro_fields_count": 0,
    "market_context_reused_from_daily_market_data": true,
    "confidence_adjustment_applied": true
  },
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

Mock phases use `backend/app/raw_store/repository.py` as a repository interface over mock JSON-like fixtures. Live phases will replace the implementation with a SQLite-backed cache. Phase 15.5 makes `repository.py` a compatibility facade; new code should prefer focused raw-store modules such as `market_cache.py`, `macro_cache.py`, `sec_cache.py`, `company_cache.py`, `snapshot.py`, and `price_reference_cache.py`.

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

`macro_regime` may also include `macro_data_quality`, which separates `fred_backed_fields`, `derived_from_fred_fields`, and `mock_context_fields`. FRED-backed fields are live or cached-live FRED observations; FRED-derived fields are calculations from those observations. DXY, gold, oil, VIX, and equity context remain mock context until providers are added. CNN Fear & Greed and ISM Manufacturing PMI are excluded from scoring and mock context. Intentional mock context is disclosed as `source_type="mock"` and is not treated as fallback. When FRED-backed and mock-context fields are mixed, the macro source status uses `source_type="derived"` and `provider="mixed_FRED_and_mock_macro"`.

Phase 12.1 adds yfinance-backed market context to that same diagnostic object. `macro_data_quality` may include `yfinance_backed_fields`, `derived_from_yfinance_fields`, `yfinance_macro_fields_count`, and `live_or_cached_context_score_weight_pct`. VIX, SPY/QQQ drawdown, SPY/QQQ gain from trough, DXY trend, gold trend, and oil trend may be live/cached/derived from yfinance. When FRED and yfinance-backed context coexist without mock macro fields, macro source status uses `source_type="derived"` with `provider="mixed_FRED_and_yfinance_macro"`. `source_type="mixed"` remains invalid.

Phase 12.3b removes ISM Manufacturing PMI from production macro scoring. `NAPM` was tested and rejected as invalid. `IPMAN` is Industrial Production: Manufacturing and must not be used as PMI. PMI search and validation CLI tools remain available for future source exploration, but they do not enable PMI in production reports. `macro_data_quality.excluded_indicators`, `data_quality.macro.excluded_indicators`, and `macro_regime.derived_metrics.excluded_indicators` include `ism_manufacturing_pmi` with `affects_score=false`.

Phase 12.4 removes CNN Fear & Greed from production scoring and mock context. `macro_data_quality.excluded_indicators`, `data_quality.macro.excluded_indicators`, and `macro_regime.derived_metrics.excluded_indicators` include `cnn_fear_greed` with `affects_score=false`. Daily reports include `jane_reference_conditions`, a display-only methodology reference panel. The panel uses `source_type="methodology_reference"` outside the `DataSourceStatus.source_type` enum, has `affects_score=false`, and must not create missing data or influence macro, market timing, overheat, smart money, or report scores.

Phase 12.5 recalibrates the macro score with `macro_regime.derived_metrics.scoring_model.version="macro_v12_5"`. The final score is a weighted component score over validated FRED, yfinance, and derived fields only. Active group weights total 100: rates and policy 25, inflation pressure 20, labor/recession resilience 15, market stress/volatility 15, cross-asset risk context 15, and rebound/recovery context 10. `component_contributions` lists each active component with group, weight, raw value, component score, weighted contribution, source type, provider, source date, and limitation. CNN Fear & Greed and ISM Manufacturing PMI remain excluded, have weight 0, do not appear in `component_contributions`, and are not counted as missing active components. Macro score bands are `restrictive_or_stress` (0-30), `cautious` (31-55), `neutral_to_constructive` (56-75), and `supportive_macro_backdrop` (76-100), with `insufficient_data` used when active data is materially unavailable. `macro_data_quality.scoring` and `data_quality.macro.scoring` expose active weight total, missing/stale/fallback active components, and confidence basis. Confidence is based on active component availability, freshness, cached-live-after-failure state, fallback state, and missing active components. `source_type="mixed"` remains invalid.

Phase 12.6 adds `macro_regime.macro_score_explanation` for API and UI display. It summarizes the existing `macro_v12_5` diagnostics without changing the score formula. Fields include `scoring_model_version`, `score`, `max_score`, `label`, `confidence`, `active_weight_total`, `weighted_contribution_sum`, `rounding_difference`, `rounding_tolerance`, grouped active components, excluded indicators, `confidence_basis`, `confidence_explanation`, and limitations. Each group includes display name, group weight, group contribution sum, and component rows with display name, raw value, component score, weight, weighted contribution, source type, provider, source date, freshness window, freshness boolean, and limitation. `confidence_explanation` reports max confidence, deductions, and confirms excluded indicators are not counted as missing. Jane reference conditions remain separate display-only methodology context.

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

`source_date` is the date of the underlying observation or filing. `fetched_at` is the cache/write or retrieval timestamp when available. `report_generated_at` is the timestamp for report assembly and must not be substituted for source freshness.

`smart_money_summary` and `smart_money` currently contain the same score object. `smart_money` is the canonical frontend-facing field; `smart_money_summary` is deprecated and retained for backwards compatibility.

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
  "analysis_mode": "ticker_validation",
  "research_verdict": {},
  "company_profile": {},
  "macro_regime": {},
  "leadership_score": {},
  "market_timing_context": {},
  "overheat_risk": {},
  "smart_money": {},
  "insider_activity": {},
  "institutional_13f": {},
  "financial_quality": {},
  "valuation_context": {},
  "risk_flags": [],
  "data_quality": {},
  "jane_reference_conditions": {},
  "missing_data": [],
  "human_verification_queue": [],
  "not_investment_advice": true
}
```

`analysis_mode` is always `ticker_validation`. `macro_regime.derived_metrics.scoring_model.version` remains `macro_v12_5`; `macro_score_explanation` is preserved. `jane_reference_conditions.affects_score=false`. Form 4 evidence is exposed under `insider_activity`; candidate-specific SEC 13F evidence is exposed through the 13F component and related smart-money raw data.

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

Still mock or excluded:

- `dxy_trend`
- `gold_trend`
- `oil_trend`
- `ism_manufacturing_pmi` is excluded from scoring and mock context.
- `cnn_fear_greed` is excluded from scoring and mock context.

FRED release schedules may lag the current date. When live macro is enabled, `data_quality.live_components` counts FRED-backed macro components, while mock-only macro components remain visible as mock. If live macro fetch fails, macro source metadata is marked as fallback and the report adds macro missing-data and limitation notes.

Phase 9.1 cleanup:

- When FRED-backed fields are combined with Phase 9 mock-only macro fields, `macro_regime.raw_data.source_type` is `derived` and `provider` is `mixed_FRED_and_mock_macro`.
- FRED freshness is series-aware: Treasury yield series use `daily_rate_5_business_days`; monthly macro releases use `monthly_macro_latest_observation`; derived FRED values use `derived_from_FRED`.
- `/api/daily-report/latest` exposes compact FRED raw-series summaries and does not include full historical FRED observations.
- `date` reflects the current report date, while `report_generated_at` is the actual report generation timestamp.

Phase 9.2 monthly FRED freshness:

- Monthly series (`FEDFUNDS`, `CPIAUCSL`, `PPIACO`, and `UNRATE`) are evaluated using observation-month freshness rather than latest-trading-day freshness.
- A March 2026 monthly observation can be fresh in an April 27, 2026 report because the observation date is the measured month, while release schedules can lag.
- Every live FRED component source status should propagate the macro snapshot `fetched_at` timestamp when available.

Phase 11.8 macro source clarity:

- FRED-backed macro fields are live/cached or derived from FRED.
- DXY, gold, oil, VIX, and equity context remain Phase 9 mock context until providers are added.
- CNN Fear & Greed and ISM Manufacturing PMI are excluded from scoring and mock context.
- Mock context is not fallback when it is intentionally used as placeholder context; each mock context component keeps `source_type="mock"` and `fallback_used=false`.
- Macro confidence is capped when mock context contributes materially to the score.
- Mixed macro output must use `source_type="derived"` with `provider="mixed_FRED_and_mock_macro"` and must not use `source_type="mixed"`.
- API keys and raw provider URLs must never appear in API responses, snapshots, logs, or fallback reasons.

Phase 12.1 live market context:

- VIX, equity drawdown, gain from trough, DXY, gold, and oil can now use existing yfinance market snapshots.
- `data_quality.macro` includes yfinance-backed and yfinance-derived field lists and counts.
- CNN Fear & Greed and ISM Manufacturing PMI are excluded from scoring.
- Yfinance data is an MVP research reference and may be delayed, adjusted, or incomplete.
- Remaining mock fields continue to reduce or cap macro confidence according to their score weight.

Phase 12.3b ISM/PMI:

- ISM Manufacturing PMI is excluded from current scoring because no valid licensed/live source is configured.
- `NAPM` was tested and rejected as invalid.
- `IPMAN` is Industrial Production: Manufacturing and must not be used as PMI.
- Search candidates with `python -m backend.app.tools.fred_series_search "ISM Manufacturing PMI"`.
- Validate candidates with `python -m backend.app.tools.fred_series_validate <SERIES_ID>`.
- These developer tools are for future source exploration only and do not enable PMI in production reports.
- PMI is absent from scoring components, `component_source_status`, `mock_context_fields`, and source contribution.
- Jane reference conditions may display Fear & Greed as methodology context only.
- API keys and raw FRED URLs or query strings must not appear in fallback reasons, snapshots, logs, or API responses.

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

## Phase 11 Official SEC EDGAR 13F

Phase 11 uses official SEC EDGAR 13F institutional holdings behind the raw-store boundary. Public response schemas remain stable; live, cached, fallback, mock, and mixed state is exposed through existing `source_status`, `raw_data`, `limitations`, `missing_data`, and `data_quality` fields.

PowerShell:

```powershell
$env:USE_LIVE_SEC_13F="true"
$env:SEC_13F_PROVIDER="sec_edgar"
$env:SEC_EDGAR_USER_AGENT="Your Name your.email@example.com"
$env:SEC_13F_TARGET_MANAGERS="0001067983"
uvicorn backend.app.main:app --reload
```

Live SEC-backed fields in `smart_money_summary.raw_data.institutional_13f` may include `holdings`, `top_holdings_by_value`, `target_cusip_holdings`, `target_ticker_holdings`, `source_status`, `delayed_institutional_support`, and `is_real_time_signal`.

Smart-money derived metrics include `latest_13f_report_date`, `latest_13f_filing_date`, `total_reported_value_usd`, `holding_count`, `target_ticker_holdings`, `target_cusip_holdings`, `top_holdings_by_value`, `quarter_over_quarter_position_change`, `manager_count_observed`, and `institutional_support_label`.

13F source status uses `provider="SEC EDGAR"` for official live or cached data, `freshness_window="quarterly_filing_delay"`, `source_date` as report date when available otherwise filing date, and `fetched_at` as the cache/write or retrieval timestamp.

13F value fields:

- `reported_value_raw` preserves the SEC XML `<value>` as reported.
- `reported_value_unit` may be `as_reported`, `usd`, `thousands_usd`, or `unknown`.
- `value_usd` is a best-effort normalized USD value used for `total_reported_value_usd` and `top_holdings_by_value`.
- `value_unit_confidence` may be `high`, `medium`, or `low`.
- `value_normalization_note` explains whether the value was preserved as reported, interpreted with a price reference, or interpreted through the explicit legacy override.
- The backend no longer blindly multiplies every SEC 13F XML value by 1000.

13F aggregation fields are additive and schema-stable. `smart_money_summary.raw_data.institutional_13f` may include:

- `portfolio_summary`
- `top_holdings_by_value`
- `target_matches`
- `qoq_changes`
- `value_confidence_breakdown`

Daily report 13F output is compact by default. Full row-level 13F data is not included under `smart_money_summary.raw_data.institutional_13f` unless `INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT=true`; when enabled, full rows appear under `raw_data_full.holdings`.

`qoq_changes` is capped for daily report readability and includes:

- `qoq_changes_count_total`
- `qoq_changes_limit`

`portfolio_summary` groups holdings by CUSIP when available. If CUSIP is missing, issuer name plus title of class is used as a fallback grouping key. Different CUSIPs are not merged solely because issuer names are similar.

Target matching:

- CUSIP exact match is high confidence.
- Ticker matching requires the local ticker-to-CUSIP map and does not call external CUSIP APIs.
- Exact issuer aliases in the local map may resolve to CUSIP with medium confidence.
- Issuer-name-only string matching remains low confidence and includes a limitation.
- Target matches may include `match_method`, `resolved_ticker`, `resolved_cusip`, `resolved_issuer_name`, and `local_security_map_used`.

Aggregation and portfolio summary may include `mapped_ticker`, `resolved_cusip`, `security_map_used`, `price_reference_used_count`, `mapped_holding_count`, and `unmapped_holding_count`. The local security map is bounded and not authoritative. If mapped 13F rows cannot obtain a reusable price reference, portfolio summaries include `price reference unavailable for mapped 13F holdings` in `missing_data`.

Value confidence may be upgraded when local mapping and a cached/reusable price reference are available. The price-reference layer checks reusable market cache first, then uses a bounded per-ticker adapter instead of refetching for every 13F row. During daily report fast mode, price references use cached market data only unless `ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST=true`. Optional bounded cache warmup can be enabled with `PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT=true`, startup warmup, or `POST /api/price-reference/warmup`; warmup is ticker-level, deduplicated, capped, and writes reusable market cache entries. Price-reference summaries may include `price_reference_grouped_holding_count`, `price_reference_row_count`, `price_reference_ticker_count`, `price_reference_cache_hit_count`, `price_reference_live_fetch_count`, `price_reference_unavailable_tickers`, and `price_reference_mode`; `price_reference_used_count` remains a backward-compatible grouped count. Price references may not match the 13F report date exactly, and confidence is capped conservatively when the reference date differs materially from the 13F report date.

`POST /api/price-reference/warmup` accepts `tickers`, optional `max_tickers`, and optional `allow_live_fetch`. The response includes warmup counts and `not_investment_advice=true`. The endpoint must not expose secrets and must not call CUSIP mapping APIs.

`POST /api/jobs/daily-research-refresh` runs the Phase 11.5 daily batch snapshot pipeline. The same workflow is available through `python -m backend.app.jobs.daily_research_refresh` from the repository root. The batch refreshes or reuses existing yfinance, FRED, SEC Form 4, and SEC 13F caches, warms mapped 13F price references when `DAILY_BATCH_PRICE_REFERENCE_WARMUP=true`, computes the daily report after warmup, and writes `daily_report_snapshot/latest.json` under raw store. It does not add providers, expose secrets, or change scoring semantics.

After successful mapped 13F price-reference warmup, snapshot 13F portfolio summaries should show `price_reference_used_count > 0`, `price_reference_cache_hit_count > 0` or `price_reference_live_fetch_count > 0`, a `value_confidence_breakdown` that is not all low, and `price_reference_mode` of `batch_warmed` or `cache_with_bounded_warmup`.

Phase 11.5b tightens snapshot SEC 13F source selection and price-reference mode semantics:

- When `USE_LIVE_SEC_13F=true` and `SEC_13F_TARGET_MANAGERS` is configured, fresh cached/live SEC EDGAR 13F is preferred over mock 13F fixtures during batch snapshot computation.
- When cached/live SEC EDGAR 13F is used, `institutional_13f.portfolio_summary.provider` must be `derived_from_SEC_EDGAR_13F`, `underlying_source_type` must be `cached_live` or `live`, and `missing_data` must not include `live SEC 13F data`.
- `price_reference_mode="batch_warmed"` is valid only when `price_reference_used_count > 0` and either `price_reference_cache_hit_count > 0` or `price_reference_live_fetch_count > 0`; failed warmup attempts use `batch_warmup_failed` or cache-only semantics.
- Mock 13F target matches are diagnostics only, do not count toward high-confidence target-match evidence, and do not boost the institutional support score.

Phase 11.6 separates portfolio-level 13F context from candidate-specific evidence. Each `stock_candidates[].institutional_13f` may include:

- `source_status`
- `candidate_specific_evidence`
- `target_matches`
- `portfolio_context`
- `limitations`
- `missing_data`

`candidate_specific_evidence` is the primary candidate interpretation field. It may include `ticker`, `resolved_ticker`, `resolved_cusip`, `resolved_issuer_name`, `local_security_map_used`, `matched_in_13f`, `match_confidence`, `match_method`, `position_value_usd`, `position_shares_or_principal_amount`, `portfolio_weight_pct`, `source_date`, `report_date`, `filing_date`, `latest_report_date`, `latest_filing_date`, `manager_cik`, `manager_name`, `manager_metadata_source`, `value_unit_confidence_summary`, `interpretation_label`, `interpretation_summary`, and `score_contribution_allowed`.

Allowed candidate 13F interpretation labels are `reported_13f_position_observed`, `no_reported_13f_position_observed`, `low_confidence_issuer_name_match`, `insufficient_identifier_mapping`, and `insufficient_13f_data`. A manager's top holdings are portfolio context only and must not be treated as support for unrelated candidates. Candidate support requires an exact CUSIP match through the bounded local security map or another CUSIP-confirmed match. Issuer-name-only matches are low confidence and carry a limitation. Unmatched mapped candidates report `no_reported_13f_position_observed`, not a negative execution signal.

`portfolio_context` is supporting context only. It may include manager identity, `manager_metadata_source`, latest report and filing dates, grouped and mapped holding counts, source status, and a capped `top_holdings_by_value` list. Candidate output must not include the full 13F holdings list; `SEC_13F_CANDIDATE_CONTEXT_TOP_HOLDINGS_LIMIT=5` caps the candidate context list by default.

Phase 11.6a adds a bounded local manager map for display polish. CIK remains the stable identifier. Known CIKs such as `0001067983` may resolve to readable names such as `Berkshire Hathaway Inc.` with `manager_metadata_source="local_static_map"`. Unknown CIKs fall back to the normalized CIK. Outputs using the local map include the limitation `Manager name is resolved from a bounded local map and may not be authoritative.`

For unmatched mapped candidates, `interpretation_summary` states that no reported 13F position was observed in the configured manager portfolio and `score_contribution_allowed=false`. This is not a negative trading signal. For matched candidates, `score_contribution_allowed=true` only when the source is live/cached SEC EDGAR-derived, the match is CUSIP-confirmed with high or medium confidence, and the 13F source status is fresh under `quarterly_filing_delay`. Matched candidate evidence must also disclose that 13F reflects delayed quarterly reporting and may not represent the manager's current position.

Phase 11.5 config:

- `DAILY_REPORT_READ_MODE=snapshot_first`
- `DAILY_BATCH_ALLOW_LIVE_FETCH=true`
- `DAILY_BATCH_PRICE_REFERENCE_WARMUP=true`
- `DAILY_BATCH_MAX_RUNTIME_SECONDS=180`

Daily report performance fields are omitted by default. When `INCLUDE_PERFORMANCE_DIAGNOSTICS=true`, responses may include `performance_diagnostics` with `total_ms`, `macro_ms`, `market_data_ms`, `sec_form4_ms`, `sec_13f_ms`, `sec_13f_price_reference_ms`, `smart_money_ms`, `candidate_generation_ms`, `network_call_count`, `cache_hit_count`, `cache_miss_count`, and `bounded_fetch_skipped_count`. Diagnostics must not include secrets, SEC User-Agent values, or tokenized URLs.

`DAILY_REPORT_FAST_MODE=true` by default keeps daily reports cache-first and adds the limitation `Daily report fast mode uses fresh cached live data when available.` SEC Form 4 fetches are bounded by `SEC_FORM4_MAX_FILINGS_PER_TICKER`, `SEC_FORM4_MAX_XML_DISCOVERY_PER_REPORT`, `SEC_FORM4_NETWORK_TIMEOUT_SECONDS`, and `SEC_FORM4_TOTAL_BUDGET_SECONDS`. Cached live data is distinct from mock fallback and must keep `source_type="cached_live"`.

QoQ comparison is by CUSIP and reflects reported quarterly changes only. It must not be interpreted as real-time institutional flow.

SEC 13F document discovery:

- The submissions API is only used to find manager filing history.
- Submissions URLs use zero-padded 10-digit CIKs.
- Archives directory URLs use CIKs without leading zeros and accession numbers without dashes.
- Archives `index.json` is tried first to find actual filing document names.
- The HTML fallback is `{accession-number}-index.html`, where the accession filename keeps dashes.
- Information table XML filenames must come from Archives index discovery. Do not assume `form13fInfoTable.xml`.
- If the first XML candidate is unavailable or is only cover-page XML, the backend tries the next bounded candidate.

Limitations:

- 13F is delayed quarterly evidence and may lag up to 45 days after quarter end.
- 13F may not show shorts, many derivatives, or current positions.
- 13F should not be interpreted as real-time institutional flow.
- Manager-name discovery is limited in v1; numeric CIKs are preferred.
- SEC Form 13F Data Sets can be considered as a future batch optimization but are not required for Phase 11.
- Fallback mock 13F does not boost smart-money score and is labeled insufficient data.
