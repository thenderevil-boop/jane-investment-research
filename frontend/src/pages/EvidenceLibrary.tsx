import { FormEvent, useEffect, useState } from 'react';
import { archiveManualEvidence, createManualEvidence, listManualEvidence, updateManualEvidence } from '../api/client';
import SignalBadge from '../components/SignalBadge';
import type { ManualQualitativeEvidence, ManualQualitativeEvidenceCreate } from '../types';

function displayKey(value: string) {
  return value.replace(/_/g, ' ');
}

const defaultEvidence: ManualQualitativeEvidenceCreate = {
  ticker: 'NVDA',
  criterion: 'network_effect',
  evidence_type: 'platform_ecosystem',
  summary: '',
  source_label: 'User research note',
  source_url: null,
  source_date: '2026-05-06',
  confidence: 0.65,
  review_status: 'unreviewed' as const,
  source_reliability_label: 'user_note',
  review_notes: null,
  expires_at: null,
  created_by: 'local_user',
  limitations: ['Requires manual verification against official filings or independent sources.'],
  tags: ['manual evidence'],
  comparison_context: null,
};

const comparisonEvidenceTypes = ['competitor_comparison', 'market_share_comparison', 'product_capability_comparison', 'ecosystem_comparison', 'pricing_power_comparison', 'switching_cost_comparison', 'r_and_d_comparison'];

function peerTextToArray(value: string) {
  return value.split(',').map((part) => part.trim().toUpperCase()).filter(Boolean);
}

