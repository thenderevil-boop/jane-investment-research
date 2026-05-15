# Phase 28 Jane Evidence Coverage Matrix Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a canonical Jane 20 criteria coverage matrix that explains, criterion-by-criterion, which submetrics are covered, partial, or insufficient based on Phase 27a canonical criteria and Phase 27b request-scoped/manual evidence metadata.

**Architecture:** Keep the existing broad `evidence_matrix` unchanged for cross-category validation. Add a new Jane-specific coverage layer to `AnalyzeStockResponse` so each canonical criterion has deterministic coverage status, covered/missing submetrics, source quality, and manual verification guidance. The new layer is read-only/reporting-only: it must not change scoring.

**Tech Stack:** FastAPI/Pydantic backend, existing stock analysis report builder, React/Vite frontend, pytest + Vitest.

---

## Current Context

Recent completed phases:

- **Phase 27a** created `backend/app/engines/jane_criteria_canonical.py` and `GET /api/jane-criteria`.
- **Phase 27b** added Stock Research UI input for Jane 20 criteria evidence and preserved optional metadata on qualitative evidence:
  - `criterion_id`
  - `criterion_name`
  - `submetric`

Current relevant files:

- Canonical criteria: `backend/app/engines/jane_criteria_canonical.py`
- Analyze schemas: `backend/app/schemas/stock_analysis.py`
- Analyze report builder: `backend/app/reports/stock_analysis.py`
- Frontend types: `frontend/src/types.ts`
- Stock Research UI: `frontend/src/pages/StockResearch.tsx`
- Stock Research tests: `frontend/src/pages/StockResearch.test.tsx`

Important boundary:

- Phase 28 **does not** change final score, Jane company quality score, macro score, or existing broad `evidence_matrix` semantics.
- Phase 28 **does not** deepen financial proxy calculations. That remains Phase 31.
- Phase 28 **does not** migrate saved manual evidence storage schema unless optional fields are already present.

---

## Proposed API Shape

Add to `AnalyzeStockResponse`:

```python
jane_criteria_coverage: JaneCriteriaCoverageMatrix
```

Suggested schemas in `backend/app/schemas/stock_analysis.py`:

```python
class JaneCriterionCoverageItem(BaseModel):
    criterion_id: int = Field(ge=1, le=20)
    criterion_name: str
    evidence_type: Literal["financial_proxy", "qualitative", "semi_structured"]
    coverage_status: Literal["covered", "partial", "insufficient"]
    source_quality: Literal[
        "filing_backed",
        "derived_live",
        "user_provided",
        "mixed_with_fallback",
        "mock_only",
        "insufficient",
    ]
    confidence: float = Field(ge=0, le=1)
    auto_derivable_submetrics: list[str]
    requires_user_input_submetrics: list[str]
    covered_submetrics: list[str]
    missing_submetrics: list[str]
    evidence_item_count: int = 0
    accepted_evidence_item_count: int = 0
    financial_proxy_source: str | None = None
    requires_human_verification: bool = True
    summary: str
    limitations: list[str]
    next_manual_check: str | None = None

class JaneCriteriaCoverageMatrix(BaseModel):
    criteria: list[JaneCriterionCoverageItem]
    covered_count: int
    partial_count: int
    insufficient_count: int
    user_input_required_count: int
    financial_proxy_available_count: int
    source_quality_summary: str
    not_investment_advice: bool = True
```

Coverage status rule:

```text
covered      = every canonical submetric is covered
partial      = at least one canonical submetric is covered, but some are missing
insufficient = no canonical submetric is covered
```

Coverage sources:

1. **User evidence:** accepted qualitative evidence item with matching `criterion_id` and `submetric`.
2. **Fallback compatibility:** accepted qualitative evidence item without `criterion_id`, mapped by legacy `criterion` slug to canonical criterion id where safe.
3. **Financial proxy metadata:** for Phase 28, only mark `auto_derivable_submetrics` as covered when current system already emits explicit supportive Jane company quality criteria or financial statement signals that can be safely mapped. Do not invent new calculations.

Recommended conservative financial-proxy behavior:

- If no explicit safe mapping exists, financial-proxy criteria can be `partial` or `insufficient`, with `financial_proxy_source` displayed and `next_manual_check` explaining that Phase 31 will deepen proxy calculation.
- Do not mark C5/C6/C9/C10 as fully covered merely because yfinance/SEC data exists.

---

## Task 1: Backend RED tests for schema and empty coverage matrix

**Objective:** Create failing tests proving analyze responses include a 20-row Jane coverage matrix with insufficient defaults.

**Files:**

- Create: `tests/phase28_jane_evidence_coverage_matrix.py`
- Modify later: `backend/app/schemas/stock_analysis.py`
- Modify later: `backend/app/reports/stock_analysis.py`

