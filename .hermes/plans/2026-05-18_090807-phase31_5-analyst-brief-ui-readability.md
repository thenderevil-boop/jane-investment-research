# Phase 31.5 Analyst Brief & UI Readability Implementation Plan

> **For Hermes:** Use test-driven-development before implementation. This is a phase-scoped frontend readability pass; implement task-by-task and keep the boundary narrow.

**Goal:** Make the Stock Research and Daily Report first screens read like a senior analyst triage workflow instead of a dense engineering/debug report.

**Architecture:** Phase 31.5 is presentation-only. It reuses existing `AnalyzeStockResponse`, `DailyResearchReport`, `ValidationOSReport`, `ScoreObject`, and `human_verification_queue` payloads. No backend scoring, provider, schema, or API contract changes are allowed unless implementation discovers an unavoidable display bug in the already-committed contract.

**Tech Stack:** React + TypeScript frontend under `frontend/src`, Vitest component tests, existing CSS in `frontend/src/styles.css`, existing backend contract tests for regression guardrails.

---

## Phase Boundary

### In Scope

- Improve Stock Research information hierarchy.
- Add a first-screen `AnalystBriefSection` above export/debug/detail sections.
- Surface Phase 31 overheat context in user-facing language:
  - `volume_ratio`
  - `price_vs_200d_pct`
  - social heat is human verification only, not scoring.
- Make raw evidence panels less visually dominant by defaulting them behind a `<details>` wrapper.
- Reduce visible form/reference clutter by defaulting Jane criteria evidence input closed while keeping core ticker/theme/reason/run controls immediately available.
- Add Daily Report data/source coverage summary so `Fallback / Mock / Stale / Missing date` badges do not dominate the first impression.
- Update frontend tests and lightweight status docs.

### Non-Goals

- Do not change backend scoring.
- Do not change `macro_v12_5`, overheat weights, smart-money weights, Form 4, 13F, SEC Companyfacts, FRED, yfinance, parsers, or provider behavior.
- Do not add news, YouTube, sentiment, scraping, paid APIs, source URL fetching, or automatic theme discovery.
- Do not expand Candidate Workspace into a portfolio/trading/task-management system.
- Do not change API request/response contracts, Pydantic models, JSON schemas, or frontend `types.ts` unless a test exposes a current mismatch.
- Do not add investment-instruction language. Keep research-only wording.

### Compatibility Requirements

- Existing `StockResearch` rendering tests must keep passing.
- Existing `DailyReport` behavior must keep loading the same endpoint.
- Existing exported report controls remain available.
- Existing raw evidence remains accessible; it is only visually de-prioritized.
- Existing `human_verification_queue` string/object compatibility remains unchanged.
- Forbidden-language guardrails must remain green.

---

## Current UI Findings From Attached HTML Snapshots

Attachment review showed these pages:

- `Jane_Research_Assistant.html`: Stock Research main workflow, very complete but dense. It renders forms, Jane 20 input, export, validation summary, validation OS report, quality summaries, multiple evidence tables, score cards, and raw panels in one long flow.
- `Jane_Research_Assistant1.html`: Candidate Workspace is acceptable as a support workflow.
- `Jane_Research_Assistant3.html`: Evidence Library is acceptable as a support workflow.
- `Jane_Research_Assistant4.html`: Evidence Dashboard is useful but table-heavy; not Phase 31.5 priority unless time remains.
- `Jane_Research_Assistant5.html`: Daily Report has good data, but data-mode badges create noise before the user sees interpretation.

Primary product issue:

> The system has enough information, but the first screen does not yet answer: “What should a senior analyst look at first?”

---

## Target User Experience

After Phase 31.5, Stock Research first screen should answer:

1. What is the research label and validation level?
2. Is macro context supportive, neutral, or a gating concern?
3. Is overheat / chase risk elevated?
4. Is data quality good enough to trust the summary?
5. What are the top 3 strengths?
6. What are the top 3 limitations?
7. What are the top 3 manual checks?
8. What does Phase 31 volume/extension context say?

Daily Report first screen should answer:

1. What is the market regime?
2. What is the crisis level?
3. Is market timing favorable/neutral/cautious?
4. Is overheat risk elevated?
5. What is data coverage quality in one compact summary?

---

## Proposed UI Structure

