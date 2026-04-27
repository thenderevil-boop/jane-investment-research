# MARKET_TIMING_SPEC.md

## Purpose

Convert Jane's timing framework into evidence-based market environment signals.

This module must not output buy or sell instructions.

## Outputs

```json
{
  "entry_environment_score": 0,
  "entry_environment_label": "",
  "components": []
}
```

Allowed labels:

```text
favorable_research_environment
watch_for_confirmation
neutral
insufficient_data_or_unfavorable
```

## Score Formula

```text
entry_environment_score =
  fed_easing_score * 0.25 +
  index_drawdown_stabilization_score * 0.25 +
  fear_greed_extreme_fear_score * 0.20 +
  vix_confirmation_score * 0.10 +
  company_cash_score * 0.07 +
  company_revenue_growth_score * 0.07 +
  founder_ceo_insider_buying_score * 0.06
```

For daily market-level report, company-specific components may be excluded or reported separately.

## Component Rules

### Fed Easing Score

Raw data:

- Federal Funds Target Rate
- FOMC decision dates
- last 3 to 6 FOMC decisions

Rule:

```text
if consecutive_rate_cut_count >= 2: score = 100
elif consecutive_rate_cut_count == 1: score = 60
elif rate trend is hold after hikes: score = 30
else: score = 0
```

### Index Drawdown + Stabilization Score

Raw data:

- S&P 500 daily close
- Nasdaq Composite or Nasdaq 100 daily close

Derived metrics:

- drawdown_from_52w_high
- drawdown_from_all_time_high
- days_since_low
- 20-day realized volatility
- 20-day range

Jane rule:

Market down 20% or more and then consolidates.

MVP consolidation definition:

```text
A: drawdown_from_52w_high <= -20%
B: index traded within +/- 8% range for at least 20 trading days
C: 20-day realized volatility lower than previous 20-day realized volatility
```

Scoring:

```text
if A and B and C: score = 100
elif A and (B or C): score = 70
elif A: score = 50
else: score = 0
```

### CNN Fear & Greed Extreme Fear Score

Rule:

```text
if latest_value < 20: score = 100
elif latest_value < 30: score = 70
elif latest_value < 45: score = 40
else: score = 0
```

### VIX Confirmation Score

Rule:

```text
if VIX > 30 and recent spike and falling from spike and index stabilization exists: score = 100
elif VIX > 25 and recent spike and falling/stabilization evidence exists: score = 60
elif VIX > 20: score = 30
else: score = 0
```

High VIX alone is not favorable evidence. It must be paired with falling-from-spike behavior and index stabilization for full confirmation.

### Company Cash Score

Rule:

```text
if cash_to_market_cap >= 10%: score = 100
elif cash_to_market_cap >= 5%: score = 50
else: score = 0
```

### Company Revenue Growth Score

Rule:

```text
if each of last 3 years YoY revenue growth >= 10%: score = 100
elif 3Y CAGR >= 10%: score = 70
elif latest YoY growth >= 10%: score = 40
else: score = 0
```

### Founder CEO + Insider Buying Score

Rule:

```text
if founder_is_ceo and net_insider_buy_value_180d > 0 and insider_buy_count_180d >= 2: score = 100
elif founder_is_ceo and net_insider_buy_value_180d > 0: score = 70
elif founder_is_ceo: score = 40
else: score = 0
```

## Final Label

```text
if score >= 80: favorable_research_environment
elif score >= 60: watch_for_confirmation
elif score >= 40: neutral
else: insufficient_data_or_unfavorable
```

## Overheat Risk Score

Jane's overheat logic becomes a separate risk score.

Formula:

```text
overheat_score =
  index_cycle_heat_score * 0.30 +
  fear_greed_greed_score * 0.20 +
  media_hype_score * 0.25 +
  youtube_hype_score * 0.15 +
  user_reported_social_heat_score * 0.10
```

Primary index heat inputs:

- `index_gain_vs_prior_cycle_high`
- `index_gain_from_recent_trough`
- `distance_from_52w_high`

`index_extension_from_200d_pct` remains supplemental context only.

Labels:

```text
if score >= 80: high_risk_warning
elif score >= 60: overheated
elif score >= 40: elevated_heat
else: normal
```