**Test cases:**

```python
def test_jane_coverage_matrix_has_20_canonical_rows_when_no_user_evidence():
    response = build_stock_analysis_response({"ticker": "NVDA"})
    matrix = response.jane_criteria_coverage

    assert len(matrix.criteria) == 20
    assert matrix.covered_count == 0
    assert matrix.insufficient_count >= 1
    assert matrix.not_investment_advice is True
    assert {item.criterion_id for item in matrix.criteria} == set(range(1, 21))
```

```python
def test_jane_coverage_rows_include_required_fields():
    response = build_stock_analysis_response({"ticker": "NVDA"})
    item = response.jane_criteria_coverage.criteria[0]

    assert item.criterion_id == 1
    assert item.criterion_name
    assert item.coverage_status in {"covered", "partial", "insufficient"}
    assert isinstance(item.covered_submetrics, list)
    assert isinstance(item.missing_submetrics, list)
    assert item.requires_human_verification is True
```

**Run to verify RED:**

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
python -m pytest -q -p no:cacheprovider tests/phase28_jane_evidence_coverage_matrix.py
```

Expected: fail because `jane_criteria_coverage` does not exist.

---

## Task 2: Add backend Pydantic schemas

**Objective:** Add typed response contracts for the Jane coverage matrix.

**Files:**

- Modify: `backend/app/schemas/stock_analysis.py`

**Implementation steps:**

1. Add `JaneCriterionCoverageItem`.
2. Add `JaneCriteriaCoverageMatrix`.
3. Add `jane_criteria_coverage: JaneCriteriaCoverageMatrix` to `AnalyzeStockResponse`.
4. Add a safe empty/default value only where fallback response construction requires it; prefer explicit construction in the report builder.

**Verification:**

```powershell
python -m pytest -q -p no:cacheprovider tests/phase28_jane_evidence_coverage_matrix.py
```

Expected: still fail until builder exists, but import/schema errors should be gone.

---

## Task 3: Implement coverage builder helper

**Objective:** Build canonical coverage rows from current analyze response components without changing scores.

**Files:**

- Modify: `backend/app/reports/stock_analysis.py`
- Uses: `backend/app/engines/jane_criteria_canonical.py`

**Suggested helper:**

```python
def _build_jane_criteria_coverage(response: AnalyzeStockResponse) -> dict:
    ...
```

**Algorithm:**

1. Index accepted qualitative evidence by `criterion_id` and `submetric`.
2. Also create a legacy slug map from current qualitative `criterion` to canonical id, for accepted evidence missing `criterion_id`.
3. For each item in `JANE_CRITERIA`:
   - `canonical_submetrics = set(item["submetrics"])`
   - `covered_submetrics = accepted user evidence submetrics intersect canonical submetrics`
   - optionally add safe existing auto-derived submetrics only when explicit existing output supports it
   - `missing_submetrics = canonical_submetrics - covered_submetrics`
   - status = `covered` / `partial` / `insufficient`
4. `source_quality`:
   - `user_provided` if covered only by accepted manual evidence
   - `filing_backed` or `derived_live` only for explicit safe financial proxy mappings
   - `insufficient` if none
5. `requires_human_verification` is true for all user-provided or qualitative/semi-structured criteria.
6. `summary` should be deterministic and non-advisory.
7. `next_manual_check` should be present when missing user-input submetrics exist.

**Do not:**

- Treat unaccepted/rejected evidence as coverage.
- Treat legacy mock leadership score as coverage.
- Treat source availability alone as coverage.
- Change final score.

**Verification:**

```powershell
python -m pytest -q -p no:cacheprovider tests/phase28_jane_evidence_coverage_matrix.py
```

Expected: Task 1 tests pass after wiring in Task 4.

---

## Task 4: Wire coverage builder into analyze response

**Objective:** Populate `response.jane_criteria_coverage` during final response enrichment.

**Files:**

- Modify: `backend/app/reports/stock_analysis.py`

Current enrichment area is near the end of the builder, where existing code sets:

```python
response.evidence_matrix = [EvidenceMatrixItem.model_validate(item) for item in _build_evidence_matrix(response)]
response.data_quality_summary = AnalyzeStockDataQualitySummary.model_validate(_build_data_quality_summary(response))
response.next_manual_checks = [NextManualCheck.model_validate(item) for item in _build_manual_checks(response)]
```

Add nearby:

```python
response.jane_criteria_coverage = JaneCriteriaCoverageMatrix.model_validate(
    _build_jane_criteria_coverage(response)
)
```

Also update fallback/minimal response construction around the insufficient/error response path so it returns a valid empty/insufficient coverage matrix.

**Verification:**

```powershell
python -m pytest -q -p no:cacheprovider tests/phase28_jane_evidence_coverage_matrix.py
```

Expected: initial backend coverage tests pass.

---

## Task 5: Backend tests for user-provided evidence coverage

**Objective:** Prove Phase 27b evidence metadata affects coverage status.

**Files:**

- Modify: `tests/phase28_jane_evidence_coverage_matrix.py`

**Test cases:**

```python
def test_request_scoped_canonical_evidence_marks_submetric_covered():
    response = build_stock_analysis_response({
        "ticker": "NVDA",
        "qualitative_evidence": [
            {
                "criterion": "monopoly_power",
                "criterion_id": 1,
                "criterion_name": "Market Monopoly / Entry Barrier",
                "submetric": "switching_cost",
                "evidence_type": "switching_cost",
                "summary": "Customer migration requires workflow retraining and data migration.",
                "source_label": "user research note",
                "confidence": 0.6,
                "user_provided": True,
            }
        ],
    })

    row = next(item for item in response.jane_criteria_coverage.criteria if item.criterion_id == 1)
    assert row.coverage_status == "partial"
    assert "switching_cost" in row.covered_submetrics
    assert row.evidence_item_count == 1
    assert row.accepted_evidence_item_count == 1
    assert row.source_quality == "user_provided"
