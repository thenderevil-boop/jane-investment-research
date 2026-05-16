# JANE_FRAMEWORK_MAPPING.md

This file maps Jane's Markdown methodology into system modules.

## 1. Long-Cycle Strategic Themes

From the long-cycle opportunity files, the system must track these strategic themes:

- AI energy infrastructure
- US debt / dollar regime / stablecoin rails
- asset tokenization
- AI and robotics replacing labor
- multinational platform companies
- space economy
- water and food resources
- gold and digital gold narratives
- payment rails and stablecoin issuers

Implementation module:

```text
Future Industry Radar
Strategic Theme Tracker
Digital Money & Capital Flow Monitor
```

## 2. CBDC / Stablecoin / Digital Money Logic

Jane distinguishes between CBDC control systems and private stablecoin-based capital flow systems.

The system should monitor:

- USDC and USDT market share
- stablecoin supply trend
- tokenization news
- payment network companies
- crypto / gold / dollar flow proxies
- regulatory news around stablecoins and CBDCs

Implementation module:

```text
Digital Money & Capital Flow Monitor
```

## 3. Crisis Playbooks

Jane's crisis framework includes:

- war or terror event headlines
- large country or oil-producing country conflict
- oil route disruption
- overseas stock and currency volatility
- VIX spike
- USD, gold, bonds, energy, defense reactions
- ceasefire or fear-relief reversal signals

Implementation module:

```text
Crisis Playbook Engine
Macro Regime Engine
Risk & Allocation Reference Engine
```

## 4. Market Timing Logic

Jane's timing framework includes:

- Fed begins consecutive rate cuts
- S&P 500 or Nasdaq falls 20% or more and then consolidates
- CNN Fear & Greed below 20
- company cash at least 10% of company value
- 3-year double-digit revenue growth
- founder CEO with insider buying

Implementation module:

```text
Market Timing Engine
```

## 5. Overheat Logic

Jane's overheat framework includes:

- broad market rises 30% or more from prior high or trough context
- media and YouTube hype surge
- yfinance-derived volume expansion and price extension versus the 200-day moving average
- people around the user frequently discuss a stock as a human-verification signal only
- speculative attention rises

Phase 31 note: `user_reported_social_heat` is no longer a scoring input because post-2020 social/media acceleration can keep discussion elevated for extended theme-driven bull markets. It is preserved as the `jane_social_heat_check` human-verification prompt when `overheat_score >= 60`.

Implementation module:

```text
Overheat Risk Engine
```

## 6. Leadership Stock Logic

Jane's future leader stock framework includes 20 criteria:

1. `monopoly_power` - monopoly power or high entry barrier
2. `visionary_founder_ceo` - visionary founder / CEO
3. `early_skepticism` - strong early skepticism
4. `disruptive_innovation` - disruptive innovation
5. `superior_technology_r_and_d` - superior technology and R&D commitment
6. `scalable_business_model` - scalable business model
7. `brand_power_fandom` - strong brand and fandom
8. `data_advantage` - data advantage
9. `capital_allocation` - capital allocation ability
10. `cash_flow_creation` - free cash flow creation
11. `mega_trend_fit` - mega trend alignment
12. `talent_attraction_retention` - talent attraction and retention
13. `global_expansion` - global market expansion
14. `life_changing_necessary_product` - product changes life and becomes necessary
15. `regulatory_government_relationship` - regulatory / government relationship
16. `network_effect` - network effects
17. `mission_narrative_power` - mission and narrative power
18. `patents_ip` - key patents and IP
19. `vc_institutional_support` - VC / institutional support
20. `retention_repurchase_rate` - high retention / repurchase rate

Phase 27 stores this canonical model in `backend/app/data/jane_leadership_criteria.json` with display names, descriptions, accepted evidence types, manual check questions, and the default status `insufficient`.

Phase 28 maps the same canonical 20-criteria model into analyze-stock `jane_criteria_coverage`, a non-scoring coverage matrix that tracks covered and missing submetrics, accepted evidence counts, and required human verification for validation completeness.

Phase 29 surfaces the same coverage and evidence gaps through analyze-stock `validation_os_report`, a non-scoring explainability layer that summarizes Jane quality context, coverage gaps, manual checks, source-quality caveats, and research-only limitations without changing the final score or verdict.

Implementation module:

```text
Leadership Stock Engine
```

## 7. Smart Money Logic

Jane references:

- 13F reports
- insider trading / Form 4
- options volume
- institutional behavior

Implementation module:

```text
Smart Money Engine
```

Important:

13F is delayed quarterly institutional support data. It is not a real-time trading signal.

## 8. Financial Literacy / Risk Logic

Jane repeatedly emphasizes:

- avoid all-in
- diversify across stocks, bonds, cash, gold / USD
- avoid excessive leverage
- inspect EPS, PER, PBR, revenue, net income, FCF
- do not chase overheated names
- avoid companies with frequent CEO changes, negative profit trend, high debt, or funding stress

Implementation module:

```text
Risk & Allocation Reference Engine
Financial Quality Engine
Valuation Context Engine
```
