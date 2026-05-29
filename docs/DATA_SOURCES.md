# DATA_SOURCES.md

## MVP Rule

Mock fixtures remain the default. Phase 8 added opt-in live market prices, Phase 9 adds opt-in live FRED-compatible macro data for selected US macro fields, Phase 10.5 adds opt-in official SEC EDGAR Form 4 insider transactions, Phase 11 adds opt-in official SEC EDGAR 13F institutional holdings, and Phase 17 adds opt-in official SEC EDGAR Companyfacts financial cross-checks. Phase 35 adds FRED `UMCSENT` as Daily Report context-only consumer sentiment and explicit yfinance-derived market-context coverage metadata. Phase 37 adds an external provider adapter foundation for future FMP, OpenBB sidecar, Alpha Vantage, and USASpending integrations. Phase 38 adds the first concrete Phase 37 adapter: opt-in FMP earnings-call transcript evidence for analyze-stock. Phase 39 maps FMP transcript analysis into non-scoring Jane C2/C17 external evidence context. Phase 40 adds opt-in USASpending.gov federal award evidence for C15 Government Relationship context. Phase 41 adds opt-in OpenBB sidecar / Stockgrid large options block evidence for the Smart Money options component. Phase 42 adds opt-in FMP financial statements and TTM ratios as an ADR / SEC-gap financial proxy for analyze-stock. Phase 57 adds `macro_flow_signal_breakdown` / `phase57_macro_flow_signal_breakdown_v1` as a non-scoring analyze-stock explanation layer for existing macro and flow sources; it is not a trading signal and does not change final score. Phase 8.1 makes source status, freshness, and fallback state visible in API responses and the frontend.

Phase 64 Evidence Gap Inbox notes:

- `evidence_gap_inbox` (`phase64_evidence_gap_inbox_v1`) is generated from existing analyze-stock response state; it does not trigger provider calls. It uses gap types such as `manual_evidence_required`, `source_setup_required`, `provider_cache_refresh_required`, and `adr_or_foreign_filer_limitation`.
- C19 SEC 13F gaps route to Operations when cache/setup review is needed; Form 4 fallback routes to SEC EDGAR user-agent/source setup review.
- ADR / foreign-filer limitations route to manual evidence/local filing review and are not automatic company-quality downgrades.
- All items preserve `affects_score=false`, `final_score_unchanged=true`, and `not_investment_advice=true`.

Phase 63 editable 13F manager universe notes:

- `GET/PUT/DELETE /api/operations/settings/13f-manager-universe` (`phase63_13f_manager_universe_settings_v1`) makes the SEC 13F target-manager universe locally editable.
- Effective precedence is `local_settings` > `startup_env` > `bundled_starter_universe`; diagnostics surface the active source for comparability review.
- Local settings update future 13F target-manager reads but do not trigger provider calls, and the settings layer does not change scoring or make 13F evidence real-time.
- Saved values are manager CIKs only; no API key values or secrets are accepted or returned.

Phase 62 operations diagnostics notes:

- `GET /api/operations/diagnostics` (`phase62_operations_diagnostics_v1`) exposes read-only Provider Health, Coverage Readiness, and 13F Runtime Universe visibility.
- Provider Health covers SEC 13F, SEC Form 4, USPTO PatentsView, FRED macro, yfinance, FMP financial proxy, FMP transcript, USASpending, OpenBB sidecar, SEC Companyfacts, and Daily Report snapshot/raw-store.
- Coverage Readiness maps C18 to USPTO `patent_count` and C19 to SEC 13F `institutional_support` / `fund_support` while preserving non-scoring/manual-review boundaries.
- Diagnostics expose only safe booleans such as `has_api_key`; `api_key_values_returned=false` and API key values are never returned.
- Phase 62 does not trigger provider calls and does not make 13F manager universe settings editable.

Phase 66 source-health action notes:

- `GET /api/operations/diagnostics` exposes `source_health_actions` (`phase66_source_health_actions_v1`) derived from existing provider diagnostics and Coverage Readiness rows.
- Actions cover missing API keys, missing SEC EDGAR user agent, disabled providers, and cache/readiness issues as routeable operations tasks.
- Daily Report `command_center.source_health_alerts` reuses the highest-attention source-health actions; this does not trigger provider calls or change score/verdict behavior.
- API key values and credential strings remain outside payloads; only safe booleans and setup categories are returned.

Phase 65 daily command-center notes:

- Daily Report `command_center` is derived from existing report fields (`today_research_actions`, `macro_delta`, `watchlist_delta`, and data-quality/source-health metadata).
- It does not trigger new provider calls, does not fetch per-ticker deep analysis, and does not alter scores or verdicts.
- Route hints are UI/workflow pointers only: `daily_report`, `operations`, `stock_research`, and `evidence_library`.

Phase 61 daily-efficiency notes:

- Daily Report adds `macro_delta` (`phase61_macro_delta_v1`) by comparing current macro score, VIX, 10Y-2Y spread, and available CPI/PPI observations with the latest stored Daily Report snapshot.
- Daily Report adds `watchlist_delta` (`phase61_watchlist_delta_v1`) for configured candidates, including price-change placeholder, overheat-score change, Form 4 placeholder, SEC 13F source/status, and data issue context.
- Overheat score adds `derived_metrics.source_backing` / `phase61_overheat_source_backing_v1` to disclose configured live/derived versus mock/fallback weight. This is transparency only and keeps `final_score_unchanged=true`.
- C18 USPTO and C19 13F Coverage Matrix links are completion gates: provider-backed patent counts and candidate-specific 13F target matches can improve non-scoring coverage completeness, but fallback/no-position states must not false-cover criteria.

## Phase 13 Endpoint Roles

`POST /api/analyze-stock` is the primary consumer of source evidence. It validates a user-provided US ticker and may reuse market, FRED macro, SEC Form 4, and SEC 13F snapshots through the raw-store boundary.

