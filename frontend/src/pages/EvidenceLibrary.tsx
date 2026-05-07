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
  created_by: 'local_user',
  limitations: ['Requires manual verification against official filings or independent sources.'],
  tags: ['manual evidence'],
};

export default function EvidenceLibrary() {
  const [tickerFilter, setTickerFilter] = useState('NVDA');
  const [items, setItems] = useState<ManualQualitativeEvidence[]>([]);
  const [form, setForm] = useState(defaultEvidence);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      setItems(await listManualEvidence(tickerFilter));
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
      });
      setForm({ ...defaultEvidence, ticker: form.ticker.trim().toUpperCase() });
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
            {['platform_ecosystem', 'founder_operator', 'market_share', 'product_disruption', 'developer_ecosystem', 'customer_adoption', 'switching_cost', 'patent', 'r_and_d_intensity', 'filing_reference', 'other'].map((value) => <option key={value} value={value}>{displayKey(value)}</option>)}
          </select>
          <label htmlFor="manualSummary">Summary</label>
          <textarea id="manualSummary" value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} rows={4} />
          <label htmlFor="manualSource">Source label</label>
          <input id="manualSource" value={form.source_label} onChange={(event) => setForm({ ...form, source_label: event.target.value })} />
          <label htmlFor="manualDate">Source date</label>
          <input id="manualDate" value={form.source_date ?? ''} onChange={(event) => setForm({ ...form, source_date: event.target.value || null })} />
          <button type="submit" disabled={loading}>Create saved evidence</button>
        </form>
      </section>

      {error && <p className="errorText">{error}</p>}

      <section className="pageSection">
        <h2>Saved Evidence</h2>
        <div className="tableWrap">
          <table>
            <thead><tr><th>Ticker</th><th>Criterion</th><th>Type</th><th>Badges</th><th>Summary</th><th>Review</th><th>Action</th></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.evidence_id}>
                  <td>{item.ticker}</td>
                  <td>{displayKey(item.criterion)}</td>
                  <td>{displayKey(item.evidence_type)}</td>
                  <td>
                    <span className="smallPill">saved_library</span>
                    <span className="smallPill">user_provided</span>
                    <SignalBadge label={item.review_status} variant={item.review_status === 'reviewed' ? 'positive' : item.review_status === 'archived' || item.review_status === 'rejected' ? 'warning' : 'neutral'} />
                  </td>
                  <td>{item.summary}</td>
                  <td>
                    <select value={item.review_status} onChange={(event) => onStatusChange(item, event.target.value as ManualQualitativeEvidence['review_status'])}>
                      {['unreviewed', 'reviewed', 'rejected', 'archived'].map((value) => <option key={value} value={value}>{value}</option>)}
                    </select>
                  </td>
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
