import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import JaneReferencePanel from './JaneReferencePanel';

describe('JaneReferencePanel', () => {
  it('renders reference conditions as unscored methodology context', () => {
    const html = renderToStaticMarkup(
      <JaneReferencePanel
        reference={{
          title: 'Methodology reference conditions',
          source_type: 'methodology_reference',
          affects_score: false,
          not_investment_advice: true,
          conditions: [
            {
              name: 'cnn_fear_greed_extreme_fear',
              display_text: '當 CNN 恐懼與貪婪指數低於 20，進入極度恐慌時',
              system_status: 'excluded_unlicensed_source',
              mapped_system_fields: [],
              score_contribution_allowed: false,
              limitation: 'CNN Fear & Greed is excluded from scoring because no licensed/stable source is configured.',
            },
          ],
          limitations: [],
        }}
      />,
    );
    expect(html).toContain('Methodology Reference Conditions');
    expect(html).toContain('未納入評分');
    expect(html).toContain('資料源未啟用');
    expect(html).toContain('score_contribution_allowed=false');
  });
});
