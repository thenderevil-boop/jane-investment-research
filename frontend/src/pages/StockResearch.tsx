import { FormEvent, useMemo, useState } from 'react';
import { analyzeStock } from '../api/client';
import EvidencePanel from '../components/EvidencePanel';
import RawDataPanel from '../components/RawDataPanel';
import ScoreCard from '../components/ScoreCard';
import SignalBadge from '../components/SignalBadge';
import WarningBanner from '../components/WarningBanner';
import type { ScoreLike, StockAnalysis } from '../types';
import { detectForbiddenLanguage } from '../utils/forbiddenLanguage';

function scoreMax(score?: ScoreLike) {
  return score?.max_score ?? score?.maxScore ?? 100;
}

function ScoreBlock({ title, score }: { title: string; score?: ScoreLike }) {
  if (!score) return null;
  return (
    <div className="evidenceGroup">
      <ScoreCard title={title} score={score.score} maxScore={scoreMax(score)} label={score.label} confidence={score.confidence} />
      <EvidencePanel source={score.source} sourceDate={score.source_date} confidence={score.confidence} limitations={score.limitations} />
      <RawDataPanel rawData={score.raw_data} derivedMetrics={score.derived_metrics} benchmark={score.benchmark} trend={score.trend} limitations={score.limitations} missingData={score.missing_data} />
    </div>
  );
}

export default function StockResearch() {
  const [ticker, setTicker] = useState('NVDA');
  const [result, setResult] = useState<StockAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const warningTerms = useMemo(() => detectForbiddenLanguage(result), [result]);
  const criteria = result?.leadership_score?.criteria as Array<Record<string, unknown>> | undefined;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      setResult(await analyzeStock(ticker));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to analyze ticker');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <WarningBanner terms={warningTerms} />
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Stock Research</p>
          <h1>US Ticker Research</h1>
          <p>Research reference only. Not investment advice.</p>
        </div>
      </header>

      <form className="tickerForm" onSubmit={onSubmit}>
        <label htmlFor="ticker">Ticker</label>
        <input id="ticker" value={ticker} onChange={(event) => setTicker(event.target.value)} maxLength={10} />
        <button type="submit" disabled={loading}>{loading ? 'Analyzing...' : 'Run research'}</button>
      </form>

      {error && <p className="errorText">{error}</p>}

      {result && (
        <>
          <section className="pageSection">
            <h2>{result.ticker} Overview</h2>
            <div className="profileGrid">
              {Object.entries(result.company_profile ?? {}).map(([key, value]) => (
                <div key={key}><strong>{key}</strong><span>{Array.isArray(value) ? value.join(', ') : String(value)}</span></div>
              ))}
            </div>
          </section>

          <section className="pageSection">
            <h2>Research Scores</h2>
            <div className="scoreGrid">
              <ScoreBlock title="Leadership" score={result.leadership_score} />
              <ScoreBlock title="Smart money" score={result.smart_money} />
              <ScoreBlock title="Market sentiment" score={result.market_timing_context} />
              <ScoreBlock title="Overheat risk" score={result.overheat_risk} />
              <ScoreBlock title="Financial quality" score={result.financial_quality} />
              <ScoreBlock title="Valuation context" score={result.valuation_context} />
            </div>
          </section>

          {!!criteria?.length && (
            <section className="pageSection">
              <h2>20 Criteria Table</h2>
              <div className="tableWrap">
                <table>
                  <thead><tr><th>ID</th><th>Criterion</th><th>Score</th><th>Confidence</th><th>Evidence</th><th>Missing data</th></tr></thead>
                  <tbody>
                    {criteria.map((criterion) => (
                      <tr key={String(criterion.criterion_id)}>
                        <td>{String(criterion.criterion_id)}</td>
                        <td>{String(criterion.criterion_name)}</td>
                        <td>{String(criterion.score)}</td>
                        <td>{typeof criterion.confidence === 'number' ? `${(criterion.confidence * 100).toFixed(0)}%` : 'N/A'}</td>
                        <td>{String(criterion.evidence_summary ?? '')}</td>
                        <td>{Array.isArray(criterion.missing_data) ? criterion.missing_data.join(', ') : 'None listed'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section className="pageSection">
            <h2>Risk Flags / Missing Data</h2>
            <div className="twoColumn">
              <div>
                <h3>Risk flags</h3>
                {result.risk_flags?.map((flag) => <SignalBadge key={flag} label={flag} variant="warning" />)}
              </div>
              <div>
                <h3>Missing data</h3>
                <ul>{result.missing_data?.map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
