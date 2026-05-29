# JANE_FRAMEWORK_MAPPING.md

This file maps Jane's Markdown methodology into system modules.

## Phase 68 Research Workflow Summary v2 Alignment

Phase 68 aligns Jane's single-name workflow summary with the routeable evidence/source workflow:

- `research_workflow_summary` now returns `phase68_research_workflow_summary_v2` and `workflow_alignment_version="phase68_workflow_alignment_v1"`.
- The dominant blocker fields summarize the highest-priority Evidence Gap Inbox item using the same route vocabulary used by Operations and Daily Command Center.
- `dominant_blocker` values are `manual_evidence_gap`, `source_health_action`, `provider_cache_refresh`, `adr_source_limitation`, or `none`; `dominant_route` values include `manual_evidence`, `operations`, `stock_research`, `evidence_library`, and `daily_report`.
- This is workflow triage only: `affects_score=false`, `final_score_unchanged=true`, and `not_investment_advice=true`.

## Phase 66 Source Health Action Routing

Phase 66 turns Jane's source-awareness rule into routeable operations work:

- `GET /api/operations/diagnostics` now returns `source_health_actions` (`phase66_source_health_actions_v1`) for missing keys, missing SEC EDGAR user-agent setup, disabled providers, and cache/readiness issues.
- Each action identifies affected Jane criteria and surfaces (`operations`, `daily_report`, `stock_research`, `evidence_library`) so the next workflow step is explicit.
- Daily Report `command_center.source_health_alerts` consumes the highest-attention source-health actions before falling back to generic data-quality alerts.
- The layer is read-only and non-scoring: no provider calls, secret values, score changes, verdict changes, or investment-advice wording.

## Phase 65 Daily Report Command Center Refinement

Phase 65 maps Jane's daily review habit into a single first-screen command-center summary:

- Daily Report `command_center` (`phase65_daily_command_center_v1`) combines macro delta context, source-health alerts, watchlist focus, and top research actions.
- Route hints point to `daily_report`, `operations`, `stock_research`, or `evidence_library` so the next step is visible without treating the output as advice.
- The section is workflow-only: `affects_score=false`, `final_score_unchanged=true`, and `not_investment_advice=true`.

## Phase 64 Evidence Gap Inbox / Manual Research Queue

Phase 64 maps Jane's evidence-gap review process into a structured non-scoring queue:

- `evidence_gap_inbox` (`phase64_evidence_gap_inbox_v1`) converts Jane Coverage Matrix gaps, manual evidence needs, C19 SEC 13F cache/setup gaps, Form 4 fallback, and ADR/local-filing limitations into prioritized research actions using gap types such as `manual_evidence_required`, `source_setup_required`, `provider_cache_refresh_required`, and `adr_or_foreign_filer_limitation`.
- Gap routes point to `manual_evidence`, `operations`, `stock_research`, or `evidence_dashboard`, so the user can resolve evidence gaps rather than only reading insufficient rows.
- The queue preserves Jane's human-review boundary with `affects_score=false`, `final_score_unchanged=true`, and `not_investment_advice=true`.

## Phase 63 Editable 13F Manager Universe

Phase 63 maps Jane's C19 institutional-support review workflow to an editable operations boundary:

- `GET/PUT/DELETE /api/operations/settings/13f-manager-universe` (`phase63_13f_manager_universe_settings_v1`) controls which SEC 13F managers are used for future target-match reads.
- Precedence is explicit: `local_settings` > `startup_env` > `bundled_starter_universe`, so C19 comparability can be reviewed across runs.
- Editing the universe changes research scope only; it does not change scoring, final verdicts, or the delayed nature of 13F evidence.
- The bundled starter universe remains a starter list for operations visibility, not a permanent scoring requirement.

## Phase 62 Read-only Operations & Data Source Diagnostics

Phase 62 maps Jane's preference for source-aware interpretation into operations visibility before scoring interpretation:

- `GET /api/operations/diagnostics` (`phase62_operations_diagnostics_v1`) and the Operations Diagnostics UI expose Provider Health, Coverage Readiness, and 13F Runtime Universe status.
- C18 readiness is tied to USPTO `patent_count`; C19 readiness is tied to SEC 13F `institutional_support` / `fund_support`.
- `api_key_values_returned=false` and safe key-present booleans keep source setup visible without exposing secrets.
- Diagnostics are read-only, do not trigger provider calls, and do not change Jane scores, verdicts, or recommendations.

## Phase 61 Auto Coverage Completion and Daily Efficiency

Phase 61 maps Jane's preference for daily change detection and evidence completion into the product workflow:

- Jane C18 Patents / IP can receive non-scoring `patent_count` coverage from USPTO PatentsView when provider-backed patent-count evidence is present. It remains a proxy that requires manual patent-quality and assignee review.
- Jane C19 VC / Institutional Support can receive non-scoring `institutional_support` / `fund_support` coverage from candidate-specific SEC 13F target matches. 13F remains delayed quarterly evidence and is not real-time flow.
- Daily Report `macro_delta` compares current macro context with the latest stored snapshot so the user sees change, not just state.
- Daily Report `watchlist_delta` compares configured candidate context with the latest stored snapshot so the user can start from changed overheat/source/data-issue context.
- Overheat `source_backing` discloses live/derived versus mock/fallback configured weight without changing the overheat score.

## Phase 57 Macro / Flow Signal Breakdown MVP

`macro_flow_signal_breakdown` (`phase57_macro_flow_signal_breakdown_v1`) maps Jane's macro-cycle and capital-flow review habits into an analyze-stock explanation layer:

