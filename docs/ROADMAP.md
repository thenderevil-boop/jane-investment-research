# Roadmap

## Current baseline

The committed baseline includes Phase 59 platform business quality card and Phase 60A coverage hardening. Phase 60B shifts the product from feature stacking to a usable daily research workflow.

## Phase 60B — Product Baseline + Hard Gates + Daily Report Entry Flow

**Fund-manager rationale:** The user should know what to review in the first five minutes.

**System rationale:** Establish hard gates so wording, provider status, and Coverage Matrix actionability do not regress.

**In scope:** `today_research_actions`, Language Policy, Product Baseline, Architecture Baseline, runtime 13F manager universe wording, and contract tests.

**Non-goals:** New providers, scoring rewrite, editable settings UI, or more decorative cards.

**Acceptance:** Daily Report shows concrete actions; language tests pass; baseline docs exist; 13F wording treats starter managers as runtime universe examples, not permanent rules.

## Phase 61 — Daily Research Workflow Status MVP

**Fund-manager rationale:** Daily Report should summarize what to do next across macro context, source quality, watchlist names, and evidence gaps.

**System rationale:** `research_workflow_summary` should be part of Daily Report, not another isolated `analyze-stock` card.

**In scope:** Consume existing scores/evidence to produce workflow statuses: `researchable`, `watchlist`, `insufficient_data`, `deprioritize_for_now`. Add dominant reason and next action.

**Non-goals:** Changing score weights or producing directive recommendations.

**Acceptance:** Workflow status changes when source quality, Coverage Matrix gaps, or watchlist evidence changes.

## Phase 62 — Read-only Operations Settings / Data Source Diagnostics

Expose provider and runtime settings: SEC 13F manager universe, cache TTL, lookback quarters, SEC EDGAR user agent status, FMP/FRED/USPTO flags, and live/cache/fallback status.

## Phase 63 — Editable 13F Manager Universe

Add local settings persistence and UI editing for manager CIKs. Read order should be local settings, startup env, then bundled starter universe.

## Phase 64 — Evidence Gap Inbox / Manual Research Queue

Convert Coverage Matrix and manual evidence gaps into a prioritized inbox with required/manual/optional actions.

## Phase 65 — Candidate Comparison / Watchlist MVP

Compare candidates across quality-growth evidence, source quality, macro context, and unresolved evidence gaps.

## Deferred work

- C18 USPTO runtime activation fix unless it directly blocks Coverage Matrix actionability.
- Additional specialized providers.
- More signal breakdown cards.
- Automatic future-theme discovery.
- Ranking engine.
