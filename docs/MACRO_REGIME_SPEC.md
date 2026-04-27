# MACRO_REGIME_SPEC.md

## Purpose

Classify the current US market macro environment using Jane's framework.

## Macro Regime Labels

```text
normal
fear_crisis
inflation_pressure
recession_warning
recession_confirmed
recovery
overheated
insufficient_data
```

## Required Inputs

Daily or latest available:

- VIX
- S&P 500 / Nasdaq trend
- DXY
- gold price
- oil price
- US 10Y yield
- US 2Y yield
- 10Y-2Y spread
- Fed policy rate
- CPI
- PPI
- unemployment rate
- ISM Manufacturing PMI
- consumer confidence
- major geopolitical news count
- CNN Fear & Greed when available

## Phase 5 Mock Engine Contract

Phase 5 uses mock data only and does not connect to live APIs.

The engine returns:

```json
{
  "name": "macro_regime_score",
  "label": "recession_warning",
  "score": 78,
  "confidence": 0.88,
  "components": [],
  "raw_data": {},
  "derived_metrics": {},
  "benchmark": {},
  "trend": {},
  "source": [],
  "source_date": "",
  "limitations": [],
  "missing_data": []
}
```

Each component includes:

- raw_data
- derived_metrics
- benchmark
- trend
- source
- source_date
- confidence
- limitations
- missing_data

## Phase 5 Deterministic Regime Rules

### fear_crisis

Conditions:

- VIX >= 30
- S&P 500 or Nasdaq drawdown <= -10%
- Fear & Greed <= 25 when available

### recession_warning

Conditions:

- 10Y minus 2Y spread < 0
- ISM Manufacturing PMI < 50 or unemployment trend is rising

### recession_confirmed

Conditions:

- unemployment trend is rising
- ISM Manufacturing PMI < 50
- S&P 500 or Nasdaq drawdown <= -20%

### inflation_pressure

Conditions:

- CPI YoY >= 4 or PPI YoY >= 4
- oil trend is rising

### recovery

Conditions:

- VIX is falling
- ISM Manufacturing PMI >= 50
- S&P 500 / Nasdaq trend is recovering from drawdown
- Fed policy trend is easing or neutral

### overheated

Conditions:

- S&P 500 or Nasdaq gain from recent trough >= 30%
- Fear & Greed >= 75 when available

### normal

Used when no strong regime condition is met.

### insufficient_data

Used when too many required indicators are missing.

## Feature Rules

### Yield Curve Inversion

```text
if 10Y-2Y spread < 0: inverted = true
```

Trend:

- days inverted
- spread steepening or flattening
- latest vs 30-day average

### Recession Warning Score

```text
recession_warning_score =
  yield_curve_score * 0.30 +
  unemployment_score * 0.25 +
  ism_score * 0.20 +
  consumer_confidence_score * 0.15 +
  equity_drawdown_score * 0.10
```

Rules:

- Yield curve inverted or recently uninverted after long inversion: elevated risk
- unemployment rising quickly: elevated risk
- ISM below 50: elevated risk
- consumer confidence dropping: elevated risk

### Inflation Pressure Score

```text
inflation_pressure_score =
  cpi_score * 0.30 +
  ppi_score * 0.20 +
  oil_score * 0.20 +
  commodity_score * 0.15 +
  fed_hawkish_score * 0.15
```

Rules:

- CPI or PPI above 4% to 5%: high inflation pressure
- oil / commodity spike: confirms pressure
- Fed hawkish language or hikes: confirms pressure

### Fear Crisis Score

```text
fear_crisis_score =
  vix_spike_score * 0.30 +
  geopolitical_news_score * 0.25 +
  dxy_spike_score * 0.15 +
  gold_treasury_strength_score * 0.15 +
  global_equity_volatility_score * 0.15
```

Rules:

- war / terror / oil-route conflict headlines increase score
- VIX spike confirms fear
- DXY, gold, treasuries strengthening confirm defensive flow

### Recovery Score

```text
recovery_score =
  vix_falling_score * 0.25 +
  index_stabilization_score * 0.25 +
  fed_easing_score * 0.20 +
  credit_spread_improvement_score * 0.15 +
  earnings_revision_score * 0.15
```

## Final Regime Selection

MVP rule:

1. Calculate all regime scores.
2. Select the highest score if confidence >= 0.6.
3. If top two scores are within 10 points, mark as mixed regime.
4. If data is missing, lower confidence and add to human verification queue.

Required output:

```json
{
  "label": "recession_warning",
  "score": 72,
  "confidence": 0.78,
  "supporting_indicators": [],
  "conflicting_indicators": [],
  "raw_data": {},
  "benchmark": {},
  "trend": {},
  "limitations": [],
  "missing_data": []
}
```
