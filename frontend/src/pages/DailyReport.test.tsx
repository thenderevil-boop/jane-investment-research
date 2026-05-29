import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { DailyReport, DataSourceStatus } from '../types';
import { DailyCommandCenter, DailyDataCoverageSummary, DailyDeltaSummary, DailyResearchActions, OverheatSourceBacking } from './DailyReport';

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

  it('renders Daily Command Center with routeable top actions and source alerts', () => {
    const report = {
      date: '2026-05-29',
      market: 'US',
      command_center: {
        version: 'phase65_daily_command_center_v1',
        headline: 'Start with source-health review, then validate NVDA evidence gaps.',
        workflow_focus: 'source_health_first',
        top_actions: [
          {
            priority: 'high',
            ticker: 'NVDA',
            action_type: 'coverage_gap',
            title: 'Resolve NVDA evidence gap',
            reason: 'Evidence gap is the highest-value research action.',
            route_hint: 'stock_research',
            source: 'existing_data',
            affects_score: false,
            not_investment_advice: true,
          },
        ],
        source_health_alerts: [
          {
            severity: 'high',
            title: 'Review fallback data sources',
            reason: 'One or more sources need setup before interpretation.',
            route_hint: 'operations',
            not_investment_advice: true,
          },
        ],
        watchlist_focus: [
          {
            ticker: 'NVDA',
            summary: 'Overheat changed versus previous snapshot.',
            route_hint: 'stock_research',
            not_investment_advice: true,
          },
        ],
        macro_snapshot: {
          summary: 'Macro context changed versus previous snapshot.',
          route_hint: 'daily_report',
          not_investment_advice: true,
        },
        affects_score: false,
        final_score_unchanged: true,
        not_investment_advice: true,
      },
    } as DailyReport;

    const html = renderToStaticMarkup(<DailyCommandCenter report={report} />);

    expect(html).toContain('Daily Command Center');
    expect(html).toContain('Start with source-health review');
    expect(html).toContain('Route: operations');
    expect(html).toContain('Route: stock_research');
    expect(html).toContain('Non-scoring workflow summary');
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

  it('renders macro and watchlist deltas compactly', () => {
    const report = {
      date: '2026-05-26',
      market: 'US',
      macro_delta: {
        version: 'phase61_macro_delta_v1',
        previous_report_date: '2026-05-25',
        macro_score_change: 4,
        vix_change: -1.5,
        yield_curve_10y2y_spread_change_bps: 6,
        latest_inflation_observations: [],
        source: 'daily_report_snapshot_compare',
        limitations: [],
        not_investment_advice: true,
      },
      watchlist_delta: {
        version: 'phase61_watchlist_delta_v1',
        previous_report_date: '2026-05-25',
        items: [
          {
            ticker: 'NVDA',
            price_change_pct: null,
            overheat_score_change: 3,
            new_form4_count: null,
            institutional_13f_status: 'cached_live',
            data_issue: 'source_date',
            source: 'daily_report_snapshot_compare',
            not_investment_advice: true,
          },
        ],
        limitations: [],
        not_investment_advice: true,
      },
    } as DailyReport;

    const html = renderToStaticMarkup(<DailyDeltaSummary report={report} />);

    expect(html).toContain('Daily efficiency');
    expect(html).toContain('Delta summary');
    expect(html).toContain('+4');
    expect(html).toContain('-1.5');
    expect(html).toContain('NVDA');
    expect(html).toContain('cached_live');
    expect(html).toContain('source_date');
    expect(html).not.toContain('[object Object]');
  });

  it('renders overheat source backing without changing the score', () => {
    const html = renderToStaticMarkup(
      <OverheatSourceBacking
        score={{
          score: 55,
          label: 'elevated_heat',
          derived_metrics: {
            source_backing: {
              live_backed_weight: 0.5,
              mock_or_fallback_weight: 0.5,
              components: [],
            },
          },
        }}
      />,
    );

    expect(html).toContain('Overheat transparency');
    expect(html).toContain('Live-backed weight disclosure');
    expect(html).toContain('Mock/fallback weight');
    expect(html).toContain('0.5');
  });
});