### Stock Research ordering after submit

Current order starts with export, then candidate summary, then Validation OS. Change to:

1. `AnalystBriefSection` — new first-screen summary.
2. `CandidateSummarySection` — keep existing candidate summary.
3. `ValidationOSReportSection` — detailed version of the summary.
4. `ValidationReportExportSection` — move below summary so export does not lead the workflow.
5. Existing quality/evidence sections.
6. `Research Scores`.
7. `Risk Flags / Missing Data`.
8. `Raw Evidence Panels` inside `<details>` closed by default.

### Daily Report ordering

Keep current page but add compact first-screen coverage:

1. Header.
2. `DailyMarketBriefSection` or enhanced `DataQualitySummary` placement.
3. Market State score cards.
4. Market Timing score cards.
5. Detailed macro explanation / raw panels remain accessible below.

---

## Implementation Tasks

### Task 1 — RED: Add test for Stock Research Analyst Brief

**Objective:** Define the first-screen Stock Research summary behavior before implementation.

**Files:**

- Modify test: `frontend/src/pages/StockResearch.test.tsx`
- Later modify: `frontend/src/pages/StockResearch.tsx`

**Step 1: Add a failing component test**

Add a test near the existing `ValidationOSReportSection` tests:

```tsx
it('renders analyst brief with triage fields and Phase 31 overheat context', () => {
  const html = renderToStaticMarkup(
    <AnalystBriefSection
      result={{
        ticker: 'NVDA',
        final_score: 41.62,
        final_label: 'watchlist_candidate',
        confidence: 0.72,
        candidate_validation_summary: {
          label: 'watchlist_candidate',
          score: 41.62,
          summary: 'NVDA is usable for preliminary validation but still needs manual evidence checks.',
          environment_summary: 'Macro environment is neutral_to_constructive.',
          company_summary: 'Company evidence is live/cached-live.',
          smart_money_summary: 'Smart-money assessment is limited by fallback components.',
          data_quality_summary: 'Source quality grade B.',
          primary_strengths: ['Macro context is usable.', 'Company profile is live.'],
          primary_limitations: ['Manual qualitative evidence still needs source review.'],
          next_actions: ['Verify monopoly power evidence.'],
          not_investment_advice: true,
        },
        validation_os_report: {
          ticker: 'NVDA',
          research_label: 'watchlist_candidate',
          validation_level: 'usable_preliminary_validation',
          data_quality_grade: 'B',
          report_sections: [],
          executive_summary: 'Validation summary text.',
          macro_backdrop: 'Macro environment is neutral_to_constructive.',
          jane_quality_summary: 'Jane quality is preliminary.',
          jane_criteria_coverage_summary: {
            covered_count: 2,
            partial_count: 3,
            insufficient_count: 15,
            coverage_gap_count: 18,
            user_input_required_count: 18,
            financial_proxy_available_count: 6,
            source_quality_summary: 'Jane 20 coverage is preliminary.',
          },
          financial_signals_summary: 'Financial signals are adequate.',
          smart_money_summary: 'Smart money is limited.',
          top_strengths: ['Macro context is usable.'],
          top_limitations: ['Manual evidence required.'],
          top_evidence_gaps: [],
          top_manual_checks: ['Verify monopoly power evidence.'],
          source_quality_caveats: ['Some components are fallback.'],
          manual_verification_required: true,
          scoring_note: 'Non-scoring report.',
          limitations: [],
          not_investment_advice: true,
        },
        macro_regime: { score: 61.8, label: 'neutral_to_constructive', confidence: 0.95 },
        overheat_risk: {
          score: 63,
          label: 'overheated',
          confidence: 0.72,
          derived_metrics: {
            components: {
              volume_and_extension_context_score: {
                score: 75,
                label: 'overheated',
                derived_metrics: { volume_ratio: 2.5, price_vs_200d_pct: 30 },
              },
            },
          },
        },
        financial_quality: { score: 52, label: 'adequate', confidence: 0.7 },
        smart_money: { score: 48, label: 'neutral', confidence: 0.62 },
        human_verification_queue: [
          {
            item: 'jane_social_heat_check',
            question: 'Have non-investor friends or family recently asked you about this stock or theme unprompted?',
            jane_reference: 'Jane handbook social heat check.',
            action: 'If yes, treat as additional overheat evidence. Not a scoring input — human judgment required.',
            needs_human_verification: true,
          },
        ],
        not_investment_advice: true,
      } as unknown as StockAnalysis}
    />,
  );

  expect(html).toContain('Analyst Brief');
  expect(html).toContain('watchlist candidate');
  expect(html).toContain('Data quality: B');
  expect(html).toContain('Macro: neutral to constructive');
  expect(html).toContain('Overheat: overheated');
  expect(html).toContain('Volume ratio: 2.5x');
  expect(html).toContain('Price vs 200d MA: 30%');
  expect(html).toContain('Social heat: human verification only');
  expect(html).toContain('Verify monopoly power evidence.');
  expect(html).toContain('Not investment advice');
  expect(html).not.toContain('[object Object]');
});
```

