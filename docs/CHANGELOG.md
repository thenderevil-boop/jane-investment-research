# Changelog

## Phase 68 — Research Workflow Summary v2 Alignment

- Upgraded `research_workflow_summary` to `phase68_research_workflow_summary_v2` with `workflow_alignment_version="phase68_workflow_alignment_v1"`.
- Added dominant workflow blocker metadata (`dominant_blocker`, `dominant_reason`, `dominant_route`, `dominant_gap_id`, `dominant_provider`, `dominant_criterion_id`) derived from Evidence Gap Inbox items.
- Added Stock Research Analyst Brief rendering for Workflow Alignment so the first screen uses the same route vocabulary as Evidence Gap Inbox, Operations, and Daily Command Center.
- Preserved score weights, final scores, final verdicts, provider behavior, and investment-advice boundaries with non-scoring metadata.

## Phase 66 — Source Health Action Routing

- Added Operations Diagnostics `source_health_actions` (`phase66_source_health_actions_v1`) so missing keys, missing SEC EDGAR user-agent setup, disabled providers, and cache/readiness issues become routeable operations actions.
- Added provider/category/severity/affected-criteria/affected-surfaces/route metadata to Daily Report `command_center.source_health_alerts`.
- Added Operations Diagnostics UI rendering for Source Health Actions and expanded Daily Command Center source-alert metadata.
- Preserved read-only diagnostics, secret redaction, provider-call boundaries, final scores, verdicts, and investment-advice boundaries.

## Phase 65 — Daily Report Command Center Refinement

- Added Daily Report `command_center` (`phase65_daily_command_center_v1`) as the first-screen workflow summary for macro/source/watchlist/evidence attention.
- Added route hints to `today_research_actions` and command-center items so actions point to `daily_report`, `operations`, `stock_research`, or `evidence_library` without adding a new page.
- Added frontend Daily Command Center rendering above existing daily actions/deltas.
- Preserved score weights, final scores, verdicts, provider behavior, and language-policy boundaries with non-scoring metadata.

## Phase 64 — Evidence Gap Inbox / Manual Research Queue

- Added `evidence_gap_inbox` (`phase64_evidence_gap_inbox_v1`) to `POST /api/analyze-stock` as a non-scoring manual research queue.
- Converted Coverage Matrix gaps, manual-evidence needs, SEC 13F cache/setup gaps, Form 4 fallback, and ADR/foreign-filer limitations into prioritized `recommended_action` items with source routes and gap types such as `manual_evidence_required`, `source_setup_required`, `provider_cache_refresh_required`, and `adr_or_foreign_filer_limitation`.
- Added Stock Research Analyst Brief rendering for top evidence gaps, route hints, blocker flags, and non-scoring copy.
- Preserved score weights, final score, final verdicts, provider behavior, and investment-advice boundaries with `affects_score=false` and `final_score_unchanged=true`.

## Phase 64A — Roadmap / Baseline Sync

- Updated `docs/ROADMAP.md` so the current baseline reflects committed Phase 61 Research Workflow Summary, Phase 62 Operations Diagnostics, and Phase 63 Editable 13F Manager Universe work.
- Updated Product and Architecture baselines to make Phase 64 Evidence Gap Inbox / Manual Research Queue the next implementation target.
- Reaffirmed deferred work: automatic future-theme discovery, more signal cards, ranking, and mock-heavy engines stay paused unless explicitly requested.
- Documentation-only sync; no backend logic, frontend UI, schema, provider, settings, scoring, or verdict changes.

## Phase 63 — Editable 13F Manager Universe

- Added `GET/PUT/DELETE /api/operations/settings/13f-manager-universe` with contract version `phase63_13f_manager_universe_settings_v1`.
- Added local raw-store persistence for editable SEC 13F manager CIK lists with precedence `local_settings` > `startup_env` > `bundled_starter_universe`.
- Wired operations diagnostics and future 13F target-manager reads to the effective manager universe while preserving 13F delay caveats.
- Added Operations Diagnostics UI controls to save/reset the local 13F manager universe; this changes research scope only and does not change scoring, verdicts, or provider calls.

