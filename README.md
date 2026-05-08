# Jane Framework Investment Research Assistant

This repo specification pack is designed to be copied into a new VSCode project and used with Codex.

## Purpose

Build a US-market-only investment research automation system based on Jane's Markdown investment framework.

This is not a trading system. It produces research signals, evidence, benchmarks, trends, confidence, and missing-data warnings.

## Phase 17 SEC Companyfacts Financial Cross-Check

Phase 17 adds official SEC EDGAR Companyfacts as a filing-backed cross-check layer for `POST /api/analyze-stock`:

- `sec_financial_facts` exposes parsed Companyfacts concepts for revenue, gross profit, operating income, net income, operating cash flow, CapEx, cash, debt, stockholders' equity, receivables, inventory, and shares when SEC concepts are available.
- `fundamentals_cross_check` compares comparable SEC Companyfacts and yfinance metrics with tolerant thresholds. Discrepancies are review signals, not automatic failures.
- SEC Companyfacts complements yfinance. Yfinance remains the MVP market/company provider, while SEC facts improve source quality for financial statement signals only where mapped concepts exist.
- Missing SEC concepts are listed in `missing_data`; the system does not infer missing filing concepts or share dilution.
- Jane qualitative moat/founder/network/disruption criteria remain insufficient until independent qualitative evidence sources exist.
- `SEC_EDGAR_USER_AGENT` is required for live Companyfacts fetches and is never exposed in API responses, snapshots, logs, fallback reasons, or tests.
- Phase 17a aligns SEC Companyfacts derived metrics by fiscal period. Income statement and cash-flow margins only use same-period annual facts, CapEx must align with OCF, and invalid period-alignment ratios are nulled with `invalid_period_alignment` rather than used as supportive evidence.
- Phase 17c tightens analyze-stock data-quality categories. `fallback_evidence_categories` are based on actual fallback source status, `mixed_with_fallback` evidence quality, or score-affecting fallback subcomponents. Derived-live macro context is not fallback when active `macro_v12_5` components are live/cached/derived, mock context score weight is 0, and excluded ISM/CNN indicators have `affects_score=false` with weight 0.

