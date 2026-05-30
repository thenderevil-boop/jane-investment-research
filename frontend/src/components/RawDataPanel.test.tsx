import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import RawDataPanel from './RawDataPanel';

describe('RawDataPanel', () => {
  it('renders raw data, benchmark, trend, limitations, and missing data', () => {
    const html = renderToStaticMarkup(
      <RawDataPanel
        rawData={{ value: 1 }}
        benchmark={{ threshold: 2 }}
        trend={{ direction: 'stable' }}
        limitations={['mock limitation']}
        missingData={['live source']}
      />,
    );
    expect(html).toContain('Raw data');
    expect(html).toContain('threshold');
    expect(html).toContain('stable');
    expect(html).toContain('mock limitation');
    expect(html).toContain('live source');
  });

  it('displays source_status if present', () => {
    const html = renderToStaticMarkup(
      <RawDataPanel
        sourceStatus={{
          source_type: 'fallback',
          provider: 'mock',
          source_date: '2026-04-24',
          fetched_at: null,
          is_fresh: false,
          freshness_window: 'latest_expected_trading_day',
          fallback_used: true,
          fallback_reason: 'network unavailable',
          limitations: [],
          missing_data: ['live market price data'],
        }}
      />,
    );
    expect(html).toContain('Fallback');
    expect(html).toContain('mock');
    expect(html).toContain('network unavailable');
  });

  it('sanitizes legacy Jane terms from raw user-visible output', () => {
    const html = renderToStaticMarkup(
      <RawDataPanel
        rawData={{ jane_company_quality: 'Jane Company Quality', summary: 'Jane criterion 1 coverage is partial.' }}
        limitations={['Jane qualitative criteria remain preliminary.']}
        missingData={['Update missing Jane evidence']}
        sourceStatus={{
          source_type: 'derived',
          provider: 'jane_company_quality',
          source_date: 'summary',
          fetched_at: null,
          is_fresh: true,
          freshness_window: 'summary',
          fallback_used: false,
          fallback_reason: 'Jane reference condition unavailable',
          limitations: [],
          missing_data: [],
        }}
      />,
    );
    expect(html).toContain('company_quality');
    expect(html).toContain('Company Quality');
    expect(html).toContain('research criterion 1 coverage is partial');
    expect(html).not.toContain('Jane');
    expect(html).not.toContain('jane');
  });
});