Daily reports remain snapshot-first background context, source-health visibility, cache warmup, and environment snapshots. They should not become the main ticker-discovery workflow.

Phase 35 Daily Report source coverage notes:

- FRED `UMCSENT` is fetched with the other FRED macro series when live macro data is enabled. It appears as `consumer_sentiment` / `consumer_sentiment_trend` and under `context_only_fred_fields`; it is not part of `macro_v12_5` active scoring weights.
- yfinance SPY/QQQ/^VIX market data emits `market_context_coverage` with `source_type="derived"` and provider `derived_from_yfinance` for index drawdown/recovery, volatility, and volume/extension context.
- Daily Report UI coverage separates live, cached-live, derived-live, fallback, mock, and missing-source-date components. This is source-health visibility only and does not make Daily Report the primary user workflow.

Phase 37 external provider adapter notes:

- Future FMP transcript/ratio, OpenBB sidecar, Alpha Vantage, USASpending, and USPTO PatentsView adapters must use the shared `ExternalProviderConfig` / `ExternalProviderStatus` foundation before exposing source evidence.
- Safe provider registry snapshots may disclose `enabled`, `requires_api_key`, `has_api_key`, `base_url`, and `cache_ttl_days`, but must never disclose API-key values.
- Phase 37 config toggles are inert until future phases add concrete fetch adapters.

Phase 38 FMP transcript source notes:

- `USE_LIVE_FMP_DATA=true` and `FMP_API_KEY` enable the FMP transcript adapter for `POST /api/analyze-stock`; disabled or missing-key states return explicit insufficient-data context instead of failing the analysis.
- Raw FMP transcript payloads are fetched from the documented legacy v4 batch endpoint (`/api/v4/batch_earning_call_transcript/{symbol}?year={year}&apikey=...`) for the current year and, when needed, the prior year; snapshots are cached under the raw-store boundary using `FMP_CACHE_TTL_DAYS`; cached-after-failure responses are labeled `cached_live` with fallback metadata.
- FMP API keys are used only for outbound provider calls and are never returned in provider registry snapshots, `source_status`, transcript analysis payloads, docs examples, or frontend UI.
- Transcript analysis is deterministic, LLM-free, non-scoring, and research context only. Management statements are not treated as independently verified facts and must be checked against filings and financial results.

Phase 39 transcript criteria mapping notes:

- `jane_criteria_external_evidence` is derived from the existing FMP transcript analysis; it does not add a new provider call and does not require additional secrets.
- The current mapping covers Jane C2 (Visionary Founder / CEO) and C17 (Mission and Narrative Power), labeling management-language evidence as `provider_backed` or `cached_live` when transcript data is available.
- C2/C17 transcript evidence can improve Coverage Matrix completeness but remains manual-review, non-scoring, and not independently verified.
- Disabled, missing-key, empty, or failed transcript states map to explicit C2/C17 `insufficient_data` items rather than failing analyze-stock.

Phase 40 USASpending source notes:

- `USE_LIVE_USASPENDING_DATA=true` enables the USASpending.gov contract-awards adapter for `POST /api/analyze-stock`; no API key is required.
- The adapter searches recipient candidates, fetches award records, caches raw snapshots under `USASPENDING_CACHE_TTL_DAYS`, and labels cache-after-failure responses as `cached_live`.
- `government_relationship_evidence` aggregates federal award count, obligated amount, and top awarding agencies, then maps evidence to Jane C15 submetrics such as `government_contracts` and `defense_or_infrastructure_status`.
- Recipient/entity matching can include subsidiaries or similarly named entities. The evidence remains non-scoring, manual-review context only and is not treated as independently verified moat evidence.
- Disabled, empty, or failed USASpending states return explicit C15 `insufficient_data` evidence instead of failing analyze-stock.

Phase 47 USPTO PatentsView source notes:

- `USE_LIVE_USPTO_PATENTS_DATA=true` enables the USPTO PatentsView patent-count adapter for `POST /api/analyze-stock`; no API key is required. Phase 55 makes this no-key provider enabled by default while preserving `USE_LIVE_USPTO_PATENTS_DATA=false` as an explicit opt-out / disabled-provider state.
- The adapter queries `https://search.patentsview.org/api/v1/patent/` for assignee organization names matching the company name and patent dates in the last three years, then caches raw snapshots under `USPTO_PATENTS_CACHE_TTL_DAYS`.
- `patent_ip_evidence` normalizes `total_hits` into `patent_count`, keeps up to 10 sample patent records, and maps positive counts to Jane C18 `patent_count` Coverage Matrix context.
- Phase 53 surfaces disabled-provider activation guidance in C18 Coverage Matrix limitations / `next_manual_check` when `USE_LIVE_USPTO_PATENTS_DATA=false`, rather than leaving the row as generic insufficient evidence.
- Assignee/entity matching can miss subsidiaries or include similarly named/acquired entities. Patent count remains non-scoring, manual-review context only and is not treated as independently verified defensibility.
- Disabled, empty, or failed PatentsView states return explicit C18 `insufficient_data` evidence instead of failing analyze-stock; cache-after-failure responses are labeled `cached_live`.

Phase 55 Coverage Matrix source notes:

- SEC 13F remains controlled by `USE_LIVE_SEC_13F` and remains delayed quarterly evidence. When the existing smart-money 13F path observes a candidate-specific target match, analyze-stock can partially cover C19 `institutional_support` and `fund_support` with `financial_proxy_source="sec_13f"`, `source_quality="filing_backed"`, and human-review limitations.
- `research_context.theme` is not fetched from external sources and does not trigger automatic theme discovery. Phase 56 makes it a user-supplied validation target in `theme_validation_context` only: C11 `jane_theme_alignment` is not auto-covered by matching theme text, `ranking_or_scoring_policy="not_ranked_or_scored"`, `affects_score=false`, and users must supply separate evidence for actual company revenue exposure, industry CAGR, policy support, and capital inflow. This does not change final score, verdict, or investment-advice boundaries.

