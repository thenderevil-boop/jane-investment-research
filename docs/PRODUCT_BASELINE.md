# Product Baseline

## Purpose

Jane Investment Research is a research workflow assistant for macro / quality-growth stock evaluation. The product baseline is not a recommendation engine. Its job is to organize source quality, evidence coverage, major research gaps, and next research actions so the user can decide what to investigate next.

## Planning baseline

Phase 64A synchronizes roadmap/baseline docs after the committed Phase 61-63 work. Current baseline now includes:

- Phase 61 Research Workflow Summary for `POST /api/analyze-stock`.
- Phase 62 read-only Operations Diagnostics.
- Phase 63 editable local 13F manager-universe settings.

The next implementation target is Phase 64 Evidence Gap Inbox / Manual Research Queue. Later phases should refine Daily Report Command Center behavior, source-health action routing, candidate comparison, and workflow-status alignment before adding new cards/providers.

## Primary user workflow

The product entry point is the **5-minute Daily Report workflow**:

1. Read macro context.
2. Review data-source and watchlist/source changes.
3. Complete 2-3 `today_research_actions`.
4. Open Stock Research only for tickers that need deep single-name work.
5. Add or review manual evidence when Coverage Matrix gaps block interpretation.

## Current Analyze-Stock output layers

`POST /api/analyze-stock` remains the deep single-name surface. It includes:

- `evidence_gap_inbox`
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

## Daily Report baseline

Daily Report now exposes `today_research_actions` as the product starting point. Actions use existing data only and can include:

- `macro_context`
- `source_setup`
- `coverage_gap`
- `evidence_review`
- `watchlist_change`

This is a hard gate: future phases should improve the 5-minute Daily Report workflow before adding more decorative cards.

## Operations Diagnostics baseline

Phase 62 adds a read-only Operations Diagnostics surface backed by `GET /api/operations/diagnostics` (`phase62_operations_diagnostics_v1`). It provides Provider Health, Coverage Readiness, 13F Runtime Universe, and secrets-policy visibility before interpreting Daily Report or Stock Research outputs. It exposes `api_key_values_returned=false`, never returns API key values, and does not trigger provider calls.

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

Phase 64 has added the Evidence Gap Inbox / Manual Research Queue to analyze-stock. The next milestone should connect its top routeable actions into Daily Report Command Center behavior without duplicating scoring or adding new providers.
