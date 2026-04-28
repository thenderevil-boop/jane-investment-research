import type { DataSourceStatus } from '../types';

type Props = {
  status?: DataSourceStatus | null;
};

function labelFor(status?: DataSourceStatus | null) {
  if (!status) return 'Unknown';
  if (!status.source_date) return 'Missing source date';
  if (status.fallback_used || status.source_type === 'fallback') return 'Fallback';
  if (!status.is_fresh) return status.source_type === 'mock' ? 'Mock' : 'Stale';
  if (status.source_type === 'cached_live') return 'Cached Live';
  if (status.source_type === 'live') return status.provider === 'FRED' ? 'Live FRED' : 'Live';
  if (status.source_type === 'derived') return status.provider === 'derived_from_FRED' ? 'Derived FRED' : 'Derived';
  if (status.source_type === 'mock') return 'Mock';
  return 'Unknown';
}

function variantFor(status?: DataSourceStatus | null) {
  if (!status || !status.source_date) return 'missing';
  if (status.fallback_used || status.source_type === 'fallback') return 'fallback';
  if (!status.is_fresh) return 'stale';
  return status.source_type;
}

export default function DataSourceBadge({ status }: Props) {
  const provider = status?.provider && status.provider !== 'unknown' ? ` from ${status.provider}` : '';
  const freshnessWindow = status?.freshness_window ? `; ${status.freshness_window}` : '';
  return (
    <span className={`dataSourceBadge ${variantFor(status)}`} title={`${labelFor(status)}${provider}${freshnessWindow}`}>
      {labelFor(status)}
    </span>
  );
}
