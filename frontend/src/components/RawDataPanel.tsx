type Props = {
  title?: string;
  rawData?: unknown;
  derivedMetrics?: unknown;
  benchmark?: unknown;
  trend?: unknown;
  limitations?: string[];
  missingData?: string[];
};

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="jsonBlock">{JSON.stringify(value ?? {}, null, 2)}</pre>;
}

export default function RawDataPanel({ title = 'Raw evidence', rawData, derivedMetrics, benchmark, trend, limitations, missingData }: Props) {
  return (
    <details className="rawPanel">
      <summary>{title}</summary>
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
          <ul>{limitations.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      )}
      {!!missingData?.length && (
        <div>
          <h4>Missing data</h4>
          <ul>{missingData.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      )}
    </details>
  );
}