## Phase 61 Research Workflow Summary

- Added top-level `research_workflow_summary` to `POST /api/analyze-stock` as a non-scoring first-screen workflow layer.
- Derived deterministic research status, confidence, top strengths, top gaps, and next research actions from existing scores, data-quality grade, Coverage Matrix counts, score drivers, Form 4, 13F, and valuation context.
- Displayed the workflow summary at the top of the Stock Research Analyst Brief before score cards and detailed evidence sections.
- Preserved final scores, weights, engine logic, provider behavior, endpoint safety boundaries, and `not_investment_advice=true`.

## Phase 62 — Read-only Operations & Data Source Diagnostics

- Added `GET /api/operations/diagnostics` with contract version `phase62_operations_diagnostics_v1`.
- Added read-only Operations Diagnostics UI with Provider Health, Coverage Readiness, 13F Runtime Universe, and secrets-policy sections.
- Mapped C18 readiness to USPTO `patent_count` and C19 readiness to SEC 13F `institutional_support` / `fund_support` without changing scoring or verdicts.
- Exposed safe key-present booleans and `api_key_values_returned=false`; API key values are never returned.
- Kept diagnostics read-only: no provider calls are triggered and no settings are editable in this phase.

## Phase 61 — Auto Coverage Completion and Daily Efficiency

- Confirmed C19 SEC 13F candidate-specific target matches flow into Coverage Matrix `institutional_support` / `fund_support`, while fallback/no-position states do not false-cover C19.
- Confirmed C18 USPTO PatentsView patent counts flow into Coverage Matrix `patent_count` as non-scoring, manual-review proxy evidence.
- Added Overheat `derived_metrics.source_backing` to disclose live/derived versus mock/fallback configured weight without changing the overheat score.
- Added Daily Report `macro_delta` and `watchlist_delta` snapshot comparisons and surfaced them in the Daily Report UI.
- Extended `today_research_actions` to prioritize watchlist/source deltas from existing data.
- Preserved score weights, final verdicts, provider boundaries, and investment-advice safety policy.

## Phase 60B — Product Baseline & Architecture Stabilization

- Made Daily Report the product starting surface by adding `today_research_actions`, a 2-3 item existing-data workflow list for macro context, source setup, evidence review, watchlist changes, or Coverage Matrix gaps.
- Added `docs/PRODUCT_BASELINE.md`, `docs/ARCHITECTURE_BASELINE.md`, `docs/LANGUAGE_POLICY.md`, and `docs/ROADMAP.md` to define hard gates, the 5-minute Daily Report workflow, runtime-maintainable 13F manager universe policy, and phase sequencing.
- Added a language-policy test gate so forbidden/directive wording is checked centrally instead of repaired one phrase at a time.
- Reframed SEC 13F manager warnings as runtime universe health/comparability guidance; the bundled starter managers are not permanent scoring requirements.
- Preserved existing score weights, final score semantics, provider set, and investment-advice boundaries.

## Phase 60A — C3/C19/C11 Coverage Auto Evidence Hardening

- Added a non-scoring `SEC_13F_TARGET_MANAGERS` override guardrail: analyze-stock surfaces a warning in `institutional_13f.limitations` and C19 Coverage Matrix limitations when a deployment override drops default core managers such as Vanguard, BlackRock, or State Street.
- Hardened C3 short-interest auto evidence copy so yfinance `shortRatio` / `shortPercentOfFloat` appears as explicit `short_interest_proxy` coverage when present and as a readable manual gap when unavailable.
- Preserved Phase 56 C11 boundary: user theme text alone remains a validation target, while explicit user-supplied criterion/submetric evidence can partially cover C11 without changing final score, verdict, or provider behavior.

## Phase 57 — Macro / Flow Signal Breakdown MVP

