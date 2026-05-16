# Phase 31 Overheat Volume & Extension Context Implementation Plan

> **For Hermes:** Use test-driven-development before implementation. Keep this phase narrowly scoped to overheat scoring and the Jane social signal human-verification queue. Do not change final research verdict weighting, provider integrations, or frontend UX unless tests reveal a contract mismatch.

**Goal:** Replace the lower-validity `user_reported_social_heat_score` scoring component with a yfinance-derived `volume_and_extension_context_score`, while preserving Jane's social heat idea as a non-scoring human-verification prompt when overheat risk is elevated.

**Architecture:** `backend/app/engines/overheat_engine.py` remains the source for deterministic overheat scoring. Phase 31 must first ensure yfinance-derived market features expose `current_price`, `current_volume`, `avg_volume_52w`, and `ma_200d` from the existing price history pipeline; do not substitute 20-day average volume for the 52-week baseline. The score component will use those features in the overheat input and keep the existing 0.12 weight. Pipeline/report code will append a structured `jane_social_heat_check` verification item when `overheat_score >= 60`, without making user-reported social discussion part of scoring. Because that item is an object rather than a string, this phase is an API contract change and must synchronize backend schemas, generated JSON schemas, frontend TypeScript types, API docs, README, AGENTS.md, and changelog before completion.

**Tech Stack:** Python 3.11, Pydantic/FastAPI, pytest, repository-backed yfinance market features, Markdown docs.

---

## Current Context

Observed files and current behavior:

- `backend/app/engines/overheat_engine.py`
  - Current function: `user_social_heat_component(data)`
  - Current component name: `user_reported_social_heat_score`
  - Current weight: `0.12`
  - Current inputs: `user_reported_social_heat`, `friends_asking_about_stock`
- `backend/app/reports/stock_analysis.py`
  - Analyze-stock builds `engine_context` from fixture + `market_context` + user context.
  - It still injects `user_reported_social_heat` and `friends_asking_about_stock` into the scoring context.
  - It builds `human_verification_queue` as a list of strings today.
- `backend/app/pipelines/research_pipeline.py`
  - Daily report builds `overheat_risk = evaluate_overheat(...)` and a `human_verification_queue` list of strings.
- `tests/overheat_engine.py`
  - Existing overheat tests still reference `user_reported_social_heat` and expect old scoring behavior.
- Docs with relevant overheat language:
  - `AGENTS.md`
  - `docs/MARKET_TIMING_SPEC.md`
  - likely `docs/API_SPEC.md`, `README.md`, `docs/CHANGELOG.md` for phase-completion sync.

Important repo rule:

- User expects every completed code phase to also synchronize docs, API/schema contract files, and change notes before reporting completion.

---

## Phase 31 Scope

### In scope

1. Replace scoring component `user_reported_social_heat_score` with `volume_and_extension_context_score` in `backend/app/engines/overheat_engine.py`.
2. Keep the component weight at `0.12`.
3. Keep existing overheat label thresholds unchanged:
   - `>= 80`: `high_risk_warning`
   - `>= 60`: `overheated`
   - `>= 40`: `elevated_heat`
   - else `normal`
4. Add non-scoring Jane social heat human-verification item when `overheat_score >= 60`.
5. Add/update tests in `tests/overheat_engine.py` and, if needed, a pipeline/analyze-stock test file for the human-verification queue behavior.
6. Update docs/status/change notes:
   - `AGENTS.md`
   - `docs/MARKET_TIMING_SPEC.md`
   - `docs/API_SPEC.md` if response examples or human-verification semantics need clarification
   - `README.md`
   - `docs/CHANGELOG.md`
7. Run full backend test suite: `python -m pytest -p no:cacheprovider`.

### Non-goals

Do **not** change:

- final research verdict weighting
- macro scoring
- market timing scoring
- Jane company quality scoring
- live provider behavior
- yfinance adapter behavior unless market features are not already passed through
- frontend UX
- JSON schema unless the API response type changes
- direct investment-advice boundaries

Do **not** add:

- new endpoint
- new provider
- scraping/news/social/video/sentiment data source
- buy/sell/hold-style investment instruction language

### Compatibility requirements