If exact `StockAnalysis` mock shape becomes too verbose, create a small `Partial<StockAnalysis>` fixture and cast only at the render call. Keep the assertions behavior-focused.

**Step 2: Run RED**

```bash
cd /mnt/d/jane-investment-research/frontend
npm test -- StockResearch.test.tsx
```

Expected: FAIL because `AnalystBriefSection` does not exist/export yet.

---

### Task 2 — GREEN: Implement `AnalystBriefSection`

**Objective:** Add the compact first-screen analyst triage section without changing backend data.

**Files:**

- Modify: `frontend/src/pages/StockResearch.tsx`
- Modify: `frontend/src/styles.css`

**Step 1: Add small formatting helpers**

Near existing helper functions in `StockResearch.tsx`, add helpers similar to:

```tsx
function formatPercentValue(value: unknown): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'N/A';
  return `${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)}%`;
}

function formatRatioValue(value: unknown): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'N/A';
  return `${value.toFixed(1)}x`;
}

function listFirst(items: string[] | undefined, count = 3): string[] {
  return (items ?? []).filter(Boolean).slice(0, count);
}
```

If similar helpers already exist, reuse them rather than duplicating.

**Step 2: Extract Phase 31 overheat component safely**

Add a helper:

```tsx
function getVolumeExtensionComponent(result: StockAnalysis): ScoreLike | undefined {
  return result.overheat_risk?.derived_metrics?.components?.volume_and_extension_context_score as ScoreLike | undefined;
}
```

If TypeScript complains about the shape, use a narrow local type:

```tsx
type ComponentWithDerivedMetrics = ScoreLike & { derived_metrics?: Record<string, unknown> };
```

**Step 3: Implement the exported section**

Add:

```tsx
export function AnalystBriefSection({ result }: { result: StockAnalysis }) {
  const report = result.validation_os_report;
  const summary = result.candidate_validation_summary;
  const volumeContext = getVolumeExtensionComponent(result) as ComponentWithDerivedMetrics | undefined;
  const volumeRatio = volumeContext?.derived_metrics?.volume_ratio;
  const priceVs200d = volumeContext?.derived_metrics?.price_vs_200d_pct;
  const socialHeatCheck = result.human_verification_queue?.some((item) => (
    typeof item === 'string'
      ? item.includes('social') || item.includes('Social')
      : item.item === 'jane_social_heat_check'
  ));

  const strengths = listFirst(report?.top_strengths ?? summary?.primary_strengths, 3);
  const limitations = listFirst(report?.top_limitations ?? summary?.primary_limitations, 3);
  const manualChecks = listFirst(report?.top_manual_checks ?? summary?.next_actions, 3);

  return (
    <section className="pageSection analystBrief">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Analyst Brief</p>
          <h2>{result.ticker} research triage</h2>
          <p className="muted">First-screen summary for research prioritization. Not investment advice.</p>
        </div>
        <SignalBadge label={report?.research_label ?? summary?.label ?? result.final_label} variant="neutral" />
      </div>
      <div className="briefMetricGrid">
        <div><span>Validation</span><strong>{displayKey(report?.validation_level ?? 'preliminary')}</strong></div>
        <div><span>Data quality</span><strong>Data quality: {report?.data_quality_grade ?? result.data_quality_summary?.source_quality_grade ?? 'N/A'}</strong></div>
        <div><span>Macro</span><strong>Macro: {displayKey(result.macro_regime?.label)}</strong></div>
        <div><span>Overheat</span><strong>Overheat: {displayKey(result.overheat_risk?.label)}</strong></div>
        <div><span>Financial quality</span><strong>{displayKey(result.financial_quality?.label)}</strong></div>
        <div><span>Smart money</span><strong>{displayKey(result.smart_money?.label)}</strong></div>
      </div>
      <div className="briefOverheatContext">
        <strong>Phase 31 overheat context</strong>
        <span>Volume ratio: {formatRatioValue(volumeRatio)}</span>
        <span>Price vs 200d MA: {formatPercentValue(priceVs200d)}</span>
        <span>Social heat: {socialHeatCheck ? 'human verification only' : 'not scoring input'}</span>
      </div>
      <div className="threeColumn">
        <div><h3>Top strengths</h3><ul>{strengths.map((item) => <li key={item}>{item}</li>)}</ul></div>
        <div><h3>Top limitations</h3><ul>{limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
        <div><h3>Manual checks</h3><ul>{manualChecks.map((item) => <li key={item}>{item}</li>)}</ul></div>
      </div>
      <p className="sourceWarning">Research reference only. Not investment advice.</p>
    </section>
  );
}
```

