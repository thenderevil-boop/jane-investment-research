# Changelog

## Phase 53 — C18 USPTO Activation and ADR Grade Explanation Refinement

- Surfaced USPTO PatentsView disabled-provider guidance in C18 Coverage Matrix limitations / `next_manual_check`, so `USE_LIVE_USPTO_PATENTS_DATA=false` is explained as an activation state rather than silently appearing as generic insufficient C18 evidence.
- Added ADR / foreign-filer C3 guidance for yfinance short-interest gaps: unavailable `shortRatio` / `shortPercentOfFloat` is treated as source coverage limitation, not company-quality weakness.
- Refined ADR source-quality Grade D copy so users understand the grade describes data-source coverage / data-structure limits, not the investment quality of the underlying company.
- Preserved scoring, verdict labels, provider set, frontend fields, schema shape, and not-investment-advice boundaries.

## Phase 52 — ADR Manual Evidence Intake and Filing Reference Workflow

- Added ADR manual filing-reference metadata to request-scoped qualitative evidence and saved Manual Evidence Library records: `adr_evidence_type`, `document_title`, `document_date`, `filing_period`, `quoted_text`, `local_market`, `local_ticker`, and `translation_note`; supported `adr_evidence_type` values include `annual_report`, `local_regulatory_filing`, `governance_page`, `investor_presentation`, `earnings_webcast`, `company_ir_page`, and `other`.
- Preserved ADR metadata in `qualitative_evidence_assessment.evidence_items[]`, labels complete filing references as `source_quality="filing_backed"` / `verification_level="filing_backed"`, and keeps every manual evidence item `affects_score=false` and `not_investment_advice=true`.
- Uses `document_date` as a `source_date` fallback for ADR evidence, while missing-date ADR evidence enters the existing Phase 49 `stale_review_queue` via `missing_source_date`.
- Allows explicitly supplied `criterion_id` / `submetric` ADR evidence to map into Jane Coverage Matrix completeness without changing score weights, final verdicts, provider integrations, or automatic filing fetch behavior.
- Added frontend ADR evidence intake helper text, ADR metadata validation, docs, schemas, and contract tests.

## Phase 51 — ADR Foreign Filer Coverage Diagnostics

- Added top-level `foreign_filer_coverage_diagnostics` to `POST /api/analyze-stock` with detected ADR/foreign-filer signals, structural/provider coverage limitations, recommended manual checks, `affects_score=false`, and `not_investment_advice=true`.
- Separated SEC Companyfacts, SEC Form 4, 13F, FMP transcript, and local-filing coverage gaps from company-specific weakness so ADR/foreign-filer limitations remain workflow context rather than scoring penalties.
- Added ADR-aware `next_manual_check` guidance to affected Jane Coverage Matrix rows such as C2, C5, C10, C12, C17, and C19 while preserving coverage status, score, verdict, provider set, and threshold rules.
- Added frontend types and a neutral Foreign Filer / ADR Coverage Note section for Stock Research.

## Phase 50 — Yfinance C2 Insider Ownership and C3 Skepticism Refinement

- Added yfinance `heldPercentInsiders` / normalized insider-ownership pass-through and non-scoring C2 `founder_ownership` auto evidence.
- C2 insider ownership is capped as a preliminary financial proxy, requires human verification, and does not auto-cover `founder_is_ceo`, founder vision, milestone execution, or crisis execution.
- Refined C3 short-interest thresholds so `shortRatio` and `shortPercentOfFloat` produce high/moderate/low skepticism labels only when meaningful thresholds are met; very low short interest no longer fills C3 coverage by itself.
- Preserved scoring weights, forbidden-language boundaries, provider set, and investment-advice safeguards.

## Phase 49 — Evidence Freshness Policy and Stale Review Queue

- Added top-level `evidence_freshness_policy` to `POST /api/analyze-stock` documenting non-scoring freshness windows for manual evidence, provider caches, market data, filings, Form 4, 13F, and macro sources.
- Added top-level `stale_review_queue` with stale manual evidence, due-for-review manual evidence, missing-source-date evidence, and stale live/cached/derived source-status items.
- Queue items carry review priority, trigger, recommended action, optional source/review dates, optional manual evidence id, and `affects_score=false`; they may add manual checks but do not change final score, verdict, or investment-advice boundaries.
- Updated AnalyzeStock schema and frontend types so freshness policy and stale review queue remain part of the documented API contract.

## Phase 47 — USPTO PatentsView C18 IP Proxy