```

```python
def test_rejected_evidence_does_not_mark_coverage():
    response = build_stock_analysis_response({
        "ticker": "NVDA",
        "qualitative_evidence": [
            {
                "criterion": "monopoly_power",
                "criterion_id": 1,
                "criterion_name": "Market Monopoly / Entry Barrier",
                "submetric": "switching_cost",
                "evidence_type": "switching_cost",
                "summary": "",  # rejected
                "source_label": "note",
                "confidence": 0.6,
                "user_provided": True,
            }
        ],
    })

    row = next(item for item in response.jane_criteria_coverage.criteria if item.criterion_id == 1)
    assert "switching_cost" not in row.covered_submetrics
```

**Verification:**

```powershell
python -m pytest -q -p no:cacheprovider tests/phase28_jane_evidence_coverage_matrix.py
```

---

## Task 6: Add frontend types

**Objective:** Represent the new coverage matrix in TypeScript.

**Files:**

- Modify: `frontend/src/types.ts`

**Types:**

```ts
export type JaneCoverageStatus = 'covered' | 'partial' | 'insufficient';

export type JaneCriterionCoverageItem = {
  criterion_id: number;
  criterion_name: string;
  evidence_type: JaneEvidenceType;
  coverage_status: JaneCoverageStatus;
  source_quality: EvidenceMatrixItem['source_quality'] | 'user_provided';
  confidence: number;
  auto_derivable_submetrics: string[];
  requires_user_input_submetrics: string[];
  covered_submetrics: string[];
  missing_submetrics: string[];
  evidence_item_count: number;
  accepted_evidence_item_count: number;
  financial_proxy_source?: string | null;
  requires_human_verification: boolean;
  summary: string;
  limitations: string[];
  next_manual_check?: string | null;
};

export type JaneCriteriaCoverageMatrix = {
  criteria: JaneCriterionCoverageItem[];
  covered_count: number;
  partial_count: number;
  insufficient_count: number;
  user_input_required_count: number;
  financial_proxy_available_count: number;
  source_quality_summary: string;
  not_investment_advice: boolean;
};
```

Add to `StockAnalysis`:

```ts
jane_criteria_coverage: JaneCriteriaCoverageMatrix;
```

**Verification:**

```powershell
cd D:\jane-investment-research\frontend
npm run build
```

Expected: TypeScript errors until UI/tests are updated.

---

## Task 7: Frontend RED tests for coverage section

**Objective:** Add tests for rendering Jane coverage counts and row details.

**Files:**

- Modify: `frontend/src/pages/StockResearch.test.tsx`

**Test cases:**

1. Renders section title: `Jane Criteria Coverage Matrix`.
2. Shows counts: covered / partial / insufficient.
3. Shows criterion name, coverage status, covered submetrics, missing submetrics.
4. Shows `not investment advice` disclaimer.

Suggested component export:

```tsx
export function JaneCriteriaCoverageSection({ coverage }: { coverage?: JaneCriteriaCoverageMatrix }) { ... }
```

**Verification:**

```powershell
cd D:\jane-investment-research\frontend
npm test -- StockResearch.test.tsx
```

Expected: fail because the section does not exist.

---

## Task 8: Implement frontend coverage section

**Objective:** Display the Jane 20 coverage matrix in Stock Research results.

**Files:**

- Modify: `frontend/src/pages/StockResearch.tsx`
- Optional CSS: existing `frontend/src/index.css` if visual layout needs classes

**UI placement:**

Place after:

```tsx
<JaneCompanyQualitySection ... />
<QualitativeEvidenceAssessmentSection ... />
```

and before the broad cross-category:

```tsx
<EvidenceMatrixSection rows={result.evidence_matrix} />
```

**UI content:**

- Header: `Jane Criteria Coverage Matrix`
- Summary counts:
  - covered
  - partial
  - insufficient
- Per criterion row:
  - `criterion_id. criterion_name`
  - `coverage_status` badge
  - `source_quality` badge/pill
  - covered submetrics
  - missing submetrics
  - `next_manual_check` if present
  - limitations collapsed or muted text

**Do not:**

- Remove the existing broad `EvidenceMatrixSection`.
- Present coverage as buy/sell advice.

**Verification:**

```powershell
npm test -- StockResearch.test.tsx
npm run build
```

---

## Task 9: Backend integration and regression tests

**Objective:** Ensure Phase 28 does not break existing analyze contract or Phase 27 behavior.

**Files:**

- Modify: `tests/phase28_jane_evidence_coverage_matrix.py`
- Possibly update existing fixtures if strict response dicts exist.

**Tests:**

```python
def test_phase28_does_not_change_legacy_leadership_boundary():
    response = build_stock_analysis_response({"ticker": "NVDA"})
    assert response.leadership_score.deprecated is True
    assert response.leadership_score.affects_final_score is False
