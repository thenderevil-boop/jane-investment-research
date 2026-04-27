import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { DataSourceStatus } from '../types';
import DataSourceBadge from './DataSourceBadge';

const baseStatus: DataSourceStatus = {
  source_type: 'live',
  provider: 'yfinance',
  source_date: '2026-04-24',
  fetched_at: null,
  is_fresh: true,
  freshness_window: 'latest_expected_trading_day',
  fallback_used: false,
  fallback_reason: null,
  limitations: [],
  missing_data: [],
};

describe('DataSourceBadge', () => {
  it('renders Live', () => {
    expect(renderToStaticMarkup(<DataSourceBadge status={baseStatus} />)).toContain('Live');
  });

  it('renders Mock', () => {
    expect(renderToStaticMarkup(<DataSourceBadge status={{ ...baseStatus, source_type: 'mock', is_fresh: true }} />)).toContain('Mock');
  });

  it('renders Fallback', () => {
    expect(renderToStaticMarkup(<DataSourceBadge status={{ ...baseStatus, source_type: 'fallback', fallback_used: true }} />)).toContain('Fallback');
  });
});
