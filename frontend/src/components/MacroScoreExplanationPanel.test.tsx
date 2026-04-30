import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import MacroScoreExplanationPanel from './MacroScoreExplanationPanel';

describe('MacroScoreExplanationPanel', () => {
  it('renders score summary, grouped components, and excluded indicators', () => {
    const html = renderToStaticMarkup(
      <MacroScoreExplanationPanel
        provider="mixed_FRED_and_yfinance_macro"
        explanation={{
          scoring_model_version: 'macro_v12_5',
          score: 65,
          max_score: 100,
          label: 'neutral_to_constructive',
          confidence: 0.95,
          active_weight_total: 100,
          weighted_contribution_sum: 65,
          rounding_difference: 0,
          rounding_tolerance: 1,
          confidence_basis: {
            excluded_indicators_count_as_missing: false,
          },
          confidence_explanation: {
            confidence: 0.95,
            basis: {
              excluded_indicators_count_as_missing: false,
            },
            deductions: [],
            max_confidence: 0.95,
          },
          limitations: [],
          groups: [
            {
              name: 'rates_and_policy',
              display_name: 'Rates and policy environment',
              weight: 25,
              weighted_contribution_sum: 7,
              components: [
                {
                  name: 'fed_policy_trend',
                  display_name: 'Fed policy trend',
                  raw_value: 'neutral',
                  component_score: 70,
                  weight: 10,
                  weighted_contribution: 7,
                  source_type: 'derived',
                  provider: 'derived_from_FRED',
                  source_date: '2026-03-01',
                  freshness_window: 'derived_from_FRED',
                  is_fresh: true,
                  limitation: 'FRED macro series may be delayed depending on release schedule.',
                },
              ],
            },
          ],
          excluded_indicators: [
            {
              name: 'ism_manufacturing_pmi',
              display_name: 'ISM Manufacturing PMI',
              reason: 'Excluded because no valid licensed/live source is configured.',
              affects_score: false,
              weight: 0,
            },
            {
              name: 'cnn_fear_greed',
              display_name: 'CNN Fear & Greed',
              reason: 'Excluded because no licensed/stable source is configured.',
              affects_score: false,
              weight: 0,
            },
          ],
        }}
      />,
    );

    expect(html).toContain('Macro Score Explanation');
    expect(html).toContain('65 / 100');
    expect(html).toContain('neutral_to_constructive');
    expect(html).toContain('95%');
    expect(html).toContain('macro_v12_5');
    expect(html).toContain('Rates and policy environment');
    expect(html).toContain('Fed policy trend');
    expect(html).toContain('derived_from_FRED');
    expect(html).toContain('Excluded Indicators');
    expect(html).toContain('ISM Manufacturing PMI');
    expect(html).toContain('CNN Fear &amp; Greed');
    expect(html).toContain('affects_score=false');
    expect(html).toContain('weight=0');
  });
});
