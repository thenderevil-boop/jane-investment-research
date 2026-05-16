# Changelog

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