- Added opt-in USPTO PatentsView patent-count evidence for Jane C18 Patents and IP via `USE_LIVE_USPTO_PATENTS_DATA=true`; no API key is required.
- Added `patent_ip_evidence` with normalized patent count, sample patent records, source status, cache/fallback semantics, manual checks, limitations, and non-scoring C18 criteria evidence.
- Integrated C18 `patent_count` into the Coverage Matrix as provider-backed completeness context while preserving Jane Company Quality scoring and final verdict boundaries.
- Added 30-day raw-store caching under `USPTO_PATENTS_CACHE_TTL_DAYS`; cache-after-failure responses are labeled `cached_live` with fallback metadata.
- Preserved manual entity-matching review: PatentsView organization matching may miss subsidiaries, acquired entities, or patent relevance and does not prove defensibility.

## Phase 46 — Jane Auto Evidence Numeric Proxies: C3 + C5

- Added auto-derived financial proxy evidence for Jane C3 Early Market Skepticism from yfinance short-interest fields (`shortPercentOfFloat` preferred, `shortRatio` fallback) so `short_interest_proxy` can be partially covered without user input.
- Added auto-derived C5 R&D intensity coverage from `rd_to_revenue_pct` or R&D expense divided by revenue, including yfinance, SEC Companyfacts, and FMP ADR financial proxy sources.
- Marked C3 as a financial-proxy-capable canonical coverage row and preserved non-scoring Coverage Matrix semantics with explicit auto-derived limitations and no investment-advice language.

## Phase 45 — FMP Stable Financial Statements for ADR Proxies

- Updated the FMP financial proxy adapter from legacy `/api/v3/{statement}/{symbol}` URLs to the FMP stable statement endpoints using `symbol={ticker}` query parameters.
- Added normalization for stable endpoint responses that return a single JSON object instead of a list, fixing NOK-style ADR financial proxy availability.
- Preserved FMP key redaction, raw-store caching, SEC Companyfacts precedence, and optional-provider source-quality semantics.

## Phase 44 — FMP Transcript API Compliance

- Updated the FMP earnings transcript adapter to use the documented legacy v4 batch endpoint: `/api/v4/batch_earning_call_transcript/{symbol}?year={year}&apikey=...`.
- Added URL-compliance regression coverage for the required `year` and `apikey` query parameters while preserving API-key redaction in analyze-stock payloads.
- Added fallback-year behavior so the adapter queries the current year and then the prior year when current-year batch transcripts are empty, keeping recent-quarter transcript context available without changing scoring.

## Phase 43 — Source Quality Semantics: Form 4 fallback, Optional FMP, ADR coverage

- Fixed Form 4 fallback detection so cached-live snapshots with `fallback_used=true` are treated as fallback-limited evidence, not clean live accumulation signals.
- Split optional FMP provider fallbacks into `data_quality_summary.optional_provider_fallback_categories` so missing-key, disabled, or uncovered FMP transcript/financial endpoints are disclosed without being counted as core live-data fallback penalties.
- Added `data_quality_summary.foreign_filer_context` for ADR / foreign-filer cases such as NOK, explaining structural SEC Companyfacts and 13F coverage limits instead of presenting them as company-specific weakness.
- Updated Stock Research to show optional provider fallback categories, FMP optional-enhancement status, and ADR / foreign-filer coverage notes.

## Phase 41 — OpenBB Sidecar Stockgrid Options Evidence

- Added opt-in OpenBB sidecar options evidence for `POST /api/analyze-stock` via `USE_OPENBB_SIDECAR=true` and `OPENBB_BASE_URL`.
- Added an HTTP-only OpenBB Stockgrid adapter and raw-store cache for large option block data, keeping OpenBB as a sidecar service and avoiding direct OpenBB imports.
- Replaced the smart-money options component with provider-backed OpenBB/Stockgrid context when available, including large block count, total premium, option volume, open interest, call/put ratio, abnormal volume ratio, order type, and sentiment score.
- Surfaced OpenBB provider, large block count, and premium in the Stock Research Smart Money Source Quality Breakdown while preserving mock/fallback disclosure when the sidecar is disabled or unavailable.
- Preserved final smart-money weights, not-investment-advice boundaries, cache/fallback source status, and AGPL isolation by using only HTTP calls to the local sidecar.

## Phase 42 — FMP Financial Statements + TTM Ratios for ADR / SEC Gaps

