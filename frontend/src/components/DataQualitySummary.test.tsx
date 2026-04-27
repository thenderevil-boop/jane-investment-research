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
});
