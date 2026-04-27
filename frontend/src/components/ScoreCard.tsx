import SignalBadge, { variantForLabel } from './SignalBadge';

type Props = {
  title: string;
  score?: number;
  maxScore?: number;
  label?: string;
  confidence?: number;
  description?: string;
};

export default function ScoreCard({ title, score, maxScore = 100, label = 'neutral', confidence, description }: Props) {
  const percent = typeof score === 'number' && maxScore ? Math.max(0, Math.min(100, (score / maxScore) * 100)) : 0;
  return (
    <section className="scoreCard">
      <div className="scoreCardHeader">
        <h3>{title}</h3>
        <SignalBadge label={label} variant={variantForLabel(label)} />
      </div>
      <div className="scoreRow">
        <strong>{typeof score === 'number' ? score.toFixed(score % 1 ? 1 : 0) : 'N/A'}</strong>
        <span>/ {maxScore}</span>
      </div>
      <div className="meter" aria-label={`${title} score`}>
        <span style={{ width: `${percent}%` }} />
      </div>
      {typeof confidence === 'number' && <p className="muted">Confidence {(confidence * 100).toFixed(0)}%</p>}
      {description && <p>{description}</p>}
    </section>
  );
}
