# SCORING_RUBRIC.md

## Global Scoring Contract

Every score produced by this system must be traceable and deterministic where possible.

Required score object:

```json
{
  "name": "",
  "score": 0,
  "max_score": 100,
  "label": "",
  "raw_data": {},
  "derived_metrics": {},
  "benchmark": {},
  "trend": {},
  "source": [],
  "source_date": "",
  "confidence": 0,
  "limitations": [],
  "missing_data": []
}
```

## Confidence Formula

Use this baseline formula unless a specific engine overrides it:

```text
confidence =
  data_completeness * 0.40 +
  data_recency * 0.30 +
  source_reliability * 0.30
```

Values range from 0 to 1.

## Leadership Stock Score

Based on Jane's 20 future leader stock criteria.

Each criterion score:

```text
1.0 = strongly supported by evidence
0.5 = partially supported by evidence
0.0 = unsupported or insufficient data
```

Total:

```text
leadership_score = sum(criteria scores)
max_score = 20
```

Labels:

```text
>= 16.0: worth_deep_research
12.0 to 15.5: watchlist_candidate
< 12.0: weak_candidate
```

## Criterion Evidence Contract

Each criterion must include:

```json
{
  "criterion_id": 1,
  "criterion_name": "Market Monopoly / Entry Barrier",
  "score": 0.5,
  "raw_data": [],
  "derived_metrics": {},
  "benchmark": {},
  "trend": {},
  "evidence_summary": "",
  "source": [],
  "source_date": "",
  "confidence": 0.0,
  "limitations": [],
  "missing_data": []
}
```

## Leadership Criteria

### 1. Market Monopoly / Entry Barrier

Sub-metrics:

- switching cost
- network effect
- economies of scale
- intangible assets
- regulatory moat
- IP moat
- customer lock-in
- infrastructure necessity

Score:

```text
1.0 if at least 3 sub-metrics are strongly supported
0.5 if 1 to 2 sub-metrics are supported
0.0 if no support or insufficient data
```

### 2. Visionary Founder / CEO

Sub-metrics:

- founder is CEO or executive chair
- long-term vision consistency
- milestone execution record
- founder ownership
- crisis execution history

### 3. Early Market Skepticism

Sub-metrics:

- negative analyst consensus in early period
- media skepticism
- short interest proxy
- product category disbelief

### 4. Disruptive Innovation

Sub-metrics:

- new category creation
- cost curve disruption
- business model disruption
- user workflow replacement

### 5. Technology and R&D Commitment

Sub-metrics:

- R&D as percentage of revenue
- patent count / quality
- product release cadence
- technical benchmarks vs peers

### 6. Scalable Business Model

Sub-metrics:

- gross margin expansion
- operating leverage
- low marginal cost
- platform economics

### 7. Brand and Fandom

Sub-metrics:

- organic search trend
- social mentions
- customer advocacy
- pricing power

### 8. Data Advantage

Sub-metrics:

- proprietary data flywheel
- personalization loop
- model / product improvement from usage
- dataset not easily replicated

### 9. Capital Allocation Ability

Sub-metrics:

- ROIC
- reinvestment effectiveness
- acquisition discipline
- shareholder dilution control

### 10. Free Cash Flow Creation

Sub-metrics:

- positive FCF
- FCF margin
- FCF growth trend
- cash conversion quality

### 11. Mega Trend Alignment

Sub-metrics:

- alignment with Jane's strategic themes
- industry CAGR
- policy support
- capital inflow

### 12. Talent Attraction and Retention

Sub-metrics:

- hiring trend
- key executive retention
- technical team reputation
- employee review trend as weak proxy

### 13. Global Market Expansion

Sub-metrics:

- international revenue mix
- global TAM
- geographic expansion
- global partnerships

### 14. Life-Changing / Necessary Product

Sub-metrics:

- mission-critical usage
- daily/weekly usage
- customer dependency
- infrastructure role

### 15. Regulatory / Government Relationship

Sub-metrics:

- government contracts
- regulatory licenses
- lobbying / policy alignment
- defense or infrastructure status

### 16. Network Effects

Sub-metrics:

- user growth increases value
- marketplace liquidity
- developer ecosystem
- data network effect

### 17. Mission and Narrative Power

Sub-metrics:

- clear long-term mission
- founder narrative consistency
- brand story adoption
- investor narrative durability

### 18. Patents and IP

Sub-metrics:

- patent count
- patent relevance
- defensibility
- litigation / licensing evidence

### 19. VC / Institutional Support

Sources:

- SEC Form 13F
- institutional ownership
- fund holdings
- strategic investors

Important:

13F is delayed quarterly data. It is institutional support evidence, not a real-time trading signal.

### 20. Retention / Repurchase Rate

Sub-metrics:

- net revenue retention
- churn
- repeat purchase
- cohort retention
- subscription renewal

## Final System Scores

The daily report must include these scores:

- macro_regime_score
- entry_environment_score
- overheat_score
- crisis_score
- leadership_score
- smart_money_score
- theme_score
- risk_score
