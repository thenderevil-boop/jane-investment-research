import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import DataQualitySummary from './DataQualitySummary';

describe('DataQualitySummary', () => {
  it('renders mixed mode', () => {
    const html = renderToStaticMarkup(
      <DataQualitySummary
        latestSourceDate="2026-04-24"
        summary={{
          mode: 'mixed',
          live_components: 4,
          mock_components: 8,
          fallback_components: 1,
          stale_components: 2,
          missing_source_date_components: 0,
          limitations: [],
        }}
      />,
    );
    expect(html).toContain('Mixed');
    expect(html).toContain('Some components still use mock or fallback data');
    expect(html).toContain('2026-04-24');
  });

  it('renders macro freshness limitations when present', () => {
    const html = renderToStaticMarkup(
      <DataQualitySummary
        latestSourceDate="2026-04-24"
        summary={{
          mode: 'mixed',
          live_components: 6,
          mock_components: 4,
          fallback_components: 0,
          stale_components: 0,
          missing_source_date_components: 0,
          limitations: ['FRED daily_rate_5_business_days monthly_macro_latest_observation derived_from_FRED'],
        }}
      />,
    );
    expect(html).toContain('FRED');
    expect(html).toContain('monthly_macro_latest_observation');
    expect(html).toContain('daily_rate_5_business_days');
  });
});