Phase 41 OpenBB sidecar options notes:

- `USE_OPENBB_SIDECAR=true` enables the OpenBB sidecar / Stockgrid options adapter for `POST /api/analyze-stock`; `OPENBB_BASE_URL` defaults to `http://127.0.0.1:6900`.
- This repo uses HTTP calls to the sidecar only. Do not import OpenBB modules, vendor OpenBB code, or couple product code to OpenBB internals; this preserves the intended AGPL sidecar boundary.
- Raw sidecar snapshots are cached under the raw-store boundary using `OPENBB_CACHE_TTL_DAYS`; cache-after-failure responses are labeled `cached_live` with fallback metadata.
- When provider-backed Stockgrid blocks are available, the existing `options_abnormal_activity_score` uses normalized option volume, open interest, abnormal volume ratio, call/put ratio, large block count, total premium, order type, and sentiment score.
- Disabled, empty, failed, or unreachable sidecar states return explicit source status and preserve mock/fallback disclosure instead of failing analyze-stock.
- Options flow is supplemental smart-money context only. It is not a trading signal, recommendation, or instruction.

Phase 42 FMP financial proxy notes:

- `USE_LIVE_FMP_DATA=true` and `FMP_API_KEY` enable the FMP financial statements / TTM-ratios adapter for `POST /api/analyze-stock`; the same toggle/key may also enable transcript evidence, but transcript availability and financial proxy availability are independent capabilities.
- The adapter fetches FMP stable income-statement, balance-sheet-statement, cash-flow-statement, and ratios-ttm endpoints with `symbol={ticker}` query parameters, then emits `fmp_financial_proxy` with normalized statements, derived metrics, ratio counts, currency/fiscal-period metadata, sanitized source status, and raw-store cache metadata.
- Analyze-stock uses the FMP proxy only when SEC Companyfacts lacks usable filing facts, such as ADR or foreign-issuer SEC gaps. Filing-backed SEC Companyfacts remains the preferred financial source when available.
- Phase 46 can use FMP-backed `rd_to_revenue_pct` / R&D expense fields as auto-derived C5 `rd_percent_of_revenue` Coverage Matrix evidence for ADR / SEC-gap cases; this remains a non-scoring proxy with verification limitations.
- `data_quality_summary.fmp_financials` exposes availability, metric counts, TTM ratio counts, currency, fiscal year, and whether the proxy filled the financial-quality gap. This is data-quality/context visibility, not an automatic confidence upgrade.
- FMP financial statements never inherit FMP transcript disabled/fallback states; disabled, missing-key, empty, or failed financial endpoints return explicit insufficient-data source status instead of failing analyze-stock.

Future Industry Radar is optional/future/reference only. Analyze-stock must not depend on automatic theme discovery and must remain usable when theme radar data is missing or stale.

Phase 14 adds user-facing source-quality composition for analyze-stock without adding providers. The endpoint keeps raw evidence available for audit while leading with `candidate_validation_summary`, `evidence_matrix`, `data_quality_summary`, `score_driver_breakdown`, and `next_manual_checks`. Fallback or cached-after-failure SEC evidence lowers confidence and appears in fallback evidence categories. CNN Fear & Greed and ISM Manufacturing PMI remain excluded from scoring.

Phase 43 refines source-quality semantics without adding providers. Cached-live Form 4 evidence with `fallback_used=true` is treated as fallback-limited; optional FMP transcript/financial fallback states are disclosed under `optional_provider_fallback_categories` instead of core fallback penalties; ADR / foreign-filer cases expose `foreign_filer_context` so structural SEC Companyfacts, 13F, yfinance `shortRatio` / `shortPercentOfFloat`, and data-structure coverage limits are explained to the user. Phase 53 further clarifies that ADR source-quality Grade D can reflect source coverage rather than company quality.

Phase 17c cleans up analyze-stock data-quality categories. `fallback_evidence_categories` are based on actual fallback source status, `mixed_with_fallback` evidence quality, or score-affecting fallback subcomponents. Derived-live macro context is not fallback when active `macro_v12_5` components are live/cached/derived, mock context score weight is 0, and excluded ISM/CNN indicators have `affects_score=false` with weight 0. `source_type: "derived"` is not fallback by itself, and `fundamentals_cross_check.agreement_level: "low"` is a discrepancy/review signal rather than fallback evidence.

Phase 18 adds structured manual qualitative evidence as an optional analyze-stock input. The system does not fetch `source_url`, scrape websites, ingest news, use YouTube/social/sentiment sources, or add paid providers. User-provided qualitative evidence is labeled `source_quality: "user_provided"` with `source_type: "derived"` and provider `user_provided_qualitative_evidence`; it is not mock evidence and not fallback evidence. It can only support preliminary Jane qualitative criteria, requires manual verification, and cannot turn `research_context.theme` into verified evidence by itself.

Phase 19 stores reusable manual qualitative evidence in a local JSON evidence library under the raw-store boundary. Saved evidence is loaded by ticker for analyze-stock, merged with request-scoped qualitative evidence, and deduplicated. Evidence items carry `origin: "saved_library"` or `origin: "request_scoped"` for audit. Archived and rejected saved evidence remains stored but is audit-only and excluded from analyze-stock scoring, active evidence counts, criteria support, and positive score drivers.

Phase 20 adds local review workflow and evidence-quality metadata. `evidence_quality_score` measures completeness and review readiness only; it is not a truth score and does not independently verify the claim. Reviewed evidence remains `user_provided`, stale evidence remains visible but capped in qualitative impact, and `source_url` is stored only as metadata without fetching or validation.

