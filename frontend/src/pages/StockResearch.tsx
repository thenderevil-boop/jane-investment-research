import { FormEvent, useMemo, useState } from 'react';
import { analyzeStock } from '../api/client';
import DataSourceBadge from '../components/DataSourceBadge';
import EvidencePanel from '../components/EvidencePanel';
import JaneReferencePanel from '../components/JaneReferencePanel';
import RawDataPanel from '../components/RawDataPanel';
import ScoreCard from '../components/ScoreCard';
import SignalBadge from '../components/SignalBadge';
import WarningBanner from '../components/WarningBanner';
import type { AnalyzeStockDataQualitySummary, DataSourceStatus, EvidenceMatrixItem, FinancialStatementSignals, JaneCompanyQuality, NextManualCheck, ScoreDriver, ScoreLike, StockAnalysis } from '../types';
import { detectForbiddenLanguage } from '../utils/forbiddenLanguage';

function scoreMax(score?: ScoreLike) {
  return score?.max_score ?? score?.maxScore ?? 100;
}

function displayKey(value: string) {
  return value.replace(/_/g, ' ');
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return 'N/A';
  if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function resolveScoreSourceStatus(score?: ScoreLike): DataSourceStatus | null {
  if (!score) return null;
  if (score.source_status) return score.source_status;
  const rawStatus = score.raw_data?.source_status;
  if (rawStatus && typeof rawStatus === 'object') return rawStatus as DataSourceStatus;
  const nestedStatus = score.raw_data?.institutional_13f;
  if (nestedStatus && typeof nestedStatus === 'object' && 'source_status' in nestedStatus) {
    return (nestedStatus as { source_status?: DataSourceStatus }).source_status ?? null;
  }
  return null;
}

export function ProfileGrid({ profile }: { profile?: Record<string, unknown> }) {
  if (!profile) return null;
  const researchContext = profile.research_context as { theme?: unknown; user_reason?: unknown } | undefined;
  const sourceStatus = profile.source_status as DataSourceStatus | undefined;
  const entries = Object.entries(profile).filter(([key]) => key !== 'research_context' && key !== 'source_status');
  return (
    <div className="profileGrid">
      {entries.map(([key, value]) => (
        <div key={key}><strong>{key}</strong><span>{Array.isArray(value) ? value.join(', ') : String(value)}</span></div>
      ))}
      {researchContext && (
        <>
          <div><strong>research_context.theme</strong><span>{String(researchContext.theme ?? '')}</span></div>
          <div><strong>research_context.user_reason</strong><span>{String(researchContext.user_reason ?? '')}</span></div>
        </>
      )}
      {sourceStatus && (
        <>
          <div><strong>source_status.source_type</strong><span>{sourceStatus.source_type}</span></div>
          <div><strong>source_status.provider</strong><span>{sourceStatus.provider}</span></div>
          <div><strong>source_status.source_date</strong><span>{sourceStatus.source_date}</span></div>
        </>
      )}
    </div>
  );
}

export function ScoreBlock({ title, score, showRaw = true }: { title: string; score?: ScoreLike; showRaw?: boolean }) {
  if (!score) return null;
  const sourceStatus = resolveScoreSourceStatus(score);
  const isMockLeadership = title === 'Leadership' && sourceStatus?.source_type === 'mock';
  return (
    <div className="evidenceGroup">
      <ScoreCard title={title} score={score.score} maxScore={scoreMax(score)} label={score.label} confidence={score.confidence} />
      {isMockLeadership && (
        <p className="sourceWarning">Leadership score is mock-based preliminary evidence and should not be treated as live validation.</p>
      )}
      <EvidencePanel source={score.source} sourceDate={score.source_date} confidence={score.confidence} limitations={score.limitations} sourceStatus={sourceStatus} />
      {showRaw && <RawDataPanel rawData={score.raw_data} derivedMetrics={score.derived_metrics} benchmark={score.benchmark} trend={score.trend} limitations={score.limitations} missingData={score.missing_data} />}
    </div>
  );
}

function sourceQualityStatus(sourceQuality: EvidenceMatrixItem['source_quality']): DataSourceStatus {
  const sourceTypeByQuality: Record<EvidenceMatrixItem['source_quality'], DataSourceStatus['source_type']> = {
    live_backed: 'live',
    derived_live: 'derived',
    cached_live: 'cached_live',
    mixed_with_fallback: 'fallback',
    user_context: 'unknown',
    mock_only: 'mock',
    insufficient: 'unknown',
  };
  return {
    source_type: sourceTypeByQuality[sourceQuality],
    provider: sourceQuality,
    source_date: 'summary',
    fetched_at: null,
    is_fresh: sourceQuality !== 'insufficient',
    freshness_window: 'analyze_stock_summary',
    fallback_used: sourceQuality === 'mixed_with_fallback',
    fallback_reason: null,
    limitations: [],
    missing_data: [],
  };
}

export function CandidateSummarySection({ result }: { result: StockAnalysis }) {
  const summary = result.candidate_validation_summary;
  if (!summary) return null;
  return (
    <section className="pageSection">
      <h2>Candidate Validation Summary</h2>
      <div className="verdictBand">
        <SignalBadge label={summary.research_priority} variant={summary.research_priority === 'high_risk_context' ? 'warning' : 'positive'} />
        <strong>{summary.score.toFixed(0)} / 100</strong>
        <span>{summary.overall_summary}</span>
      </div>
      <div className="summaryGrid">
        <div><strong>Environment</strong><span>{summary.environment_assessment}</span></div>
        <div><strong>Company</strong><span>{summary.company_assessment}</span></div>
        <div><strong>Smart money</strong><span>{summary.smart_money_assessment}</span></div>
        <div><strong>Data quality</strong><span>{summary.data_quality_assessment}</span></div>
      </div>
      <div className="twoColumn">
        <div>
          <h3>Primary strengths</h3>
          <ul>{summary.primary_strengths.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
        <div>
          <h3>Primary risks</h3>
          <ul>{summary.primary_risks.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>
      {!!summary.missing_or_mock_evidence.length && (
        <p className="sourceWarning">Missing or mock evidence: {summary.missing_or_mock_evidence.join(', ')}</p>
      )}
    </section>
  );
}

export function AnalyzeDataQualitySection({ dataQuality }: { dataQuality?: AnalyzeStockDataQualitySummary }) {
  if (!dataQuality) return null;
  return (
    <section className="pageSection">
      <h2>Data Quality Summary</h2>
      <div className="summaryMain">
        <span className="smallPill">Grade {dataQuality.source_quality_grade}</span>
        <span className="smallPill">{dataQuality.mode}</span>
        {dataQuality.confidence_cap_applied && <span className="smallPill">Confidence capped</span>}
      </div>
      <p>{dataQuality.source_quality_summary}</p>
      {dataQuality.confidence_cap_reason && <p className="sourceWarning">{dataQuality.confidence_cap_reason}</p>}
      <dl className="qualityMetrics">
        <div><dt>Live/derived</dt><dd>{dataQuality.live_components}</dd></div>
        <div><dt>Mock</dt><dd>{dataQuality.mock_components}</dd></div>
        <div><dt>Fallback</dt><dd>{dataQuality.fallback_components}</dd></div>
        <div><dt>Missing dates</dt><dd>{dataQuality.missing_source_date_components}</dd></div>
        <div><dt>Stale</dt><dd>{dataQuality.stale_components}</dd></div>
      </dl>
      <div className="twoColumn">
        <div>
          <h3>Mock evidence</h3>
          <ul>{dataQuality.mock_evidence_categories.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
        <div>
          <h3>Fallback evidence</h3>
          <ul>{dataQuality.fallback_evidence_categories.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>
      {dataQuality.company_quality && (
        <dl className="qualityMetrics">
          <div><dt>Quality backed</dt><dd>{dataQuality.company_quality.evidence_backed_criteria_count}</dd></div>
          <div><dt>Quality insufficient</dt><dd>{dataQuality.company_quality.insufficient_criteria_count}</dd></div>
          <div><dt>Quality derived</dt><dd>{dataQuality.company_quality.derived_live_criteria_count}</dd></div>
          <div><dt>User context</dt><dd>{dataQuality.company_quality.user_context_criteria_count}</dd></div>
        </dl>
      )}
      {!!dataQuality.insufficient_evidence_categories?.length && (
        <p className="sourceWarning">Insufficient company quality evidence: {dataQuality.insufficient_evidence_categories.join(', ')}</p>
      )}
      {!!dataQuality.excluded_from_scoring.length && <p className="muted">Excluded from scoring: {dataQuality.excluded_from_scoring.join(', ')}</p>}
    </section>
  );
}

export function JaneCompanyQualitySection({ quality, profile }: { quality?: JaneCompanyQuality; profile?: Record<string, unknown> }) {
  if (!quality) return null;
  const researchContext = profile?.research_context as { theme?: unknown; user_reason?: unknown } | undefined;
  return (
    <section className="pageSection">
      <h2>Jane Company Quality</h2>
      <div className="summaryMain">
        <span className="smallPill">{quality.label}</span>
        <strong>{quality.score.toFixed(0)} / {quality.max_score}</strong>
        <span>Confidence {(quality.confidence * 100).toFixed(0)}%</span>
        <DataSourceBadge status={quality.source_status} />
      </div>
      {Boolean(researchContext?.theme) && <p className="muted">User theme context: {String(researchContext?.theme)}. This is context, not verified evidence.</p>}
      <div className="tableWrap">
        <table>
          <thead><tr><th>Criterion</th><th>Status</th><th>Score</th><th>Source quality</th><th>Missing data</th></tr></thead>
          <tbody>
            {quality.criteria.map((criterion) => (
              <tr key={criterion.name}>
                <td>{criterion.display_name}</td>
                <td><SignalBadge label={criterion.status} variant={criterion.status === 'supportive' ? 'positive' : criterion.status === 'insufficient' || criterion.status === 'caution' ? 'warning' : 'neutral'} /></td>
                <td>{criterion.score === null || criterion.score === undefined ? 'N/A' : `${criterion.score.toFixed(0)} / ${criterion.max_score}`}</td>
                <td>{criterion.source_quality}</td>
                <td>{criterion.missing_data.length ? criterion.missing_data.join(', ') : 'None listed'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!!quality.limitations.length && <p className="muted">Limitations: {quality.limitations.join(' ')}</p>}
    </section>
  );
}

export function FinancialStatementSignalsSection({ signals }: { signals?: FinancialStatementSignals }) {
  if (!signals) return null;
  return (
    <section className="pageSection">
      <h2>Financial Statement Signals</h2>
      <div className="summaryMain">
        <span className="smallPill">{signals.label}</span>
        <strong>{signals.score.toFixed(0)} / 100</strong>
        <span>Confidence {(signals.confidence * 100).toFixed(0)}%</span>
        <DataSourceBadge status={signals.source_status} />
      </div>
      <div className="tableWrap">
        <table>
          <thead><tr><th>Signal</th><th>Status</th><th>Source quality</th><th>Evidence</th><th>Missing data</th></tr></thead>
          <tbody>
            {signals.signals.map((signal) => (
              <tr key={signal.name}>
                <td>{displayKey(signal.name)}</td>
                <td><SignalBadge label={signal.status} variant={signal.status === 'supportive' ? 'positive' : signal.status === 'insufficient' || signal.status === 'caution' ? 'warning' : 'neutral'} /></td>
                <td>{signal.source_quality}</td>
                <td>{signal.evidence.length ? signal.evidence.join(', ') : 'N/A'}</td>
                <td>{signal.missing_data.length ? signal.missing_data.join(', ') : 'None listed'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!!signals.limitations.length && <p className="muted">Limitations: {signals.limitations.join(' ')}</p>}
    </section>
  );
}

export function CompanyFundamentalsSection({ result }: { result: StockAnalysis }) {
  const profile = result.company_profile ?? {};
  const financial = result.financial_quality;
  const valuation = result.valuation_context;
  const financialRaw = financial?.raw_data ?? {};
  const valuationRaw = valuation?.raw_data ?? {};
  const profileStatus = profile.source_status as DataSourceStatus | undefined;
  const financialStatus = resolveScoreSourceStatus(financial);
  if (!financial && !valuation) return null;
  return (
    <section className="pageSection">
      <h2>Company Fundamentals</h2>
      <div className="summaryMain">
        {profileStatus && <DataSourceBadge status={profileStatus} />}
        {financialStatus && <DataSourceBadge status={financialStatus} />}
        {valuation?.source_status && <DataSourceBadge status={valuation.source_status} />}
      </div>
      <div className="fundamentalsGrid">
        <div><strong>Revenue growth</strong><span>{displayValue(financialRaw.revenue_yoy_growth_pct)}%</span></div>
        <div><strong>Gross margin</strong><span>{displayValue(financialRaw.gross_margin_pct)}%</span></div>
        <div><strong>Free cash flow</strong><span>{displayValue(financialRaw.free_cash_flow_ttm)}</span></div>
        <div><strong>Cash/debt</strong><span>{displayValue(financialRaw.cash_and_equivalents)} / {displayValue(financialRaw.total_debt)}</span></div>
        <div><strong>Market cap</strong><span>{displayValue(profile.market_cap ?? valuationRaw.market_cap)}</span></div>
        <div><strong>Enterprise value</strong><span>{displayValue(profile.enterprise_value ?? valuationRaw.enterprise_value)}</span></div>
        <div><strong>Price/sales TTM</strong><span>{displayValue(valuationRaw.price_to_sales_ttm)}</span></div>
        <div><strong>EV/sales TTM</strong><span>{displayValue(valuationRaw.ev_to_sales_ttm)}</span></div>
      </div>
      {typeof valuationRaw.valuation_summary === 'string' && valuationRaw.valuation_summary && <p>{valuationRaw.valuation_summary}</p>}
      {!!financial?.missing_data?.length && <p className="sourceWarning">Missing fundamentals: {financial.missing_data.join(', ')}</p>}
      {!!valuation?.missing_data?.length && <p className="muted">Valuation missing data: {valuation.missing_data.join(', ')}</p>}
    </section>
  );
}

export function EvidenceMatrixSection({ rows }: { rows?: EvidenceMatrixItem[] }) {
  if (!rows?.length) return null;
  return (
    <section className="pageSection">
      <h2>Evidence Matrix</h2>
      <div className="evidenceMatrix">
        {rows.map((row) => (
          <article className="evidenceRow" key={row.category}>
            <div className="evidenceRowHeader">
              <h3>{displayKey(row.category)}</h3>
              <div>
                <SignalBadge label={row.status} variant={row.status === 'caution' || row.status === 'insufficient' ? 'warning' : 'neutral'} />
                <DataSourceBadge status={sourceQualityStatus(row.source_quality)} />
                <span className="smallPill">{row.source_quality}</span>
              </div>
            </div>
            <p>{row.summary}</p>
            {(row.source_quality === 'mock_only' || row.source_quality === 'mixed_with_fallback') && (
              <p className="sourceWarning">{row.source_quality === 'mock_only' ? 'Mock-only evidence; treat as preliminary.' : 'Fallback or mixed source quality; manual confirmation required.'}</p>
            )}
            <ul>{row.key_evidence.map((item) => <li key={item}>{item}</li>)}</ul>
            {!!row.limitations.length && <p className="muted">Limitations: {row.limitations.join(' ')}</p>}
          </article>
        ))}
      </div>
    </section>
  );
}

function DriverList({ title, drivers }: { title: string; drivers?: ScoreDriver[] }) {
  if (!drivers?.length) return null;
  return (
    <div>
      <h3>{title}</h3>
      <ul>{drivers.map((driver) => <li key={`${driver.category}-${driver.name}`}><strong>{driver.category}</strong>: {driver.summary}</li>)}</ul>
    </div>
  );
}

export function ScoreDriverSection({ result }: { result: StockAnalysis }) {
  const breakdown = result.score_driver_breakdown;
  if (!breakdown) return null;
  return (
    <section className="pageSection">
      <h2>Score Driver Breakdown</h2>
      <div className="verdictBand">
        <strong>{breakdown.final_score.toFixed(0)} / 100</strong>
        <span>Confidence {(breakdown.final_confidence * 100).toFixed(0)}%</span>
      </div>
      <div className="twoColumn">
        <DriverList title="Positive drivers" drivers={breakdown.positive_drivers} />
        <DriverList title="Limiting drivers" drivers={breakdown.negative_or_limiting_drivers} />
        <DriverList title="Neutral drivers" drivers={breakdown.neutral_drivers} />
      </div>
    </section>
  );
}

export function ManualChecksSection({ checks }: { checks?: NextManualCheck[] }) {
  if (!checks?.length) return null;
  return (
    <section className="pageSection">
      <h2>Next Manual Checks</h2>
      <ul className="checkList">
        {checks.map((item) => (
          <li key={`${item.area}-${item.check}`}>
            <span className={`checkPriority ${item.priority}`}>{item.priority}</span>
            <div><strong>{displayKey(item.area)}</strong><span>{item.check}</span><small>{item.reason}</small></div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function StockResearch() {
  const [ticker, setTicker] = useState('NVDA');
  const [theme, setTheme] = useState('AI infrastructure');
  const [userReason, setUserReason] = useState('External trend research');
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
      setResult(await analyzeStock(ticker, { theme, user_reason: userReason }));
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
        <label htmlFor="theme">Theme</label>
        <input id="theme" value={theme} onChange={(event) => setTheme(event.target.value)} />
        <label htmlFor="reason">Reason</label>
        <input id="reason" value={userReason} onChange={(event) => setUserReason(event.target.value)} />
        <button type="submit" disabled={loading}>{loading ? 'Analyzing...' : 'Run research'}</button>
      </form>

      {error && <p className="errorText">{error}</p>}

      {result && (
        <>
          <CandidateSummarySection result={result} />
          <AnalyzeDataQualitySection dataQuality={result.data_quality_summary} />
          <JaneCompanyQualitySection quality={result.jane_company_quality} profile={result.company_profile} />
          <FinancialStatementSignalsSection signals={result.financial_statement_signals} />
          <CompanyFundamentalsSection result={result} />
          <EvidenceMatrixSection rows={result.evidence_matrix} />
          <ScoreDriverSection result={result} />
          <ManualChecksSection checks={result.next_manual_checks} />

          <section className="pageSection">
            <h2>{result.ticker} Overview</h2>
            {result.research_verdict && (
              <div className="verdictBand">
                <SignalBadge label={result.research_verdict.label} variant={result.research_verdict.label === 'high_risk_context' ? 'warning' : 'positive'} />
                <strong>{result.research_verdict.score.toFixed(0)} / 100</strong>
                <span>{result.research_verdict.summary}</span>
              </div>
            )}
            <ProfileGrid profile={result.company_profile} />
          </section>

          <section className="pageSection">
            <h2>Research Scores</h2>
            <div className="scoreGrid">
              <ScoreBlock title="Leadership" score={result.leadership_score} showRaw={false} />
              <ScoreBlock title="Macro regime" score={result.macro_regime} showRaw={false} />
              <ScoreBlock title="Smart money" score={result.smart_money} showRaw={false} />
              <ScoreBlock title="Insider Form 4" score={result.insider_activity} showRaw={false} />
              <ScoreBlock title="Institutional 13F" score={result.institutional_13f} showRaw={false} />
              <ScoreBlock title="Market sentiment" score={result.market_timing_context} showRaw={false} />
              <ScoreBlock title="Overheat risk" score={result.overheat_risk} showRaw={false} />
              <ScoreBlock title="Financial quality" score={result.financial_quality} showRaw={false} />
              <ScoreBlock title="Valuation context" score={result.valuation_context} showRaw={false} />
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

          {result.jane_reference_conditions && (
            <section className="pageSection">
              <JaneReferencePanel reference={result.jane_reference_conditions} />
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

          <section className="pageSection">
            <h2>Raw Evidence Panels</h2>
            <RawDataPanel title="Macro raw evidence" rawData={result.macro_regime?.raw_data} derivedMetrics={result.macro_regime?.derived_metrics} benchmark={result.macro_regime?.benchmark} trend={result.macro_regime?.trend} limitations={result.macro_regime?.limitations} missingData={result.macro_regime?.missing_data} sourceStatus={resolveScoreSourceStatus(result.macro_regime)} />
            <RawDataPanel title="Leadership raw evidence" rawData={result.leadership_score?.raw_data} derivedMetrics={result.leadership_score?.derived_metrics} benchmark={result.leadership_score?.benchmark} trend={result.leadership_score?.trend} limitations={result.leadership_score?.limitations} missingData={result.leadership_score?.missing_data} sourceStatus={resolveScoreSourceStatus(result.leadership_score)} />
            <RawDataPanel title="Jane company quality raw evidence" rawData={{ criteria: result.jane_company_quality?.criteria }} derivedMetrics={{ score: result.jane_company_quality?.score, label: result.jane_company_quality?.label }} limitations={result.jane_company_quality?.limitations} missingData={result.jane_company_quality?.missing_data} sourceStatus={result.jane_company_quality?.source_status} />
            <RawDataPanel title="Financial statement signals raw evidence" rawData={{ signals: result.financial_statement_signals?.signals }} derivedMetrics={{ score: result.financial_statement_signals?.score, label: result.financial_statement_signals?.label }} limitations={result.financial_statement_signals?.limitations} missingData={result.financial_statement_signals?.missing_data} sourceStatus={result.financial_statement_signals?.source_status} />
            <RawDataPanel title="Smart money raw evidence" rawData={result.smart_money?.raw_data} derivedMetrics={result.smart_money?.derived_metrics} benchmark={result.smart_money?.benchmark} trend={result.smart_money?.trend} limitations={result.smart_money?.limitations} missingData={result.smart_money?.missing_data} sourceStatus={resolveScoreSourceStatus(result.smart_money)} />
            <RawDataPanel title="Insider Form 4 raw evidence" rawData={result.insider_activity?.raw_data} derivedMetrics={result.insider_activity?.derived_metrics} benchmark={result.insider_activity?.benchmark} trend={result.insider_activity?.trend} limitations={result.insider_activity?.limitations} missingData={result.insider_activity?.missing_data} sourceStatus={resolveScoreSourceStatus(result.insider_activity)} />
            <RawDataPanel title="Institutional 13F raw evidence" rawData={result.institutional_13f?.raw_data} derivedMetrics={result.institutional_13f?.derived_metrics} benchmark={result.institutional_13f?.benchmark} trend={result.institutional_13f?.trend} limitations={result.institutional_13f?.limitations} missingData={result.institutional_13f?.missing_data} sourceStatus={resolveScoreSourceStatus(result.institutional_13f)} />
          </section>
        </>
      )}
    </main>
  );
}
