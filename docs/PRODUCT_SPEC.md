# PRODUCT_SPEC.md

## Product Name

Jane Framework Daily Investment Research Assistant

## Product Goal

Create a US-market-only daily research automation system that converts Jane's Markdown investment framework into traceable, evidence-based research signals.

The product must support both:

1. Daily automated market and theme reports.
2. On-demand stock analysis by ticker.

## Source of Truth

Use the uploaded Markdown methodology files as the conceptual basis:

- 30年才出現一次的致富機會.md
- CBDC帶來的未來災難與機會.md
- Jane的祕密手冊.md
- 成為超級有錢人的未來龍頭股發掘方法.md
- 能讓你成為大富豪的未來成長產業.md
- 最快、最簡單成為有錢人的方法.md
- 擺脫金融文盲.md

Do not use the old docx specification as the design basis.

## Core User Jobs

1. See the daily US market regime.
2. See whether the market environment is fearful, favorable, neutral, or overheated.
3. Track future investment themes Jane repeatedly discusses.
4. Identify US-listed companies that deserve deeper research.
5. See smart money, insider, and institutional support signals.
6. Inspect raw data and evidence behind every score.
7. Know which items require human verification.

## Main Product Modes

### Daily Report Mode

The system automatically generates a daily report after US market close.

Suggested Taiwan time for report generation:

```text
06:30 to 08:00 Asia/Taipei
```

### Stock Research Mode

User enters a US ticker and receives:

- company profile
- leadership stock score
- smart money score
- market timing context
- overheat risk
- financial quality
- risk warnings
- raw evidence panels

## Required Output Principles

Every score must include:

- raw_data
- source
- source_date
- derived_metrics
- benchmark
- trend
- confidence
- limitations
- missing_data

## Product Boundary

This system does not:

- execute trades
- provide portfolio execution
- provide direct buy/sell instructions
- guarantee results
- replace human research

## Product Language

Use research labels only.

Allowed examples:

- worth_deep_research
- watchlist_candidate
- favorable_research_environment
- elevated_heat
- high_risk_warning
- needs_human_verification

Forbidden examples:

- buy
- sell
- sell half
- exit all
- all in
- guaranteed
