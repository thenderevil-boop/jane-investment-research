type Props = {
  direction?: string;
  duration?: string;
  benchmarkComparison?: string;
  trend?: Record<string, unknown>;
};

export default function TrendSummary({ direction, duration, benchmarkComparison, trend }: Props) {
  const entries = trend ? Object.entries(trend) : [];
  return (
    <div className="trendSummary">
      <strong>{direction || 'Trend context'}</strong>
      {duration && <span>{duration}</span>}
      {benchmarkComparison && <span>{benchmarkComparison}</span>}
      {entries.map(([key, value]) => (
        <span key={key}>{key}: {String(value)}</span>
      ))}
    </div>
  );
}
