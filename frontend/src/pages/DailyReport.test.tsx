import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { DailyReport, DataSourceStatus } from '../types';
import { DailyDataCoverageSummary, DailyResearchActions } from './DailyReport';

function status(sourceType: DataSourceStatus['source_type'], sourceDate = '2026-05-15', isFresh = true): DataSourceStatus {
  return {
    source_type: sourceType,
    provider: `${sourceType}_provider`,
    source_date: sourceDate,
    fetched_at: null,
    is_fresh: isFresh,
    freshness_window: 'latest_expected_trading_day',
    fallback_used: sourceType === 'fallback',
    fallback_reason: sourceType === 'fallback' ? 'fixture fallback' : null,
    limitations: sourceType === 'mock' ? ['Some components still use mock data.'] : [],
    missing_data: sourceDate ? [] : ['source_date'],
  };
}

describe('DailyReport presentation helpers', () => {
  it('renders daily data coverage summary compactly', () => {
    const report = {
      date: '2026-05-18',
      market: 'US',
      macro_regime: { source_status: status('derived') },
      market_timing: { source_status: status('live') },
      overheat_risk: { source_status: status('cached_live') },
      crisis_risk: { source_status: status('mock') },
      smart_money: { source_status: status('fallback', '', false) },
      future_themes: [{ source_status: status('derived') }],
      missing_data: ['source_date'],
      limitations: ['Some components still use mock data.'],
    } as unknown as DailyReport;

    const html = renderToStaticMarkup(<DailyDataCoverageSummary report={report} />);

    expect(html).toContain('Data Coverage');
    expect(html).toContain('Live');
    expect(html).toContain('Cached live');
    expect(html).toContain('Derived live');
    expect(html).toContain('Fallback');
    expect(html).toContain('Mock');
    expect(html).toContain('Missing source date');
    expect(html).toContain('Some components still use mock data.');
    expect(html).not.toContain('Live / derived');
    expect(html).not.toContain('[object Object]');
  });

  it('renders today research actions as the daily starting point', () => {
    const html = renderToStaticMarkup(
      <DailyResearchActions
        actions={[
          {
            priority: 'high',
            ticker: 'NVDA',
            action_type: 'coverage_gap',
            title: 'Resolve evidence gap',
            reason: 'C1 moat evidence is the highest-value research action.',
            source: 'existing_data',
            affects_score: false,
            not_investment_advice: true,
          },
        ]}
      />,
    );

    expect(html).toContain('5-minute workflow');
    expect(html).toContain('Today research actions');
    expect(html).toContain('NVDA: Resolve evidence gap');
    expect(html).toContain('C1 moat evidence');
    expect(html).not.toContain('[object Object]');
  });
});
