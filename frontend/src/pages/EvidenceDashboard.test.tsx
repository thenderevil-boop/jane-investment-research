import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import EvidenceDashboard from './EvidenceDashboard';

describe('EvidenceDashboard', () => {
  it('renders dashboard sections and filters without object leaks', () => {
    const html = renderToStaticMarkup(<EvidenceDashboard />);
    expect(html).toContain('Manual Evidence Dashboard');
    expect(html).toContain('Filters');
    expect(html).toContain('Ticker Summaries');
    expect(html).toContain('Review Queue');
    expect(html).toContain('Stale Queue');
    expect(html).toContain('Peer Company Index');
    expect(html).toContain('Local Backup Export');
    expect(html).toContain('Export Local Backup JSON');
    expect(html).toContain('Backup contains local user-provided evidence and workspace metadata. It does not verify claims.');
    expect(html).toContain('Stale only');
    expect(html).toContain('Comparison context');
    expect(html).not.toContain('[object Object]');
  });
});
