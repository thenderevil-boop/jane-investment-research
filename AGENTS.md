# AGENTS.md

## Project

Build a US-market-only daily investment research automation system based on Jane's investing framework extracted from the uploaded Markdown source files.

This project must not use the old `龍頭股智能篩選服務規格書.docx` as the source of truth.

## Product Positioning

This is an investment research assistance system, not an investment advisory, trading, or portfolio execution system.

The system helps the user answer:

1. What is the current market regime?
2. Is the market closer to fear, recovery, normal, or overheat?
3. Which user-provided US-listed companies deserve deeper research under Jane's framework?
4. Are externally discovered themes and ticker ideas supported by structured evidence?
5. Are smart money, insiders, or sentiment signals changing?
6. Which items require human verification because data is incomplete or uncertain?

## Analyze-Stock First Architecture

Phase 13 makes `POST /api/analyze-stock` the primary product workflow.

The user discovers themes and candidate tickers externally. The system validates user-provided US tickers using structured evidence, macro context, Jane company quality, financial statement signals, legacy leadership reference evidence, SEC Form 4, SEC 13F, risk flags, source quality, and Jane methodology reference conditions.

Daily reports remain available as background context, source-health visibility, cache warmup, and environment snapshots. Daily reports must stay snapshot-first and must not become the main user workflow.

Future Industry Radar is optional/future/reference only. Do not rebuild automatic theme discovery as a core requirement, and do not let Future Industry Radar block ticker validation.

## Product Boundary

This system is a ticker validation system for user-provided US-listed stock ideas, not a general-purpose research note system.

- The primary workflow is `POST /api/analyze-stock`.
- The primary frontend workflow is the Stock Research UI for validating a user-supplied ticker.
- Candidate Workspace is limited to local ticker validation workflow metadata for externally discovered ideas.
- Candidate review notes are append-only audit notes only and never affect scoring.
- Candidate status is workflow state only, never investment advice, and never a scoring input.
- Manual Evidence Library records are local, user-provided evidence inventory, review-readiness metadata, and bounded research-note workflow metadata; they are not independently verified research conclusions.
- Evidence Library and Evidence Dashboard exist only to support validation evidence quality.
- The system must not become a full research notebook, task manager, portfolio tracker, trading journal, or execution workflow.
- Future work should prioritize analyze-stock validation quality, data quality, evidence quality, and export/backup, not workspace expansion.
- Do not add news, YouTube, sentiment, scraping, source URL fetching, paid qualitative providers, or automatic theme/ticker discovery as part of Candidate Workspace or manual evidence flows.

## Hard Safety Rules

The system must not output direct investment instructions.

Form 4, 13F, options, insider activity, and institutional activity are research evidence only. Do not convert transaction evidence into buy/sell/hold/liquidate/enter/exit/must invest instructions. Form 4 code `P` may be labeled accumulation evidence. Form 4 code `S` may be labeled disposition evidence. Do not describe `P` or `S` as a user trading instruction.

Forbidden language:

- buy
- sell
- hold
- liquidate
- exit all
- sell half
- must invest
- guaranteed return
- target price as instruction

Allowed labels:

- worth_deep_research
- watchlist_candidate
- weak_candidate
- favorable_research_environment
- watch_for_confirmation
- neutral
- insufficient_data_or_unfavorable
- normal
- elevated_heat
- overheated
- high_risk_warning
- positive_signal
- weak_positive_signal
- negative_signal
- needs_human_verification

Every output must include:

- `not_investment_advice: true`
- raw data
- data source
- source date
- derived metrics
- benchmark
- trend
- confidence
- limitations
- missing data

## Market Scope

MVP supports US-listed stocks only.

Do not build Taiwan stock support.

Remove or ignore:

- MOPS
- TEJ
- Taiwan exchange data
- Taiwan insider reports
- Taiwan-specific funds or filings

## Development Environment

Target user environment:

- Windows 11
- Visual Studio Code
- Codex IDE extension
- PowerShell terminal
- Git repo workspace

MVP can run natively on Windows. Avoid Linux-only shell assumptions in app code. When writing README commands, include PowerShell examples.

## MVP Scope

Build in phases.