- `macro_signals` summarize existing macro-regime components such as Fed policy, inflation, VIX, equity drawdown, and cross-asset context.
- `flow_signals` summarize Form 4, delayed SEC 13F, and options context with source-quality and limitation copy.
- The section is not a trading signal, does not change final score or final scoring, and keeps `affects_score=false` / `not_investment_advice=true`.

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

Phase 34 expands financial proxy coverage within the same non-scoring Coverage Matrix. Filing-backed SEC Companyfacts values may cover `rd_percent_of_revenue` for criterion 5, `gross_margin_expansion` and `operating_leverage` for criterion 6, and free-cash-flow submetrics for criterion 10 when period-aligned facts exist. These proxy rows remain validation completeness evidence and do not replace manual qualitative research for moat, founder, network effect, disruption, or customer validation criteria.

Phase 46 adds first-pass numeric auto-evidence for qualitative gaps that can be safely proxied without LLMs or new providers. Criterion 3 can partially cover `short_interest_proxy` from yfinance `shortPercentOfFloat` or `shortRatio`; criterion 5 can partially cover `rd_percent_of_revenue` from yfinance, SEC Companyfacts, or FMP ADR financial proxy R&D intensity. These remain auto-derived financial proxies with explicit verification limitations and do not convert the broader qualitative thesis into scoring.

Phase 50 expands the same non-scoring auto-evidence layer to C2 and refines C3. Criterion 2 can partially cover only `founder_ownership` from yfinance `heldPercentInsiders`; `founder_is_ceo`, founder vision, execution record, and crisis execution remain manual qualitative checks. Criterion 3 now requires meaningful short-interest thresholds before covering `short_interest_proxy`, so very low short interest is not treated as positive skepticism evidence.

Phase 47 adds USPTO PatentsView as an opt-in no-key external provider for criterion 18. Positive PatentsView `total_hits` can partially cover C18 `patent_count` in the Coverage Matrix through `patent_ip_evidence`, but patent relevance, assignee/subsidiary matching, licensing value, and defensibility remain manual qualitative checks. Phase 53 makes the disabled-provider state visible as C18 activation guidance when `USE_LIVE_USPTO_PATENTS_DATA=false`.

Phase 51 adds ADR / foreign-filer diagnostics above the same non-scoring coverage workflow. `foreign_filer_coverage_diagnostics` explains structural SEC Companyfacts, SEC Form 4, 13F, FMP transcript, yfinance short-interest, and local-filing limitations, and affected Coverage Matrix rows receive ADR-aware `next_manual_check` guidance. These diagnostics do not cover submetrics, change scores, or imply company weakness; they turn structural data gaps into a manual local-filing / annual-report research path. Phase 53 adds explicit C3 short-interest gap language and clarifies that ADR source-quality Grade D can reflect source coverage / data-structure limits rather than underlying company quality.

Phase 52 adds the intake side of that ADR path. Manual evidence can carry filing-reference metadata (`adr_evidence_type`, `document_title`, `document_date`, `filing_period`, `quoted_text`, `local_market`, `local_ticker`, `translation_note`) and, when complete, is labeled filing-backed for validation completeness. It can cover only explicitly selected Jane submetrics through `criterion_id` / `submetric`, remains user-provided and manually reviewed, and does not modify score weights, final verdicts, or automatic provider behavior.

Phase 54 connects that ADR intake metadata to the saved Evidence Library and review queue UX. The Evidence Library form exposes ADR helper fields, saved ADR items fallback `document_date` into `source_date` for freshness review, and dashboard queue rows surface ADR filing metadata plus `adr_review_label` / `adr_review_guidance` while keeping `affects_score=false` and `not_investment_advice=true`. This improves manual review workflow visibility only; it does not add provider fetching, source verification, scoring weight, or verdict changes.

Phase 55 expands non-scoring Coverage Matrix auto-evidence for selected manual-review gaps. C18 `patent_count` uses USPTO PatentsView by default as a no-key provider but remains manually verified for relevance and defensibility. C19 can use existing SEC 13F target-match evidence to cover `institutional_support` and `fund_support` as delayed quarterly filing context. Phase 56 then tightens C11: explicit `research_context.theme` text is surfaced in `theme_validation_context` as a user-supplied validation target only, not as automatic `jane_theme_alignment` evidence, theme discovery, ranking, or scoring. C11 still requires manual evidence for company revenue exposure, industry CAGR, policy support, and capital inflow. This does not change final score, verdict, or investment-advice boundaries.

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

## Phase 58 Company Event / Insider / Lock-Up Boundary

Phase 58 maps company-event signals into `company_event_signal_breakdown` (`phase58_company_event_signal_breakdown_v1`) as validation explainability only. `event_signals` cover Form 4 accumulation/disposition evidence, systematic-plan review risk, delayed 13F positioning, options attention, and manual IPO lock-up verification. These signals support human review of Jane framework context but do not change final scoring, do not create automatic theme discovery, and are not a trading signal.

## Phase 59 Platform Business Quality Boundary

Phase 59 maps platform-business quality questions into `platform_business_quality_card` (`phase59_platform_business_quality_card_v1`) as validation explainability only. The card helps review Jane-style scalable business model, network effect, cash-flow creation, retention, and marketplace-quality questions through `gmv_growth`, `take_rate`, `net_dollar_retention`, `burn_rate`, `runway`, `marketplace_liquidity`, `network_effect`, `ltv_cac`, and `contribution_margin_operating_leverage`. Public financial proxies may help with burn/runway and operating leverage, but GMV, take rate, NDR, marketplace liquidity, network effect, and LTV/CAC remain manual or disclosed evidence. Phase 59 does not change final scoring, does not infer private platform KPIs, and does not create automatic theme discovery.