- Added opt-in FMP financial statement and TTM-ratio proxy evidence for `POST /api/analyze-stock` via existing `USE_LIVE_FMP_DATA=true` and `FMP_API_KEY` settings.
- Added `fmp_financial_proxy` to analyze-stock responses with normalized income statement, balance sheet, cash-flow, derived metrics, TTM ratios, reported currency, fiscal year, filing date, cache/fallback status, and sanitized limitations.
- Analyze-stock uses FMP financial proxies only when SEC Companyfacts has insufficient usable facts (common ADR / SEC-gap case); valid SEC Companyfacts continues to take precedence.
- Added `data_quality_summary.fmp_financials` and Stock Research UI rendering for FMP proxy availability, metric counts, TTM ratios, currency, fiscal year, and whether it was used for financial quality.
- Preserved final scoring boundaries, transcript capability separation, provider secret redaction, and not-investment-advice behavior.

## Phase 40 — USASpending Government Relationship Evidence for C15

- Added opt-in USASpending.gov federal award evidence for `POST /api/analyze-stock` via `USE_LIVE_USASPENDING_DATA=true`; no API key is required.
- Added `government_relationship_evidence` with recipient candidates, award records, obligated amount, award count, top agencies, and non-scoring C15 criteria evidence.
- Integrated C15 government-contract evidence into the Coverage Matrix as provider-backed completeness context while preserving Jane Company Quality scoring and final verdict boundaries.
- Surfaced Government Relationship Context in the Stock Research Analyst Brief and preserved disabled/failure/cache states as explicit manual-review evidence.

## Phase 39 — Transcript Criteria Evidence Mapping for C2/C17

- Added `jane_criteria_external_evidence` to `POST /api/analyze-stock`, derived from FMP earnings transcript analysis.
- Mapped transcript language patterns into non-scoring Jane C2 (Visionary Founder / CEO) and C17 (Mission and Narrative Power) evidence items with support level, snippets, covered submetrics, manual checks, and limitations.
- Allowed C2/C17 Coverage Matrix rows to treat transcript evidence as provider-backed completeness context while preserving Jane Company Quality scoring and final verdict boundaries.
- Surfaced C2/C17 transcript criteria context in the Stock Research Analyst Brief and kept disabled/missing-key transcript states as graceful insufficient-data evidence.

## Phase 38 — FMP Earnings Transcript Evidence

- Added opt-in FMP earnings-call transcript evidence for `POST /api/analyze-stock`, using the Phase 37 provider foundation and `FMP_CACHE_TTL_DAYS` cache behavior.
- Added deterministic management narrative extraction for management consistency, strategy clarity, risk acknowledgement, customer demand, margin pressure, and capital allocation context.
- Surfaced `earnings_transcript_analysis` as a non-scoring analyze-stock section and displayed Management Narrative Context in the Stock Research Analyst Brief.
- Preserved final scoring, research verdicts, provider secrets, LLM-free deterministic behavior, and not-investment-advice boundaries.

## Phase 37 — External Provider Adapter Foundation

- Added a shared external provider configuration/status foundation for future FMP, OpenBB sidecar, Alpha Vantage, and USASpending adapters.
- Added safe provider registry snapshots that expose enablement, cache TTL, sidecar base URL, and API-key presence without exposing secrets.
- Added conversion from external provider status into the existing `DataSourceStatus` contract, including cache-hit, rate-limit, fallback, limitations, and missing-data metadata.
- Phase 37 does not fetch from external providers, change scoring, add frontend UI, or expose API keys.

## Phase 36 — Market Timing Condition Explanation v2

- Added a non-scoring `market_timing_condition_explanation_v2` checklist to `market_timing_context.derived_metrics` for Fed consecutive cuts, market drawdown/stabilization, VIX spike/recovery, and overheat/normal/fear state.
- Added explicit score-0 interpretation text: “Score 0 means Jane entry timing conditions are not met; this is expected near market highs.”
- Surfaced the checklist in the Stock Research Analyst Brief as entry-timing explanation context.
- Preserved existing market-timing scoring weights, labels, provider behavior, and research-only / not-investment-advice boundaries.

## Phase 35 — Daily Report Live/Derived Coverage Upgrade