- Existing overheat component count can remain 4.
- Old request fields `social_discussion_level` and `friends_asking_about_stock` may remain accepted user context, but they must not affect overheat scoring after this phase.
- Jane social signal must be represented only as human-verification guidance when `overheat_score >= 60`.
- Missing volume/MA inputs must degrade gracefully with explicit `missing_data`.

---

### Task 0 — Amend market-feature and contract prerequisites

**Objective:** Make the implementation safe before scoring changes by using real 52-week volume and 200-day MA fields, and by treating the structured queue item as an explicit API contract change.

**Files:**

- Modify: `backend/app/features/market_features.py`
- Modify: `backend/app/schemas/stock_analysis.py`
- Modify: `backend/app/schemas/daily_report.py`
- Modify if schema changes: `frontend/src/types.ts`, `schemas/analyze_stock.schema.json`, `schemas/daily_report.schema.json`

**Requirements:**

1. `market_features.py` must derive and expose these fields from yfinance price rows:
   - `current_price` (alias of latest close)
   - `current_volume` (alias of latest volume)
   - `avg_volume_52w` (average over up to the latest 252 trading days, not 20 days)
   - `ma_200d` (average of latest 200 closes)
2. Existing fields such as `latest_close`, `latest_volume`, and `average_volume_20d` remain for backward compatibility.
3. Human-verification queues must support both legacy strings and structured objects.
4. The structured Jane social heat item requires schema/type/docs sync before final completion.

---

## Implementation Tasks

### Task 1 — RED: Add/adjust overheat component tests

**Objective:** Define the new yfinance-derived component behavior before implementation.

**Files:**

- Modify: `tests/overheat_engine.py`
- Read: `backend/app/engines/overheat_engine.py`

**Step 1: Replace old social-score expectations with new component expectations**

Add or update tests so they assert:

```python
def test_volume_and_extension_context_scores_high_when_volume_and_price_are_extended() -> None:
    result = evaluate_overheat(
        {
            "index_gain_vs_prior_cycle_high": 5.0,
            "index_gain_from_recent_trough": 10.0,
            "distance_from_52w_high": -10.0,
            "media_hype_ratio": 1.0,
            "youtube_hype_ratio": 1.0,
            "current_volume": 2_500_000,
            "avg_volume_52w": 1_000_000,
            "current_price": 130.0,
            "ma_200d": 100.0,
        }
    )

    component = result.derived_metrics["components"]["volume_and_extension_context_score"]
    assert component["score"] >= 75
    assert component["derived_metrics"]["volume_ratio"] == 2.5
    assert component["derived_metrics"]["price_vs_200d_pct"] == 30.0
    assert "user_reported_social_heat_score" not in result.derived_metrics["components"]
```

Add missing-data test:

```python
def test_volume_and_extension_context_missing_volume_and_ma_fields_are_reported() -> None:
    result = evaluate_overheat(
        {
            "index_gain_vs_prior_cycle_high": 5.0,
            "index_gain_from_recent_trough": 10.0,
            "distance_from_52w_high": -10.0,
            "media_hype_ratio": 1.0,
            "youtube_hype_ratio": 1.0,
        }
    )

    component = result.derived_metrics["components"]["volume_and_extension_context_score"]
    assert component["score"] == 10
    assert component["missing_data"] == ["volume_ratio_52w", "price_vs_200d_ma"]
    assert "volume_ratio_52w" in result.missing_data
    assert "price_vs_200d_ma" in result.missing_data
```

**Step 2: Run RED**

```bash
/home/paulchang/workspace/jane-investment-research/.venv/bin/python -m pytest -q -p no:cacheprovider tests/overheat_engine.py
```

Expected before implementation:

- FAIL because `volume_and_extension_context_score` does not exist yet.

---

### Task 2 — GREEN: Implement `volume_and_extension_context_component`

**Objective:** Replace user-reported social heat scoring with yfinance-derived volume/extension context.

**Files:**

- Modify: `backend/app/engines/overheat_engine.py`
- Test: `tests/overheat_engine.py`

**Implementation details:**

1. Replace `user_social_heat_component` with a new function, likely named:

```python
def volume_and_extension_context_component(data: dict[str, Any]) -> ScoreObject:
```

2. Use these input fields from `data`:

```python
current_volume = data.get("current_volume")
avg_volume_52w = data.get("avg_volume_52w")
current_price = data.get("current_price")
ma_200d = data.get("ma_200d")
```

If the actual market context uses different names, map the closest existing yfinance market fields after inspecting `read_market_data()` output. Do not invent a provider.