export default function EvidenceLibrary() {
  const [tickerFilter, setTickerFilter] = useState('NVDA');
  const [reviewStatusFilter, setReviewStatusFilter] = useState('');
  const [items, setItems] = useState<ManualQualitativeEvidence[]>([]);
  const [form, setForm] = useState(defaultEvidence);
  const [peerCompaniesText, setPeerCompaniesText] = useState('AMD, INTC');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      setItems(await listManualEvidence(tickerFilter, reviewStatusFilter || undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load manual evidence');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      await createManualEvidence({
        ...form,
        ticker: form.ticker.trim().toUpperCase(),
        limitations: form.limitations.filter(Boolean),
        tags: form.tags.filter(Boolean),
        comparison_context: form.comparison_context?.comparison_summary
          ? {
              ...form.comparison_context,
              subject_company: form.ticker.trim().toUpperCase(),
              peer_companies: peerTextToArray(peerCompaniesText),
              limitations: form.comparison_context.limitations.filter(Boolean),
            }
          : null,
      });
      setForm({ ...defaultEvidence, ticker: form.ticker.trim().toUpperCase() });
      setPeerCompaniesText('AMD, INTC');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create manual evidence');
      setLoading(false);
    }
  }

  async function onStatusChange(item: ManualQualitativeEvidence, reviewStatus: ManualQualitativeEvidence['review_status']) {
    await updateManualEvidence(item.evidence_id, { review_status: reviewStatus });
    await refresh();
  }

  async function onReliabilityChange(item: ManualQualitativeEvidence, sourceReliabilityLabel: ManualQualitativeEvidence['source_reliability_label']) {
    await updateManualEvidence(item.evidence_id, { source_reliability_label: sourceReliabilityLabel });
    await refresh();
  }

  async function onReviewNotesBlur(item: ManualQualitativeEvidence, reviewNotes: string) {
    if ((item.review_notes ?? '') === reviewNotes) return;
    await updateManualEvidence(item.evidence_id, { review_notes: reviewNotes || null });
    await refresh();
  }

  async function onArchive(item: ManualQualitativeEvidence) {
    await archiveManualEvidence(item.evidence_id);
    await refresh();
  }

  return (
    <main className="page">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Evidence Library</p>
          <h1>Manual Evidence Library</h1>
          <p>Local user-provided qualitative evidence. Not independently verified.</p>
        </div>
      </header>

      <section className="pageSection">
        <h2>Filter</h2>
        <div className="tickerForm">
          <label htmlFor="evidenceTickerFilter">Ticker</label>
          <input id="evidenceTickerFilter" value={tickerFilter} onChange={(event) => setTickerFilter(event.target.value)} />
          <label htmlFor="evidenceReviewFilter">Review status</label>
          <select id="evidenceReviewFilter" value={reviewStatusFilter} onChange={(event) => setReviewStatusFilter(event.target.value)}>
            <option value="">All</option>
            {['unreviewed', 'reviewed', 'rejected', 'archived'].map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <button type="button" onClick={refresh} disabled={loading}>{loading ? 'Loading...' : 'Load evidence'}</button>
        </div>
      </section>

      <section className="pageSection">
        <h2>Create Evidence Item</h2>
        <form className="tickerForm" onSubmit={onCreate}>
          <label htmlFor="manualTicker">Ticker</label>
          <input id="manualTicker" value={form.ticker} onChange={(event) => setForm({ ...form, ticker: event.target.value })} />
          <label htmlFor="manualCriterion">Criterion</label>
          <select id="manualCriterion" value={form.criterion} onChange={(event) => setForm({ ...form, criterion: event.target.value })}>
            {['network_effect', 'visionary_founder_ceo', 'monopoly_power', 'disruptive_innovation', 'continuous_r_and_d', 'mega_trend_fit'].map((value) => <option key={value} value={value}>{displayKey(value)}</option>)}
          </select>
          <label htmlFor="manualType">Evidence type</label>
          <select id="manualType" value={form.evidence_type} onChange={(event) => setForm({ ...form, evidence_type: event.target.value })}>
            {['platform_ecosystem', 'founder_operator', 'market_share', 'product_disruption', 'developer_ecosystem', 'customer_adoption', 'switching_cost', 'patent', 'r_and_d_intensity', 'filing_reference', ...comparisonEvidenceTypes, 'other'].map((value) => <option key={value} value={value}>{displayKey(value)}</option>)}
          </select>
          <label htmlFor="manualSummary">Summary</label>
          <textarea id="manualSummary" value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} rows={4} />
          <label htmlFor="manualSource">Source label</label>
          <input id="manualSource" value={form.source_label} onChange={(event) => setForm({ ...form, source_label: event.target.value })} />
          <label htmlFor="manualDate">Source date</label>
          <input id="manualDate" value={form.source_date ?? ''} onChange={(event) => setForm({ ...form, source_date: event.target.value || null })} />
          <label htmlFor="manualReliability">Source reliability</label>
          <select id="manualReliability" value={form.source_reliability_label} onChange={(event) => setForm({ ...form, source_reliability_label: event.target.value as ManualQualitativeEvidence['source_reliability_label'] })}>
            {['user_note', 'official_company_material', 'sec_filing_reference', 'company_investor_relations', 'reputable_third_party_research', 'unknown', 'other'].map((value) => <option key={value} value={value}>{displayKey(value)}</option>)}
          </select>
          <label htmlFor="manualExpires">Expires at</label>
          <input id="manualExpires" value={form.expires_at ?? ''} onChange={(event) => setForm({ ...form, expires_at: event.target.value || null })} />
          <label htmlFor="manualComparisonType">Comparison type</label>
          <select
            id="manualComparisonType"
            value={form.comparison_context?.comparison_type ?? ''}
            onChange={(event) => setForm({
              ...form,
              evidence_type: comparisonEvidenceTypes.includes(form.evidence_type) ? form.evidence_type : 'competitor_comparison',
              comparison_context: {
                comparison_type: event.target.value as NonNullable<ManualQualitativeEvidence['comparison_context']>['comparison_type'],
                subject_company: form.ticker.trim().toUpperCase(),
                peer_companies: peerTextToArray(peerCompaniesText),
                comparison_summary: form.comparison_context?.comparison_summary ?? '',
                claimed_advantage: form.comparison_context?.claimed_advantage ?? 'unclear',
                metric_name: null,
                metric_value: null,
                metric_unit: null,
                comparison_period: form.comparison_context?.comparison_period ?? null,
                source_basis: form.comparison_context?.source_basis ?? 'user_note',
                limitations: form.comparison_context?.limitations ?? ['Manual comparison requires independent verification.'],
              },
            })}
          >
            <option value="">No comparison context</option>
            {['competitor', 'market_share', 'product_capability', 'platform_ecosystem', 'customer_adoption', 'pricing_power', 'switching_cost', 'r_and_d_intensity', 'other'].map((value) => <option key={value} value={value}>{displayKey(value)}</option>)}
          </select>
          <label htmlFor="manualPeers">Peer companies</label>
          <input id="manualPeers" value={peerCompaniesText} onChange={(event) => setPeerCompaniesText(event.target.value)} />
          <label htmlFor="manualAdvantage">Claimed advantage</label>
          <select
            id="manualAdvantage"
            value={form.comparison_context?.claimed_advantage ?? 'unclear'}
            onChange={(event) => setForm({
              ...form,
              comparison_context: {
                ...(form.comparison_context ?? {
                  comparison_type: 'competitor',
                  subject_company: form.ticker.trim().toUpperCase(),
                  peer_companies: peerTextToArray(peerCompaniesText),
                  comparison_summary: '',
                  metric_name: null,
                  metric_value: null,
                  metric_unit: null,
                  comparison_period: null,
                  source_basis: 'user_note',
                  limitations: ['Manual comparison requires independent verification.'],
                }),
                claimed_advantage: event.target.value as NonNullable<ManualQualitativeEvidence['comparison_context']>['claimed_advantage'],
              },
            })}
          >
            {['unclear', 'stronger', 'similar', 'weaker'].map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <label htmlFor="manualComparisonSummary">Comparison summary</label>
          <textarea
            id="manualComparisonSummary"
            value={form.comparison_context?.comparison_summary ?? ''}
            onChange={(event) => setForm({
              ...form,
              evidence_type: comparisonEvidenceTypes.includes(form.evidence_type) ? form.evidence_type : 'competitor_comparison',
              comparison_context: {
                ...(form.comparison_context ?? {
                  comparison_type: 'competitor',
                  subject_company: form.ticker.trim().toUpperCase(),
                  peer_companies: peerTextToArray(peerCompaniesText),
                  claimed_advantage: 'unclear',
                  metric_name: null,
                  metric_value: null,
                  metric_unit: null,
                  comparison_period: null,
                  source_basis: 'user_note',
                  limitations: ['Manual comparison requires independent verification.'],
                }),
                comparison_summary: event.target.value,
              },
            })}
            rows={3}
          />
          <label htmlFor="manualSourceBasis">Comparison source basis</label>
          <select
            id="manualSourceBasis"
            value={form.comparison_context?.source_basis ?? 'user_note'}
            onChange={(event) => setForm({
              ...form,
              comparison_context: {
                ...(form.comparison_context ?? {
                  comparison_type: 'competitor',
                  subject_company: form.ticker.trim().toUpperCase(),
                  peer_companies: peerTextToArray(peerCompaniesText),
                  comparison_summary: '',
                  claimed_advantage: 'unclear',
                  metric_name: null,
                  metric_value: null,
                  metric_unit: null,
                  comparison_period: null,
                  limitations: ['Manual comparison requires independent verification.'],
                }),
                source_basis: event.target.value as NonNullable<ManualQualitativeEvidence['comparison_context']>['source_basis'],
              },
            })}
          >
            {['user_note', 'company_filing', 'investor_presentation', 'third_party_research', 'manual_estimate', 'other'].map((value) => <option key={value} value={value}>{displayKey(value)}</option>)}
          </select>
          <button type="submit" disabled={loading}>Create saved evidence</button>
        </form>
      </section>

      {error && <p className="errorText">{error}</p>}

      <section className="pageSection">
        <h2>Saved Evidence</h2>
        <div className="tableWrap">
          <table>
            <thead><tr><th>Ticker</th><th>Criterion</th><th>Type</th><th>Badges</th><th>Quality</th><th>Summary</th><th>Review</th><th>Reliability</th><th>Notes</th><th>Action</th></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.evidence_id}>
                  <td>{item.ticker}</td>
                  <td>{displayKey(item.criterion)}</td>
                  <td>{displayKey(item.evidence_type)}</td>
                  <td>
                    <span className="smallPill">saved_library</span>
                    <span className="smallPill">user_provided</span>
                    {item.is_stale && <span className="smallPill">stale</span>}
                    {item.next_review_due_at && <span className="smallPill">review_due</span>}
                    {item.comparison_context && <span className="smallPill">{displayKey(item.comparison_context.comparison_type)}</span>}
                    <SignalBadge label={item.review_status} variant={item.review_status === 'reviewed' ? 'positive' : item.review_status === 'archived' || item.review_status === 'rejected' ? 'warning' : 'neutral'} />
                  </td>
                  <td>
                    <strong>{item.evidence_quality_score}</strong>
                    <div><SignalBadge label={item.evidence_quality_label} variant={item.evidence_quality_label === 'high' ? 'positive' : item.evidence_quality_label === 'incomplete' ? 'warning' : 'neutral'} /></div>
                    {item.stale_reason && <small>{item.stale_reason}</small>}
                  </td>
                  <td>
                    {item.summary}
                    {item.comparison_context && <small> Peers: {item.comparison_context.peer_companies.join(', ') || 'N/A'}; advantage: {item.comparison_context.claimed_advantage}</small>}
                  </td>
                  <td>
                    <select value={item.review_status} onChange={(event) => onStatusChange(item, event.target.value as ManualQualitativeEvidence['review_status'])}>
                      {['unreviewed', 'reviewed', 'rejected', 'archived'].map((value) => <option key={value} value={value}>{value}</option>)}
                    </select>
                  </td>
                  <td>
                    <select value={item.source_reliability_label} onChange={(event) => onReliabilityChange(item, event.target.value as ManualQualitativeEvidence['source_reliability_label'])}>
                      {['user_note', 'official_company_material', 'sec_filing_reference', 'company_investor_relations', 'reputable_third_party_research', 'unknown', 'other'].map((value) => <option key={value} value={value}>{displayKey(value)}</option>)}
                    </select>
                  </td>
                  <td><input defaultValue={item.review_notes ?? ''} onBlur={(event) => onReviewNotesBlur(item, event.target.value)} /></td>
                  <td><button type="button" onClick={() => onArchive(item)}>Archive</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!items.length && <p className="muted">No saved manual evidence for this filter.</p>}
      </section>
    </main>
  );
}
