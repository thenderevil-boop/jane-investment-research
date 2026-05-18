# Changelog

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