Adjust exact field names to match `frontend/src/types.ts`. Do not add new API fields.

**Step 4: Add CSS**

In `frontend/src/styles.css`, add classes near `.summaryGrid`:

```css
.analystBrief {
  border-color: #cbd5e1;
}

.briefMetricGrid, .threeColumn {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  margin-bottom: 14px;
}

.briefMetricGrid div, .threeColumn div, .briefOverheatContext {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
}

.briefMetricGrid span, .briefOverheatContext span {
  color: #64748b;
  display: block;
  font-size: 12px;
}

.briefMetricGrid strong {
  display: block;
  margin-top: 4px;
}

.briefOverheatContext {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-bottom: 14px;
}

.briefOverheatContext strong {
  flex-basis: 100%;
}
```

**Step 5: Run GREEN**

```bash
cd /mnt/d/jane-investment-research/frontend
npm test -- StockResearch.test.tsx
```

Expected: PASS.

---

### Task 3 — RED: Test Stock Research ordering and reduced first-screen clutter

**Objective:** Ensure the main Stock Research page leads with Analyst Brief after results, not export/debug panels.

**Files:**

- Modify test: `frontend/src/pages/StockResearch.test.tsx`
- Modify: `frontend/src/pages/StockResearch.tsx`

**Step 1: Add a rendering/order test**

If there is already a full-page render test for `StockResearch`, extend it. Otherwise add a static component test around the result section helper if one exists. If full `StockResearch` requires API mocks, use the existing test mock pattern in this file.

Behavior assertions:

```tsx
expect(html.indexOf('Analyst Brief')).toBeLessThan(html.indexOf('Validation Report Export'));
expect(html.indexOf('Analyst Brief')).toBeLessThan(html.indexOf('Validation OS Report'));
expect(html).toContain('Raw Evidence Panels');
expect(html).toContain('<details');
```

The exact test may need to use `render` rather than `renderToStaticMarkup` if it exercises async analysis. Keep it as small as possible.

**Step 2: Run RED**

```bash
cd /mnt/d/jane-investment-research/frontend
npm test -- StockResearch.test.tsx
```

Expected: FAIL because the current order puts `ValidationReportExportSection` before `CandidateSummarySection` and there is no `AnalystBriefSection` in the result flow.

---

### Task 4 — GREEN: Reorder Stock Research result sections and collapse raw panels

**Objective:** Make the first result screen summary-first and raw-evidence-last/collapsible.

**Files:**

- Modify: `frontend/src/pages/StockResearch.tsx:1192-1295`

**Step 1: Insert Analyst Brief first**

Change result rendering from:

```tsx
<ValidationReportExportSection ... />
<CandidateSummarySection result={result} />
<ValidationOSReportSection report={result.validation_os_report} />
```

to:

```tsx
<AnalystBriefSection result={result} />
<CandidateSummarySection result={result} />
<ValidationOSReportSection report={result.validation_os_report} />
<ValidationReportExportSection ticker={ticker} theme={theme} userReason={userReason} qualitativeEvidenceJson={qualitativeEvidenceJson} />
```

**Step 2: Wrap raw panels in closed details**

Change:

