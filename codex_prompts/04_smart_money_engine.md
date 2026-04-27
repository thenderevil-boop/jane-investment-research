# Codex Prompt 04: Smart Money Engine

Read:

- `AGENTS.md`
- `docs/SMART_MONEY_SPEC.md`

Implement Smart Money Engine using mock data.

## Requirements

Create:

- `backend/app/engines/smart_money_engine.py`
- tests for Smart Money Engine

Components:

1. 13F institutional support
2. Form 4 insider signal
3. options abnormal activity

13F rules:

- Must be treated as delayed institutional support.
- Must not be treated as real-time trading data.
- Must always include quarter, filing_date, source, and limitations.

Form 4 rules:

- net insider buying is positive signal
- repeated insider selling is risk signal

Options rules:

- abnormal volume is ambiguous
- must include limitation that it may represent hedging or spread trades

Final score:

```text
smart_money_score =
  institutional_support_13f_score * 0.30 +
  insider_form4_score * 0.45 +
  options_abnormal_activity_score * 0.25
```

Do not output direct investment instructions.
