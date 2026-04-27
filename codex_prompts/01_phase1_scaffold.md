# Codex Prompt 01: Phase 1 Scaffold

Read `AGENTS.md` and all files under `/docs`.

Build Phase 1 only.

## Goal

Create a mock-data US-market-only daily investment research automation backend.

## Requirements

1. Use Python FastAPI and Pydantic.
2. Create a backend folder structure matching `AGENTS.md`.
3. Use mock data only. Do not connect to live APIs.
4. Implement:
   - `GET /api/health`
   - `GET /api/daily-report/latest`
   - `POST /api/analyze-stock`
5. Daily report must include:
   - macro_regime
   - market_timing
   - overheat_risk
   - crisis_risk
   - future_themes
   - stock_candidates
   - smart_money_summary
   - risk_notes
   - missing_data
   - human_verification_queue
   - not_investment_advice: true
6. Stock analysis must include:
   - ticker
   - market
   - company_profile
   - leadership_score
   - market_timing_context
   - overheat_risk
   - smart_money
   - financial_quality
   - valuation_context
   - risk_flags
   - missing_data
   - human_verification_queue
   - not_investment_advice: true
7. Every scoring object must include:
   - raw_data
   - source
   - source_date
   - derived_metrics
   - benchmark
   - trend
   - confidence
   - limitations
   - missing_data
8. Add pytest tests.
9. Add a README section with PowerShell commands for Windows.
10. Ensure API responses do not contain prohibited language from AGENTS.md.

Before coding, provide a short implementation plan.
After coding, run tests and show results.
