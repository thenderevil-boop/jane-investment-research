# CRISIS_PLAYBOOK_SPEC.md

## Purpose

Classify US-market crisis pressure using mock evidence for Phase 5.

The Crisis Playbook Engine is research reference only. It does not provide portfolio execution or trading instructions.

## Crisis Levels

```text
normal
elevated
high
severe
insufficient_data
```

## Required Indicators

- VIX spike
- oil price spike
- gold price spike
- DXY spike
- Treasury yield movement
- geopolitical news count
- geopolitical news severity
- defense / energy sector relative strength when available
- global equity volatility when available

## Rules

### severe

Conditions:

- VIX >= 40
- geopolitical news severity is high
- oil price spike >= 10% over 5 trading days

### high

Conditions:

- VIX >= 30
- geopolitical news severity is medium or high
- gold or DXY is rising strongly

### elevated

Conditions:

- VIX >= 25, or
- geopolitical news count is above benchmark, or
- oil price spike >= 5% over 5 trading days

### normal

Used when no crisis condition is met.

### insufficient_data

Used when too many required indicators are missing.

## Reference Labels

Allowed reference labels:

```text
defensive_assets_positive
risk_assets_under_pressure
monitor_energy_and_defense
monitor_volatility
no_crisis_signal
insufficient_data
```

## Output

```json
{
  "level": "elevated",
  "confidence": 0.76,
  "reference": {
    "cash_usd": "defensive_assets_positive",
    "gold": "defensive_assets_positive",
    "treasury": "defensive_assets_positive",
    "energy": "monitor_energy_and_defense",
    "defense": "monitor_energy_and_defense",
    "growth_stocks": "risk_assets_under_pressure"
  },
  "components": [],
  "limitations": [],
  "missing_data": []
}
```

Every component includes raw data, derived metrics, benchmark, trend, source, source date, confidence, limitations, and missing data.