```tsx
<section className="pageSection">
  <h2>Raw Evidence Panels</h2>
  ...raw panels...
</section>
```

to:

```tsx
<section className="pageSection">
  <details>
    <summary>Raw Evidence Panels</summary>
    <p className="muted">Detailed raw data, derived metrics, benchmarks, limitations, and missing-data diagnostics for audit/debug review.</p>
    ...raw panels...
  </details>
</section>
```

Do not remove any `RawDataPanel`.

**Step 3: Make Jane evidence input closed by default**

Change:

```tsx
<details className="qualitativeEvidenceInput" open>
```

to:

```tsx
<details className="qualitativeEvidenceInput">
```

Keep ticker/theme/reason/run controls visible.

**Step 4: Run tests**

```bash
cd /mnt/d/jane-investment-research/frontend
npm test -- StockResearch.test.tsx
```

Expected: PASS.

---

### Task 5 — RED: Add Daily Report data coverage summary test

**Objective:** Define compact data/source coverage behavior before changing the Daily Report UI.

**Files:**

- Modify or create test: `frontend/src/pages/DailyReport.test.tsx` if it exists; otherwise create it.
- Modify: `frontend/src/pages/DailyReport.tsx`

**Step 1: Check existing tests**

Run:

```bash
cd /mnt/d/jane-investment-research
search_files equivalent: inspect frontend/src/pages/*Daily*test*.tsx
```

In Hermes implementation use `search_files("*Daily*test*.tsx", target="files", path="frontend/src/pages")`.

**Step 2: Add a component test for a helper section**

Prefer exporting a pure section rather than mocking the whole endpoint:

```tsx
it('renders daily data coverage summary compactly', () => {
  const html = renderToStaticMarkup(
    <DailyDataCoverageSummary
      report={{
        date: '2026-05-18',
        market: 'US',
        macro_regime: { source_status: { source_type: 'derived', provider: 'mixed_FRED_and_yfinance_macro', source_date: '2026-05-15', is_stale: false } },
        market_timing: { source_status: { source_type: 'fallback', provider: 'mock_fixture', is_stale: false } },
        overheat_risk: { source_status: { source_type: 'derived', provider: 'yfinance_market_features', source_date: '2026-05-15', is_stale: false } },
        crisis_risk: { source_status: { source_type: 'mock', provider: 'fixture', is_stale: false } },
        smart_money: { source_status: { source_type: 'fallback', provider: 'fixture', is_stale: true } },
        future_themes: [],
        missing_data: ['source_date'],
        limitations: ['Some components still use mock data.'],
      } as unknown as DailyReport}
    />,
  );

  expect(html).toContain('Data Coverage');
  expect(html).toContain('Live / derived');
  expect(html).toContain('Fallback');
  expect(html).toContain('Mock');
  expect(html).toContain('Stale / missing date');
  expect(html).toContain('Some components still use mock data.');
  expect(html).not.toContain('[object Object]');
});
```

**Step 3: Run RED**

```bash
cd /mnt/d/jane-investment-research/frontend
npm test -- DailyReport.test.tsx
```

Expected: FAIL because `DailyDataCoverageSummary` does not exist/export yet.

---

### Task 6 — GREEN: Implement Daily Data Coverage Summary

**Objective:** Replace first-impression badge noise with a compact analyst summary while preserving detailed source badges below.

**Files:**

- Modify: `frontend/src/pages/DailyReport.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/pages/DailyReport.test.tsx`

**Step 1: Add helper to collect source statuses**

In `DailyReport.tsx`:

```tsx
function collectSourceStatuses(report: DailyReport) {
  return [
    report.macro_regime?.source_status,
    report.market_timing?.source_status,
    report.overheat_risk?.source_status,
    report.crisis_risk?.source_status,
    (report.smart_money ?? report.smart_money_summary)?.source_status,
    ...(report.future_themes ?? []).map((theme) => theme.source_status),
  ].filter(Boolean);
}
```

**Step 2: Add exported section**