3. Compute:

```python
volume_ratio = current_volume / avg_volume_52w
price_vs_200d = (current_price - ma_200d) / ma_200d * 100
```

Guard against `None`, zero, and invalid denominators:

```python
volume_ratio = None if current_volume is None or not avg_volume_52w else current_volume / avg_volume_52w
price_vs_200d = None if current_price is None or not ma_200d else (current_price - ma_200d) / ma_200d * 100
```

4. Apply exact scoring logic:

```python
if volume_ratio is not None and price_vs_200d is not None and volume_ratio >= 2.5 and price_vs_200d >= 30:
    score = 100
elif (volume_ratio is not None and volume_ratio >= 2.0) or (price_vs_200d is not None and price_vs_200d >= 25):
    score = 75
elif (volume_ratio is not None and volume_ratio >= 1.5) or (price_vs_200d is not None and price_vs_200d >= 15):
    score = 50
elif (volume_ratio is not None and volume_ratio >= 1.2) or (price_vs_200d is not None and price_vs_200d >= 8):
    score = 30
else:
    score = 10
```

5. Missing-data behavior:

```python
missing = []
if volume_ratio is None:
    missing.append("volume_ratio_52w")
if price_vs_200d is None:
    missing.append("price_vs_200d_ma")
```

6. Score object fields:

```python
return _score(
    "volume_and_extension_context_score",
    score,
    label,
    {
        "current_volume": current_volume,
        "avg_volume_52w": avg_volume_52w,
        "current_price": current_price,
        "ma_200d": ma_200d,
    },
    {
        "volume_ratio": round(volume_ratio, 4) if volume_ratio is not None else None,
        "price_vs_200d_pct": round(price_vs_200d, 2) if price_vs_200d is not None else None,
    },
    {
        "high_volume_ratio": 2.5,
        "high_price_vs_200d_pct": 30,
        "elevated_volume_ratio": 1.5,
        "elevated_price_vs_200d_pct": 15,
    },
    {"volume_extension_context": "up" if score >= 50 else "elevated" if score >= 30 else "stable"},
    missing,
)
```

7. Update `evaluate_overheat()`:

```python
components = [
    index_overextension_component(data),
    media_hype_component(data),
    youtube_hype_component(data),
    volume_and_extension_context_component(data),
]
```

8. Update weights with requested names/comments:

```python
weights = {
    "index_overextension_score": 0.38,         # price cycle heat
    "media_hype_score": 0.32,                 # mock until provider
    "youtube_hype_score": 0.18,               # mock until provider
    "volume_and_extension_context_score": 0.12,  # yfinance-derived
}
```

Note: Python dict comments will not appear in runtime output; this satisfies source-code documentation. If docs/tests expect runtime labels, use component name as above.

**Step 3: Run GREEN**

```bash
/home/paulchang/workspace/jane-investment-research/.venv/bin/python -m pytest -q -p no:cacheprovider tests/overheat_engine.py
```

Expected after implementation:

- PASS or only failures related to old tests expecting exact score `0` with missing context. Update those tests to reflect new baseline score `10 * 0.12 = 1.2` only if needed and consistent with the new spec.

---

### Task 3 — RED/GREEN: Ensure pipeline human-verification queue gets Jane social heat item

**Objective:** Preserve Jane's social heat idea as a human-verification prompt, not a scoring input.

**Files:**

- Modify tests:
  - Preferred: `tests/overheat_engine.py` only if it already has pipeline imports available, or
  - Create: `tests/phase31_overheat_social_heat_queue.py`
- Modify production:
  - `backend/app/reports/stock_analysis.py` for analyze-stock pipeline output
  - `backend/app/pipelines/research_pipeline.py` for daily research report output if daily report is part of “pipeline output”

**Human-verification item:**

Use this exact dict in API/pipeline output when the model supports dict queue items:

```python
JANE_SOCIAL_HEAT_CHECK = {
    "item": "jane_social_heat_check",
    "question": "Have non-investor friends or family recently asked you about this stock or theme unprompted?",
    "jane_reference": "Jane handbook: widespread non-investor discussion is a late-cycle overheat signal",
    "action": "If yes, treat as additional overheat evidence. Not a scoring input — human judgment required.",
    "needs_human_verification": True,
}
```

Important compatibility check:

- `AnalyzeStockResponse.human_verification_queue` currently appears typed as `list[str]` in `backend/app/schemas/stock_analysis.py`.
- `DailyResearchReport.human_verification_queue` appears typed as `list[str]` in `backend/app/schemas/daily_report.py`.
- User explicitly asked for a dict object, so this phase may require schema/type changes from `list[str]` to a union type.

Recommended minimal schema approach:

```python
HumanVerificationItem = dict[str, Any] | str
human_verification_queue: list[HumanVerificationItem]
```

If Pydantic model definitions need a named model, prefer:

```python
class HumanVerificationQueueItem(BaseModel):
    item: str
    question: str
    jane_reference: str
    action: str
    needs_human_verification: bool = True
```

Then use:

```python
human_verification_queue: list[str | HumanVerificationQueueItem]
```

Only change schema/contracts if tests require the structured dict.

**Test case:**

For analyze-stock output, add:

```python
def test_overheated_analyze_stock_adds_jane_social_heat_check_to_human_verification_queue() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200
    payload = response.json()

    if payload["overheat_risk"]["score"] < 60:
        # Use monkeypatch/fixture or targeted direct pipeline construction instead of relying on NVDA default.
        pytest.skip("fixture not overheated enough for queue check")

    queue = payload["human_verification_queue"]
    item = next(entry for entry in queue if isinstance(entry, dict) and entry.get("item") == "jane_social_heat_check")
    assert item["needs_human_verification"] is True
    assert "Not a scoring input" in item["action"]
```

Better than `skip`: use `monkeypatch` to force `evaluate_overheat` or market context into an `overheat_score >= 60` state. Keep the test deterministic.

**Production logic:**

Add a helper to avoid duplication:

```python
JANE_SOCIAL_HEAT_CHECK = {...}


def add_jane_social_heat_check(queue: list, overheat_score: float) -> None:
    if overheat_score < 60:
        return
    if any(isinstance(item, dict) and item.get("item") == "jane_social_heat_check" for item in queue):
        return
    queue.append(JANE_SOCIAL_HEAT_CHECK.copy())
```

Place helper in a small shared module if both daily report and analyze-stock need it, for example:

```text
backend/app/utils/human_verification.py
```

Then call after response/report object construction and before final return:

```python
add_jane_social_heat_check(response.human_verification_queue, overheat_risk.score)
```

and in daily pipeline:

```python
add_jane_social_heat_check(report.human_verification_queue, overheat_risk.score)
```

**Run targeted tests:**

```bash
/home/paulchang/workspace/jane-investment-research/.venv/bin/python -m pytest -q -p no:cacheprovider tests/overheat_engine.py tests/phase31_overheat_social_heat_queue.py
```

---

### Task 4 — Remove scoring dependence on user-reported social fields

**Objective:** Ensure `user_reported_social_heat` no longer affects overheat scoring.

**Files:**

- Modify: `backend/app/reports/stock_analysis.py`
- Possibly modify: `backend/app/data_sources/mock_data.py`
- Test: `tests/overheat_engine.py`

**Steps:**

1. In `backend/app/reports/stock_analysis.py`, keep request user-context fields available for non-scoring risk flags if desired, but do not pass them as a scoring component input if avoidable:

Current:

```python
engine_context = {
    **fixture,
    **market_context,
    "user_reported_social_heat": request.user_context.social_discussion_level,
    "friends_asking_about_stock": request.user_context.friends_asking_about_stock,
}
```

Preferred Phase 31:

```python
engine_context = {
    **fixture,
    **market_context,
}
```

If `risk_flags` still wants social context, keep it as a separate non-scoring response flag, but document that it is not scoring input.

2. Add a direct engine test:

```python
def test_user_reported_social_heat_no_longer_changes_overheat_score() -> None:
    base = {... same market fields ..., "user_reported_social_heat": "low", "friends_asking_about_stock": False}
    hot = {**base, "user_reported_social_heat": "high", "friends_asking_about_stock": True}

    assert evaluate_overheat(base).score == evaluate_overheat(hot).score
```

3. Run:

```bash
/home/paulchang/workspace/jane-investment-research/.venv/bin/python -m pytest -q -p no:cacheprovider tests/overheat_engine.py
```

---

### Task 5 — Documentation / contract sync