Enable live Companyfacts:

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
$env:USE_LIVE_SEC_COMPANYFACTS="true"
$env:SEC_EDGAR_USER_AGENT="Your Name your.email@example.com"
uvicorn backend.app.main:app --reload
```

## Phase 16 Jane Company Quality Evidence Hardening

Phase 16 replaces mock leadership as the primary company-quality framing for `POST /api/analyze-stock`:

- `jane_company_quality` is now the top-level evidence-backed Jane company quality model.
- The seven Jane qualitative principles are explicit: Market Monopoly / Moat, Mega Trend Fit, Visionary Founder / CEO, Disruptive Innovation, Scalability, Network Effect, and Continuous R&D.
- Financial statement criteria are added for financial statement quality, balance sheet strength, and cash-flow quality.
- `financial_statement_signals` derives revenue growth, margin, income, cash-flow, cash buffer, debt, receivables, inventory, CapEx/OCF, and dilution checks from live/cached yfinance fundamentals when available.
- User-provided `research_context.theme` is context only and is not independently verified evidence.
- Qualitative moat, founder/CEO, network effect, and disruption items are marked insufficient when evidence is unavailable instead of receiving mock-positive credit.
- Legacy `leadership_score` remains mock-only for backward compatibility and is marked `deprecated_by="jane_company_quality"` with `affects_score=false`.
- SEC Companyfacts now provides the Phase 17 filing-backed financial cross-check layer.

## Phase 15.5 Architecture Stabilization

Phase 15.5 stabilizes the Phase 15 architecture before Jane Company Quality expansion:

- `backend/app/pipelines/research_pipeline.py` is the main daily research pipeline.
- `backend/app/pipelines/mock_pipeline.py` is a compatibility shim only.
- `backend/app/raw_store/repository.py` is now a facade over focused raw-store modules for market, macro, SEC, company, snapshot, and price-reference cache access.
- Daily report candidates are config-driven with `DEFAULT_DAILY_REPORT_CANDIDATES`, defaulting to `NVDA:AI energy infrastructure,TSLA:humanoid robotics`.
- Daily batch refresh uses a per-job context instead of mutating global config such as `ALLOW_LIVE_FETCH_ON_REPORT_REQUEST` or `PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT`.
- Source-status enrichment is legacy compatibility only; new engines should emit `source_status` directly.
- `smart_money` is canonical. `smart_money_summary` remains only as a deprecated backward-compatible alias.

## Phase 15 Company Fundamentals Live Integration

`POST /api/analyze-stock` is now the primary product workflow. The user brings externally discovered themes and candidate tickers; the system validates each US-listed ticker with structured evidence and Jane methodology.

Analyze-stock responses now lead with a readable candidate validation report:

- `candidate_validation_summary` is the main user-facing summary.
- `evidence_matrix` is the main explanation layer across macro, company profile, financial quality, valuation context, Jane company quality, financial statement signals, legacy leadership, smart money, Form 4, 13F, and risk flags.
- `data_quality_summary` converts raw source-quality counts into a source-quality grade and confidence-cap explanation.
- `score_driver_breakdown` separates positive, limiting, and neutral score drivers.
- `next_manual_checks` lists research-oriented follow-up checks.

Phase 18 adds a structured manual qualitative evidence framework for `POST /api/analyze-stock` without adding scraping, news, YouTube/social, sentiment, or paid providers. Optional `qualitative_evidence` request items are labeled `user_provided`, are not independently verified, and can only support preliminary Jane qualitative criteria such as moat, founder/CEO, disruption, and network effect. User-provided evidence is not mock evidence, not fallback evidence, and cannot by itself upgrade source quality to A or make `jane_company_quality` fully `evidence_backed`. `research_context.theme` remains context only unless structured qualitative evidence is supplied.

Phase 19 adds a local Manual Evidence Library. Saved qualitative evidence is stored by ticker under the raw-store boundary, managed through `/api/manual-evidence`, and automatically loaded into analyze-stock. Saved evidence and request-scoped evidence are merged and deduplicated with auditable `origin` values. Archived or rejected saved evidence does not affect scoring, and request-scoped evidence is not saved unless the user explicitly creates a library item.

Phase 20 adds a manual review workflow and evidence-quality scoring for the Manual Evidence Library. The quality score measures completeness and review readiness, not objective truth. Reviewed evidence remains user-provided, stale evidence is flagged and capped in impact, and `source_url` is never fetched or automatically verified.

Phase 21 adds manual competitor/comparison context hooks. Saved or request-scoped qualitative evidence may include `comparison_context` with peer companies, comparison type, claimed advantage, comparison summary, source basis, and limitations. Comparison evidence remains user-provided and preliminary, is not independently verified, is not mock or fallback evidence, does not fetch or validate source URLs, and cannot infer moat or disruption from market cap or price performance alone.

Phase 22 adds a local Manual Evidence Dashboard at `GET /api/manual-evidence/dashboard` and an Evidence Dashboard frontend tab. It summarizes saved manual evidence across tickers, stale items, scheduled and overdue reviews, archived/rejected audit items when explicitly requested, Jane qualitative criteria coverage, comparison evidence, and peer companies mentioned in user-provided `comparison_context`. The dashboard is local-only, does not call analyze-stock per ticker, does not call live providers, does not fetch URLs, and does not verify evidence truth. `review_due_count` and `review_scheduled_count` count items with any `next_review_due_at`; `review_overdue_count` counts items due at or before dashboard generation.

Phase 23 adds a local Candidate Research Workspace at `/api/candidates` and a Candidate Workspace frontend tab. The user supplies US tickers, themes, reasons, source labels, priority, and tags from external research. Workspace status is local workflow metadata, not a recommendation. The dashboard reads the local candidate store and Manual Evidence Library summaries only; it does not discover tickers, call live providers, fetch source URLs, scrape, or ingest news, YouTube, social, or sentiment. Candidate analyze calls the existing `POST /api/analyze-stock` pipeline for one selected candidate and caches only summary metadata such as score, confidence, label, and data-quality grade. Request-scoped qualitative evidence is not automatically saved.

Phase 24 hardens the Candidate Research Workspace UX and audit trail. Candidates now keep append-only review note history, validated workflow status transitions, compact analysis metadata history, local-only filters and sorting, review queue reason codes, and evidence coverage badges. Review notes and candidate statuses remain user-provided workflow metadata, do not become Manual Evidence Library records unless saved there explicitly, and do not affect analyze-stock scoring. Candidate workspace list and dashboard endpoints remain local-only and do not fetch external sources.

Phase 24.5 aligns documentation, scope boundaries, testing expectations, and repo hygiene with the Phase 24 implementation. It does not add product features, APIs, scoring changes, analyze-stock behavior changes, parser changes, live providers, scraping, source URL fetching, news, YouTube, sentiment, or Future Industry Radar work. The product boundary remains ticker validation for user-provided US-listed ideas.

Phase 15 live-enables company profile and company fundamentals through the repository-backed yfinance adapter when `USE_LIVE_COMPANY_DATA=true` or when live market data is enabled. Company profile, financial quality, valuation context, Jane company quality financial criteria, and financial statement signals use live or cached yfinance data when available and fall back to clearly labeled mock/insufficient evidence when unavailable. Valuation context is risk context only, not an investment instruction. Legacy leadership remains mock-disclosed and deprecated. Future Industry Radar is not required for analyze-stock.

Daily reports remain available as snapshot-first background context, source health, cache warmup, and market-environment snapshots. They are not the main user workflow. Future Industry Radar may remain as optional/future/reference context, but automatic theme discovery is not a core requirement.

## Current Implementation Status

`AGENTS.md` originally defined early planning phases for the MVP. The actual implementation has advanced through Phase 13 architecture realignment.

Completed live integrations now documented in this README:

- Phase 8: yfinance market data
- Phase 9: FRED macro data
- Phase 10: official SEC EDGAR Form 4
- Phase 11: official SEC EDGAR 13F
- Phase 12: macro modernization with `macro_v12_5`
- Phase 13: analyze-stock first architecture
- Phase 14: analyze-stock response composition and data-quality cleanup
- Phase 15: yfinance-backed company profile, fundamentals, and derived valuation context
- Phase 16: evidence-based Jane company quality and financial statement signals
- Phase 17: official SEC Companyfacts financial statement cross-check
- Phase 18: structured user-provided qualitative evidence assessment
- Phase 19: local reusable manual qualitative evidence library
- Phase 20: manual evidence review workflow and quality scoring
- Phase 21: manual comparison evidence and competitor context hooks
- Phase 22: manual evidence portfolio dashboard and cross-ticker review queue
- Phase 23: candidate research workspace and watchlist review flow
- Phase 24: candidate workspace review notes, analysis history, filters, badges, and UX hardening
- Phase 24.5: documentation, scope boundary, testing, and repo hygiene alignment

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

Analyze-stock validates user-provided ticker ideas.
Jane Company Quality, financial statement signals, and smart-money evidence help prioritize deeper research.
Market Timing and Macro Regime tell us whether the current research environment is favorable, neutral, fearful, or overheated.
None of these are direct investment recommendations.

Candidate Workspace is local workflow metadata for externally discovered ticker ideas. Review notes are append-only audit notes only, candidate status is workflow state only, and neither review notes nor candidate status affect scoring. The system should not expand into a full research notebook, task manager, portfolio tracker, trading journal, or execution workflow.

## Environment Variables Reference

| Variable | Default | Required for | Notes |
|---|---|---|---|
| USE_LIVE_MARKET_DATA | false | yfinance live prices | |
| MARKET_DATA_PROVIDER | yfinance | yfinance live prices | |
| MANUAL_EVIDENCE_DIR | backend/raw_store/manual_evidence | local manual evidence library | local JSON store; no external providers |
| CANDIDATE_WORKSPACE_DIR | backend/raw_store/candidate_workspace | local candidate workspace | local JSON store; workflow metadata only |
| USE_LIVE_COMPANY_DATA | follows USE_LIVE_MARKET_DATA | yfinance company profile and fundamentals | |
| COMPANY_DATA_PROVIDER | yfinance | yfinance company profile and fundamentals | |
| USE_LIVE_MACRO_DATA | false | FRED live macro | |
| MACRO_DATA_PROVIDER | fred | FRED live macro | |
| FRED_API_KEY | none | FRED live macro | secret; never expose |
| ENABLE_LIVE_ISM_MANUFACTURING_PMI | false | deprecated PMI exploration | production reports ignore PMI |
| ISM_MANUFACTURING_PMI_SERIES_ID | empty | deprecated PMI exploration | no default series is assumed valid |
| ISM_MANUFACTURING_PMI_SOURCE_LABEL | Unconfigured FRED PMI source | deprecated PMI exploration | developer tooling only |
| ISM_MANUFACTURING_PMI_IS_PROXY | true | deprecated PMI exploration | production reports ignore PMI |
| USE_LIVE_SEC_FORM4 | false | SEC EDGAR Form 4 | |
| SEC_FORM4_PROVIDER | sec_edgar | SEC EDGAR Form 4 | |
| SEC_EDGAR_USER_AGENT | none | SEC EDGAR Form 4 | required; never expose |
| SEC_EDGAR_REQUEST_DELAY_SECONDS | 0.2 | SEC EDGAR Form 4 | |
| SEC_FORM4_CACHE_TTL_HOURS | 24 | SEC EDGAR Form 4 cache | |
| SEC_FORM4_LOOKBACK_DAYS | 180 | SEC EDGAR Form 4 | |
| SEC_FORM4_MAX_FILINGS_PER_TICKER | 10 | SEC EDGAR Form 4 | performance guardrail |
| SEC_FORM4_MAX_XML_DISCOVERY_PER_REPORT | 20 | SEC EDGAR Form 4 | performance guardrail |
| SEC_FORM4_NETWORK_TIMEOUT_SECONDS | 10 | SEC EDGAR Form 4 | per-request timeout |
| SEC_FORM4_TOTAL_BUDGET_SECONDS | 20 | SEC EDGAR Form 4 | per-ticker fetch budget |
| USE_LIVE_SEC_COMPANYFACTS | follows USE_LIVE_COMPANY_DATA | SEC Companyfacts financial cross-check | |
| SEC_COMPANYFACTS_CACHE_TTL_DAYS | 7 | SEC Companyfacts cache | |
| SEC_COMPANYFACTS_NETWORK_TIMEOUT_SECONDS | 10 | SEC Companyfacts fetch | |
| USE_LIVE_SEC_13F | false | SEC EDGAR 13F | |
| SEC_13F_PROVIDER | sec_edgar | SEC EDGAR 13F | official SEC EDGAR only |
| SEC_13F_CACHE_TTL_DAYS | 7 | SEC EDGAR 13F cache | TTL is days, not hours |
| SEC_13F_LOOKBACK_QUARTERS | 4 | SEC EDGAR 13F | |
| SEC_13F_TARGET_MANAGERS | none | SEC EDGAR 13F | optional comma-separated manager names or CIKs |
| SEC_13F_TARGET_CUSIPS | none | SEC EDGAR 13F | optional comma-separated target CUSIPs; highest confidence target matching |
| SEC_13F_TARGET_TICKERS | none | SEC EDGAR 13F | optional comma-separated tickers for future mapping support |
| SEC_13F_TARGET_ISSUERS | none | SEC EDGAR 13F | optional comma-separated issuer-name fallback targets; low confidence |
| SEC_13F_ASSUME_VALUE_THOUSANDS | false | SEC EDGAR 13F | legacy fallback only; modern XML values are preserved unless disambiguated |
| SEC_13F_PRICE_REFERENCE_MAX_TICKERS | 20 | SEC EDGAR 13F price reference | performance guardrail |
| SEC_13F_PRICE_REFERENCE_TOTAL_BUDGET_SECONDS | 10 | SEC EDGAR 13F price reference | performance guardrail |
| SEC_13F_CANDIDATE_CONTEXT_TOP_HOLDINGS_LIMIT | 5 | candidate 13F evidence | caps portfolio context shown per candidate |
| INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT | false | daily report output | include full 13F row list only under `raw_data_full` when explicitly enabled |
| DAILY_REPORT_FAST_MODE | true | daily report output | cache-first report generation |
| ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST | false | daily report output | use cached market data for 13F price references by default |
| PRICE_REFERENCE_CACHE_WARMUP_ON_STARTUP | false | 13F price reference warmup | optional bounded ticker-level cache warmup |
| PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT | false | 13F price reference warmup | optional bounded ticker-level cache warmup before daily report 13F summary |
| PRICE_REFERENCE_CACHE_WARMUP_MAX_TICKERS | 20 | 13F price reference warmup | warmup ticker limit |
| DEFAULT_DAILY_REPORT_CANDIDATES | NVDA:AI energy infrastructure,TSLA:humanoid robotics | daily report candidates | comma-separated `TICKER:theme`; analyze-stock remains request-ticker driven |
| INCLUDE_PERFORMANCE_DIAGNOSTICS | false | daily report output | optional timing and cache counters |
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

Still mock or excluded:

- DXY trend
- gold trend
- oil trend
- Fear & Greed
- macro equity drawdown context unless live market prices are separately enabled
- ISM Manufacturing PMI is excluded from scoring because no valid licensed/live source is configured.

If `USE_LIVE_MACRO_DATA=true` but `FRED_API_KEY` is missing, FRED is unavailable, or the provider is unsupported, the raw store returns deterministic mock fallback macro data with `source_type="fallback"`. FRED release schedules can lag the current date, so live macro components include release-delay limitations and may require human verification.

Phase 9.1 keeps `/api/daily-report/latest` compact: FRED raw payloads include latest/previous values and bounded recent observations instead of full historical series. The report `date` is the current report date, `report_generated_at` is the actual generation timestamp, and each data source keeps its own `source_date`.

Phase 11.7 hardens FRED failure handling:

- transient FRED 5xx and timeout failures are retried within a bounded adapter budget
- FRED fallback reasons are sanitized and never include `FRED_API_KEY` or tokenized request URLs
- if a live refresh fails but fresh cached-live FRED data exists, the report uses that cached-live macro data before considering mock fallback
- mock fallback is used only when live refresh and usable cached-live data are both unavailable, with `missing_data` disclosing `live FRED macro data`

Phase 11.8 clarifies mixed macro evidence without adding providers:

- `macro_regime.macro_data_quality` separates FRED-backed fields, FRED-derived fields, and Phase 9 mock context fields
- direct FRED fields include federal funds, Treasury yields, and unemployment; derived FRED fields include yield spread, CPI/PPI YoY, policy trend, and unemployment trend
- DXY, gold, oil, VIX, and equity context remain intentional mock context until providers are added
- ISM Manufacturing PMI is excluded from scoring and mock context; `NAPM` is invalid and `IPMAN` is Industrial Production: Manufacturing, not PMI
- CNN Fear & Greed is excluded from scoring and mock context because no licensed/stable source is configured
- intentional mock context is not labeled fallback, but it is disclosed and reduces macro confidence when it contributes
- mixed macro output keeps `source_type="derived"` with `provider="mixed_FRED_and_mock_macro"`; `source_type="mixed"` is not used

Phase 12.1 live-enables low-risk market context through the existing yfinance integration:

- VIX, SPY/QQQ drawdown, SPY/QQQ gain from trough, DXY trend, gold trend, and oil trend can now be live, cached-live, or derived from yfinance-backed market snapshots.
- CNN Fear & Greed and ISM Manufacturing PMI are excluded from scoring and mock context.
- The macro provider becomes `mixed_FRED_and_yfinance_macro` when FRED and yfinance-backed context coexist without mock macro fields.
- Yfinance data is suitable for MVP research reference only, and remaining mock context continues to reduce confidence when it contributes materially.

Phase 12.3b excludes ISM Manufacturing PMI from scoring:

- ISM Manufacturing PMI is not live-enabled at this time.
- `NAPM` was tested and rejected as invalid.
- `IPMAN` is Industrial Production: Manufacturing and must not be used as PMI.
- Search candidates with `python -m backend.app.tools.fred_series_search "ISM Manufacturing PMI"`.
- Validate a candidate with `python -m backend.app.tools.fred_series_validate <SERIES_ID>`.
- These tools are for future data source exploration only and do not enable PMI in production reports.
- Current reports include `excluded_indicators` noting that `ism_manufacturing_pmi` does not affect score.
- CNN Fear & Greed may be reconsidered only if a licensed/stable data provider is selected.
- Jane reference conditions are displayed as methodology context only and do not affect score.
- Existing system-observable substitutes include FRED rate trend and yfinance-derived SPY/QQQ drawdown.
- FRED API keys and raw provider URLs must never appear in fallback reasons, logs, snapshots, or API responses.

Phase 12.5 recalibrates macro scoring after removing unlicensed indicators:

- `macro_regime.derived_metrics.scoring_model.version` is `macro_v12_5`.
- The active macro score uses only FRED-backed fields, FRED-derived fields, yfinance-backed market context, and yfinance-derived market context.
- Active component weights total 100: rates and policy 25, inflation pressure 20, labor/recession resilience 15, market stress/volatility 15, cross-asset risk context 15, and rebound/recovery context 10.
- CNN Fear & Greed and ISM Manufacturing PMI remain excluded with `affects_score=false` and scoring weight 0.
- Excluded indicators are disclosed separately and do not make the macro category fallback evidence. `source_type="derived"` and `source_quality="derived_live"` are not fallback by themselves.
- Jane reference conditions remain display-only; `jane_reference_conditions.affects_score=false` and condition-level `score_contribution_allowed=false`.
- Macro confidence is based on active component availability, freshness, cached-live-after-failure state, fallback state, and missing active components. Excluded indicators are not counted as missing active components.
- Mixed macro evidence continues to use `source_type="derived"` with a descriptive provider such as `mixed_FRED_and_yfinance_macro`; `source_type="mixed"` is invalid.

Phase 12.6 adds macro score explanation output and UI polish:

- `macro_regime.macro_score_explanation` summarizes `macro_v12_5` score, label, confidence, active weight total, weighted contribution sum, rounding difference, grouped score components, excluded indicators, and confidence explanation.
- Explanation groups mirror the active scoring model and show component raw value, component score, weight, weighted contribution, provider, source date, and freshness status.
- Excluded indicators are shown separately with `affects_score=false` and weight 0; they do not appear as active components.
- Jane reference conditions are shown separately as methodology context and do not affect macro score or confidence.

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

If a live SEC EDGAR Form 4 fetch fails after cache-first checks but usable cached live data exists, the component remains `source_type="cached_live"` with `provider="SEC EDGAR"` and uses the safe fallback reason `Live SEC EDGAR Form 4 fetch failed; cached live data used.` This cached-live warning is not treated as mock fallback for candidate-level source status.

Form 4 live fetches are bounded by `SEC_FORM4_MAX_FILINGS_PER_TICKER`, `SEC_FORM4_MAX_XML_DISCOVERY_PER_REPORT`, `SEC_FORM4_NETWORK_TIMEOUT_SECONDS`, and `SEC_FORM4_TOTAL_BUDGET_SECONDS`. When a fetch is bounded, responses include `SEC Form 4 fetch was bounded for performance.` and use cached live data when available.

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

13F aggregation and target matching:

- Daily reports aggregate row-level 13F holdings by CUSIP when available. If CUSIP is missing, issuer name plus title of class is used as a lower-stability grouping key.
- The same issuer may appear under multiple CUSIPs or share classes, so similar issuer names are not blindly merged.
- Portfolio summaries use normalized `value_usd` for `total_reported_value_usd`, top holdings, and portfolio weights.
- Target matching is highest confidence by exact CUSIP. Ticker matching uses only a small local ticker-to-CUSIP map and does not call external CUSIP APIs. Issuer-name-only matching is low confidence and disclosed as a limitation.
- The local security map is bounded and not authoritative. It is used only for target matching and value-confidence enrichment.
- Candidate-level `institutional_13f` separates `candidate_specific_evidence` from `portfolio_context`. A manager's top holdings are context only and are not support for unrelated candidates.
- Candidate support requires an exact 13F CUSIP match through the local security map or another CUSIP-confirmed match. Unmatched mapped candidates use `no_reported_13f_position_observed`, not a negative execution signal.
- Manager display names are resolved from a bounded local manager map when available; CIK remains the stable identifier and the local map is not authoritative.
- Candidate evidence includes `interpretation_summary` and `score_contribution_allowed` to make clear when candidate-specific 13F evidence can affect the score.
- A reported 13F position reflects delayed quarterly reporting and may not represent the manager's current position.
- Candidate `portfolio_context.top_holdings_by_value` is capped by `SEC_13F_CANDIDATE_CONTEXT_TOP_HOLDINGS_LIMIT` and does not include the full holdings list.
- Value confidence may be upgraded when a CUSIP resolves through the local map and a cached/reusable price reference is available. The price-reference layer checks reusable market cache first, then uses a bounded per-ticker adapter instead of refetching for every 13F row.
- During daily report fast mode, 13F price references use cached market data only unless `ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST=true`.
- Fast mode can preserve 13F value confidence when mapped tickers already have cached market prices. If no cached price exists, confidence remains lower and unavailable tickers appear in `price_reference_unavailable_tickers`.
- Optional bounded cache warmup is available through `PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT=true`, startup warmup, or `POST /api/price-reference/warmup`. Warmup is ticker-level, deduplicated, capped, and never row-level.
- 13F price-reference output distinguishes grouped, row, and ticker counts through `price_reference_grouped_holding_count`, `price_reference_row_count`, and `price_reference_ticker_count`; `price_reference_used_count` remains as a backward-compatible grouped count.
- If mapped 13F rows cannot obtain a reusable price reference, portfolio summaries include `price reference unavailable for mapped 13F holdings` in `missing_data`.
- Price references may not match the 13F report date exactly, so confidence is capped conservatively when the reference date differs materially from the 13F report date.
- QoQ comparison reflects reported quarterly 13F changes only. It is not real-time institutional flow.
- Daily report smart-money output is compact by default: it includes portfolio summary, top holdings, target matches, capped QoQ changes, source status, limitations, and missing data. Full 13F rows are omitted unless `INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT=true`, in which case they appear under `raw_data_full`.
- `qoq_changes` is capped in the daily report and includes `qoq_changes_count_total` plus `qoq_changes_limit`.

Repository behavior:

- `DAILY_REPORT_FAST_MODE=true` keeps daily reports cache-first and adds the limitation `Daily report fast mode uses fresh cached live data when available.`
- Daily reports are cache-first and do not repeatedly live-fetch SEC 13F unless `ALLOW_LIVE_FETCH_ON_REPORT_REQUEST=true`.
- Cached live SEC 13F data within `SEC_13F_CACHE_TTL_DAYS` returns `source_type="cached_live"` with `provider="SEC EDGAR"`.
- Missing `SEC_EDGAR_USER_AGENT` returns fallback mock 13F with `fallback_reason="SEC_EDGAR_USER_AGENT missing"` and never exposes the User-Agent value.
- Fallback mock 13F does not boost smart-money score and is labeled insufficient data.
- Manager-name display is limited to a small local mapping in v1; numeric CIKs remain the stable identifiers.
- SEC Form 13F Data Sets may be considered later as a batch optimization, but Phase 11 does not depend on them.

Performance diagnostics:

- `INCLUDE_PERFORMANCE_DIAGNOSTICS=false` by default.
- When enabled, daily reports include `performance_diagnostics` with total timing, macro/market/SEC/smart-money/candidate timing, network call count, cache hit/miss count, and bounded-fetch skip count.
- Diagnostics never include secrets, SEC User-Agent values, or tokenized URLs.

## Project Guardrails

Before changing an endpoint, verify Pydantic models, JSON schemas under `schemas\`, frontend TypeScript types, and `docs\API_SPEC.md` together. Mock raw data should be accessed through `backend.app.raw_store.repository`; live API clients should not be called from engines directly.