```tsx
export function DailyDataCoverageSummary({ report }: { report: DailyReport }) {
  const statuses = collectSourceStatuses(report);
  const liveOrDerived = statuses.filter((status) => ['live', 'cached_live', 'derived'].includes(status?.source_type ?? '')).length;
  const fallback = statuses.filter((status) => status?.source_type === 'fallback').length;
  const mock = statuses.filter((status) => status?.source_type === 'mock').length;
  const staleOrMissing = statuses.filter((status) => status?.is_stale || !status?.source_date).length;
  const topLimitations = collectLimitations(report).slice(0, 2);

  return (
    <section className="pageSection dataCoverageBrief">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Data Coverage</p>
          <h2>Source health summary</h2>
          <p className="muted">Compact source-quality view before detailed evidence panels.</p>
        </div>
      </div>
      <div className="briefMetricGrid">
        <div><span>Live / derived</span><strong>{liveOrDerived}</strong></div>
        <div><span>Fallback</span><strong>{fallback}</strong></div>
        <div><span>Mock</span><strong>{mock}</strong></div>
        <div><span>Stale / missing date</span><strong>{staleOrMissing}</strong></div>
      </div>
      {topLimitations.length > 0 && <ul className="noteList">{topLimitations.map((item) => <li key={item}>{item}</li>)}</ul>}
    </section>
  );
}
```

Use exact `DataSourceStatus` field names from `frontend/src/types.ts`. If the field is `stale` instead of `is_stale`, adapt to existing type.

**Step 3: Render it near the top**

In `DailyReport` after header and before or after `DataQualitySummary`:

```tsx
<DailyDataCoverageSummary report={report} />
<DataQualitySummary summary={report.data_quality} latestSourceDate={latestSourceDate(report)} />
```

If this duplicates too much with `DataQualitySummary`, keep both for Phase 31.5; a later refactor can merge them.

**Step 4: Run tests**

```bash
cd /mnt/d/jane-investment-research/frontend
npm test -- DailyReport.test.tsx
```

Expected: PASS.

---

### Task 7 — RED/GREEN: Add visual regression guardrails through markup tests

**Objective:** Prevent accidental reversion to dense/debug-first ordering.

**Files:**

- Modify: `frontend/src/pages/StockResearch.test.tsx`
- Modify: `frontend/src/pages/DailyReport.test.tsx`

**Step 1: Add assertions**

Add assertions to existing tests:

```tsx
expect(html).not.toContain('Social heat score');
expect(html).toContain('Social heat: human verification only');
expect(html.indexOf('Analyst Brief')).toBeLessThan(html.indexOf('Raw Evidence Panels'));
```

For Daily Report:

```tsx
expect(html.indexOf('Data Coverage')).toBeLessThan(html.indexOf('Macro Score Explanation'));
```

**Step 2: Run focused frontend tests**

```bash
cd /mnt/d/jane-investment-research/frontend
npm test -- StockResearch.test.tsx DailyReport.test.tsx
```

Expected: PASS.

---

### Task 8 — Documentation / Status Sync

**Objective:** Document that Phase 31.5 is a UI readability phase with no backend scoring or contract changes.

**Files:**

- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/CHANGELOG.md`
- Optional if needed: `docs/API_SPEC.md` only if implementation touches UI interpretation wording that should be visible to API consumers. Prefer not to modify API spec because Phase 31.5 should not alter contracts.

**Step 1: README**

Add after Phase 31 paragraph:

```markdown
Phase 31.5 adds a frontend analyst-readability pass. Stock Research now starts with an Analyst Brief that summarizes research label, validation level, data quality, macro context, overheat context, top strengths, top limitations, and manual checks before detailed evidence/debug panels. Daily Report adds a compact Data Coverage summary. This phase does not change scoring, providers, backend contracts, JSON schemas, or investment-advice boundaries.
```

**Step 2: AGENTS.md**

Update current implementation sentence to mention Phase 31.5, and add a note under validation quality / Phase 31 notes:

```markdown
- Phase 31.5 is frontend readability only: Analyst Brief and compact data coverage summaries may reorganize existing fields but must not change scoring, source quality, or endpoint contracts.
```

**Step 3: CHANGELOG**

Add top entry:

```markdown
## Phase 31.5 — Analyst Brief UI Readability

