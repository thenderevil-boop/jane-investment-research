# Architecture Baseline

## Planning baseline

Phase 69 adds the Manual Evidence Quality Loop on top of the Phase 64A-aligned Phase 61-68 routeable workflow stack. Phase 64 adds `evidence_gap_inbox` (`phase64_evidence_gap_inbox_v1`), a non-scoring Evidence Gap Inbox that converts Coverage Matrix/manual-evidence/operations-readiness state into prioritized research actions. Gap types include `manual_evidence_required`, `source_setup_required`, `provider_cache_refresh_required`, `provider_limitation`, `adr_or_foreign_filer_limitation`, and `optional_context`. Phase 68 aligns the Stock Research workflow summary with the same dominant blocker/reason/route vocabulary. Phase 69 links saved manual evidence back to those gaps through `manual_evidence_resolution` metadata.

## Backend request flow

- `backend/app/api/routes.py` exposes API endpoints.
- `backend/app/pipelines/research_pipeline.py` builds Daily Report payloads, the 5-minute `today_research_actions` starting flow, and the Phase 65 `command_center` first-screen workflow summary; Phase 66 source-health actions can feed command-center source alerts.
- `backend/app/services/operations_diagnostics_service.py` builds Phase 62 read-only provider diagnostics, Coverage Readiness, 13F manager-universe visibility, and Phase 66 routeable `source_health_actions`.
- `backend/app/reports/stock_analysis.py` builds deep single-name `POST /api/analyze-stock` responses, the Phase 64 `evidence_gap_inbox` non-scoring manual research queue, and the Phase 68 `research_workflow_summary` alignment layer derived from that queue.
- `backend/app/services/operations_settings_service.py` builds Phase 63 editable local settings for `GET/PUT/DELETE /api/operations/settings/13f-manager-universe`; local_settings override startup_env, then bundled_starter_universe, and this changes research scope only but does not change scoring.

## Scoring engines

Scoring engines live under `backend/app/engines/`. They evaluate macro regime, market timing, smart money, crisis, overheat, risk allocation, and Jane-style company-quality evidence. Phase 60B does not rewrite score weights.

## Evidence and coverage layers

Deep single-name analysis includes Evidence Matrix, Jane Coverage Matrix, data quality summary, validation OS report, theme validation context, event-signal explanations, and platform-business quality review. Coverage Matrix gaps should become research actions rather than remaining passive `insufficient` rows.

## Provider and data-source layers

Provider adapters live under `backend/app/data_sources/` and cache/raw-store logic under `backend/app/raw_store/`. Runtime settings such as `SEC_13F_TARGET_MANAGERS`, cache TTL, lookback quarters, FMP, FRED, SEC, and USPTO flags should remain visible and eventually maintainable through operations settings.

## Raw store and cache boundaries

Cache state can change independently from scoring logic. Provider status must be reported as live, cached live, derived, mock, fallback, disabled, failed, or unknown where available.

## Manual Evidence Library

Manual evidence and review queues support human-supplied source-backed thesis evidence. They should feed Coverage Matrix actionability and Daily Report next actions when evidence is stale, incomplete, or pending review.

## Frontend pages

- `frontend/src/pages/DailyReport.tsx` is the product starting surface.
- `frontend/src/pages/StockResearch.tsx` is the deep single-name analysis surface and renders the Phase 64 Evidence Gap Inbox top actions in Analyst Brief.
- `frontend/src/pages/EvidenceLibrary.tsx` and `frontend/src/pages/EvidenceDashboard.tsx` support manual evidence workflow.
- `frontend/src/pages/OperationsDiagnostics.tsx` is the operations visibility and local settings surface for Provider Health, Coverage Readiness, 13F Runtime Universe, and editable local 13F manager universe controls.
- `frontend/src/types.ts` mirrors backend contracts.

## Contract surfaces

- `backend/app/schemas/stock_analysis.py`
- `backend/app/schemas/daily_report.py`
- `backend/app/schemas/operations_diagnostics.py`
- `backend/app/schemas/operations_settings.py`
- `schemas/operations_diagnostics.schema.json`
- `schemas/operations_13f_manager_universe_settings.schema.json`
- `schemas/analyze_stock.schema.json`
- `schemas/daily_report.schema.json`
- `docs/API_SPEC.md`
- `docs/DATA_SOURCES.md`
- `docs/JANE_FRAMEWORK_MAPPING.md`
- `docs/PRODUCT_BASELINE.md`
- `docs/LANGUAGE_POLICY.md`
- `docs/ROADMAP.md`

## Where future work should go

- Research workflow status now exists in analyze-stock and should be aligned with Daily Report/Evidence Gap Inbox rather than expanded as a separate card.
- Evidence Gap Inbox now exists in analyze-stock; the next architecture target is to route its top actions into Daily Report Command Center behavior.
- 13F manager universe visibility and local editability belong in operations settings.
- New providers should be added only when they unblock a hard gate or a concrete research action.