- Added FRED `UMCSENT` consumer sentiment as Daily Report macro context with `context_only_fred_fields`; it is visible in raw macro context and source-quality metadata but remains outside `macro_v12_5` scoring and does not count as missing active score evidence.
- Added yfinance-derived `market_context_coverage` metadata for SPY/QQQ/^VIX index, volatility, and volume/extension context so Daily Report market evidence can distinguish derived-live context from mock/fallback inputs.
- Split the Daily Report Data Coverage UI from a combined “Live / derived” count into separate `Live`, `Cached live`, `Derived live`, `Fallback`, `Mock`, and `Missing source date` counts.
- Updated backend/frontend tests, schemas, docs, and local ignore hygiene. Phase 35 does not change analyze-stock final scoring or convert Daily Report into the main ticker-discovery workflow.

## Phase 34 — SEC Companyfacts Jane Financial Proxy Expansion

- Added SEC Companyfacts R&D concept parsing (`ResearchAndDevelopmentExpense` and `ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost`) with period alignment and invalid-ratio safeguards.
- Expanded SEC-derived financial proxy fields that flow into analyze-stock financial quality: `rd_expense_ttm`, `rd_to_revenue_pct`, `rd_to_revenue_trend_pct`, `gross_margin_trend_pct`, `operating_margin_trend_pct`, and `free_cash_flow_margin_trend_pct`.
- Coverage Matrix now treats filing-backed SEC Companyfacts proxies as validation evidence for Jane criteria 5 (continuous R&D), 6 (scalability), and 10 (cash-flow quality) while preserving manual qualitative evidence requirements and final scoring boundaries.
- Frontend coverage rendering already displays `financial_proxy_source`, covered/missing submetrics, source quality, and limitations; no new UI contract field was required.
- Added `tests/phase34_sec_companyfacts_jane_proxies.py` for parser, period-alignment, analyze-stock merge, and Coverage Matrix regression coverage.

## Phase 33 — Jane Evidence Library / Research Note Workflow

- Extended Manual Evidence Library records with optional research-note workflow metadata: `note_title`, `research_question`, `thesis_direction`, and `workflow_status`.
- Persisted the new metadata through create, list, get, patch, and saved-library analyze-stock flows while preserving existing ticker-scoped JSON storage.
- Surfaced research-note metadata in Stock Research qualitative evidence assessment and in the Evidence Library create/table UI.
- Added validation so research-note metadata rejects secret/API-key markers and investment-instruction language.
- Added backend and frontend regression coverage for metadata persistence, patching, analyze-stock propagation, and UI rendering.
- No scoring formula, provider behavior, live-source fetching, source URL fetching, or automatic qualitative ingestion changes.

## Phase 32 — Explanation Layer / Research Clarity

- Added a Stock Research `Research Signal Explanation` section immediately after Analyst Brief.
- Clarified common non-scoring interpretation points: Coverage Matrix versus Jane Company Quality, Market Sentiment as entry environment, fallback badges as lower-confidence evidence, 13F no-position observations as non-negative signals, and elevated valuation as risk context rather than a trading instruction.
- Added fallback Form 4 explanation copy when fallback source status is present, reinforcing that fallback disposition counts are treated as neutral context and are not scored as insider selling pressure.
- Added frontend regression coverage for the explanation section and Form 4 fallback neutrality copy.
- No backend scoring, provider behavior, JSON schema, 13F universe, or Form 4 scoring changes.

## Phase 31.8 — SEC 13F Manager Universe Expansion

- Expanded the default SEC 13F manager universe to five CIKs: Berkshire Hathaway, Vanguard, BlackRock, State Street, and Geode Capital.
- Added local manager metadata and SEC EDGAR alias resolution for the expanded default universe, including BlackRock's current default CIK mapping.
- Preserved explicit empty `SEC_13F_TARGET_MANAGERS` behavior so fixture/mock fallback remains available for deterministic tests and local mock runs.
- Added regression coverage for default manager ordering, fixture fallback semantics, and manager metadata/alias resolution.
- No scoring formula, schema, frontend, Form 4, or macro behavior changes.

## Phase 31.7 — Macro Source-Quality Test Determinism

- Stabilized Phase 26.4 macro source-quality regression coverage so it no longer depends on local live FRED/yfinance availability, credentials, or cache state.
- Split the macro source-quality assertions into explicit derived-live and fallback macro fixtures.
- Verified derived-live macro context remains `derived_live` and excluded from mock/fallback evidence categories.
- Verified fallback macro context remains `mixed_with_fallback`, does not count as reliable active live weight, and is reported in fallback evidence categories rather than mock-only categories.
- No production scoring, provider, schema, frontend, or Form 4 behavior changes.