Current implementation has reached Phase 31.5 analyst-readability UI on top of Phase 31 overheat volume/extension context, Phase 30 analyze-stock contract/docs synchronization, Phase 29 Validation OS Report, Phase 28 Jane criteria coverage matrix, Phase 27 canonical Jane 20 criteria, and Phase 26.4 source quality and Form 4 interpretation hardening. Phase 27 standardizes the canonical Jane criteria file, request metadata, and qualitative-evidence validation contract. Phase 28 adds `jane_criteria_coverage` as a non-scoring validation workflow output that tracks coverage across the canonical Jane 20 criteria, accepted evidence items, covered and missing submetrics, human-verification needs, and next manual checks. Phase 29 adds `validation_os_report`, a non-scoring explainability/report layer that summarizes existing analyze-stock outputs, Jane criteria coverage gaps, manual checks, source-quality caveats, and research-only limitations. Phase 30 adds contract sync guardrails that compare committed analyze-stock JSON schema, API docs, status docs, changelog, frontend TypeScript types, and live payload smoke checks against the backend Pydantic contract. Phase 31 replaces `user_reported_social_heat_score` scoring with yfinance-derived `volume_and_extension_context_score`; Jane social heat is preserved as a structured `human_verification_queue` item when `overheat_score >= 60`. Phase 31.5 is frontend readability only: Stock Research may reorganize existing analyze-stock fields into an Analyst Brief and Daily Report may summarize source coverage, but it must not change scoring, source quality, provider behavior, endpoint contracts, or JSON schemas. These phases must not change macro_v12_5 scoring, SEC parsers, macro parsers, Form 4 fetch behavior, 13F parsers, Companyfacts parsers, scraping, source URL fetching, news, YouTube, sentiment, paid APIs, Candidate Workspace scope, or Future Industry Radar work.

Phase labels in historical docs may be non-contiguous. For current development, prefer these implementation references in order:

1. JSON schemas under `schemas/`
2. Backend and frontend tests
3. README current implementation status
4. AGENTS.md safety rules

### Phase 1: Mock Daily Research System

Implement:

1. FastAPI backend
2. Pydantic schemas
3. Mock data store
4. Daily research pipeline using mock data
5. `GET /api/daily-report/latest`
6. `POST /api/analyze-stock`
7. Unit tests

Do not connect to live APIs in Phase 1.

### Phase 2: Engines

Implement deterministic rule engines:

1. Macro Regime Engine
2. Market Timing Engine
3. Overheat Risk Engine
4. Future Industry Radar as optional/reference context only
5. Leadership Stock Engine
6. Smart Money Engine
7. Risk & Allocation Reference Engine

### Phase 3: UI

Implement a dashboard with expandable evidence panels.

### Phase 4: Live Data Integrations

Connect live APIs only after mock pipeline and tests are stable.

## Required Architecture

Use this structure unless there is a strong reason to change it:

```text
backend/
  app/
    main.py
    pipelines/
    data_sources/
    raw_store/
    features/
    engines/
    reports/
    api/
    schemas/
frontend/
  src/
    pages/
    components/
tests/
```

## Schema Contract Rules

Before implementing or modifying any endpoint, Codex must verify response shapes against:

- `schemas/daily_report.schema.json`
- `schemas/analyze_stock.schema.json`
- `docs/API_SPEC.md`

If Pydantic models, JSON schema files, frontend TypeScript types, and API docs disagree, update them together in the same task. Do not let backend responses, frontend assumptions, and documented contracts drift apart.

## raw_store Contract

In mock phases, `backend/app/raw_store` contains repository interfaces over JSON-like mock fixtures.

In live phases, `raw_store` becomes a SQLite-backed cache for raw source snapshots.

Engines must not call external APIs directly. Engines must read data through repository interfaces so live integrations can be audited, cached, and tested independently from deterministic rule evaluation.

## Frontend Proxy Requirement

During local development, Vite must proxy `/api` requests to:

```text
http://localhost:8000
```

Keep `frontend/vite.config.ts` aligned with this requirement.

## Required Backend Endpoints

Minimum endpoints:

- `GET /api/health`
- `GET /api/daily-report/latest`
- `GET /api/daily-report/{date}`
- `POST /api/analyze-stock`
- `GET /api/themes/latest`
- `GET /api/macro-regime/latest`
- `GET /api/raw-data/{ticker}`
- `GET /api/signals/{ticker}`

## Daily Research Pipeline

The pipeline must produce one daily report object for background context, cache warmup, source health, and environment snapshot use. It is not the primary user workflow.

Phase 24.5 documentation and hygiene notes:

