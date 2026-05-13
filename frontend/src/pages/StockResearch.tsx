import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { analyzeStock, exportAnalyzeStockReport } from '../api/client';
import DataSourceBadge from '../components/DataSourceBadge';
import EvidencePanel from '../components/EvidencePanel';
import JaneReferencePanel from '../components/JaneReferencePanel';
import RawDataPanel from '../components/RawDataPanel';
import ScoreCard from '../components/ScoreCard';
import SignalBadge from '../components/SignalBadge';
import WarningBanner from '../components/WarningBanner';
import type { AnalyzeStockDataQualitySummary, ComparisonContext, ComparisonEvidenceAssessment, DataSourceStatus, EvidenceMatrixItem, FinancialStatementSignals, JaneCompanyQuality, NextManualCheck, QualitativeEvidenceAssessment, QualitativeEvidenceInput, ScoreDriver, ScoreLike, StockAnalysis, ValidationQualitySummary } from '../types';
import { detectForbiddenLanguage } from '../utils/forbiddenLanguage';

export const janeLeadershipCriteria = [
  { name: 'monopoly_power', displayName: 'Monopoly Power / High Entry Barrier', description: 'Durable market power, switching costs, entry barriers, ecosystem control, or defensible share.' },
  { name: 'visionary_founder_ceo', displayName: 'Visionary Founder / CEO', description: 'Founder-like ownership, long-term vision, execution record, and strategic discipline.' },
  { name: 'early_skepticism', displayName: 'Early Skepticism', description: 'Material skepticism followed by improved operating, adoption, or filing evidence.' },
  { name: 'disruptive_innovation', displayName: 'Disruptive Innovation', description: 'Products or business architecture that change customer behavior, cost curves, or industry structure.' },
  { name: 'superior_technology_r_and_d', displayName: 'Superior Technology and R&D', description: 'Technology capability, R&D intensity, patents, cadence, or technical benchmarks.' },
  { name: 'scalable_business_model', displayName: 'Scalable Business Model', description: 'Growth potential with operating leverage, repeatable distribution, and resilient margins.' },
  { name: 'brand_power_fandom', displayName: 'Brand Power / Fandom', description: 'Brand trust or customer attachment supporting pricing, retention, or adoption.' },
  { name: 'data_advantage', displayName: 'Data Advantage', description: 'Proprietary data, usage scale, feedback loops, or data infrastructure that improve products.' },
  { name: 'capital_allocation', displayName: 'Capital Allocation', description: 'Disciplined use of capital across R&D, acquisitions, balance sheet, and shareholder-return choices.' },
  { name: 'cash_flow_creation', displayName: 'Cash Flow Creation', description: 'Durable cash flow after operating needs and reinvestment requirements.' },
  { name: 'mega_trend_fit', displayName: 'Mega Trend Fit', description: 'Alignment with a durable long-cycle theme rather than narrative only.' },
  { name: 'talent_attraction_retention', displayName: 'Talent Attraction / Retention', description: 'Ability to attract and retain critical technical, operational, or leadership talent.' },
  { name: 'global_expansion', displayName: 'Global Expansion', description: 'Expansion across geographies, customer segments, or channels with execution evidence.' },
  { name: 'life_changing_necessary_product', displayName: 'Life-Changing Necessary Product', description: 'A product customers treat as important, workflow-critical, or difficult to replace.' },
  { name: 'regulatory_government_relationship', displayName: 'Regulatory / Government Relationship', description: 'Regulatory posture, government demand, approvals, or policy relationships requiring review.' },
  { name: 'network_effect', displayName: 'Network Effect', description: 'Value that increases as users, developers, customers, partners, or data participants grow.' },
  { name: 'mission_narrative_power', displayName: 'Mission / Narrative Power', description: 'Mission clarity and narrative strength that can attract customers, talent, capital, or ecosystem participation.' },
  { name: 'patents_ip', displayName: 'Patents / IP', description: 'Patents, trade secrets, software assets, or IP supporting durability or differentiation.' },
  { name: 'vc_institutional_support', displayName: 'VC / Institutional Support', description: 'Sophisticated long-horizon capital support, strategic investors, or institutional validation as research context.' },
  { name: 'retention_repurchase_rate', displayName: 'Retention / Repurchase Rate', description: 'Customers continue using, renewing, expanding, or repeatedly purchasing.' },
] as const;