## Phase 31.6 — Form 4 Fallback Scoring Hotfix

- Treat any Form 4 `source_type=fallback` as unreliable fallback for insider-activity scoring, even when the provider remains `SEC EDGAR` because cached/live SEC data was unavailable.
- Set fallback Form 4 insider activity to neutral `score=40` with `insider_activity_neutral` label and neutral trend so fallback disposition rows do not become `insider_distribution_risk`.
- Preserve the separate mock-fallback guardrail that prevents mock fallback Form 4 data from boosting smart-money score.
- Added regression coverage for SEC EDGAR fallback disposition rows and updated fallback mock expectations to preserve the slight fallback penalty.

## Phase 31.5 — Analyst Brief UI Readability

- Added Stock Research Analyst Brief as the first result section using existing analyze-stock fields.
- Surfaced Phase 31 volume/extension overheat context and social-heat human-verification wording in the UI.
- Moved export below the first-screen triage summary and collapsed raw evidence panels by default.
- Added Daily Report Data Coverage summary to reduce first-screen source-mode noise.
- No backend scoring, provider, schema, or API contract changes.

## Phase 31 — Overheat Volume & Extension Context

- Replaced `user_reported_social_heat_score` with `volume_and_extension_context_score` in overheat scoring while keeping the 0.12 component weight and existing label thresholds.
- Added yfinance-derived market features for `current_price`, `current_volume`, `avg_volume_52w`, and `ma_200d`; the overheat component derives `volume_ratio` and `price_vs_200d_pct` from those fields.
- Preserved Jane's social heat signal as a structured `jane_social_heat_check` human-verification item when `overheat_score >= 60`; it is not a scoring input.
- Updated `human_verification_queue` contracts to support both legacy strings and structured verification objects across daily reports, analyze-stock, JSON schemas, and frontend TypeScript types.
- Added Phase 31 tests for high volume/extension scoring, missing volume/MA data, social heat non-scoring behavior, market-feature derivation, and pipeline queue insertion.

## Phase 30 — Analyze-Stock Contract / Docs Sync

- Added `tests/phase30_contract_docs_sync.py` to guard against drift between backend Pydantic models, committed JSON schema, API docs, status docs, changelog, frontend TypeScript types, and live analyze-stock payloads.
- Added `tools/generate_schemas.py` to regenerate `schemas/analyze_stock.schema.json` from `AnalyzeStockResponse.model_json_schema()`.
- Confirmed Phase 27b qualitative evidence metadata (`criterion_id`, `criterion_name`, `submetric`), Phase 28 `jane_criteria_coverage`, and Phase 29 `validation_os_report` are represented in contract surfaces.
- Updated README, AGENTS.md, and API_SPEC to mark Phase 30 as a contract/docs synchronization guardrail.
- This phase does not change scoring, endpoint behavior, provider behavior, frontend UX, or investment-advice boundaries.

## Phase 29 — Validation OS Report

- Added `validation_os_report` to `POST /api/analyze-stock` as a non-scoring explainability and validation workflow report.
- Summarizes existing analyze-stock outputs: research label, validation level, data-quality grade, macro backdrop, Jane company quality context, Jane criteria coverage counts and gaps, financial statement signals, smart-money context, manual checks, source-quality caveats, and research-only limitations.
- Added backend schema models for `ValidationOSReport` and `ValidationOSEvidenceGap`.
- Added frontend `ValidationOSReportSection` and TypeScript contracts.
- Added backend and frontend tests covering report presence, safety boundaries, forbidden-language checks, evidence gap prioritization, and UI rendering.
- Updated documentation and `schemas/analyze_stock.schema.json` to keep the API contract synchronized.
- This phase does not change final scoring, macro scoring, provider behavior, source fetching, or investment-advice boundaries.

## Phase 28 — Jane Criteria Coverage Matrix

- Added `jane_criteria_coverage` to `POST /api/analyze-stock` as a non-scoring validation completeness matrix.
- Reports all 20 canonical Jane criteria with coverage status, covered/missing submetrics, evidence counts, source quality, human verification requirements, and next manual checks.
- Preserves legacy leadership-score deprecation and does not alter final scoring.

## Phase 27 — Canonical Jane 20 Criteria Contract

- Added canonical Jane 20 criteria model and `/api/jane-criteria` support.
- Extended request-scoped qualitative evidence with optional `criterion_id`, `criterion_name`, and `submetric` metadata.
- Preserved backward compatibility for legacy qualitative evidence request flows.
