# Roadmap

## Current baseline after Phase 68

The committed Phase 63 baseline added Phase 61 research workflow summary, Phase 62 read-only Operations Diagnostics, and Phase 63 editable 13F manager-universe local settings. Phase 64 added analyze-stock `evidence_gap_inbox` (`phase64_evidence_gap_inbox_v1`) so Coverage Matrix gaps become routeable manual research actions. Phase 65 added Daily Report `command_center` (`phase65_daily_command_center_v1`) so the first screen combines macro/source/watchlist/evidence attention with route hints. Phase 66 added Operations Diagnostics `source_health_actions` (`phase66_source_health_actions_v1`) and routes high-attention source-health items into the Daily Command Center. Phase 68 upgrades analyze-stock `research_workflow_summary` to `phase68_research_workflow_summary_v2` so Stock Research exposes dominant blocker/reason/route metadata aligned with Evidence Gap Inbox and source-health routing.

The product direction is intentionally **workflow-first**:

1. Daily Report is the 5-minute starting surface.
2. Stock Research is the deep single-name validation surface.
3. Operations Diagnostics explains provider/settings readiness before interpreting research output.
4. Coverage Matrix gaps should become concrete research actions instead of passive insufficient rows.

Do not resume feature stacking with more cards, mock-heavy engines, automatic theme discovery, or ranking until the workflow hard gates below remain green.

## Hard gates that must stay green

- **Language Policy gate:** no directive investment wording or trading-timing language.
- **Daily Report workflow gate:** the first surface must show macro/source/watchlist changes and 2-3 concrete next actions.
- **Coverage Matrix actionability gate:** important gaps must route to source setup, provider limitation, cache refresh, ADR limitation, or manual evidence actions.
- **Provider/settings visibility gate:** provider readiness, key-present booleans, cache TTLs, and runtime settings must be visible without exposing secrets.
- **13F manager universe maintainability gate:** `local_settings` > `startup_env` > `bundled_starter_universe`; editing this scope must not change scoring, final verdicts, provider keys, or 13F delay caveats.

## Phase 64A — Roadmap / Baseline Sync

**Fund-manager rationale:** Everyone using the repo should see the same current product state before implementing the next workflow phase.

**System rationale:** The roadmap had fallen behind the committed Phase 61-63 baseline, which increases the risk of Codex/Hermes implementing outdated priorities.

**In scope:** Update roadmap, product baseline, architecture baseline, README, changelog, and docs contract tests so the current baseline points to Phase 63 and the next implementation target is Phase 64 Evidence Gap Inbox.

**Non-goals:** Backend logic, frontend UI, schema changes, scoring changes, provider changes, editable settings changes, or full verification.

**Acceptance:** Current baseline states Phase 61-63 are complete; deferred work remains explicit; Phase 64+ sequencing is clear; docs contract tests pass.

## Phase 64 — Evidence Gap Inbox / Manual Research Queue

**Fund-manager rationale:** The user should know which evidence gap blocks the next research decision and how to resolve it.

**System rationale:** Coverage Matrix rows currently expose coverage state, but they need to become prioritized, routeable research actions.

**In scope:** Add a non-scoring `evidence_gap_inbox` to deep single-name analysis that maps Coverage Matrix rows, manual evidence state, ADR diagnostics, Form 4 fallback, and SEC 13F cache/setup readiness into prioritized actions.

**Initial gap types:**

- `manual_evidence_required`
- `source_setup_required`
- `provider_cache_refresh_required`
- `provider_limitation`
- `adr_or_foreign_filer_limitation`
- `optional_context`

**Non-goals:** Score changes, ranking, trade-direction guidance, automatic theme discovery, new providers, or live provider refresh.

**Acceptance:** Top evidence gaps include priority, criterion, gap type, recommended action, source route, whether the gap blocks workflow status, `affects_score=false`, `final_score_unchanged=true`, and `not_investment_advice=true`.

**Status:** Implemented for analyze-stock and Analyst Brief. Next step is Phase 65: route top actions into Daily Report Command Center behavior.

## Phase 65 — Daily Report Command Center Refinement