```

```python
def test_phase28_does_not_mutate_final_score_when_evidence_coverage_changes():
    base = build_stock_analysis_response({"ticker": "NVDA"})
    with_evidence = build_stock_analysis_response({...})
    # If current model legitimately uses qualitative evidence in company quality,
    # assert only that jane_criteria_coverage is reporting-only and does not directly
    # add a new score category. Avoid brittle exact score unless current behavior is stable.
    assert hasattr(with_evidence, "jane_criteria_coverage")
```

**Verification:**

```powershell
python -m pytest -q -p no:cacheprovider tests/phase28_jane_evidence_coverage_matrix.py tests/phase27b_evidence_input_ux.py tests/jane_criteria_canonical.py tests/leadership_engine.py
```

---

## Task 10: Full validation and commit

**Objective:** Verify full app health and commit Phase 28 only.

**Commands:**

Backend:

```powershell
cd D:\jane-investment-research
.\.venv\Scripts\Activate.ps1
python -m pytest -q -p no:cacheprovider
```

Frontend:

```powershell
cd D:\jane-investment-research\frontend
npm test
npm run build
```

Expected:

- Backend full suite passes.
- Frontend test suite passes.
- Frontend production build passes.

Commit:

```powershell
cd D:\jane-investment-research
git add backend/app/schemas/stock_analysis.py backend/app/reports/stock_analysis.py frontend/src/types.ts frontend/src/pages/StockResearch.tsx frontend/src/pages/StockResearch.test.tsx tests/phase28_jane_evidence_coverage_matrix.py
git commit -m "feat: add Jane criteria coverage matrix"
```

Do not push unless explicitly requested.

---

## Acceptance Criteria

Phase 28 is complete when:

- Analyze response includes `jane_criteria_coverage`.
- Coverage has exactly 20 canonical rows.
- Each row includes covered/missing submetrics.
- Accepted Phase 27b evidence with `criterion_id/submetric` marks that submetric covered.
- Rejected evidence does not count as coverage.
- Financial proxy criteria remain conservative and do not claim full coverage without explicit existing support.
- Legacy leadership remains deprecated/mock-only/not scoring.
- Existing broad `evidence_matrix` remains present and unchanged in purpose.
- Frontend displays the Jane coverage matrix separately from the broad evidence matrix.
- Backend tests, frontend tests, and frontend build pass.

---

## Risks / Tradeoffs

1. **Overclaiming financial proxy coverage**
   - Mitigation: conservative mapping only; Phase 31 handles deeper calculations.

2. **Duplicate matrix confusion**
   - Mitigation: name the new section `Jane Criteria Coverage Matrix`; keep existing `Evidence Matrix` as cross-category source quality.

3. **Legacy evidence without criterion_id**
   - Mitigation: support safe fallback mapping by legacy criterion slug, but prefer Phase 27b metadata.

4. **Coverage interpreted as recommendation**
   - Mitigation: include `not_investment_advice` and UI disclaimer.

5. **Large response payload**
   - Mitigation: rows contain summaries and submetric lists only; no raw evidence bodies beyond existing qualitative assessment.

---

## Recommended Execution Scope

Execute **Phase 28 only** in one local commit:

```text
Phase 28 — Jane Evidence Coverage Matrix
```

Do not include:

- Phase 29 Validation OS Report
- Phase 31 financial proxy deepening
- Phase 32 macro playbook explanation
- Phase 33 export report upgrade