- Added Stock Research Analyst Brief as the first result section using existing analyze-stock fields.
- Surfaced Phase 31 volume/extension overheat context and social-heat human-verification wording in the UI.
- Moved export below the first-screen triage summary and collapsed raw evidence panels by default.
- Added Daily Report Data Coverage summary to reduce first-screen source-mode noise.
- No backend scoring, provider, schema, or API contract changes.
```

**Step 4: Run docs-related contract guard**

Even though contracts should not change, run:

```bash
cd /mnt/d/jane-investment-research
/home/paulchang/workspace/jane-investment-research/.venv/bin/python -m pytest -q -p no:cacheprovider tests/phase30_contract_docs_sync.py
```

Expected: PASS.

---

### Task 9 — Final Verification

**Objective:** Prove Phase 31.5 is safe and did not affect backend contracts/scoring.

**Commands:**

```bash
cd /mnt/d/jane-investment-research/frontend
npm test
npm run build
```

Expected:

- All frontend tests pass.
- TypeScript build succeeds.

Then run backend smoke/contract tests:

```bash
cd /mnt/d/jane-investment-research
/home/paulchang/workspace/jane-investment-research/.venv/bin/python -m pytest -q -p no:cacheprovider tests/phase30_contract_docs_sync.py tests/phase31_overheat_social_heat_queue.py tests/overheat_engine.py
```

Expected: PASS.

For final completion, run full backend suite unless time is explicitly constrained:

```bash
cd /mnt/d/jane-investment-research
/home/paulchang/workspace/jane-investment-research/.venv/bin/python -m pytest -q -p no:cacheprovider
```

Expected: PASS.

Inspect diff:

```bash
git diff --stat
git status --short
```

Expected changed files should be limited to frontend UI/tests and docs:

```text
frontend/src/pages/StockResearch.tsx
frontend/src/pages/StockResearch.test.tsx
frontend/src/pages/DailyReport.tsx
frontend/src/pages/DailyReport.test.tsx   # if created
frontend/src/styles.css
README.md
AGENTS.md
docs/CHANGELOG.md
.hermes/plans/2026-05-18_090807-phase31_5-analyst-brief-ui-readability.md
```

No backend engine/schema/API files should be modified.

---

## Suggested Commit

Only after implementation and verification, commit locally:

```bash
git add frontend/src/pages/StockResearch.tsx frontend/src/pages/StockResearch.test.tsx frontend/src/pages/DailyReport.tsx frontend/src/pages/DailyReport.test.tsx frontend/src/styles.css README.md AGENTS.md docs/CHANGELOG.md .hermes/plans/2026-05-18_090807-phase31_5-analyst-brief-ui-readability.md
git commit -m "feat: add phase31.5 analyst brief ui"
```

Do not push unless explicitly requested.

---

## Acceptance Criteria

Phase 31.5 is complete when:

- Stock Research result view starts with `Analyst Brief` before export, validation details, raw evidence, and large tables.
- Analyst Brief shows research label, validation level, data quality, macro label, overheat label, financial quality, smart-money label, top strengths, top limitations, and manual checks.
- Analyst Brief surfaces Phase 31 overheat context:
  - `Volume ratio: Nx`
  - `Price vs 200d MA: N%`
  - `Social heat: human verification only` or equivalent.
- Jane 20 evidence input is no longer open by default.
- Raw Evidence Panels are accessible but collapsed by default.
- Daily Report includes a compact data coverage summary before deep macro/source details.
- No forbidden direct investment-instruction language is introduced.
- No backend scoring/provider/schema/API contract changes are made.
- `npm test` passes.
- `npm run build` passes.
- `tests/phase30_contract_docs_sync.py`, `tests/phase31_overheat_social_heat_queue.py`, and `tests/overheat_engine.py` pass.
- Full backend suite passes before final completion unless the user explicitly authorizes a narrower verification run.

---

## Implementation Notes / Pitfalls

- Keep labels research-oriented. Use `research triage`, `manual checks`, `validation`, `overheat context`; avoid trading instruction words from AGENTS.md forbidden list.
- Do not display structured human-verification objects directly; always format `item.question` or a clear summary string.
- Avoid `[object Object]` by testing object queue entries and score component derived metrics.
- Do not hide data quality warnings; only summarize them before detailed panels.
- Do not remove raw evidence panels; contract/debug/audit needs remain important.
- If TypeScript types make the derived component extraction awkward, add a narrow local display type rather than changing global API types.
- If `DailyReport.test.tsx` does not exist, create it with pure exported component tests rather than endpoint mocks.
