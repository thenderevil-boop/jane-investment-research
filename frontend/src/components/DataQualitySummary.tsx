import type { DataQualitySummary as Summary } from '../types';
import DataSourceBadge from './DataSourceBadge';

type Props = {
  summary?: Summary | null;
  latestSourceDate?: string;
};

function modeLabel(mode?: Summary['mode']) {
  if (mode === 'mostly_live') return 'Live';
  if (mode === 'live_with_fallback') return 'Fallback';
  if (mode === 'mixed') return 'Mixed';
  return 'Mock';
}

export default function DataQualitySummary({ summary, latestSourceDate }: Props) {
  if (!summary) return null;
  const warning =
    summary.mock_components > 0 || summary.fallback_components > 0
      ? 'Some components still use mock or fallback data. Review source details before interpreting scores.'
      : '';
  return (
    <section className="dataQualitySummary" aria-label="Data quality summary">
      <div className="summaryMain">
        <span className="muted">Data mode</span>
        <strong>{modeLabel(summary.mode)}</strong>
        <DataSourceBadge
          status={{
            source_type: summary.mode === 'mostly_live' ? 'live' : summary.mode === 'live_with_fallback' ? 'fallback' : summary.mode === 'mixed' ? 'derived' : 'mock',
            provider: 'summary',
            source_date: latestSourceDate ?? '',
            fetched_at: null,
            is_fresh: summary.stale_components === 0,
            freshness_window: 'component_summary',
            fallback_used: summary.fallback_components > 0,
            fallback_reason: null,
            limitations: summary.limitations,
            missing_data: latestSourceDate ? [] : ['source_date'],
          }}
        />
      </div>
      <dl className="qualityMetrics">
        <div><dt>Live</dt><dd>{summary.live_components}</dd></div>
        <div><dt>Mock</dt><dd>{summary.mock_components}</dd></div>
        <div><dt>Fallback</dt><dd>{summary.fallback_components}</dd></div>
        <div><dt>Stale</dt><dd>{summary.stale_components}</dd></div>
        <div><dt>Missing date</dt><dd>{summary.missing_source_date_components ?? 0}</dd></div>
        <div><dt>Latest source date</dt><dd>{latestSourceDate || 'N/A'}</dd></div>
      </dl>
      {warning && <p className="sourceWarning">{warning}</p>}
    </section>
  );
}
