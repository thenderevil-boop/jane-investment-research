# Codex Prompt 05: Macro Regime and Future Industry Engines

Read:

- `AGENTS.md`
- `docs/MACRO_REGIME_SPEC.md`
- `docs/FUTURE_INDUSTRY_SPEC.md`

Implement:

1. Macro Regime Engine
2. Crisis Engine
3. Future Industry Radar

Use mock data only.

## Macro Regime Engine

Must classify:

- normal
- fear_crisis
- inflation_pressure
- recession_warning
- recession_confirmed
- recovery
- overheated
- insufficient_data

Inputs should be mock versions of:

- VIX
- S&P 500 / Nasdaq
- DXY
- gold
- oil
- 10Y / 2Y yields
- CPI
- PPI
- unemployment
- ISM
- consumer confidence
- geopolitical news count

## Future Industry Radar

Return at least these themes:

- AI energy infrastructure
- quantum computing
- aerospace / defense technology
- humanoid robotics
- stablecoin / payment rails
- data center cooling
- space economy
- water resources
- food resources
- synthetic biology
- longevity science

Every theme must include:

- score
- label
- trend
- candidate_companies
- raw_data
- derived_metrics
- benchmark
- source
- source_date
- confidence
- limitations
- missing_data

Add unit tests.
