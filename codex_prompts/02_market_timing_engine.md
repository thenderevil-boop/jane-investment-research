# Codex Prompt 02: Market Timing and Overheat Engines

Read:

- `AGENTS.md`
- `docs/MARKET_TIMING_SPEC.md`
- `docs/SCORING_RUBRIC.md`

Implement deterministic market timing and overheat engines using mock data.

## Requirements

Create:

- `backend/app/engines/market_timing_engine.py`
- `backend/app/engines/overheat_engine.py`
- tests for both engines

Market timing components:

1. Fed consecutive rate cuts
2. S&P 500 / Nasdaq drawdown >= 20% and stabilization
3. CNN Fear & Greed below 20
4. VIX confirmation
5. company cash >= 10% of market cap
6. 3-year double-digit revenue growth
7. founder CEO + insider buying

Overheat components:

1. index overextension
2. Fear & Greed greed level
3. media hype
4. YouTube hype
5. user-reported social heat

Each component must return:

- score
- label if applicable
- raw_data
- derived_metrics
- benchmark
- trend
- source
- source_date
- confidence
- limitations
- missing_data

Do not output buy, sell, hold, liquidate, or exit instructions.

Add tests for:

- extreme fear environment
- neutral environment
- overheated environment
- missing Fear & Greed data
- founder CEO with insider buying
