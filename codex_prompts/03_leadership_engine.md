# Codex Prompt 03: Leadership Stock Engine

Read:

- `AGENTS.md`
- `docs/SCORING_RUBRIC.md`
- `docs/JANE_FRAMEWORK_MAPPING.md`

Implement the Leadership Stock Engine.

## Requirements

Create:

- `backend/app/engines/leadership_engine.py`
- `backend/app/schemas/leadership.py`
- tests for leadership scoring

Implement Jane's 20 criteria.

Each criterion must return:

- criterion_id
- criterion_name
- score: 0, 0.5, or 1
- raw_data
- derived_metrics
- benchmark
- trend
- evidence_summary
- source
- source_date
- confidence
- limitations
- missing_data

Total score:

- sum of 20 criteria
- >= 16: worth_deep_research
- 12 to 15.5: watchlist_candidate
- < 12: weak_candidate

Use mock data only.

Do not connect to live APIs.

Do not output buy/sell/hold language.