- Documentation must align AGENTS.md, README, schemas, API docs, and tests with the Phase 24 implementation boundary.
- This phase is repo hygiene and contract clarification only; do not change scoring, analyze-stock behavior, SEC parsers, macro parsers, Form 4 parsers, 13F parsers, Companyfacts parsers, or live provider behavior.
- Ignore generated process files, caches, virtual environments, frontend build output, local manual evidence stores, local candidate workspace stores, and local SQLite databases.
- `backend_phase*.pid` files are local process artifacts and must not be tracked.

Phase 15.5 architecture notes:

- `backend/app/pipelines/research_pipeline.py` is the main pipeline; `mock_pipeline.py` is a compatibility shim only.
- `backend/app/raw_store/repository.py` is a facade over focused raw-store cache modules.
- Daily report candidates are config-driven; analyze-stock remains request-ticker driven.
- Batch jobs must not mutate global config for temporary state. Use a request/job context object.
- `_enrich_source_status` is legacy compatibility only. New engines must emit `source_status` directly.
- `smart_money` is canonical; `smart_money_summary` is deprecated and retained for backward compatibility.

Phase 17 SEC Companyfacts notes:

- SEC Companyfacts is the official filing-backed cross-check layer for financial statement signals.
- Yfinance remains the MVP company/fundamentals provider; SEC Companyfacts complements it and does not replace it.
- Missing SEC concepts must be reported as `missing_data` and must not be fabricated.
- SEC Companyfacts derived financial metrics must be period-aligned; invalid SEC ratios must be nulled and disclosed instead of used as supportive evidence.
- SEC/yfinance discrepancies are review signals for human verification.
- `SEC_EDGAR_USER_AGENT` is required for live SEC Companyfacts fetches and must never appear in API responses, snapshots, logs, fallback reasons, or tests.
- Qualitative Jane criteria remain insufficient unless independent qualitative evidence exists.

Phase 18 qualitative evidence notes:

- `POST /api/analyze-stock` may accept optional structured `qualitative_evidence` supplied by the user.
- User-provided qualitative evidence is labeled `user_provided`, is not independently verified, and must not be treated as live-verified proof.
- The system must not scrape websites, fetch source URLs, add news/YouTube/social/sentiment ingestion, or add paid qualitative providers for Phase 18.
- User-provided evidence can only support preliminary qualitative Jane criteria under conservative confidence caps.
- User-provided qualitative evidence is not mock evidence and not fallback evidence.
- `research_context.theme` remains context only unless structured qualitative evidence is supplied.
- `source_type="derived"` is not fallback, and `source_type="mixed"` remains invalid.

Phase 20 manual evidence review notes:

- Manual Evidence Library quality scoring measures completeness and review readiness only, not objective truth.
- Reviewed manual evidence remains user-provided and must not be treated as independently verified or live verified.
- Stale manual evidence can remain visible, but its qualitative impact is capped and it should trigger manual review checks.
- `source_url` is stored only as metadata; do not fetch, crawl, scrape, or automatically validate it.
- Archived and rejected manual evidence remains stored for audit and must not affect analyze-stock scoring.

Phase 21 comparison evidence notes:

- Manual evidence may include optional `comparison_context` for peer companies, comparison type, claimed advantage, comparison summary, source basis, period, metric metadata, and limitations.
- Comparison evidence is user-provided and must not be treated as independently verified or live verified, even when reviewed locally.
- Do not fetch `source_url`, scrape competitor websites, add news/social/video/sentiment providers, or infer monopoly/network/disruption from market cap or price performance.
- Comparison evidence can only support preliminary Jane qualitative criteria under conservative caps; stale, archived, or rejected comparison evidence must be capped or ignored according to manual evidence rules.
- `comparison_evidence_assessment` and the `comparison_evidence` evidence-matrix row must not count as mock or fallback evidence.

Phase 22 manual evidence dashboard notes:

- `GET /api/manual-evidence/dashboard` is a local-only Manual Evidence Library inventory and review workflow endpoint.
- The dashboard must not call analyze-stock per ticker, live providers, web scraping, source URL validation, news, YouTube, social, sentiment, paid APIs, or Future Industry Radar.
- Dashboard summaries are operational metadata, not investment recommendations.
- Archived and rejected evidence is excluded by default and included only when explicitly requested for audit.
- Peer company index is derived only from user-provided `comparison_context`; peer companies and claimed advantages are not externally validated.
- `review_due_count` and `review_scheduled_count` count items with any `next_review_due_at`; `review_overdue_count` counts items due at or before dashboard generation.