Phase 21 adds manual comparison context hooks to the same evidence library. Evidence may include `comparison_context` with peer companies, comparison type, claimed advantage, comparison summary, source basis, period, and limitations. This is user-provided metadata only: the system does not fetch source URLs, scrape competitor sites, or automatically verify peer claims. Comparison evidence can support preliminary Jane criteria such as monopoly power, network effect, disruptive innovation, continuous R&D, and mega-trend fit, but it remains capped, cannot become independently verified, and cannot upgrade source-quality grade by itself.

Phase 22 adds a Manual Evidence Dashboard summary API and frontend tab. The dashboard reads only the local manual evidence JSON store, summarizes portfolio-level evidence inventory, stale and review queues, archived/rejected audit rows when explicitly requested, criteria coverage by ticker, comparison-evidence counts, and a peer-company index derived only from user-provided `comparison_context`. It does not call live providers, does not call analyze-stock per ticker, does not fetch or validate `source_url`, and does not verify competitor claims. `review_due_count` is preserved as the count of items with any scheduled `next_review_due_at`; `review_scheduled_count` is the same explicit scheduled-review count; `review_overdue_count` is the subset due at or before dashboard generation.

Phase 23 adds a local Candidate Research Workspace. Candidate entries are user-provided workflow metadata stored under `CANDIDATE_WORKSPACE_DIR`; they are not source evidence and do not affect analyze-stock scoring. Candidate list and dashboard endpoints read the local workspace and Manual Evidence Library summaries only. They do not discover themes or tickers, call yfinance, SEC, FRED, web, YouTube, social, sentiment, paid APIs, Future Industry Radar, or fetch/validate `source_url`. Candidate analyze is explicitly per candidate and reuses the existing analyze-stock pipeline.

Phase 24 extends that same local workspace with review note history, compact analysis metadata history, status transition validation, filters, sorting, review queue reason codes, and evidence coverage badges. These fields are local UX and audit metadata only. Review notes are not reusable manual evidence unless explicitly saved through `/api/manual-evidence`, analysis history stores compact metadata rather than full reports, and badges do not change scoring.

Phase 24.6 makes the validation-first workflow explicit. Stock Research and `POST /api/analyze-stock` remain the primary product path for user-supplied tickers. Candidate Workspace, Evidence Library, and Evidence Dashboard are supporting local workflow and evidence-quality tools only; they do not discover tickers, call live providers for dashboards, fetch source URLs, or affect analyze-stock scoring.

Phase 25 adds export and backup surfaces without adding data sources. Analyze-stock validation export calls the existing analyze-stock pipeline and packages the response as JSON or Markdown for review; it does not change scoring, does not persist request-scoped evidence, and redacts secrets, raw provider URLs, and local paths. Local backup export reads only local Manual Evidence Library and Candidate Workspace stores; it does not call analyze-stock, live providers, web sources, source URLs, provider caches, Future Industry Radar, or import/restore workflows.

Phase 26.4 adds source-quality and Form 4 interpretation hardening without adding providers or fetch behavior. SEC/yfinance discrepancy explanations help reviewers understand provider normalization, filing concept coverage, and period-alignment limits. `macro_environment` source quality is derived through `macro_v12_5`; excluded non-scoring context such as CNN Fear & Greed or unsupported ISM PMI does not downgrade the macro row when active inputs are live/cached/derived and non-fallback. Smart-money source-quality breakdowns disclose delayed quarterly 13F, mock/fallback/cached-after-failure Form 4 limits, and mock options context. Valuation-risk explanations are research context only, and prioritized manual checks are validation tasks.

Phase 15 live-enables company profile and fundamentals through the existing repository-backed yfinance dependency. `company_profile` may be live or cached-live with `provider: "yfinance"`. `financial_quality` may use yfinance fundamentals and provider-normalized fields. `valuation_context` is derived from yfinance profile and fundamentals inputs with `provider: "derived_from_yfinance"`. Valuation context is risk context only. Missing financial fields are listed in `missing_data` and are not fabricated. If yfinance is unavailable after a live attempt, mock fallback data is clearly labeled with `fallback_used=true`. Leadership evidence remains mock-disclosed until a later live leadership phase.

Phase 16 uses the same yfinance fundamentals path to harden company-quality evidence. `jane_company_quality` is derived from explicit Jane criteria and only scores criteria that have available evidence. Qualitative moat, founder/CEO, network effect, and disruption evidence is marked insufficient when unavailable. `research_context.theme` is user context only and does not verify mega-trend fit. `financial_statement_signals` derives revenue growth, operating margin, net income, operating cash flow, cash buffer, debt, receivables, inventory, CapEx/OCF, and dilution checks from available fundamentals. Missing fields are not fabricated.

Phase 17 adds official SEC EDGAR Companyfacts as a filing-backed cross-check for financial statement signals. SEC Companyfacts uses `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`, requires `SEC_EDGAR_USER_AGENT`, caches raw/parsed snapshots, and never exposes the User-Agent, headers, or raw provider URL in responses or fallback reasons. SEC Companyfacts complements yfinance; it does not replace yfinance as the MVP market/company provider. Concept coverage varies by issuer and reporting period, so missing concepts are listed in `missing_data` and are not guessed. SEC/yfinance discrepancies appear as review signals in `fundamentals_cross_check`. Phase 34 expands this layer with R&D expense and period-aligned multi-year margin/free-cash-flow trend proxies that can support Jane coverage validation for criteria 5, 6, and 10.

Legacy `leadership_score` remains mock-only for backward compatibility and is deprecated by `jane_company_quality`; it must not boost candidate confidence as live company-quality evidence.

Phase 15.5 stabilizes source architecture without adding providers or changing scoring. Daily batch refresh uses `DailyBatchContext` instead of mutating global config for temporary live-fetch and price-reference warmup state. `research_pipeline.py` is the main daily pipeline; `mock_pipeline.py` is a compatibility shim. `repository.py` is a raw-store facade over focused cache modules. Daily report candidates are config-driven through `DEFAULT_DAILY_REPORT_CANDIDATES`, and analyze-stock remains request-ticker driven. Source-status enrichment is legacy compatibility only; new engines must emit `source_status` directly.