const qualitativeCriteria = new Set([...janeLeadershipCriteria.map((criterion) => criterion.name), 'continuous_r_and_d']);
const qualitativeEvidenceTypes = new Set([
  'market_share',
  'patent',
  'platform_ecosystem',
  'founder_operator',
  'management_tenure',
  'product_disruption',
  'customer_adoption',
  'developer_ecosystem',
  'switching_cost',
  'brand_power',
  'r_and_d_intensity',
  'user_provided_note',
  'filing_reference',
  'competitor_comparison',
  'market_share_comparison',
  'product_capability_comparison',
  'ecosystem_comparison',
  'pricing_power_comparison',
  'switching_cost_comparison',
  'r_and_d_comparison',
  'other',
]);
const comparisonTypes = new Set(['competitor', 'market_share', 'product_capability', 'platform_ecosystem', 'customer_adoption', 'pricing_power', 'switching_cost', 'r_and_d_intensity', 'other']);
const claimedAdvantages = new Set(['stronger', 'similar', 'weaker', 'unclear']);

export function parseQualitativeEvidenceJson(value: string): QualitativeEvidenceInput[] | undefined {
  if (!value.trim()) return undefined;
  const parsed = JSON.parse(value) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error('Qualitative evidence JSON must be an array.');
  }
  return parsed.map((item, index) => {
    if (!item || typeof item !== 'object') {
      throw new Error(`Qualitative evidence item ${index + 1} must be an object.`);
    }
    const evidence = item as Partial<QualitativeEvidenceInput>;
    if (!qualitativeCriteria.has(String(evidence.criterion))) {
      throw new Error(`Qualitative evidence item ${index + 1} has an unsupported criterion.`);
    }
    if (!qualitativeEvidenceTypes.has(String(evidence.evidence_type))) {
      throw new Error(`Qualitative evidence item ${index + 1} has an unsupported evidence_type.`);
    }
    if (!String(evidence.summary ?? '').trim()) {
      throw new Error(`Qualitative evidence item ${index + 1} needs a summary.`);
    }
    if (!String(evidence.source_label ?? '').trim()) {
      throw new Error(`Qualitative evidence item ${index + 1} needs a source_label.`);
    }
    if (typeof evidence.confidence !== 'number' || evidence.confidence < 0 || evidence.confidence > 1) {
      throw new Error(`Qualitative evidence item ${index + 1} confidence must be between 0 and 1.`);
    }
    if (evidence.user_provided !== true) {
      throw new Error(`Qualitative evidence item ${index + 1} must set user_provided to true.`);
    }
    const comparisonContext = evidence.comparison_context;
    if (comparisonContext) {
      if (!comparisonTypes.has(String(comparisonContext.comparison_type))) {
        throw new Error(`Qualitative evidence item ${index + 1} has an unsupported comparison_type.`);
      }
      if (!String(comparisonContext.comparison_summary ?? '').trim()) {
        throw new Error(`Qualitative evidence item ${index + 1} needs a comparison_summary.`);
      }
      if (!claimedAdvantages.has(String(comparisonContext.claimed_advantage ?? 'unclear'))) {
        throw new Error(`Qualitative evidence item ${index + 1} has an unsupported claimed_advantage.`);
      }
    }
    return {
      ...evidence,
      criterion: String(evidence.criterion),
      evidence_type: String(evidence.evidence_type),
      summary: String(evidence.summary),
      source_label: String(evidence.source_label),
      confidence: evidence.confidence,
      user_provided: true,
      limitations: Array.isArray(evidence.limitations) ? evidence.limitations.map(String) : [],
      comparison_context: comparisonContext
        ? {
            ...comparisonContext,
            comparison_type: String(comparisonContext.comparison_type) as ComparisonContext['comparison_type'],
            peer_companies: Array.isArray(comparisonContext.peer_companies) ? comparisonContext.peer_companies.map(String) : [],
            comparison_summary: String(comparisonContext.comparison_summary),
            claimed_advantage: String(comparisonContext.claimed_advantage ?? 'unclear') as ComparisonContext['claimed_advantage'],
            source_basis: String(comparisonContext.source_basis ?? 'user_note') as ComparisonContext['source_basis'],
            limitations: Array.isArray(comparisonContext.limitations) ? comparisonContext.limitations.map(String) : [],
          } as ComparisonContext
        : null,
    } as QualitativeEvidenceInput;
  });
}

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

function listFromUnknown(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => typeof item === 'string' ? item : JSON.stringify(item)) : [];
}

