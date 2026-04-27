import type { DataSourceStatus } from '../types';
import DataSourceBadge from './DataSourceBadge';

type Props = {
  evidenceSummary?: string;
  source?: string[];
  sourceDate?: string;
  confidence?: number;
  limitations?: string[];
  sourceStatus?: DataSourceStatus | null;
};

export default function EvidencePanel({ evidenceSummary, source, sourceDate, confidence, limitations, sourceStatus }: Props) {
  return (
    <section className="evidencePanel">
      {evidenceSummary && <p>{evidenceSummary}</p>}
      <DataSourceBadge status={sourceStatus} />
      <dl className="metaGrid">
        <div>
          <dt>Source</dt>
          <dd>{source?.length ? source.join(', ') : 'mock source'}</dd>
        </div>
        <div>
          <dt>Source date</dt>
          <dd>{sourceDate || 'N/A'}</dd>
        </div>
        <div>
          <dt>Freshness</dt>
          <dd>{sourceStatus ? (sourceStatus.is_fresh ? (sourceStatus.source_type === 'mock' ? 'Mock reference' : 'Fresh') : 'Stale') : 'N/A'}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{typeof confidence === 'number' ? `${(confidence * 100).toFixed(0)}%` : 'N/A'}</dd>
        </div>
      </dl>
      {!!limitations?.length && (
        <ul className="compactList">{limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      )}
    </section>
  );
}
