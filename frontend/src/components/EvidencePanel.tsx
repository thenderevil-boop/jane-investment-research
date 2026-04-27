type Props = {
  evidenceSummary?: string;
  source?: string[];
  sourceDate?: string;
  confidence?: number;
  limitations?: string[];
};

export default function EvidencePanel({ evidenceSummary, source, sourceDate, confidence, limitations }: Props) {
  return (
    <section className="evidencePanel">
      {evidenceSummary && <p>{evidenceSummary}</p>}
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
