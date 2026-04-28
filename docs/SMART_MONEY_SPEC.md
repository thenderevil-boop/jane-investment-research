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
insider_distribution_risk
insider_activity_neutral
insufficient_data
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
- transaction code
- transaction category
- security title
- shares
- price
- acquired/disposed code
- value
- transaction date
- filing date
- director/officer flags
- officer title
- ownership type
- direct or indirect ownership code
- accession number and CIK when SEC-backed

Derived metrics:

- net_insider_accumulation_value_180d
- total_transactions_180d
- accumulation_count_180d
- disposition_count_180d
- officer_accumulation_count
- director_accumulation_count
- founder_or_ceo_accumulation
- largest_accumulation_value
- latest_transaction_date
- latest_filing_date

SEC Form 4 code handling:

- `P`: open market or private purchase; count as accumulation.
- `S`: open market or private disposition; count as disposition.
- `M`: option exercise; do not count as accumulation by default.
- `A`: grant or award; do not count as accumulation by default.
- `F`: tax withholding or payment; do not count as bearish disposition by default.
- `G`: gift; do not count as accumulation or disposition by default.
- `J`, missing, and unknown codes: classify as other unless later rules add context.

Parsing and output controls:

- Official SEC EDGAR XML parsing reads `nonDerivativeTable.nonDerivativeTransaction` and `derivativeTable.derivativeTransaction`.
- Holdings-only rows are excluded from transaction scoring.
- Duplicate rows are removed using ticker, CIK, accession number, insider name, transaction date, transaction code, security title, shares, price, ownership type, and acquired/disposed code.
- Form 4 freshness uses `form4_recent_180_days` based on latest filing date, not latest expected trading day.
- Daily report raw Form 4 rows are capped at 25. Derived metrics use all lookback-window rows.
- Mock fallback Form 4 data is not used to boost the smart-money score.
- If all live rows are missing transaction codes, label is neutral or insufficient, `transaction_code` is reported as missing data, and Form 4 does not increase the component score.

Score:

```text
if multiple officers/directors show accumulation and no disposition: score = 100
elif CEO/founder accumulation is observed and net accumulation value is positive: score = 90
elif net accumulation value is positive: score = 70
elif repeated disposition activity is observed: score = 20
else: score = 50
```

Limitations:

- Form 4 transaction codes require context from compensation plans, indirect ownership, and filing notes.
- Code `M`, `A`, and `F` activity is not treated as accumulation by default.
- Form 4 evidence is research context only and is not a trading instruction.

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
