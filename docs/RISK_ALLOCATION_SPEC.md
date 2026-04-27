# RISK_ALLOCATION_SPEC.md

## Purpose

Provide risk and allocation reference signals based on Jane's risk-control and financial literacy framework.

This module must not provide portfolio instructions. It only provides risk posture and research reference.

## Output Labels

```text
risk_on_watch
balanced_watch
defensive_watch
crisis_watch
overheat_warning
insufficient_data
```

## Inputs

- macro regime
- market timing score
- overheat score
- crisis score
- VIX
- DXY
- gold trend
- treasury trend
- equity trend
- inflation pressure
- recession warning
- stock-specific risk factors

## Risk Posture Rules

### Defensive Watch

Conditions may include:

- VIX elevated
- recession warning elevated
- yield curve risk
- unemployment rising
- ISM below 50
- insider selling
- high debt company risk

### Crisis Watch

Conditions may include:

- geopolitical conflict headlines
- oil shock
- VIX spike
- DXY spike
- gold and treasuries strengthening
- global equity volatility

### Overheat Warning

Conditions may include:

- overheat score >= 60
- Fear & Greed high
- media hype ratio high
- market extended
- retail/social heat high

## Reference Asset Roles

The system may describe asset roles, not instructions.

Allowed language:

- cash has optionality in fearful markets
- gold may act as crisis hedge
- treasuries may act as defensive asset in recession scare
- growth stocks require selectivity in overheated markets
- defense/energy may be tactical crisis-related themes

Forbidden language:

- allocate X% now
- sell all stocks
- buy gold
- enter defense stocks

## Stock-Specific Risk Flags

Flag when available:

- CEO changed frequently
- revenue growth but net income deteriorating
- negative FCF trend
- high debt / low interest coverage
- repeated insider selling
- dilution / convertible debt / funding stress
- media hype with weak fundamentals
- high leverage product exposure

## Output Schema

```json
{
  "risk_posture": "defensive_watch",
  "score": 70,
  "reference": {
    "market_risk": "defensive_watch",
    "volatility": "defensive_watch",
    "theme_research": "balanced_watch",
    "quality_filter": "defensive_watch"
  },
  "risk_flags": [],
  "raw_data": {},
  "derived_metrics": {},
  "benchmark": {},
  "trend": {},
  "source": [],
  "source_date": "",
  "confidence": 0.0,
  "limitations": [],
  "missing_data": []
}
```

Phase 7.1 restricts `risk_posture` and `reference` values to:

- `risk_on_watch`
- `balanced_watch`
- `defensive_watch`
- `crisis_watch`
- `overheat_warning`
- `insufficient_data`

The engine does not output allocation percentages.