Phase 23 candidate workspace notes:

- Candidate Workspace is local-only user-provided workflow metadata for externally discovered US ticker ideas.
- Candidate status values are `watching`, `researching`, `reviewed`, and `archived`; status is not a recommendation and must not affect analyze-stock scoring.
- Candidate dashboard must not discover themes or tickers, call live providers, scrape, fetch `source_url`, ingest news/YouTube/social/sentiment, call paid APIs, or call analyze-stock for every candidate.
- Evidence summaries come from the local Manual Evidence Library and exclude archived or rejected evidence from active counts.
- Candidate analyze may call the existing analyze-stock pipeline for one selected candidate and cache only summary metadata; request-scoped qualitative evidence must not be automatically saved.
- Candidate workspace responses must include `not_investment_advice: true` and must not use `source_type="mixed"`.

Phase 24 candidate workspace notes:

- Candidate review notes are append-only local workflow metadata, are safety-checked, and must not affect scoring.
- Candidate analysis history stores compact metadata only and must not persist full analyze-stock reports unless separately designed and safety-reviewed.
- Candidate status transitions are workflow validation only; status remains non-recommendation metadata and must not affect analyze-stock scoring.
- Candidate filters, sorting, review queues, and evidence badges are local UX hints only.
- Candidate workspace dashboard must not call live providers, discover tickers, scrape, fetch URLs, or validate source URLs.
- Candidate Workspace must remain a ticker validation workflow surface, not a full research notebook, task manager, portfolio tracker, trading journal, or execution workflow.

Phase 25 export and backup notes:

- `POST /api/analyze-stock/export` packages the existing analyze-stock response as JSON or Markdown validation report output and must not change scoring.
- Analyze-stock export must not persist request-scoped qualitative evidence.
- Exported validation reports must preserve source quality, source status, limitations, missing data, evidence matrix, score driver breakdown, and next manual checks.
- `GET /api/local-backup/export` reads local Manual Evidence Library and Candidate Workspace stores only.
- Local backup must not call analyze-stock, live providers, web sources, source URLs, provider caches, import/restore, cloud sync, or scheduling.
- Export and backup output must redact secrets, raw provider URLs, and local paths where present.
- Export and backup features support validation review only and must not expand Candidate Workspace into a research notebook.

Phase 26 validation quality notes:

- `validation_quality_summary` is explanatory and does not alter scoring by itself.
- SEC/yfinance fundamentals explanations are provider-normalization and period-alignment aids; neither provider is treated as always correct.
- `legacy_leadership_score` is deprecated, mock-only, replaced by `jane_company_quality`, and does not affect final score.
- `macro_environment` is derived through `macro_v12_5`; excluded/non-scoring context inputs such as CNN Fear & Greed or unsupported ISM PMI do not downgrade macro source quality when active scoring inputs are live/cached/derived and non-fallback.
- Smart-money evidence may include delayed quarterly 13F, cached/fallback/mock Form 4 constraints, and mock options context; these constraints must be visible. Mock or fallback Form 4 is treated as `mixed_with_fallback` because Form 4 is live-capable evidence.
- Repeated distributed code `S` dispositions may be labeled a likely systematic pattern only as a heuristic. Do not claim a confirmed 10b5-1 plan without filing footnote review; the pattern remains cautionary and requires manual review.
- Valuation risk is research context only.
- Overheat weights are `index_overextension_score: 0.38` (price cycle heat), `media_hype_score: 0.32` (mock until provider), `youtube_hype_score: 0.18` (mock until provider), and `volume_and_extension_context_score: 0.12` (yfinance-derived).
- `user_reported_social_heat` is replaced by `volume_and_extension_context` in scoring. The Jane social signal is preserved as a `human_verification_queue` item when `overheat_score >= 60`.
- `next_manual_checks` are validation tasks, not investment instructions.

Phase 19 manual evidence library notes:

- Saved qualitative evidence is local-only, user-provided, reusable by ticker, and not independently verified.
- `POST /api/analyze-stock` automatically loads non-archived, non-rejected saved manual evidence for the requested ticker and merges it with request-scoped `qualitative_evidence`.
- Request-scoped qualitative evidence must not be silently persisted; the user must explicitly create saved evidence through the manual-evidence API.
- Saved manual evidence remains preliminary, cannot make qualitative criteria independently verified, cannot make source quality grade A by itself, and must not be counted as mock or fallback evidence.
- Archived or rejected saved evidence must not affect analyze-stock scoring, active evidence counts, accepted evidence counts, criteria support, or positive score drivers.

