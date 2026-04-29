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

13F is delayed institutional holdings evidence.

It must not be treated as real-time trading data.

Required limitations for every 13F output:

- 13F may lag up to 45 days after quarter end.
- 13F generally discloses long positions in covered securities.
- 13F may not show shorts, derivatives, or current positions.
- Do not use 13F alone as a trading signal.
- Fallback mock 13F does not boost smart-money score.

## 13F Institutional Support

Raw data:

- institution name
- issuer name
- CUSIP
- shares
- reported_value_raw
- reported_value_unit
- value_usd
- value_unit_confidence
- value_normalization_note
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
if live/cached SEC 13F holdings exist and target CUSIP is observed: score = 60
elif live/cached SEC 13F holdings exist but target CUSIP is not mapped: score = 50
elif fallback 13F is used: score = 20
elif mock 13F is used: score = 40
elif insufficient data: score = 30
```

Live SEC 13F derived metrics:

```text
latest_13f_report_date
latest_13f_filing_date
total_reported_value_usd
holding_count
target_ticker_holdings
target_cusip_holdings
top_holdings_by_value
quarter_over_quarter_position_change
manager_count_observed
institutional_support_label
```

Source status:

- provider: `SEC EDGAR`
- freshness_window: `quarterly_filing_delay`
- source_date: report date when available, otherwise filing date
- fetched_at: cache/write or retrieval timestamp
- source_type: `live`, `cached_live`, `mock`, `fallback`, `derived`, or `unknown`

Value normalization:

- SEC 13F XML `<value>` is preserved as `reported_value_raw`.
- `value_usd` is a best-effort normalized USD value for aggregate metrics and rankings.
- The system does not blindly multiply every XML value by 1000.
- If a reliable price reference is available, the parser compares raw value and raw value times 1000 against shares times the reference price and assigns `reported_value_unit` as `usd` or `thousands_usd`.
- If no reliable price reference is available, the raw value is preserved with `reported_value_unit` set to `as_reported` and confidence below high.

Aggregation and target matching:

- Row-level 13F holdings are aggregated by CUSIP when available.
- If CUSIP is missing, normalized issuer name plus title of class is used as the fallback grouping key.
- The same issuer can appear under multiple CUSIPs or classes, so issuer-name similarity alone must not merge securities.
- Target matching is highest confidence by exact CUSIP.
- Ticker matching requires a local ticker-to-CUSIP fixture and must not call external CUSIP APIs.
- Issuer-name matching is low confidence and must disclose that limitation.
- QoQ comparison is by CUSIP and reflects reported quarterly 13F changes only.
- Fallback or mock 13F does not boost the smart-money score.
- Daily report raw data is compact by default and excludes the full 13F row list.
- Full 13F rows are included only when `INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT=true`, under `raw_data_full.holdings`.
- `qoq_changes` is capped and accompanied by `qoq_changes_count_total` and `qoq_changes_limit`.

SEC EDGAR discovery:

- Use `data.sec.gov/submissions/CIK##########.json` only for manager filing discovery.
- Use SEC Archives `index.json` or `{accession-number}-index.html` to discover the actual information table XML filename.
- Submissions CIKs are zero-padded to 10 digits.
- Archives paths strip CIK leading zeros and remove accession dashes.
- The HTML index filename keeps accession dashes.
- Do not hardcode `form13fInfoTable.xml`.

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

- `P`: open market or private purchase; label as accumulation evidence and count as accumulation.
- `S`: open market or private disposition; label as disposition evidence and count as disposition.
- `M`: option exercise; do not count as accumulation by default.
- `A`: grant or award; do not count as accumulation by default.
- `F`: tax withholding or payment; do not count as bearish disposition by default.
- `G`: gift; do not count as accumulation or disposition by default.
- `D`: acquired/disposed ownership-code context; do not treat as a transaction-code accumulation signal.
- `J`, missing, and unknown codes: classify as other unless later rules add context.

Parsing and output controls:

- Official SEC EDGAR XML parsing reads `nonDerivativeTable.nonDerivativeTransaction` and `derivativeTable.derivativeTransaction`.
- Holdings-only rows are excluded from transaction scoring.
- Duplicate rows are removed using ticker, CIK, accession number, insider name, transaction date, transaction code, security title, shares, price, ownership type, and acquired/disposed code.
- Form 4 freshness uses `form4_recent_180_days` based on latest filing date, not latest expected trading day.
- Daily report raw Form 4 rows are capped at 25. Derived metrics use all lookback-window rows.
- Mock fallback Form 4 data is not used to boost the smart-money score.
- If all live rows are missing transaction codes, label is neutral or insufficient, `transaction_code` is reported as missing data, and Form 4 does not increase the component score.
- 13F is official SEC EDGAR-backed when `USE_LIVE_SEC_13F=true`, `SEC_EDGAR_USER_AGENT` is configured, and manager CIKs or supported local manager names are configured.
- Form 4, 13F, options, insider activity, and institutional activity are research evidence only and must not be expressed as user trading instructions.

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
