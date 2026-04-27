# SMART_MONEY_SPEC.md

## Purpose

Track institutional, insider, and options-related smart money signals referenced in Jane's methodology.

## Outputs

```json
{
  "smart_money_score": 0,
  "label": "",
  "components": {
    "institutional_support_13f": {},
    "insider_form4_signal": {},
    "options_abnormal_activity": {}
  }
}
```

Allowed labels:

```text
smart_money_supportive
smart_money_mixed
smart_money_neutral
institutional_supportive
insider_accumulation_observed
options_activity_elevated
risk_warning
needs_human_verification
```

## Important 13F Rule

13F is delayed institutional support data.

It must not be treated as real-time trading data.

Required limitations for every 13F output:

- 13F may lag up to 45 days after quarter end.
- 13F generally discloses long positions in covered securities.
- 13F may not show shorts, derivatives, or current positions.
- Do not use 13F alone as a trading signal.

## 13F Institutional Support

Raw data:

- institution name
- issuer name
- CUSIP
- shares
- market value
- quarter
- filing date

Derived metrics:

- holder_count
- holder_count_change
- top_10_holder_concentration
- quarterly_position_change_pct
- institutional_ownership_proxy

Benchmark:

- peer average institutional ownership
- peer average quarterly position change
- sector median

Score:

```text
if position trend > peer benchmark and holder count increases: score = 100
elif either trend or holder count is positive: score = 60
elif major holders reduce materially: score = 20
else: score = 40
```

## Form 4 Insider Signal

Raw data:

- insider name
- role
- transaction type
- shares
- price
- value
- transaction date
- filing date

Derived metrics:

- net_insider_buy_value_180d
- buy_count_180d
- sell_count_180d
- buy_value_vs_estimated_compensation if available

Score:

```text
if multiple officers/directors net buy and no major selling: score = 100
elif CEO/founder net buy: score = 90
elif net insider buying positive: score = 70
elif repeated insider selling: score = 20
else: score = 50
```

## Options Abnormal Activity

Raw data:

- option volume
- open interest
- call / put split
- implied volatility
- expiration date

Derived:

- volume_to_open_interest
- call_put_ratio
- abnormal_volume_ratio

Score:

```text
if abnormal_volume_ratio >= 3 and direction consistent with price action: score = 80
elif abnormal_volume_ratio >= 2: score = 60
else: score = 40
```

Limitation:

Options activity is ambiguous and may reflect hedging, speculation, or spread trades.

## Final Smart Money Score

```text
smart_money_score =
  institutional_support_13f_score * 0.30 +
  insider_form4_score * 0.45 +
  options_abnormal_activity_score * 0.25
```

For daily updates, Form 4 and options are more timely than 13F.