`USE_LIVE_COMPANY_DATA=true` enables this company-data path directly. If unset, it follows `USE_LIVE_MARKET_DATA`. `COMPANY_DATA_PROVIDER` defaults to `yfinance`. No paid provider is added, and no website scraping is used.

SEC Companyfacts now supplies the official filing-backed financial cross-check layer for analyze-stock. It may also provide financial proxy coverage for R&D intensity, scalability, and cash-flow quality where aligned filing facts exist. Qualitative Jane criteria still require independent qualitative evidence and are not inferred from Companyfacts.

## Phase 18 Manual Qualitative Evidence

Analyze-stock accepts optional `qualitative_evidence` items for moat, founder/CEO, disruption, network effect, continuous R&D, and mega-trend fit. Each item must include a criterion, evidence type, summary, source label/date when available, confidence, user-provided flag, and limitations. The system validates the item locally, rejects unsafe or unsupported evidence, caps user confidence above 0.8 to 0.7, and returns `qualitative_evidence_assessment` for audit.

Accepted user-provided evidence may move a covered qualitative criterion from insufficient to preliminary/user-provided, but it remains manually reviewable and not independently verified. Excluded scoring indicators, missing optional indicators, limitations, and `source_type: "derived"` do not automatically create fallback evidence categories.

## Phase 19 Manual Evidence Library

Manual evidence endpoints manage local-only evidence items:

- `GET /api/manual-evidence?ticker=NVDA`
- `GET /api/manual-evidence/{evidence_id}`
- `POST /api/manual-evidence`
- `PATCH /api/manual-evidence/{evidence_id}`
- `DELETE /api/manual-evidence/{evidence_id}` soft-archives evidence

Request-scoped qualitative evidence is not automatically saved. Saved manual evidence remains `user_provided`, preliminary, not independently verified, not mock, and not fallback. Saved evidence cannot make `source_quality_grade` A by itself, cannot make qualitative criteria independently verified, and cannot create investment instructions.

Phase 20 quality fields include `source_reliability_label`, `evidence_quality_score`, `evidence_quality_label`, `evidence_quality_reasons`, `is_stale`, `stale_reason`, `expires_at`, `reviewed_at`, `reviewed_by`, `review_notes`, `last_reviewed_at`, and `next_review_due_at`. These fields support local review workflow and auditability only.

Phase 21 comparison fields include optional `comparison_context` with `comparison_type`, `subject_company`, `peer_companies`, `comparison_summary`, `claimed_advantage`, optional metric metadata, `comparison_period`, `source_basis`, and limitations. Peer companies and claimed advantage are manual claims requiring verification; they are not fetched, validated, or inferred from market cap or price performance.

## Phase 22 Manual Evidence Dashboard

`GET /api/manual-evidence/dashboard` is a local-only operational metadata endpoint over the saved Manual Evidence Library. It supports filters for ticker, review status, criterion, stale-only, scheduled-review-only, comparison context, and minimum quality label. Archived and rejected evidence is excluded by default and appears in `audit_queue` only when `include_archived=true` or `include_rejected=true`.

The endpoint returns `source_status.source_type: "derived"` with provider `local_manual_evidence_library`. It never uses `source_type: "mixed"`, never calls yfinance, SEC, FRED, web, YouTube, social, sentiment, paid APIs, or Future Industry Radar, and never fetches or validates source URLs. Peer company index rows are derived only from user-provided comparison context and are not externally validated.

Phase 54 adds ADR Manual Evidence Library UX and Review Queue Integration on top of this local-only endpoint. Saved ADR manual evidence preserves `adr_evidence_type`, `document_title`, `document_date`, `filing_period`, `local_market`, and `local_ticker` in dashboard queue items, uses `document_date` as a `source_date` fallback for freshness review, and emits `adr_review_label`, `adr_review_guidance`, `affects_score=false`, and `not_investment_advice=true` for ADR review workflow visibility. These fields are operational review metadata only; they do not fetch filing URLs, verify translations, change source-quality truth scores, or alter Jane scoring/verdict output.

## Phase 23 Candidate Research Workspace

Candidate Workspace endpoints manage local-only user-supplied ticker ideas:

- `GET /api/candidates`
- `GET /api/candidates/{candidate_id}`
- `POST /api/candidates`
- `PATCH /api/candidates/{candidate_id}`
- `DELETE /api/candidates/{candidate_id}` soft-archives a candidate
- `POST /api/candidates/{candidate_id}/refresh-evidence-summary`
- `POST /api/candidates/{candidate_id}/analyze`
- `GET /api/candidates/dashboard`

The dashboard source status is `source_type: "derived"` and `provider: "local_candidate_workspace"`. Status values are `watching`, `researching`, `reviewed`, and `archived`; these are workflow states only and not investment recommendations. Evidence summaries are derived from active local Manual Evidence Library records and exclude archived or rejected evidence from active counts.

Phase 24 candidate workspace additions remain local-only:

- Review notes are append-only user-provided workflow notes and are safety-checked.
- Analysis history stores compact metadata for the latest candidate analyze runs.
- Status transitions are workflow validations only and do not alter analyze-stock scoring.
- Filters, sorting, review queues, and evidence badges read the local candidate store and local evidence summaries only.

## Phase 17 Official SEC EDGAR Companyfacts

Default:

- `USE_LIVE_SEC_COMPANYFACTS` follows `USE_LIVE_COMPANY_DATA`
- live Companyfacts fetches require `SEC_EDGAR_USER_AGENT`
- if unavailable, analyze-stock remains usable and lists SEC Companyfacts items in `missing_data`

Opt-in:

```powershell
$env:USE_LIVE_SEC_COMPANYFACTS="true"
$env:SEC_EDGAR_USER_AGENT="Your Name your.email@example.com"
uvicorn backend.app.main:app --reload
```