Phase 16 company-quality notes:

- `jane_company_quality` replaces mock leadership as the primary company-quality model.
- Jane's seven company quality principles are explicit and evidence-gated.
- User-provided `research_context.theme` is context only and must not be treated as independently verified evidence.
- Qualitative evidence is marked insufficient when not available.
- Financial statement signals derive from live/cached yfinance fundamentals in the MVP.
- SEC Companyfacts is now the Phase 17 filing-backed financial cross-check layer.
- Legacy `leadership_score` is mock-only and backward compatible; it must not act as a positive score driver.

1. macro regime
2. market timing environment
3. overheat risk
4. crisis risk
5. future industry radar
6. leadership stock candidates
7. smart money signals
8. risk and allocation reference
9. missing data
10. human verification queue

`POST /api/analyze-stock` must remain usable even if Future Industry Radar is unavailable or not refreshed.

## Testing Requirements

Before marking a task complete:

1. Run unit tests.
2. Run type checks if configured.
3. Confirm API response matches schema.
4. Confirm no output contains direct buy/sell/hold/liquidate language.
5. Confirm every score contains raw data, source, benchmark, trend, confidence, limitations, and missing data.
6. Confirm Form 4, 13F, and insider transaction outputs include `not_investment_advice` where applicable.
7. Confirm transaction and institutional outputs do not contain prohibited trading instruction language.
8. Confirm fallback mock Form 4 does not boost smart-money score.
9. Confirm macro scoring model diagnostics use `macro_v12_5`, active weights total 100, excluded indicators have weight 0, `macro_score_explanation` groups active components separately from excluded indicators, and `source_type` never uses `mixed`.
10. Confirm user-provided qualitative evidence is never treated as independently verified, live verified, mock evidence, or fallback evidence, and cannot upgrade `source_quality_grade` to A by itself.
11. Confirm archived or rejected manual evidence never affects analyze-stock scoring or active evidence counts.
12. Confirm candidate workspace status values are workflow state only, not investment recommendations, and do not affect analyze-stock scoring.
13. Confirm Evidence Dashboard endpoints do not call live providers, discover tickers, scrape, fetch or validate source URLs, ingest news/YouTube/social/sentiment, call paid APIs, or call analyze-stock per dashboard item.
14. Confirm request-scoped qualitative evidence is not silently persisted to the Manual Evidence Library or Candidate Workspace.
15. Confirm stale manual evidence remains visible where appropriate but has capped qualitative impact and triggers review checks.
16. Confirm comparison evidence remains `user_provided`, preliminary, not independently verified, not mock evidence, and not fallback evidence.
17. Confirm review notes are append-only audit metadata only and do not affect scoring.
18. Confirm evidence and workspace endpoints include `not_investment_advice: true` where applicable.
19. Confirm `source_type` never equals `mixed`.
20. Confirm analyze-stock export does not change scoring or persist request-scoped qualitative evidence.
21. Confirm local backup export reads local stores only and does not call analyze-stock or live providers.
22. Confirm validation quality explanations remain conservative and do not add recommendation language.
23. Confirm prioritized manual checks remain validation tasks and not action instructions.

## Data Freshness Contract

- Market prices: latest expected US trading day.
- FRED daily rates: `daily_rate_5_business_days`.
- FRED monthly macro: `monthly_macro_latest_observation`.
- Form 4: `form4_recent_180_days`.
- SEC 13F: `quarterly_filing_delay`. Fresh window covers the latest quarter-end filing plus 45-day SEC deadline. Cache TTL is days-based (`SEC_13F_CACHE_TTL_DAYS`). Not daily freshness.
- Options future: requires an explicit provider-specific timestamp and should not use stale mock data.
- News/sentiment future: source timestamp and deduplication are required.
- Mock data is excluded from stale-data counts but must be disclosed as mock.

## Definition of Done

A task is done only when:

1. Code runs locally.
2. Tests pass.
3. API schemas are documented.
4. Mock daily report works.
5. No prohibited investment instruction language appears in API responses.
6. All rule engines are deterministic unless explicitly marked qualitative.
