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

  it('exposes FRED and derived FRED providers in the title', () => {
    const fred = renderToStaticMarkup(<DataSourceBadge status={{ ...baseStatus, provider: 'FRED', freshness_window: 'daily_rate_5_business_days' }} />);
    const derived = renderToStaticMarkup(<DataSourceBadge status={{ ...baseStatus, source_type: 'derived', provider: 'derived_from_FRED', freshness_window: 'derived_from_FRED' }} />);
    expect(fred).toContain('Live FRED');
    expect(fred).toContain('daily_rate_5_business_days');
    expect(derived).toContain('Derived FRED');
    expect(derived).toContain('derived_from_FRED');
  });
});