**Fund-manager rationale:** The first five minutes should answer what changed and what to do next.

**System rationale:** Daily Report already has macro/watchlist deltas and `today_research_actions`; it should combine them with source/gap state into a clearer command-center section.

**In scope:** Add a daily command-center summary that surfaces top actions, source-health alerts, watchlist/source changes, and route hints to Operations, Evidence Library, or Stock Research.

**Non-goals:** Ranking engine, automatic ticker discovery, new providers, or deep per-ticker recalculation from the Daily Report endpoint.

**Status:** Implemented for Daily Report as `command_center` with routeable top actions, source-health alerts, watchlist focus, and macro snapshot context. Phase 66 now turns provider/setup issues into richer source-health action routing.

## Phase 66 — Source Health Action Routing

**Fund-manager rationale:** Provider/setup problems should become actionable operations tasks rather than hidden caveats.

**System rationale:** Operations Diagnostics should feed Evidence Gap Inbox and Daily Report actions with routeable source-health items.

**In scope:** Add read-only action routes for missing SEC user agent, disabled providers, missing FMP/FRED keys, stale 13F cache, disabled USPTO, and similar readiness issues.

**Non-goals:** Secret editing, automatic provider refresh, provider-side effects, scoring changes, or credential storage.

**Acceptance:** Each route has provider id, severity, category, action, affected criteria/surfaces, and `not_investment_advice=true`.

**Status:** Implemented as Operations Diagnostics `source_health_actions` plus Daily Command Center source-alert metadata. Next planning target should align candidate/workflow readiness only after source-health routing remains consistent across Daily Report, Operations, and Stock Research.

## Phase 67 — Candidate Comparison / Watchlist MVP

**Fund-manager rationale:** The user needs to compare research readiness across candidate tickers without turning the system into a recommendation engine.

**System rationale:** Candidate comparison should summarize source quality, coverage, workflow status, top gap, and next action across candidates.

**In scope:** Compare configured or user-selected candidates by evidence completeness, source quality, workflow status, and next research action.

**Non-goals:** Directional ranking, portfolio allocation, automatic ticker discovery, or price-target generation.

**Acceptance:** Comparison output uses safe research-readiness language and makes unresolved evidence gaps more visible than raw score ordering.

## Phase 68 — Research Workflow Summary v2 Alignment

**Fund-manager rationale:** Single-name and Daily Report workflow statuses should use compatible language so the user can move between surfaces without translation.

**System rationale:** Phase 61 added analyze-stock `research_workflow_summary`; later phases should align it with Daily Report command-center actions and Evidence Gap Inbox blockers.

**In scope:** Align status vocabulary, expose dominant blocker/reason, and let evidence gaps explain why a candidate is watchlist/blocked/deprioritized.

**Non-goals:** Score changes, new verdict semantics, or directive recommendation wording.

**Acceptance:** `research_workflow_summary` returns `phase68_research_workflow_summary_v2`, dominant blocker/reason/route metadata, non-scoring flags, and Stock Research UI copy aligned with Evidence Gap Inbox / Operations / Daily Command Center routing.

**Status:** Implemented as a non-scoring v2 alignment layer derived from Evidence Gap Inbox items.

## Phase 69 — Manual Evidence Quality Loop

**Fund-manager rationale:** User-supplied evidence should clearly show whether it resolves a gap, still needs review, or is stale.

**System rationale:** Manual Evidence Library should connect to Evidence Gap Inbox and Coverage Matrix actionability.

**In scope:** Track evidence-to-gap resolution metadata, missing required fields, review state, and freshness state.

**Non-goals:** Automatically trusting user evidence as high-confidence scoring input or changing final verdicts.

## Deferred work

- Automatic Future Theme Library / theme discovery unless high-confidence external research integration exists.
- Additional specialized providers unless they directly unblock Coverage Matrix actionability or source-health routing.
- More signal breakdown cards before Daily Report and Evidence Gap Inbox are useful.
- Ranking engine, trade-direction language, portfolio allocation, or price-target workflows.
- Mock-heavy Crisis or Future Industry Radar expansion unless explicitly requested.