Implemented SEC endpoint:

- `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

Mapped concepts:

- revenue, gross profit, operating income, net income
- operating cash flow and CapEx
- cash, debt, stockholders' equity
- receivables and inventory
- shares when a reliable share concept exists

Repository behavior:

- live Companyfacts fetches are made only through the raw-store/repository boundary
- successful snapshots are cached under `backend/raw_store/cache/sec_companyfacts` unless `SEC_COMPANYFACTS_CACHE_DIR` overrides it
- cached live data within `SEC_COMPANYFACTS_CACHE_TTL_DAYS` returns `source_type: "cached_live"`
- fallback reasons are sanitized as `SEC Companyfacts fetch failed; cached or provider fallback used.`
- no User-Agent value, request header, or raw Companyfacts URL is stored or returned

Freshness:

- `freshness_window: "latest_company_filing"`
- `source_date` is the latest filing date used when available, otherwise the latest report period

Limitations:

- SEC Companyfacts concept coverage varies by issuer and period
- SEC FY values may differ from yfinance TTM/provider-normalized values
- Phase 17a aligns income-statement and cash-flow facts by annual fiscal period before computing margins, FCF, and CapEx/OCF ratios
- Phase 34 uses the same period-alignment rule for R&D/revenue, multi-year gross/operating margin trend, and multi-year free-cash-flow margin trend proxies
- stale revenue, CapEx, or balance-sheet facts are not mixed into current-period derived metrics
- invalid SEC derived ratios are marked with `invalid_period_alignment` and yfinance may remain the provider-backed fallback for financial signals
- discrepancies are human-review signals, not automatic failures
- share dilution is not fabricated when reliable share series are unavailable

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
# Optional override. If omitted, defaults to Berkshire, Vanguard, BlackRock, State Street, and Geode.
$env:SEC_13F_TARGET_MANAGERS="0001067983,0000102909,0001364742,0000093751,0001214717"
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

Aggregation and target matching:

- 13F row-level holdings are aggregated by CUSIP when available.
- If CUSIP is missing, the fallback grouping key is normalized issuer name plus title of class.
- Different CUSIPs are not merged solely because issuer names look similar.
- Portfolio totals and top-holding rankings use normalized `value_usd`, not `reported_value_raw`, unless `value_usd` is unavailable.
- `SEC_13F_TARGET_CUSIPS` is the preferred target configuration and produces high-confidence exact matches.
- `SEC_13F_TARGET_MANAGERS` defaults to five local CIKs: Berkshire Hathaway (`0001067983`), Vanguard (`0000102909`), BlackRock (`0001364742`), State Street (`0000093751`), and Geode (`0001214717`). The list can be overridden; explicitly setting it to an empty string keeps fixture/mock fallback semantics.
- `SEC_13F_TARGET_TICKERS` can match only through the bounded local ticker-to-CUSIP map. The system must not call external CUSIP APIs or scrape mappings.
- `SEC_13F_TARGET_ISSUERS` can resolve through exact local aliases. Issuer-name-only matching without CUSIP confirmation remains low confidence and must carry a limitation.
- Candidate-level 13F evidence uses the same local map but separates `candidate_specific_evidence` from `portfolio_context`.
- A manager's top holdings are portfolio context only; they are not support for an unrelated candidate ticker.
- Candidate support requires a CUSIP-confirmed match. If a mapped candidate CUSIP is absent from the configured manager portfolio, candidate output reports `no_reported_13f_position_observed`.
- Candidate output includes `interpretation_summary` and `score_contribution_allowed` so unmatched evidence is not confused with candidate-specific support.
- Candidate `portfolio_context.top_holdings_by_value` is capped by `SEC_13F_CANDIDATE_CONTEXT_TOP_HOLDINGS_LIMIT` and does not include the full holdings list.
- Manager display names are resolved only through a bounded local manager map. CIK remains the stable identifier, unknown CIKs fall back to the normalized CIK, and the local map is not authoritative.
- The local security map is not authoritative and is used only for deterministic target matching and value-confidence enrichment.
- Value confidence may be upgraded when local CUSIP-to-ticker mapping and a cached/reusable price reference are both available.
- The price-reference layer checks reusable market cache first, then uses a bounded per-ticker adapter instead of refetching for every 13F row.
- Daily report fast mode uses cached market data for 13F price references unless `ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST=true`.
- Fast mode can preserve 13F value confidence when mapped tickers already have cached market prices.
- Optional bounded cache warmup can be enabled with `PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT=true`, `PRICE_REFERENCE_CACHE_WARMUP_ON_STARTUP=true`, or `POST /api/price-reference/warmup`.
- Warmup deduplicates tickers, respects `PRICE_REFERENCE_CACHE_WARMUP_MAX_TICKERS` and `SEC_13F_PRICE_REFERENCE_MAX_TICKERS`, uses the existing yfinance adapter only at ticker level, and writes reusable market cache entries.
- Price-reference summaries distinguish `price_reference_grouped_holding_count`, `price_reference_row_count`, and `price_reference_ticker_count`; `price_reference_used_count` remains a backward-compatible grouped count.
- `price_reference_unavailable_tickers` lists mapped tickers without a cached or warmed reference, and `price_reference_mode` reports `cache_only`, `cache_with_bounded_warmup`, or `live_allowed`.
- If mapped 13F rows cannot obtain a reusable price reference, portfolio summaries include `price reference unavailable for mapped 13F holdings` in `missing_data`.
- Price references may not match the 13F report date exactly, and confidence is capped conservatively when the reference date differs materially from the 13F report date.
- QoQ comparison is by CUSIP and reflects reported quarterly 13F changes only. It does not imply real-time activity.
- Daily report output omits full row-level 13F data by default and keeps only portfolio summary, top holdings, target matches, capped QoQ changes, source status, limitations, and missing data.
- Full 13F rows appear only under `raw_data_full.holdings` when `INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT=true`.
- Capped QoQ output reports both `qoq_changes_count_total` and `qoq_changes_limit`.
- Phase 19.5 logs sanitized warnings when cached 13F local-context enrichment fails. The warning may include manager CIK, holding ticker, and exception type, but it must not include raw SEC URLs, headers, User-Agent values, API keys, or secrets.

Repository behavior:

- live SEC 13F fetches are made only through `backend.app.raw_store.repository`
- successful snapshots are cached under `backend/raw_store/cache/sec_13f` unless `SEC_13F_CACHE_DIR` overrides it
- cached live EDGAR data within `SEC_13F_CACHE_TTL_DAYS` returns `source_type: "cached_live"` with `provider: "SEC EDGAR"`
- daily reports are cache-first and do not perform live SEC 13F fetches unless `ALLOW_LIVE_FETCH_ON_REPORT_REQUEST=true`
- missing `SEC_EDGAR_USER_AGENT` or fetch failures return cached live data when available, otherwise mock fallback 13F data with `source_type: "fallback"`
- fallback metadata includes a safe summarized `fallback_reason` and does not expose stack traces or `SEC_EDGAR_USER_AGENT`
- smart-money engines consume normalized 13F snapshots from the raw store and do not call SEC directly
- fallback mock 13F does not boost smart-money score and is labeled insufficient data
- mock/fallback candidate target matches are diagnostics only and do not affect candidate smart-money scoring

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
- manager-name display is limited to a small local mapping in v1; numeric CIKs remain the stable identifiers
- no reported 13F position observed is not a negative trading signal
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
- Mock, fallback, or cached-after-failure Form 4 source context is surfaced as limited `mixed_with_fallback` evidence in analyze-stock smart-money and insider-activity source quality.
- Repeated distributed, similar-sized code `S` dispositions may be flagged as a likely systematic pattern using a conservative heuristic. This is not confirmation of a 10b5-1 plan without filing footnote review and remains cautionary evidence requiring manual review.
- If all live rows are missing transaction codes, the smart-money Form 4 component remains neutral or insufficient and reports `transaction_code` in `missing_data`.

Repository behavior:

- live SEC fetches are made only through `backend.app.raw_store.repository`
- successful snapshots are cached under `backend/raw_store/cache/sec` unless `SEC_FORM4_CACHE_DIR` overrides it
- daily reports are cache-first and do not perform live EDGAR fetches unless `ALLOW_LIVE_FETCH_ON_REPORT_REQUEST=true`
- missing `SEC_EDGAR_USER_AGENT` or fetch failures return cached live data when available, otherwise mock fallback Form 4 data with `source_type: "fallback"`
- if a live SEC EDGAR Form 4 fetch fails after cache-first checks and cached live data is available, the component remains `source_type: "cached_live"` with fallback reason `Live SEC EDGAR Form 4 fetch failed; cached live data used.`
- Form 4 live fetches are bounded by `SEC_FORM4_MAX_FILINGS_PER_TICKER`, `SEC_FORM4_MAX_XML_DISCOVERY_PER_REPORT`, `SEC_FORM4_NETWORK_TIMEOUT_SECONDS`, and `SEC_FORM4_TOTAL_BUDGET_SECONDS`
- if Form 4 live fetch budget is exhausted and cached live data exists, the component remains `source_type: "cached_live"` rather than mock fallback
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

Still mock or excluded:

- DXY trend
- gold trend
- oil trend
- 13F, options, news, YouTube, and theme APIs
- ISM Manufacturing PMI is excluded from scoring and mock context because no valid licensed/live source is configured.
- CNN Fear & Greed is excluded from scoring and mock context because no licensed/stable source is configured.

Phase 11.8 source clarity:

- FRED-backed fields are live or cached-live FRED observations: federal funds, 10-year Treasury yield, 2-year Treasury yield, and unemployment rate.
- Derived-from-FRED fields are calculated from FRED observations: yield spread, CPI YoY, PPI YoY, fed policy trend, and unemployment trend.
- DXY, gold, oil, VIX, and equity drawdown/rebound context remain Phase 9 mock context until providers are added.
- CNN Fear & Greed and ISM Manufacturing PMI are excluded from scoring and mock context.
- Intentional mock context is not a live-source fallback. It uses `source_type: "mock"`, `fallback_used: false`, and the limitation `This field remains mock context in Phase 9 and is not live market evidence.`
- `macro_regime.macro_data_quality` and `data_quality.macro` expose live/derived/mock macro counts and whether confidence adjustment was applied.
- Macro confidence is adjusted when mock context contributes materially.
- Mixed FRED/mock macro output uses `source_type: "derived"` and `provider: "mixed_FRED_and_mock_macro"`; `source_type: "mixed"` is not valid.
- FRED API keys and tokenized provider URLs must not appear in logs, snapshots, API responses, exceptions, or fallback reasons.

Phase 12.1 live market context:

- The existing yfinance market-price integration is reused for low-risk macro context.
- VIX uses `^VIX`.
- Equity drawdown and gain from trough use `SPY` and `QQQ`.
- DXY uses `DX-Y.NYB`.
- Gold uses `GC=F`, with `GLD` as a documented yfinance fallback if the primary symbol is unavailable.
- Oil uses `CL=F`, with `USO` as a documented yfinance fallback if the primary symbol is unavailable.
- CNN Fear & Greed and ISM Manufacturing PMI are excluded from scoring.
- Daily reports reuse already fetched SPY, QQQ, and VIX market data for macro context when available, then use cache/live retrieval for the extra yfinance symbols.
- Yfinance-derived macro context uses `provider: "derived_from_yfinance"` and `freshness_window: "latest_expected_trading_day"`.
- If a market-context symbol is unavailable and no fresh cache exists, that field remains mock context with a clear limitation; it must not pretend to be live.
- When FRED and yfinance context coexist without remaining mock macro fields, the macro provider is `mixed_FRED_and_yfinance_macro` with `source_type: "derived"`.

Phase 12.3b FRED manufacturing PMI exclusion:

- ISM Manufacturing PMI is not live-enabled at this time.
- `NAPM` was tested and rejected as invalid.
- `IPMAN` is Industrial Production: Manufacturing and must not be used as PMI.
- Search candidates with `python -m backend.app.tools.fred_series_search "ISM Manufacturing PMI"`.
- Validate candidates with `python -m backend.app.tools.fred_series_validate <SERIES_ID>`.
- These tools are for future source exploration only and do not enable PMI in production reports.
- `ism_manufacturing_pmi` is absent from scoring components, source contribution, component source status, and mock context counts.
- Reports disclose the exclusion through `excluded_indicators` with `affects_score=false`.
- CNN Fear & Greed may be reconsidered only if a licensed/stable data provider is selected.
- Jane reference conditions may display Fear & Greed as methodology context only and never as live/mock evidence.
- FRED API keys, raw provider URLs, and query strings must not appear in fallback reasons, logs, snapshots, or API responses.

Phase 12.5 macro scoring calibration:

- The active macro scoring model is `macro_v12_5`.
- Active score inputs are limited to FRED-backed observations, FRED-derived metrics, yfinance-backed market context, and yfinance-derived market context.
- Weights total 100 across rates/policy, inflation, labor/recession resilience, market stress/volatility, cross-asset context, and rebound/recovery context.
- CNN Fear & Greed and ISM Manufacturing PMI are excluded indicators with `affects_score: false` and weight 0. They must not appear in active component contributions or missing active components.
- `macro_data_quality.scoring` reports active component count, active weight total, excluded component count, missing/stale/fallback active components, and the confidence basis.
- Macro confidence is not capped for mock context when `mock_macro_fields_count=0`; it is reduced for missing active fields, stale active fields, cached-live-after-failure use, and fallback active components.
- Mixed source summaries must use `source_type: "derived"` and must not use `source_type: "mixed"`.

Phase 12.6 macro score explanation:

- `macro_regime.macro_score_explanation` is a display-oriented summary of the existing `macro_v12_5` diagnostics.
- It groups active components by scoring group and shows raw value, component score, weight, weighted contribution, provider, source date, freshness window, and freshness status.
- It repeats excluded indicators separately with `affects_score: false` and weight 0 so UI panels do not mix excluded indicators with active score components.
- It includes confidence basis and deductions based only on active data availability, freshness, cached-live-after-failure state, fallback state, and missing active components.
- Jane methodology reference conditions remain separate display-only context and do not affect score or confidence.

Repository behavior:

- live FRED fetches are made only through `backend.app.raw_store.repository`
- successful live macro snapshots are cached under `backend/raw_store/cache/macro` unless `MACRO_DATA_CACHE_DIR` overrides it
- transient FRED 5xx and timeout failures are retried inside the adapter before the raw store considers fallback
- if a live FRED refresh fails and fresh cached-live FRED data exists, the raw store returns the cached-live snapshot before mock fallback
- missing API key, unsupported provider, or fetch failures without usable cached-live data return mock fallback macro data with `source_type: "fallback"`
- FRED fallback metadata is sanitized and must not expose `FRED_API_KEY` or tokenized FRED request URLs
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
- 13F: `quarterly_filing_delay`. Fresh window covers the latest quarter-end filing plus 45-day SEC deadline. Cache TTL is days-based (`SEC_13F_CACHE_TTL_DAYS`). Not daily freshness.
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

### Daily Report Performance Guardrails

- `DAILY_REPORT_FAST_MODE=true` by default.
- Fast mode keeps daily reports cache-first and adds the limitation `Daily report fast mode uses fresh cached live data when available.`
- `ALLOW_LIVE_FETCH_ON_REPORT_REQUEST=true` is still required for report-triggered SEC live refreshes when cache is missing or stale.
- `ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST=false` by default, so 13F price references use cached market data during daily reports.
- `PRICE_REFERENCE_CACHE_WARMUP_ON_REPORT=false` by default, so warmup is opt-in and daily reports remain fast.
- `INCLUDE_PERFORMANCE_DIAGNOSTICS=false` by default. When enabled, responses include timing and cache/network counters only; diagnostics must not expose secrets, SEC User-Agent values, or tokenized URLs.

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

- VIX
- news sentiment
- Jane methodology reference for CNN Fear & Greed, unscored

Potential sources:

- CNN Fear & Greed only if a licensed/stable provider is selected later
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

## Phase 58 Company Event / Insider / Lock-Up Signal Breakdown

`company_event_signal_breakdown` (`phase58_company_event_signal_breakdown_v1`) reuses existing SEC Form 4, SEC 13F, and options source-status metadata to present non-scoring `event_signals`. Form 4 remains transaction-code and footnote dependent; 13F remains delayed quarterly evidence; options remain ambiguous event context. Lock-up context is explicitly `lockup_data_not_available` because Phase 58 does not add prospectus, resale-registration, IPO calendar, or lock-up datasets. The layer is not a trading signal and does not change final scoring.

## Phase 59 Platform Business Quality Card

`platform_business_quality_card` (`phase59_platform_business_quality_card_v1`) reuses existing company fundamentals and user-supplied qualitative evidence to organize platform-business review metrics. `burn_rate` and `runway` are computed only when public cash/free-cash-flow proxies are already available. `contribution_margin_operating_leverage` can show operating-margin and free-cash-flow-margin proxies, but contribution margin still requires disclosure review. `gmv_growth`, `take_rate`, `net_dollar_retention`, `marketplace_liquidity`, `network_effect`, and `ltv_cac` remain manual or disclosed evidence; the system does not infer GMV, take rate, NDR, marketplace liquidity, or LTV/CAC from revenue or price history. Phase 59 does not add a provider, does not change final score, and should be treated as review context only.
