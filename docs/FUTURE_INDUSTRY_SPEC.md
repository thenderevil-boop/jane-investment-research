# FUTURE_INDUSTRY_SPEC.md

## Purpose

Track future investment themes repeatedly discussed in Jane's Markdown files.

The system should produce a daily Future Industry Radar.

## Core Themes

MVP theme universe:

```text
AI energy infrastructure
quantum computing
aerospace / defense technology
humanoid robotics
stablecoin / payment rails
tokenization / digital asset infrastructure
space economy
water resources
food resources
data center cooling
synthetic biology
longevity science
cybersecurity / blockchain
smart agriculture / food tech
electric grid infrastructure
```

## Theme Score

```text
theme_score =
  news_momentum_score * 0.20 +
  capital_flow_score * 0.20 +
  policy_support_score * 0.15 +
  technology_progress_score * 0.15 +
  commercialization_score * 0.15 +
  strategic_relevance_score * 0.15
```

## Component Definitions

### News Momentum Score

Raw data:

- number of news mentions in last 7 / 30 days
- historical average mentions
- source quality

Derived:

- theme_hype_ratio
- positive / negative ratio

### Capital Flow Score

Raw data:

- ETF flows if available
- VC funding news if available
- public company capex references
- institutional positioning proxies

### Policy Support Score

Raw data:

- government budget announcements
- bills / laws / regulations
- defense or infrastructure procurement
- subsidies

### Technology Progress Score

Raw data:

- patents
- product launches
- technical milestones
- demos
- research papers where available

### Commercialization Score

Raw data:

- customer contracts
- revenue contribution
- production scale
- enterprise adoption

### Strategic Relevance Score

Static mapping to Jane themes:

- AI energy / data center / cooling
- quantum after AI maturity
- stablecoin and payment rails
- space and satellite infrastructure
- humanoid robotics and automation
- water and food resources

## Output

```json
{
  "theme": "data_center_cooling",
  "score": 84,
  "label": "heating_up",
  "trend": "up",
  "candidate_companies": [],
  "raw_data": {},
  "derived_metrics": {},
  "benchmark": {},
  "source": [],
  "source_date": "",
  "confidence": 0.0,
  "limitations": [],
  "missing_data": [],
  "candidate_companies": []
}
```

Phase 7.1 implements this as `backend/app/engines/future_industry_engine.py` using mock theme fixtures only.

## Labels

```text
heating_up
stable
cooling_down
needs_human_verification
insufficient_data
```

## Candidate Company Selection

A company may enter the candidate list when:

1. It maps to a theme.
2. Theme score >= 70.
3. Company has sufficient US-market data.
4. Leadership score can be calculated.

Do not mark candidates as investments. Mark them as research candidates only.
