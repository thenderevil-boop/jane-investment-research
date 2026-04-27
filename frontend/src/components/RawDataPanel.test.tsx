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
});
