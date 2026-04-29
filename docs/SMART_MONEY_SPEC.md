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
elif live/cached SEC 13F holdings exist but no candidate CUSIP match is observed: score = 40
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
- Ticker matching requires the bounded local ticker-to-CUSIP map and must not call external CUSIP APIs.
- Exact issuer aliases in the local map may resolve to CUSIP with medium confidence.
- Issuer-name-only matching is low confidence and must disclose that limitation.
- The local security map is not authoritative and is used only for deterministic matching and value-confidence enrichment.
- Candidate-level 13F output separates `candidate_specific_evidence` from `portfolio_context`.
- A manager's top holdings are supporting context only and do not count as candidate-specific support unless the candidate CUSIP is present in the holdings.
- `candidate_specific_evidence.matched_in_13f=true` contributes only when source data is live or cached live, provider is SEC EDGAR-derived, freshness uses `quarterly_filing_delay`, and match confidence is high or medium.
- `matched_in_13f=false` does not add positive 13F support for that candidate, should use `no_reported_13f_position_observed` when the candidate ticker resolves locally, and should set `score_contribution_allowed=false`.
- `matched_in_13f=true` may set `score_contribution_allowed=true` only when source and confidence guardrails pass; 13F contribution remains bounded by `maximum_score_from_delayed_13f_only`.
- Issuer-name-only candidate matches use `low_confidence_issuer_name_match` and do not carry high-confidence evidence.
- Mock or fallback target matches are diagnostics only and do not boost candidate smart-money scoring.
- Candidate `portfolio_context.top_holdings_by_value` is capped by `SEC_13F_CANDIDATE_CONTEXT_TOP_HOLDINGS_LIMIT`, default 5.
- Manager names are display metadata resolved from a bounded local manager map when available. CIK remains the stable identifier, and the local map is not authoritative.
- Candidate summaries must disclose that no reported 13F position observed is not a negative trading signal and that observed 13F positions reflect delayed quarterly reporting rather than current positions.
- Value confidence may be upgraded when local mapping and a cached/reusable price reference are both available.
- The price-reference layer checks reusable market cache first, then uses a bounded per-ticker adapter instead of refetching for every 13F row.
- Daily report fast mode uses cached market data for 13F price references unless `ALLOW_PRICE_REFERENCE_LIVE_FETCH_ON_REPORT_REQUEST=true`.
- Fast mode can preserve 13F value confidence when mapped tickers already have cached market prices.
- Optional bounded cache warmup can improve value confidence, but it remains ticker-level, deduplicated, capped, and separate from scoring semantics.
- Price-reference summaries distinguish grouped, row, and ticker counts through `price_reference_grouped_holding_count`, `price_reference_row_count`, and `price_reference_ticker_count`; `price_reference_used_count` remains a backward-compatible grouped count.
- `price_reference_unavailable_tickers` lists mapped tickers without a cached or warmed reference, and `price_reference_mode` reports `cache_only`, `cache_with_bounded_warmup`, or `live_allowed`.
- If mapped 13F rows cannot obtain a reusable price reference, the portfolio summary reports `price reference unavailable for mapped 13F holdings` in `missing_data`.
- Price references may not match the 13F report date exactly, and confidence is capped conservatively when the reference date differs materially from the 13F report date.
- QoQ comparison is by CUSIP and reflects reported quarterly 13F changes only.
- Fallback or mock 13F does not boost the smart-money score.
- Daily report raw data is compact by default and excludes the full 13F row list.
- Full 13F rows are included only when `INCLUDE_FULL_13F_HOLDINGS_IN_DAILY_REPORT=true`, under `raw_data_full.holdings`.
- `qoq_changes` is capped and accompanied by `qoq_changes_count_total` and `qoq_changes_limit`.
- Daily report performance guardrails do not change smart-money scoring semantics. `DAILY_REPORT_FAST_MODE=true` keeps SEC and price-reference access cache-first, while optional `performance_diagnostics` reports timing and bounded-fetch counters without secrets.

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
