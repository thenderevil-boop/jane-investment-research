import type { DataSourceStatus } from '../types';
import DataSourceBadge from './DataSourceBadge';
import { sanitizeUserFacingText, sanitizeUserFacingValue } from '../utils/userFacingCopy';

type Props = {
  title?: string;
  rawData?: unknown;
  derivedMetrics?: unknown;
  benchmark?: unknown;
  trend?: unknown;
  limitations?: string[];
  missingData?: string[];
  sourceStatus?: DataSourceStatus | null;
};

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="jsonBlock">{JSON.stringify(sanitizeUserFacingValue(value ?? {}), null, 2)}</pre>;
}

function sanitizeSourceStatus(status: DataSourceStatus): DataSourceStatus {
  return sanitizeUserFacingValue(status);
}

export default function RawDataPanel({ title = 'Raw evidence', rawData, derivedMetrics, benchmark, trend, limitations, missingData, sourceStatus }: Props) {
  const displayedSourceStatus = sourceStatus ? sanitizeSourceStatus(sourceStatus) : undefined;
  return (
    <details className="rawPanel">
      <summary>{title}</summary>
      {displayedSourceStatus && (
        <div className="sourceStatusRow">
          <DataSourceBadge status={displayedSourceStatus} />
          <span>{displayedSourceStatus.provider}</span>
          <span>{displayedSourceStatus.source_date || 'Missing source date'}</span>
          {displayedSourceStatus.fallback_reason && <span>{displayedSourceStatus.fallback_reason}</span>}
        </div>
      )}
      <div className="rawGrid">
        <div>
          <h4>Raw data</h4>
          <JsonBlock value={rawData} />
        </div>
        <div>
          <h4>Derived metrics</h4>
          <JsonBlock value={derivedMetrics} />
        </div>
        <div>
          <h4>Benchmark</h4>
          <JsonBlock value={benchmark} />
        </div>
        <div>
          <h4>Trend</h4>
          <JsonBlock value={trend} />
        </div>
      </div>
      {!!limitations?.length && (
        <div>
          <h4>Limitations</h4>
          <ul>{limitations.map((item) => <li key={item}>{sanitizeUserFacingText(item)}</li>)}</ul>
        </div>
      )}
      {!!missingData?.length && (
        <div>
          <h4>Missing data</h4>
          <ul>{missingData.map((item) => <li key={item}>{sanitizeUserFacingText(item)}</li>)}</ul>
        </div>
      )}
    </details>
  );
}
