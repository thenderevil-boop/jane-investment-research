# Architecture Baseline

## Backend request flow

- `backend/app/api/routes.py` exposes API endpoints.
- `backend/app/pipelines/research_pipeline.py` builds Daily Report payloads and the 5-minute `today_research_actions` starting flow.
- `backend/app/reports/stock_analysis.py` builds deep single-name `POST /api/analyze-stock` responses.

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
- `frontend/src/pages/StockResearch.tsx` is the deep single-name analysis surface.
- `frontend/src/pages/EvidenceLibrary.tsx` and `frontend/src/pages/EvidenceDashboard.tsx` support manual evidence workflow.
- `frontend/src/types.ts` mirrors backend contracts.

## Contract surfaces

- `backend/app/schemas/stock_analysis.py`
- `backend/app/schemas/daily_report.py`
- `schemas/analyze_stock.schema.json`
- `schemas/daily_report.schema.json`
- `docs/API_SPEC.md`
- `docs/DATA_SOURCES.md`
- `docs/JANE_FRAMEWORK_MAPPING.md`
- `docs/PRODUCT_BASELINE.md`
- `docs/LANGUAGE_POLICY.md`
- `docs/ROADMAP.md`

## Where future work should go

- Research workflow status belongs in Daily Report first.
- 13F manager universe visibility belongs in operations settings.
- Editable manager universe belongs in a later local settings/UI phase.
- New providers should be added only when they unblock a hard gate or a concrete research action.
