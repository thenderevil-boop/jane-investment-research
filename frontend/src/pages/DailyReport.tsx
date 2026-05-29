import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { getLatestDailyReport } from '../api/client';
import DataQualitySummary from '../components/DataQualitySummary';
import DataSourceBadge from '../components/DataSourceBadge';
import EvidencePanel from '../components/EvidencePanel';
import JaneReferencePanel from '../components/JaneReferencePanel';
import MacroScoreExplanationPanel from '../components/MacroScoreExplanationPanel';
import RawDataPanel from '../components/RawDataPanel';
import ScoreCard from '../components/ScoreCard';
import SignalBadge from '../components/SignalBadge';
import TrendSummary from '../components/TrendSummary';
import WarningBanner from '../components/WarningBanner';
import type { DailyReport, ScoreLike, TodayResearchAction } from '../types';
import { detectForbiddenLanguage } from '../utils/forbiddenLanguage';

function scoreMax(score?: ScoreLike) {
  return score?.max_score ?? score?.maxScore ?? 100;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="pageSection">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function ScoreEvidence({ title, score }: { title: string; score?: ScoreLike }) {
  if (!score) return null;
  return (
    <div className="evidenceGroup">
      <ScoreCard title={title} score={score.score} maxScore={scoreMax(score)} label={score.label} confidence={score.confidence} />
      <EvidencePanel source={score.source} sourceDate={score.source_date} confidence={score.confidence} limitations={score.limitations} sourceStatus={score.source_status} />
      <TrendSummary trend={score.trend} />
      <RawDataPanel rawData={score.raw_data} derivedMetrics={score.derived_metrics} benchmark={score.benchmark} trend={score.trend} limitations={score.limitations} missingData={score.missing_data} sourceStatus={score.source_status} />
    </div>
  );
}

function collectLimitations(report?: DailyReport): string[] {
  if (!report) return [];
  const scores = [report.macro_regime, report.market_timing, report.overheat_risk, report.crisis_risk, report.smart_money ?? report.smart_money_summary, ...(report.future_themes ?? [])];
  const scoreLimitations = scores.flatMap((score) => score?.limitations ?? []);
  return Array.from(new Set([...scoreLimitations, ...(report.crisis?.limitations ?? []), ...(report.risk_allocation?.limitations ?? []), ...(report.limitations ?? [])]));
}

function collectSourceStatuses(report: DailyReport) {
  return [
    report.macro_regime?.source_status,
    report.market_timing?.source_status,
    report.overheat_risk?.source_status,
    report.crisis_risk?.source_status,
    (report.smart_money ?? report.smart_money_summary)?.source_status,
    ...(report.future_themes ?? []).map((theme) => theme.source_status),
  ].filter(Boolean);
}

export function DailyDataCoverageSummary({ report }: { report: DailyReport }) {
  const statuses = collectSourceStatuses(report);
  const live = statuses.filter((status) => status?.source_type === 'live').length;
  const cachedLive = statuses.filter((status) => status?.source_type === 'cached_live').length;
  const derivedLive = statuses.filter((status) => status?.source_type === 'derived').length;
  const fallback = statuses.filter((status) => status?.source_type === 'fallback').length;
  const mock = statuses.filter((status) => status?.source_type === 'mock').length;
  const missingSourceDate = statuses.filter((status) => !status?.source_date).length;
  const topLimitations = collectLimitations(report).slice(0, 2);

  return (
    <section className="pageSection dataCoverageBrief">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Data Coverage</p>
          <h2>Source health summary</h2>
          <p className="muted">Compact source-quality view before detailed evidence panels.</p>
        </div>
      </div>
      <div className="briefMetricGrid">
        <div><span>Live</span><strong>{live}</strong></div>
        <div><span>Cached live</span><strong>{cachedLive}</strong></div>
        <div><span>Derived live</span><strong>{derivedLive}</strong></div>
        <div><span>Fallback</span><strong>{fallback}</strong></div>
        <div><span>Mock</span><strong>{mock}</strong></div>
        <div><span>Missing source date</span><strong>{missingSourceDate}</strong></div>
      </div>
      {topLimitations.length > 0 && <ul className="noteList">{topLimitations.map((item) => <li key={item}>{item}</li>)}</ul>}
    </section>
  );
}

function actionLabel(action: TodayResearchAction) {
  return action.ticker ? `${action.ticker}: ${action.title}` : action.title;
}

function routeForAction(action: TodayResearchAction) {
  return action.route_hint ?? ({
    source_setup: 'operations',
    evidence_review: 'evidence_library',
    coverage_gap: 'stock_research',
    watchlist_change: 'stock_research',
    macro_context: 'daily_report',
  }[action.action_type] ?? 'daily_report');
}

export function DailyCommandCenter({ report }: { report: DailyReport }) {
  const center = report.command_center;
  if (!center) return null;
  return (
    <section className="pageSection dailyCommandCenter">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">5-minute workflow</p>
          <h2>Daily Command Center</h2>
          <p className="muted">Non-scoring workflow summary: start with the highest-attention source, delta, or evidence task.</p>
        </div>
      </div>
      <p>{center.headline}</p>
      <div className="briefMetricGrid">
        <div><span>Workflow focus</span><strong>{center.workflow_focus}</strong></div>
        <div><span>Top actions</span><strong>{center.top_actions?.length ?? 0}</strong></div>
        <div><span>Source alerts</span><strong>{center.source_health_alerts?.length ?? 0}</strong></div>
        <div><span>Watchlist focus</span><strong>{center.watchlist_focus?.length ?? 0}</strong></div>
      </div>
      {center.macro_snapshot && <p className="muted">Macro: {center.macro_snapshot.summary} · Route: {center.macro_snapshot.route_hint}</p>}
      {center.source_health_alerts?.length ? (
        <ul className="noteList">
          {center.source_health_alerts.map((alert) => (
            <li key={`${alert.severity}-${alert.title}`}>
              <strong>{alert.severity.toUpperCase()} · {alert.title}</strong>
              <span> — {alert.reason} · Route: {alert.route_hint}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {center.top_actions?.length ? (
        <ol className="noteList">
          {center.top_actions.map((action) => (
            <li key={`${action.priority}-${action.action_type}-${action.ticker ?? 'market'}-${action.title}`}>
              <strong>{action.priority.toUpperCase()} · {actionLabel(action)}</strong>
              <span> — {action.reason} · Route: {routeForAction(action)}</span>
            </li>
          ))}
        </ol>
      ) : null}
      {center.watchlist_focus?.length ? (
        <ul className="noteList">
          {center.watchlist_focus.map((item) => (
            <li key={item.ticker}><strong>{item.ticker}</strong><span> — {item.summary} · Route: {item.route_hint}</span></li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export function DailyResearchActions({ actions }: { actions?: TodayResearchAction[] }) {
  if (!actions?.length) return null;
  return (
    <section className="pageSection dailyActions">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">5-minute workflow</p>
          <h2>Today research actions</h2>
          <p className="muted">Start here: macro context, source changes, then the highest-value evidence work.</p>
        </div>
      </div>
      <ol className="noteList">
        {actions.map((action) => (
          <li key={`${action.action_type}-${action.ticker ?? 'market'}-${action.title}`}>
            <strong>{action.priority.toUpperCase()} · {actionLabel(action)}</strong>
            <span> — {action.reason}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function formatDelta(value?: number | null, suffix = '') {
  if (value === null || value === undefined) return 'N/A';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value}${suffix}`;
}

export function DailyDeltaSummary({ report }: { report: DailyReport }) {
  const macro = report.macro_delta;
  const watchlist = report.watchlist_delta;
  if (!macro && !watchlist?.items?.length) return null;
  return (
    <section className="pageSection dailyDelta">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Daily efficiency</p>
          <h2>Delta summary</h2>
          <p className="muted">Compare today with the previous stored snapshot before opening detailed evidence.</p>
        </div>
      </div>
      {macro && (
        <div className="briefMetricGrid">
          <div><span>Macro score</span><strong>{formatDelta(macro.macro_score_change)}</strong></div>
          <div><span>VIX</span><strong>{formatDelta(macro.vix_change)}</strong></div>
          <div><span>10Y-2Y spread</span><strong>{formatDelta(macro.yield_curve_10y2y_spread_change_bps, ' bps')}</strong></div>
        </div>
      )}
      {watchlist?.items?.length ? (
        <div className="tableWrap">
          <table>
            <thead><tr><th>Ticker</th><th>Price change</th><th>Overheat change</th><th>New Form 4</th><th>13F status</th><th>Data issue</th></tr></thead>
            <tbody>
              {watchlist.items.map((item) => (
                <tr key={item.ticker}>
                  <td>{item.ticker}</td>
                  <td>{formatDelta(item.price_change_pct, '%')}</td>
                  <td>{formatDelta(item.overheat_score_change)}</td>
                  <td>{item.new_form4_count ?? 'N/A'}</td>
                  <td>{item.institutional_13f_status}</td>
                  <td>{item.data_issue || 'None listed'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

export function OverheatSourceBacking({ score }: { score?: ScoreLike }) {
  const backing = score?.derived_metrics?.source_backing as { live_backed_weight?: number; mock_or_fallback_weight?: number; components?: Array<{ component: string; source_type: string; configured_weight: number }> } | undefined;
  if (!backing) return null;
  return (
    <section className="pageSection overheatBacking">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Overheat transparency</p>
          <h2>Live-backed weight disclosure</h2>
          <p className="muted">Score is unchanged; this only shows how much configured weight is live/derived versus mock/fallback.</p>
        </div>
      </div>
      <div className="briefMetricGrid">
        <div><span>Live-backed weight</span><strong>{backing.live_backed_weight ?? 0}</strong></div>
        <div><span>Mock/fallback weight</span><strong>{backing.mock_or_fallback_weight ?? 0}</strong></div>
      </div>
      {(backing.mock_or_fallback_weight ?? 0) > 0 && <p className="muted">Treat overheat as context until mock/fallback-backed components are replaced by stable live sources.</p>}
    </section>
  );
}

function latestSourceDate(report: DailyReport): string {
  const dates = [
    report.macro_regime?.source_status?.source_date,
    report.market_timing?.source_status?.source_date,
    report.overheat_risk?.source_status?.source_date,
    report.crisis_risk?.source_status?.source_date,
    report.smart_money?.source_status?.source_date,
    ...(report.future_themes ?? []).map((theme) => theme.source_status?.source_date),
  ].filter(Boolean) as string[];
  const sorted = dates.sort();
  return sorted[sorted.length - 1] ?? report.date;
}

export default function DailyReport() {
  const [report, setReport] = useState<DailyReport | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getLatestDailyReport()
      .then(setReport)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const warningTerms = useMemo(() => detectForbiddenLanguage(report), [report]);
  const limitations = collectLimitations(report ?? undefined);

  if (loading) return <main className="page"><p>Loading daily report...</p></main>;
  if (error) return <main className="page"><p className="errorText">{error}</p></main>;
  if (!report) return <main className="page"><p>No report payload returned.</p></main>;

  const smartMoney = report.smart_money ?? report.smart_money_summary;
  const smartComponents = smartMoney?.derived_metrics?.components as Record<string, ScoreLike> | undefined;

  return (
    <main className="page">
      <WarningBanner terms={warningTerms} />
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Daily US Market Report</p>
          <h1>{report.market} Research Dashboard</h1>
          <p>Report date {report.date}</p>
        </div>
        <div className="disclaimer">Research reference only. Not investment advice.</div>
      </header>
      <DailyCommandCenter report={report} />
      <DailyResearchActions actions={report.today_research_actions} />
      <DailyDeltaSummary report={report} />
      <DailyDataCoverageSummary report={report} />
      <DataQualitySummary summary={report.data_quality} latestSourceDate={latestSourceDate(report)} />

      <Section title="Market State">
        <div className="scoreGrid">
          <div className="cardWithSource"><ScoreCard title="Macro regime" score={report.macro_regime?.score} label={report.macro_regime?.label} confidence={report.macro_regime?.confidence} /><DataSourceBadge status={report.macro_regime?.source_status} /></div>
          <div className="cardWithSource"><ScoreCard title="Crisis level" score={report.crisis_risk?.score} label={report.crisis?.level ?? report.crisis_risk?.label} confidence={report.crisis?.confidence} /><DataSourceBadge status={report.crisis_risk?.source_status} /></div>
        </div>
        <ul className="noteList">{report.risk_notes?.map((item) => <li key={item}>{item}</li>)}</ul>
        <MacroScoreExplanationPanel explanation={report.macro_regime?.macro_score_explanation} provider={report.data_quality?.macro?.provider} />
        <RawDataPanel title="Macro regime evidence" rawData={report.macro_regime?.raw_data} derivedMetrics={report.macro_regime?.derived_metrics} benchmark={report.macro_regime?.benchmark} trend={report.macro_regime?.trend} limitations={report.macro_regime?.limitations} missingData={report.macro_regime?.missing_data} sourceStatus={report.macro_regime?.source_status} />
      </Section>

      <Section title="Methodology Reference">
        <JaneReferencePanel reference={report.jane_reference_conditions} />
      </Section>

      <Section title="Market Timing">
        <div className="scoreGrid">
          <ScoreEvidence title="Entry environment" score={report.market_timing} />
          <ScoreEvidence title="Overheat risk" score={report.overheat_risk} />
        </div>
        <OverheatSourceBacking score={report.overheat_risk} />
      </Section>

      <Section title="Future Industry Radar">
        <div className="tableWrap">
          <table>
            <thead><tr><th>Theme</th><th>Score</th><th>Trend</th><th>Candidates</th><th>Evidence</th><th>Source</th><th>Missing data</th></tr></thead>
            <tbody>
              {report.future_themes?.map((theme) => (
                <tr key={String(theme.theme ?? theme.raw_data?.theme ?? theme.label)}>
                  <td>{String(theme.theme ?? theme.raw_data?.theme ?? theme.name ?? 'Theme')}</td>
                  <td>{theme.score}</td>
                  <td>{Object.values(theme.trend ?? {}).join(', ') || 'N/A'}</td>
                  <td>{theme.candidate_companies?.join(', ') || 'None listed'}</td>
                  <td><SignalBadge label={theme.label} /></td>
                  <td><DataSourceBadge status={theme.source_status} /></td>
                  <td>{theme.missing_data?.join(', ') || 'None listed'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Stock Candidate Radar">
        <div className="tableWrap">
          <table>
            <thead><tr><th>Ticker</th><th>Company</th><th>Leadership</th><th>Smart money</th><th>Risk</th><th>Label</th><th>Source</th><th>Missing data</th></tr></thead>
            <tbody>
              {report.stock_candidates?.map((candidate) => (
                <tr key={candidate.ticker}>
                  <td>{candidate.ticker}</td>
                  <td>{candidate.company_name}</td>
                  <td>{candidate.leadership_score}</td>
                  <td>{candidate.smart_money_score}</td>
                  <td>{candidate.risk_score}</td>
                  <td><SignalBadge label={candidate.label} /></td>
                  <td><DataSourceBadge status={candidate.source_status} /></td>
                  <td>{candidate.missing_data?.join(', ') || 'None listed'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Smart Money Signals">
        <div className="scoreGrid">
          <ScoreEvidence title="13F institutional support" score={smartComponents?.institutional_support_13f} />
          <ScoreEvidence title="Form 4 insider signal" score={smartComponents?.insider_form4_signal} />
          <ScoreEvidence title="Options abnormal activity" score={smartComponents?.options_abnormal_activity} />
        </div>
      </Section>

      <Section title="Risk & Allocation Reference">
        <div className="scoreGrid">
          <ScoreCard title="Risk posture" score={report.risk_allocation?.score} label={report.risk_allocation?.risk_posture} confidence={report.risk_allocation?.confidence} />
        </div>
        <div className="referenceGrid">
          {Object.entries(report.risk_allocation?.reference ?? report.crisis?.reference ?? {}).map(([asset, label]) => (
            <div key={asset} className="referenceItem">
              <span>{asset}</span>
              <SignalBadge label={label} />
            </div>
          ))}
        </div>
        <RawDataPanel title="Risk reference evidence" rawData={report.risk_allocation?.raw_data} derivedMetrics={report.risk_allocation?.derived_metrics} benchmark={report.risk_allocation?.benchmark} trend={report.risk_allocation?.trend} limitations={report.risk_allocation?.limitations} missingData={report.risk_allocation?.missing_data} sourceStatus={report.risk_allocation?.source_status} />
      </Section>

      <Section title="Missing Data / Limitations">
        <div className="twoColumn">
          <div>
            <h3>Missing data</h3>
            <ul>{report.missing_data?.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
          <div>
            <h3>Limitations</h3>
            <ul>{limitations.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
        </div>
      </Section>
    </main>
  );
}
