# Product Baseline

## Purpose

Jane Investment Research is a research workflow assistant for macro / quality-growth stock evaluation. The product baseline is not a recommendation engine. Its job is to organize source quality, evidence coverage, major research gaps, and next research actions so the user can decide what to investigate next.

## Planning baseline

Current baseline includes the Phase 64A docs-aligned Phase 61-69 routeable research workflow stack:

- Phase 64 Evidence Gap Inbox / Manual Research Queue for Coverage Matrix actionability.
- Phase 65 Daily Report Command Center for first-screen routeable actions.
- Phase 66 Source Health Action Routing for provider/setup readiness actions.
- Phase 68 Research Workflow Summary v2 Alignment for Stock Research dominant blocker / reason / route vocabulary.
- Phase 69 Manual Evidence Quality Loop for linking saved evidence back to Evidence Gap Inbox and Coverage Matrix gaps.
- Phase 62 read-only Operations Diagnostics and Phase 63 editable local 13F manager-universe settings remain the provider/settings visibility baseline.

The next implementation target should improve candidate/watchlist comparison or Daily Report action usefulness only if the hard gates below remain green; avoid adding decorative cards/providers before routeable evidence workflows stay useful.

## Primary user workflow

The product entry point is the **5-minute Daily Report workflow**:

1. Read the Daily Report `command_center` headline and workflow focus.
2. Review macro context plus data-source and watchlist/source changes.
3. Complete 2-3 routeable top actions from `command_center.top_actions` / `today_research_actions`.
4. Open Operations, Stock Research, or Evidence Library only when the route hint points there.
5. Add or review manual evidence when Coverage Matrix gaps block interpretation.

## Current Analyze-Stock output layers

`POST /api/analyze-stock` remains the deep single-name surface. It includes:

- Evidence Gap Inbox / Manual Evidence Quality Loop
- final score and existing research verdict fields
- Evidence Matrix
- Jane Coverage Matrix
- data quality summary
- foreign-filer / ADR diagnostics
- theme validation context
- macro / flow signal breakdown
- company event signal breakdown
- platform business quality card
- manual evidence and stale review support

These layers should not replace the Daily Report starting workflow.

## Evidence Gap Inbox baseline

Phase 64 adds `evidence_gap_inbox` (`phase64_evidence_gap_inbox_v1`) to `POST /api/analyze-stock`. It turns Coverage Matrix/manual evidence/ADR/source readiness gaps into prioritized manual research actions with route hints and gap types such as `manual_evidence_required`, `source_setup_required`, `provider_cache_refresh_required`, and `adr_or_foreign_filer_limitation`. It is non-scoring (`affects_score=false`, `final_score_unchanged=true`) and does not trigger provider calls.

## Manual Evidence Quality Loop baseline

Phase 69 adds local quality-loop metadata to saved Manual Evidence Library items and surfaces it inside Stock Research. Saved evidence can link to `linked_gap_id`, `linked_criterion_id`, and `linked_submetrics`; analyze-stock derives `manual_evidence_resolution` for Evidence Gap Inbox items and Coverage Matrix rows. The resolution state shows whether evidence is reviewed, stale, incomplete, rejected/archived, or unresolved before the user treats a gap as handled. It is workflow metadata only (`affects_score=false`, `final_score_unchanged=true`, `not_investment_advice=true`), does not fetch URLs, does not independently verify source truth, and does not change provider behavior or final verdict semantics.

## Daily Report baseline

Daily Report now exposes `command_center` as the first screen and keeps `today_research_actions` as the underlying 2-3 item action list. Actions use existing data only and can include:

- `macro_context`
- `source_setup`
- `coverage_gap`
- `evidence_review`
- `watchlist_change`

This is a hard gate: future phases should improve the 5-minute Daily Report workflow before adding more decorative cards. Command-center route hints should point to `daily_report`, `operations`, `stock_research`, or `evidence_library` and must remain non-scoring.

## Operations Diagnostics baseline

Phase 62 adds a read-only Operations Diagnostics surface backed by `GET /api/operations/diagnostics` (`phase62_operations_diagnostics_v1`). It provides Provider Health, Coverage Readiness, 13F Runtime Universe, and secrets-policy visibility before interpreting Daily Report or Stock Research outputs. Phase 66 adds `source_health_actions` (`phase66_source_health_actions_v1`) so missing keys, SEC EDGAR setup, disabled providers, and cache/readiness issues become routeable operations tasks that can also feed Daily Command Center source alerts. It exposes `api_key_values_returned=false`, never returns API key values, and does not trigger provider calls.

Phase 63 adds editable local 13F manager-universe settings via `GET/PUT/DELETE /api/operations/settings/13f-manager-universe` (`phase63_13f_manager_universe_settings_v1`). Precedence is `local_settings` > `startup_env` > `bundled_starter_universe`. The editor changes research scope only; it does not change scoring, final verdicts, provider calls, or 13F's delayed filing limitations.

## Current data sources

The system can use a mix of live, cached live, derived, mock, fallback, and user-provided evidence. Key sources include SEC EDGAR, SEC 13F, SEC Companyfacts, FMP, yfinance, FRED-compatible macro data, USPTO PatentsView, manual evidence, and bundled fixtures.

## Runtime settings

Startup environment variables remain the operational baseline. Example:

```powershell
cd D:\jane-investment-research
$env:USE_LIVE_SEC_13F="true"
$env:SEC_13F_TARGET_MANAGERS="0001067983,0000102909,0001364742,0000093751,0001214717"
$env:SEC_13F_CACHE_TTL_DAYS="7"
$env:SEC_13F_LOOKBACK_QUARTERS="4"
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

The 13F manager list above is a starter runtime universe, not a permanent scoring rule. Users may replace it with their intended manager universe through the Phase 63 Operations Diagnostics local settings editor. Local settings override `SEC_13F_TARGET_MANAGERS`; clearing local settings falls back to startup env or bundled starter universe.

## Coverage Matrix product gate

Coverage Matrix usefulness is a product gate. If many Jane criteria remain `insufficient`, the UI must help the user choose the next evidence action instead of simply displaying gaps. The baseline action path is:

1. Identify the highest-value evidence_gap.
2. Explain whether the gap is source setup, provider limitation, or manual evidence.
3. Surface it through Daily Report `today_research_actions` or the manual evidence queue.

## Hard gates

Future development should not proceed to new cards or providers unless these hard gates remain green:

- Language Policy gate
- Daily Report 5-minute workflow gate
- Coverage Matrix actionability gate
- Provider/settings visibility gate
- 13F manager universe runtime-maintainability gate

## What the system does not do

- It does not produce directive investment recommendations.
- It does not replace human review of filings, disclosures, or thesis evidence.
- It does not automatically discover future themes with high confidence.
- It does not treat starter 13F managers as permanent mandatory targets.
- It does not infer private platform KPIs without disclosed evidence.

## Next milestone

Phase 69 has connected saved manual evidence quality state back into Evidence Gap Inbox and Coverage Matrix actionability. The next milestone should improve cross-candidate/watchlist readiness comparison or Daily Report action usefulness while preserving the same routeable, non-scoring workflow boundaries.
