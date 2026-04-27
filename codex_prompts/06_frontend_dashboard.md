# Codex Prompt 06: Frontend Dashboard

Read:

- `AGENTS.md`
- `docs/API_SPEC.md`

Build the MVP frontend.

## Requirements

Use:

- React
- TypeScript
- Vite

Pages:

1. Dashboard
2. Daily Report
3. Stock Research

Components:

- ScoreCard
- SignalBadge
- RawDataPanel
- EvidenceTable
- TrendChart placeholder
- MissingDataPanel
- HumanVerificationQueue

Dashboard must show:

- macro regime
- market timing
- overheat risk
- future themes
- stock candidates
- risk notes
- missing data

Stock Research page must allow ticker input and call:

- `POST /api/analyze-stock`

Every score must show expandable:

- raw data
- benchmark
- trend
- confidence
- limitations
- missing data

Do not show buy/sell/hold recommendations.