- Added `macro_flow_signal_breakdown` / `phase57_macro_flow_signal_breakdown_v1` to analyze-stock responses with separate `macro_signals` and `flow_signals`, source-quality labels, limitations, manual checks, and `final_score_unchanged=true`.
- Added Stock Research UI rendering and frontend types for the breakdown, labeled as `Non-scoring explanation only`, `Final score unchanged`, and `Not investment advice`.
- Preserved final score, verdict, scoring weights, provider behavior, and investment-advice boundaries; the section is not a trading signal and does not change final score.

## Phase 56 — User-Supplied Theme Validation Boundary

- Added `theme_validation_context` to analyze-stock responses so `research_context.theme` is visible as a user-supplied validation target with `theme_discovery_enabled=false`, `system_generated_theme=false`, `ranking_or_scoring_policy="not_ranked_or_scored"`, `confidence=0`, `affects_score=false`, and `not_investment_advice=true`.
- Tightened C11 Coverage Matrix behavior: theme text alone no longer auto-covers `jane_theme_alignment`; C11 remains insufficient until explicit manual evidence supports revenue exposure, industry CAGR, policy support, or capital inflow.
- Added Stock Research UI copy for the user-supplied theme boundary and preserved final score, verdict, scoring weights, investment-advice boundaries, and provider behavior.

## Phase 55 — Coverage Matrix Auto-Evidence Expansion

- Default-enabled no-key USPTO PatentsView C18 `patent_count` coverage while preserving `USE_LIVE_USPTO_PATENTS_DATA=false` as an explicit disabled-provider state.
- Linked existing SEC 13F target-match context into C19 `institutional_support` / `fund_support` Coverage Matrix completeness as delayed, filing-backed, manual-review evidence.
- Phase 56 supersedes the prior C11 theme-text auto-coverage behavior: user-supplied themes remain validation targets only and require separate manual evidence for `jane_theme_alignment`.
- Preserved final score, verdict, scoring weights, investment-advice boundaries, and existing response schema shape.

## Phase 54 — ADR Manual Evidence Library UX and Review Queue Integration

- Added Evidence Library ADR helper fields for `adr_evidence_type`, `document_title`, `document_date`, `filing_period`, `quoted_text`, `local_market`, `local_ticker`, and `translation_note`, so saved manual filing references can be entered without pasting raw JSON.
- Saved ADR manual evidence now uses `document_date` as a `source_date` fallback for freshness and review-queue logic, matching request-scoped ADR evidence behavior.
- `GET /api/manual-evidence/dashboard` queue items now expose ADR metadata plus `adr_review_label`, `adr_review_guidance`, `affects_score=false`, and `not_investment_advice=true`; these fields are workflow guidance only and do not fetch source URLs, verify claims, or change scoring/verdict semantics.
- Missing ADR `document_date` / `source_date` continues to enter the local review queue as `source_date_missing` with metadata-completion guidance.

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

## Phase 58 — Company Event / Insider / Lock-Up Signal Breakdown MVP

- Added `company_event_signal_breakdown` (`phase58_company_event_signal_breakdown_v1`) to analyze-stock responses and frontend types.
- Added Stock Research rendering for `event_signals`, `insider_summary`, `institutional_summary`, `options_summary`, and `lockup_summary`.
- Preserved final score, verdict, confidence gates, and scoring weights; Phase 58 is not a trading signal and does not change final score.
- Kept lock-up handling as a manual review boundary: no prospectus, resale-registration, IPO calendar, or lock-up provider fetches were added.

## Phase 59 — Platform Business Quality Card MVP

- Added `platform_business_quality_card` (`phase59_platform_business_quality_card_v1`) to analyze-stock responses, frontend types, and Stock Research rendering.
- Added platform metric rows for `gmv_growth`, `take_rate`, `net_dollar_retention`, `burn_rate`, `runway`, `marketplace_liquidity`, `network_effect`, `ltv_cac`, and `contribution_margin_operating_leverage`.
- Kept GMV, take rate, NDR, marketplace liquidity, network effect, and LTV/CAC as manual/disclosed evidence unless supplied with source context; the system does not guess private platform KPIs.
- Preserved final score, verdict, confidence gates, and scoring weights; Phase 59 does not change final score.
