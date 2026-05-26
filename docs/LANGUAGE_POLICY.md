# Language Policy

## Purpose

This policy is a hard gate for Jane Investment Research development. New backend, frontend, and documentation changes must use research-workflow language, not directive investment language. The goal is to keep the product focused on evidence, source quality, and next research actions.

## Allowed research workflow terms

Use these terms when describing outputs:

- researchable
- watchlist
- insufficient_data
- deprioritize_for_now
- manual_review_required
- evidence_gap
- risk_flag
- valuation_pressure
- quality_concern
- source_setup
- coverage_gap
- watchlist_change
- macro_context
- tailwind/headwind as context only

Chinese UI or report copy should prefer:

- 可研究
- 觀察名單
- 資料不足
- 需要人工確認
- 證據缺口
- 風險旗標
- 估值壓力
- 品質疑慮

## Forbidden and restricted terms

The following terms are forbidden when used as recommendations or directives:

- BUY
- SELL
- HOLD as a recommendation
- short-term trade
- enter / exit position
- liquidate
- must invest
- 買進
- 賣出
- 持有 as a recommendation
- 短線
- 中短線
- 進出場
- 停損
- 目標價 as a directive

Allowed factual exceptions must be narrow and justified, for example SEC 13F holdings as a filing noun.

## Replacement patterns

Use:

- `researchable` instead of directive action wording.
- `watchlist` instead of a recommendation label.
- `insufficient_data` when source quality or evidence gaps block useful interpretation.
- `deprioritize_for_now` when current evidence does not justify deeper research.
- `manual_review_required` when evidence needs human validation.

## API and UI copy rules

- Every workflow status must include the dominant reason and next research action.
- Evidence-only fields must keep `affects_score=false` when they do not change the existing score.
- Daily Report should start with macro context, source/watchlist changes, and 2-3 concrete research actions.
- Stock Research remains the deep single-name surface.
- Do not add new cards unless they improve one hard gate: language, provider visibility, Coverage Matrix actionability, or Daily Report workflow usefulness.

## Automated gate

`tests/phase60b_product_baseline_stabilization.py` scans key backend, frontend, and documentation surfaces. Future phases should expand that gate rather than fixing wording one phrase at a time.