function downloadText(filename: string, contentType: string, content: string) {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
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
    user_provided: 'derived',
    mock_only: 'mock',
    filing_backed: 'live',
    provider_backed: 'derived',
    derived_from_mixed_sources: 'derived',
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

export function ValidationQualitySummarySection({ summary }: { summary?: ValidationQualitySummary }) {
  if (!summary) return null;
  return (
    <section className="pageSection">
      <h2>Validation Quality Summary</h2>
      <div className="summaryMain">
        <span className="smallPill">{summary.overall_validation_level}</span>
        <span className="smallPill">Grade {summary.data_quality_grade}</span>
        {summary.manual_review_required && <span className="smallPill">manual review required</span>}
        {summary.confidence_cap_applied && <span className="smallPill">confidence capped</span>}
      </div>
      <p>{summary.why}</p>
      {summary.confidence_cap_reason && <p className="sourceWarning">{summary.confidence_cap_reason}</p>}
      <div className="twoColumn">
        <div>
          <h3>Supporting evidence</h3>
          <ul>{summary.primary_supporting_evidence.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
        <div>
          <h3>Limiting factors</h3>
          <ul>{summary.primary_limiting_factors.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>
      {!!summary.highest_priority_review_items.length && (
        <p className="muted">Highest priority checks: {summary.highest_priority_review_items.join(' | ')}</p>
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
          <div><dt>Filing backed</dt><dd>{dataQuality.company_quality.filing_backed_criteria_count ?? 0}</dd></div>
        </dl>
      )}
      {dataQuality.qualitative_evidence && (
        <dl className="qualityMetrics">
          <div><dt>Qualitative provided</dt><dd>{dataQuality.qualitative_evidence.provided ? 'Yes' : 'No'}</dd></div>
          <div><dt>Accepted</dt><dd>{dataQuality.qualitative_evidence.accepted_count}</dd></div>
          <div><dt>Rejected</dt><dd>{dataQuality.qualitative_evidence.rejected_count}</dd></div>
          <div><dt>User provided</dt><dd>{dataQuality.qualitative_evidence.user_provided_count}</dd></div>
          <div><dt>Verified</dt><dd>{dataQuality.qualitative_evidence.independently_verified_count}</dd></div>
          <div><dt>Reviewed active</dt><dd>{dataQuality.qualitative_evidence.reviewed_active_count ?? 0}</dd></div>
          <div><dt>Unreviewed active</dt><dd>{dataQuality.qualitative_evidence.unreviewed_active_count ?? 0}</dd></div>
          <div><dt>Stale manual</dt><dd>{dataQuality.qualitative_evidence.stale_count ?? 0}</dd></div>
          <div><dt>Avg quality</dt><dd>{dataQuality.qualitative_evidence.quality_score_average ?? 'N/A'}</dd></div>
          <div><dt>Incomplete</dt><dd>{dataQuality.qualitative_evidence.incomplete_count ?? 0}</dd></div>
          <div><dt>Comparison accepted</dt><dd>{dataQuality.qualitative_evidence.comparison?.accepted_count ?? 0}</dd></div>
          <div><dt>Comparison peers</dt><dd>{dataQuality.qualitative_evidence.comparison?.peer_company_count ?? 0}</dd></div>
        </dl>
      )}
      {dataQuality.sec_companyfacts && (
        <dl className="qualityMetrics">
          <div><dt>SEC facts</dt><dd>{dataQuality.sec_companyfacts.filing_backed_metric_count}</dd></div>
          <div><dt>Missing concepts</dt><dd>{dataQuality.sec_companyfacts.missing_concept_count}</dd></div>
          <div><dt>SEC filing</dt><dd>{dataQuality.sec_companyfacts.latest_filing_date ?? 'N/A'}</dd></div>
          <div><dt>Agreement</dt><dd>{dataQuality.sec_companyfacts.agreement_level_with_yfinance}</dd></div>
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
          <thead><tr><th>Criterion</th><th>Status</th><th>Score</th><th>Source quality</th><th>Strength</th><th>Verification</th><th>Missing data</th></tr></thead>
          <tbody>
            {quality.criteria.map((criterion) => (
              <tr key={criterion.name}>
                <td>{criterion.display_name}</td>
                <td><SignalBadge label={criterion.status} variant={criterion.status === 'supportive' ? 'positive' : criterion.status === 'insufficient' || criterion.status === 'caution' ? 'warning' : 'neutral'} /></td>
                <td>{criterion.score === null || criterion.score === undefined ? 'N/A' : `${criterion.score.toFixed(0)} / ${criterion.max_score}`}</td>
                <td>{criterion.source_quality}</td>
                <td>{criterion.evidence_strength ?? 'none'}</td>
                <td>{criterion.verification_level ?? 'insufficient'}</td>
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

export function QualitativeEvidenceAssessmentSection({ assessment }: { assessment?: QualitativeEvidenceAssessment }) {
  if (!assessment) return null;
  return (
    <section className="pageSection">
      <h2>Qualitative Evidence Assessment</h2>
      <div className="summaryMain">
        <span className="smallPill">Accepted {assessment.accepted_evidence_count}</span>
        <span className="smallPill">Rejected {assessment.rejected_evidence_count}</span>
        <span className="smallPill">Saved {assessment.saved_evidence_count ?? 0}</span>
        <span className="smallPill">Request {assessment.request_evidence_count ?? 0}</span>
        <span className="smallPill">Reviewed {assessment.reviewed_active_count ?? 0}</span>
        <span className="smallPill">Unreviewed {assessment.unreviewed_active_count ?? 0}</span>
        <span className="smallPill">Stale {assessment.stale_count ?? 0}</span>
        <span className="smallPill">Avg quality {assessment.quality_score_average ?? 'N/A'}</span>
        <span className="smallPill">user-provided, not independently verified</span>
        <DataSourceBadge status={assessment.source_status} />
      </div>
      <p>{assessment.source_quality_summary}</p>
      {!!assessment.criteria_covered.length && <p className="muted">Criteria covered: {assessment.criteria_covered.join(', ')}</p>}
      {!!assessment.criteria_still_insufficient.length && <p className="sourceWarning">Still insufficient: {assessment.criteria_still_insufficient.join(', ')}</p>}
      {!!assessment.evidence_items.length && (
        <div className="tableWrap">
          <table>
            <thead><tr><th>Criterion</th><th>Type</th><th>Status</th><th>Badges</th><th>Quality</th><th>Source</th><th>Reason</th><th>Summary</th></tr></thead>
            <tbody>
              {assessment.evidence_items.map((item, index) => (
                <tr key={`${item.criterion}-${item.evidence_type}-${index}`}>
                  <td>{displayKey(item.criterion)}</td>
                  <td>{displayKey(item.evidence_type)}</td>
                  <td><SignalBadge label={item.accepted ? 'accepted' : 'rejected'} variant={item.accepted ? 'positive' : 'warning'} /></td>
                  <td>
                    <span className="smallPill">{item.origin ?? 'request_scoped'}</span>
                    <span className="smallPill">{item.source_quality}</span>
                    {item.review_status && <span className="smallPill">{item.review_status}</span>}
                    {item.is_stale && <span className="smallPill">stale</span>}
                  </td>
                  <td>
                    {item.evidence_quality_score ?? 0}
                    <div><SignalBadge label={item.evidence_quality_label ?? 'incomplete'} variant={item.evidence_quality_label === 'high' ? 'positive' : item.evidence_quality_label === 'incomplete' ? 'warning' : 'neutral'} /></div>
                    <small>{item.source_reliability_label ?? 'unknown'}</small>
                  </td>
                  <td>{item.source_label || 'N/A'} {item.source_date ? `(${item.source_date})` : ''}</td>
                  <td>{item.acceptance_reason}</td>
                  <td>{item.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!!assessment.limitations.length && <p className="muted">Limitations: {assessment.limitations.join(' ')}</p>}
    </section>
  );
}

export function ComparisonEvidenceAssessmentSection({ assessment }: { assessment?: ComparisonEvidenceAssessment }) {
  if (!assessment) return null;
  return (
    <section className="pageSection">
      <h2>Comparison Evidence Assessment</h2>
      <div className="summaryMain">
        <span className="smallPill">Accepted {assessment.accepted_comparison_count}</span>
        <span className="smallPill">Reviewed {assessment.reviewed_comparison_count}</span>
        <span className="smallPill">Stale {assessment.stale_comparison_count}</span>
        <span className="smallPill">{assessment.source_quality}</span>
        <span className="smallPill">user-provided, not independently verified</span>
        <DataSourceBadge status={assessment.source_status} />
      </div>
      {!!assessment.peer_companies_mentioned.length && <p className="muted">Peer companies: {assessment.peer_companies_mentioned.join(', ')}</p>}
      {!!assessment.criteria_supported.length && <p className="muted">Criteria supported: {assessment.criteria_supported.join(', ')}</p>}
      <dl className="qualityMetrics">
        {Object.entries(assessment.claimed_advantage_breakdown).map(([key, value]) => (
          <div key={key}><dt>{displayKey(key)}</dt><dd>{value}</dd></div>
        ))}
      </dl>
      {!!assessment.limitations.length && <p className="sourceWarning">{assessment.limitations.join(' ')}</p>}
      {!!assessment.items.length && (
        <div className="tableWrap">
          <table>
            <thead><tr><th>Criterion</th><th>Type</th><th>Peers</th><th>Advantage</th><th>Quality</th><th>Status</th><th>Summary</th></tr></thead>
            <tbody>
              {assessment.items.map((item, index) => (
                <tr key={`${item.evidence_id ?? 'comparison'}-${index}`}>
                  <td>{displayKey(item.criterion)}</td>
                  <td>{displayKey(item.comparison_type)}</td>
                  <td>{item.peer_companies.length ? item.peer_companies.join(', ') : 'N/A'}</td>
                  <td>{item.claimed_advantage}</td>
                  <td>{item.evidence_quality_score} / {item.evidence_quality_label}</td>
                  <td>
                    <SignalBadge label={item.accepted ? 'accepted' : 'rejected'} variant={item.accepted ? 'positive' : 'warning'} />
                    {item.review_status && <span className="smallPill">{item.review_status}</span>}
                    {item.is_stale && <span className="smallPill">stale</span>}
                  </td>
                  <td>{item.comparison_summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!assessment.items.length && <p className="muted">No structured competitor or comparison evidence was provided.</p>}
    </section>
  );
}

export function SecFinancialFactsSection({ facts }: { facts?: Record<string, unknown> }) {
  if (!facts) return null;
  const sourceStatus = facts.source_status as DataSourceStatus | undefined;
  const factMap = (facts.facts ?? {}) as Record<string, { value?: number; unit?: string; period?: string; form?: string; filed?: string; concept?: string } | null>;
  const missingData = Array.isArray(facts.missing_data) ? facts.missing_data.map(String) : [];
  return (
    <section className="pageSection">
      <h2>SEC Financial Facts</h2>
      <div className="summaryMain">
        {sourceStatus && <DataSourceBadge status={sourceStatus} />}
        <span className="smallPill">CIK {displayValue(facts.cik)}</span>
        <span className="smallPill">Filing {displayValue(facts.latest_filing_date)}</span>
        <span className="smallPill">Period {displayValue(facts.latest_report_period)}</span>
      </div>
      <div className="tableWrap">
        <table>
          <thead><tr><th>Metric</th><th>Value</th><th>Period</th><th>Form</th><th>Concept</th></tr></thead>
          <tbody>
            {Object.entries(factMap).map(([name, fact]) => (
              <tr key={name}>
                <td>{displayKey(name)}</td>
                <td>{fact ? `${displayValue(fact.value)} ${fact.unit ?? ''}` : 'Missing'}</td>
                <td>{fact?.period ?? 'N/A'}</td>
                <td>{fact?.form ?? 'N/A'}</td>
                <td>{fact?.concept ?? 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!!missingData.length && <p className="sourceWarning">Missing SEC concepts: {missingData.join(', ')}</p>}
    </section>
  );
}

export function FundamentalsCrossCheckSection({ crossCheck }: { crossCheck?: Record<string, unknown> }) {
  if (!crossCheck) return null;
  const sourceStatus = crossCheck.source_status as DataSourceStatus | undefined;
  const metrics = Array.isArray(crossCheck.checked_metrics) ? crossCheck.checked_metrics as Array<Record<string, unknown>> : [];
  const explanation = crossCheck.explanation as Record<string, unknown> | undefined;
  const reviewMetrics = Array.isArray(explanation?.metrics_requiring_review) ? explanation.metrics_requiring_review as Array<Record<string, unknown>> : [];
  const agreement = String(crossCheck.agreement_level ?? 'insufficient');
  return (
    <section className="pageSection">
      <h2>Fundamentals Cross-Check Explanation</h2>
      <div className="summaryMain">
        <span className="smallPill">{agreement}</span>
        {Boolean(explanation?.manual_check_priority) && <span className="smallPill">review {String(explanation?.manual_check_priority)}</span>}
        {sourceStatus && <DataSourceBadge status={sourceStatus} />}
      </div>
      {agreement === 'low' && <p className="sourceWarning">SEC/yfinance discrepancy requires manual review.</p>}
      <p>{String(explanation?.plain_language_summary ?? crossCheck.summary ?? '')}</p>
      {!!listFromUnknown(explanation?.likely_reasons).length && (
        <ul>{listFromUnknown(explanation?.likely_reasons).map((item) => <li key={item}>{item}</li>)}</ul>
      )}
      {Boolean(explanation?.confidence_impact) && <p className="muted">{String(explanation?.confidence_impact)}</p>}
      <div className="tableWrap">
        <table>
          <thead><tr><th>Metric</th><th>yfinance</th><th>SEC</th><th>Difference</th><th>Status</th></tr></thead>
          <tbody>
            {metrics.map((metric) => (
              <tr key={String(metric.name)}>
                <td>{displayKey(String(metric.name))}</td>
                <td>{displayValue(metric.yfinance_value)}</td>
                <td>{displayValue(metric.sec_value)}</td>
                <td>{metric.difference_pct === null || metric.difference_pct === undefined ? 'N/A' : `${displayValue(metric.difference_pct)}%`}</td>
                <td>{String(metric.status ?? 'insufficient')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!!reviewMetrics.length && (
        <div className="tableWrap">
          <table>
            <thead><tr><th>Review metric</th><th>Why it matters</th><th>Review hint</th></tr></thead>
            <tbody>
              {reviewMetrics.map((metric) => (
                <tr key={String(metric.metric)}>
                  <td>{displayKey(String(metric.metric))}</td>
                  <td>{String(metric.why_it_matters ?? '')}</td>
                  <td>{String(metric.review_hint ?? '')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function SmartMoneySourceQualitySection({ smartMoney }: { smartMoney?: ScoreLike }) {
  const breakdown = smartMoney?.source_quality_breakdown as Record<string, Record<string, unknown>> | undefined;
  if (!breakdown) return null;
  const rows = ['form4', 'institutional_13f', 'options'].map((key) => ({ key, value: breakdown[key] ?? {} }));
  return (
    <section className="pageSection">
      <h2>Smart Money Source Quality Breakdown</h2>
      <div className="tableWrap">
        <table>
          <thead><tr><th>Component</th><th>Source type</th><th>Interpretation</th><th>Score impact</th></tr></thead>
          <tbody>
            {rows.map(({ key, value }) => (
              <tr key={key}>
                <td>{displayKey(key)}</td>
                <td>{displayValue(value.source_type)}</td>
                <td>{displayValue(value.interpretation)}</td>
                <td>{displayValue(value.score_impact)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {breakdown.aggregate_interpretation && <p className="sourceWarning">{String(breakdown.aggregate_interpretation)}</p>}
    </section>
  );
}

export function ValuationRiskExplanationSection({ valuation }: { valuation?: ScoreLike }) {
  const explanation = (valuation?.explanation ?? valuation?.raw_data?.explanation) as Record<string, unknown> | undefined;
  if (!explanation) return null;
  const metrics = Array.isArray(explanation.metrics_used) ? explanation.metrics_used as Array<Record<string, unknown>> : [];
  return (
    <section className="pageSection">
      <h2>Valuation Risk Explanation</h2>
      <div className="summaryMain">
        <span className="smallPill">{String(explanation.valuation_risk_label ?? valuation?.label ?? 'unavailable')}</span>
      </div>
      <p>{String(explanation.plain_language_summary ?? '')}</p>
      <div className="tableWrap">
        <table>
          <thead><tr><th>Metric</th><th>Value</th><th>Threshold context</th><th>Limitation</th></tr></thead>
          <tbody>
            {metrics.map((metric) => (
              <tr key={String(metric.name)}>
                <td>{displayKey(String(metric.name))}</td>
                <td>{displayValue(metric.value)}</td>
                <td>{String(metric.threshold_context ?? '')}</td>
                <td>{String(metric.limitation ?? '')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {Boolean(explanation.why_it_matters) && <p className="muted">{String(explanation.why_it_matters)}</p>}
      {Boolean(explanation.manual_review_hint) && <p className="sourceWarning">{String(explanation.manual_review_hint)}</p>}
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
          <article className={`evidenceRow ${row.is_deprecated ? 'deprecatedEvidenceRow' : ''}`} key={row.category}>
            <div className="evidenceRowHeader">
              <h3>{displayKey(row.category)}</h3>
              <div>
                <SignalBadge label={row.status} variant={row.status === 'caution' || row.status === 'insufficient' ? 'warning' : 'neutral'} />
                <DataSourceBadge status={sourceQualityStatus(row.source_quality)} />
                <span className="smallPill">{row.source_quality}</span>
                {row.review_priority && row.review_priority !== 'none' && <span className="smallPill">review {row.review_priority}</span>}
                {row.affects_final_score === false && <span className="smallPill">not scoring</span>}
                {row.is_deprecated && <span className="smallPill">deprecated</span>}
              </div>
            </div>
            <p>{row.summary}</p>
            {row.replaced_by && <p className="muted">Replaced by {row.replaced_by}.</p>}
            {row.why_it_matters && <p className="muted">{row.why_it_matters}</p>}
            {(row.source_quality === 'mock_only' || row.source_quality === 'mixed_with_fallback') && (
              <p className="sourceWarning">{row.source_quality === 'mock_only' ? 'Mock-only evidence; treat as preliminary.' : 'Fallback or mixed source quality; manual confirmation required.'}</p>
            )}
            {row.is_deprecated ? (
              <details>
                <summary>Legacy mock details</summary>
                <ul>{row.key_evidence.map((item) => <li key={item}>{item}</li>)}</ul>
              </details>
            ) : (
              <ul>{row.key_evidence.map((item) => <li key={item}>{item}</li>)}</ul>
            )}
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
  const [showAll, setShowAll] = useState(false);
  if (!checks?.length) return null;
  const visibleChecks = showAll ? checks : checks.slice(0, 8);
  return (
    <section className="pageSection">
      <h2>Next Manual Checks</h2>
      <ul className="checkList">
        {visibleChecks.map((item) => (
          <li key={`${item.area}-${item.check}`}>
            <span className={`checkPriority ${item.priority}`}>{item.priority}</span>
            <div>
              <strong>#{item.priority_rank ?? '?'} {displayKey(item.category ?? item.area)} {item.blocking ? '(blocking)' : ''}</strong>
              <span>{item.check}</span>
              <small>{item.reason_short || item.reason}</small>
            </div>
          </li>
        ))}
      </ul>
      {checks.length > 8 && (
        <button type="button" onClick={() => setShowAll((value) => !value)}>
          {showAll ? 'Show top checks' : `Show all checks (${checks.length})`}
        </button>
      )}
    </section>
  );
}

export function ValidationReportExportSection({
  ticker,
  theme,
  userReason,
  qualitativeEvidenceJson,
}: {
  ticker: string;
  theme: string;
  userReason: string;
  qualitativeEvidenceJson: string;
}) {
  const [includeRawEvidence, setIncludeRawEvidence] = useState(false);
  const [includeManualEvidence, setIncludeManualEvidence] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  const [filename, setFilename] = useState('');

  async function runExport(format: 'json' | 'markdown') {
    setExporting(true);
    setExportError('');
    try {
      const qualitativeEvidence = parseQualitativeEvidenceJson(qualitativeEvidenceJson);
      const response = await exportAnalyzeStockReport({
        ticker,
        market: 'US',
        research_context: { theme, user_reason: userReason },
        qualitative_evidence: qualitativeEvidence,
        format,
        include_raw_evidence: includeRawEvidence,
        include_manual_evidence: includeManualEvidence,
        redact_sensitive_fields: true,
      });
      const content = typeof response.report === 'string' ? response.report : JSON.stringify(response.report, null, 2);
      downloadText(response.filename, response.content_type, content);
      setFilename(response.filename);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Unable to export validation report');
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="pageSection">
      <h2>Validation Report Export</h2>
      <p className="muted">Export is research reference only. Not investment advice.</p>
      <div className="filterBar">
        <label><input type="checkbox" checked={includeRawEvidence} onChange={(event) => setIncludeRawEvidence(event.target.checked)} /> Include raw evidence</label>
        <label><input type="checkbox" checked={includeManualEvidence} onChange={(event) => setIncludeManualEvidence(event.target.checked)} /> Include manual evidence summary</label>
        <button type="button" onClick={() => runExport('json')} disabled={exporting}>{exporting ? 'Exporting...' : 'Export JSON'}</button>
        <button type="button" onClick={() => runExport('markdown')} disabled={exporting}>{exporting ? 'Exporting...' : 'Export Markdown'}</button>
      </div>
      {filename && <p className="muted">Generated filename: {filename}</p>}
      {exportError && <p className="errorText">{exportError}</p>}
    </section>
  );
}

export default function StockResearch() {
  const [ticker, setTicker] = useState('NVDA');
  const [theme, setTheme] = useState('AI infrastructure');
  const [userReason, setUserReason] = useState('External trend research');
  const [qualitativeEvidenceJson, setQualitativeEvidenceJson] = useState('');
  const [result, setResult] = useState<StockAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const analyzeAbortRef = useRef<AbortController | null>(null);
  const warningTerms = useMemo(() => detectForbiddenLanguage(result), [result]);
  const criteria = result?.leadership_score?.criteria as Array<Record<string, unknown>> | undefined;

  useEffect(() => () => analyzeAbortRef.current?.abort(), []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    analyzeAbortRef.current?.abort();
    const controller = new AbortController();
    analyzeAbortRef.current = controller;
    setLoading(true);
    setError('');
    try {
      const qualitativeEvidence = parseQualitativeEvidenceJson(qualitativeEvidenceJson);
      setResult(await analyzeStock(ticker, { theme, user_reason: userReason }, qualitativeEvidence, controller.signal));
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setError(err instanceof Error ? err.message : 'Unable to analyze ticker');
    } finally {
      if (analyzeAbortRef.current === controller) {
        analyzeAbortRef.current = null;
        setLoading(false);
      }
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
          <p className="muted">Primary workflow: submit a ticker to validate the idea using evidence, data quality, and missing-data checks.</p>
        </div>
      </header>

      <form className="tickerForm" onSubmit={onSubmit}>
        <label htmlFor="ticker">Ticker</label>
        <input id="ticker" value={ticker} onChange={(event) => setTicker(event.target.value)} maxLength={10} />
        <label htmlFor="theme">Theme</label>
        <input id="theme" value={theme} onChange={(event) => setTheme(event.target.value)} />
        <label htmlFor="reason">Reason</label>
        <input id="reason" value={userReason} onChange={(event) => setUserReason(event.target.value)} />
        <details className="qualitativeEvidenceInput">
          <summary>Qualitative Evidence JSON</summary>
          <label htmlFor="qualitativeEvidence">Structured qualitative evidence</label>
          <textarea
            id="qualitativeEvidence"
            value={qualitativeEvidenceJson}
            onChange={(event) => setQualitativeEvidenceJson(event.target.value)}
            rows={8}
            placeholder='[{"criterion":"network_effect","evidence_type":"platform_ecosystem","summary":"Specific claim requiring manual verification.","source_label":"User research note","source_date":"2026-05-06","confidence":0.65,"user_provided":true,"limitations":["Requires manual verification."]}]'
          />
          <details className="criteriaHelp">
            <summary>Jane 20 criteria reference</summary>
            <ul>
              {janeLeadershipCriteria.map((criterion) => (
                <li key={criterion.name}>
                  <strong>{criterion.name}</strong>: {criterion.description}
                </li>
              ))}
            </ul>
          </details>
        </details>
        <button type="submit" disabled={loading}>{loading ? 'Analyzing...' : 'Run research'}</button>
      </form>

      {error && <p className="errorText">{error}</p>}

      {result && (
        <>
          <ValidationReportExportSection ticker={ticker} theme={theme} userReason={userReason} qualitativeEvidenceJson={qualitativeEvidenceJson} />
          <CandidateSummarySection result={result} />
          <ValidationQualitySummarySection summary={result.validation_quality_summary} />
          <AnalyzeDataQualitySection dataQuality={result.data_quality_summary} />
          <JaneCompanyQualitySection quality={result.jane_company_quality} profile={result.company_profile} />
          <QualitativeEvidenceAssessmentSection assessment={result.qualitative_evidence_assessment} />
          <ComparisonEvidenceAssessmentSection assessment={result.comparison_evidence_assessment} />
          <FinancialStatementSignalsSection signals={result.financial_statement_signals} />
          <SecFinancialFactsSection facts={result.sec_financial_facts} />
          <FundamentalsCrossCheckSection crossCheck={result.fundamentals_cross_check} />
          <CompanyFundamentalsSection result={result} />
          <SmartMoneySourceQualitySection smartMoney={result.smart_money} />
          <ValuationRiskExplanationSection valuation={result.valuation_context} />
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
            <RawDataPanel title="SEC financial facts raw evidence" rawData={result.sec_financial_facts} derivedMetrics={(result.sec_financial_facts?.derived_metrics as Record<string, unknown>) ?? {}} limitations={(result.sec_financial_facts?.limitations as string[]) ?? []} missingData={(result.sec_financial_facts?.missing_data as string[]) ?? []} sourceStatus={result.sec_financial_facts?.source_status as DataSourceStatus | undefined} />
            <RawDataPanel title="Fundamentals cross-check raw evidence" rawData={result.fundamentals_cross_check} derivedMetrics={{ agreement_level: result.fundamentals_cross_check?.agreement_level }} limitations={(result.fundamentals_cross_check?.limitations as string[]) ?? []} missingData={(result.fundamentals_cross_check?.missing_data as string[]) ?? []} sourceStatus={result.fundamentals_cross_check?.source_status as DataSourceStatus | undefined} />
            <RawDataPanel title="Smart money raw evidence" rawData={result.smart_money?.raw_data} derivedMetrics={result.smart_money?.derived_metrics} benchmark={result.smart_money?.benchmark} trend={result.smart_money?.trend} limitations={result.smart_money?.limitations} missingData={result.smart_money?.missing_data} sourceStatus={resolveScoreSourceStatus(result.smart_money)} />
            <RawDataPanel title="Insider Form 4 raw evidence" rawData={result.insider_activity?.raw_data} derivedMetrics={result.insider_activity?.derived_metrics} benchmark={result.insider_activity?.benchmark} trend={result.insider_activity?.trend} limitations={result.insider_activity?.limitations} missingData={result.insider_activity?.missing_data} sourceStatus={resolveScoreSourceStatus(result.insider_activity)} />
            <RawDataPanel title="Institutional 13F raw evidence" rawData={result.institutional_13f?.raw_data} derivedMetrics={result.institutional_13f?.derived_metrics} benchmark={result.institutional_13f?.benchmark} trend={result.institutional_13f?.trend} limitations={result.institutional_13f?.limitations} missingData={result.institutional_13f?.missing_data} sourceStatus={resolveScoreSourceStatus(result.institutional_13f)} />
          </section>
        </>
      )}
    </main>
  );
}