**Objective:** Keep phase-completion hygiene: docs, API contract notes, and changelog must match the behavior change.

**Files:**

- Modify: `AGENTS.md`
- Modify: `docs/MARKET_TIMING_SPEC.md`
- Modify: `README.md`
- Modify: `docs/API_SPEC.md` if `human_verification_queue` supports structured dict items
- Modify: `docs/CHANGELOG.md`
- Modify: `schemas/*.schema.json` only if response schemas changed
- Modify: `frontend/src/types.ts` only if API queue type changes to include dict items

**Required AGENTS.md note:**

Add exactly or equivalently:

```text
user_reported_social_heat is replaced by volume_and_extension_context in scoring. The Jane social signal is preserved as a human_verification_queue item when overheat_score >= 60.
```

**Required overheat weight documentation:**

Update docs/source comments to clarify:

```text
index_overextension_score:        0.38  # price cycle heat
media_hype_score:                 0.32  # mock until provider
youtube_hype_score:               0.18  # mock until provider
volume_and_extension_context:     0.12  # yfinance-derived
```

In code the actual key should likely be `volume_and_extension_context_score`; in prose it can use the requested shorthand.

**README / CHANGELOG:**

Add Phase 31 summary:

```text
Phase 31 replaces user-reported social heat as an overheat scoring input with yfinance-derived volume and 200d-extension context, while preserving Jane's social heat signal as a non-scoring human-verification prompt when overheat_score >= 60.
```

**Schema/type sync if needed:**

If `human_verification_queue` changes from `list[str]` to mixed string/object entries:

1. Update backend Pydantic schemas.
2. Update `frontend/src/types.ts` for the queue type.
3. Run:

```bash
/home/paulchang/workspace/jane-investment-research/.venv/bin/python tools/generate_schemas.py
```

4. Confirm schema diff is intentional.
5. Update `docs/API_SPEC.md` examples.

---

### Task 6 — Verification and commit

**Objective:** Prove Phase 31 only is complete and cleanly committed locally.

**Commands:**

Targeted backend:

```bash
/home/paulchang/workspace/jane-investment-research/.venv/bin/python -m pytest -q -p no:cacheprovider tests/overheat_engine.py
/home/paulchang/workspace/jane-investment-research/.venv/bin/python -m pytest -q -p no:cacheprovider tests/phase31_overheat_social_heat_queue.py
```

Full backend per user request:

```bash
/home/paulchang/workspace/jane-investment-research/.venv/bin/python -m pytest -p no:cacheprovider
```

If schema/types changed, also run frontend tests/build:

```bash
cd frontend
npm test
npm run build
```

Final checks:

```bash
git diff --check
git status --short
git diff --stat
```

Commit only Phase 31 files, excluding existing untracked `.hermes/plans/*` unless user asks to include plan files:

```bash
git add backend/app/engines/overheat_engine.py backend/app/reports/stock_analysis.py backend/app/pipelines/research_pipeline.py backend/app/utils/human_verification.py tests/overheat_engine.py tests/phase31_overheat_social_heat_queue.py AGENTS.md README.md docs/API_SPEC.md docs/MARKET_TIMING_SPEC.md docs/CHANGELOG.md schemas/analyze_stock.schema.json schemas/daily_report.schema.json frontend/src/types.ts

git commit -m "feat: replace social heat overheat scoring"
```

If some listed files are unchanged, omit them from `git add`.

---

## Acceptance Checklist

- [ ] `user_reported_social_heat_score` no longer appears as an overheat scoring component.
- [ ] `volume_and_extension_context_score` appears in overheat components.
- [ ] Weight remains `0.12`.
- [ ] Label thresholds remain unchanged.
- [ ] High `volume_ratio` + high `price_vs_200d` gives component score `>= 75`.
- [ ] Missing volume/MA data returns `missing_data` including `volume_ratio_52w` and `price_vs_200d_ma`.
- [ ] `overheat_score >= 60` adds `jane_social_heat_check` to `human_verification_queue`.
- [ ] Jane social heat item is non-scoring and says human judgment required.
- [ ] AGENTS.md contains the required replacement note.
- [ ] Overheat weight comments/docs match requested wording.
- [ ] Docs/changelog/schema/types are synchronized if contracts changed.
- [ ] `python -m pytest -p no:cacheprovider` passes.
- [ ] Local commit created; no GitHub push unless explicitly requested.
