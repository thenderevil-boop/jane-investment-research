import { FormEvent, useEffect, useRef, useState } from 'react';
import { analyzeCandidate, archiveCandidate, createCandidate, getCandidateDashboard, listCandidates, refreshCandidateEvidenceSummary, updateCandidate } from '../api/client';
import SignalBadge from '../components/SignalBadge';
import type { CandidateDashboard, CandidatePriority, CandidateResearchItem, CandidateStatus } from '../types';

function displayKey(value: string) {
  return value.replace(/_/g, ' ');
}

function joinList(values: string[]) {
  return values.length ? values.join(', ') : 'None';
}

function SummaryCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="scoreCard">
      <div className="scoreCardHeader"><span>{label}</span></div>
      <div className="scoreRow"><strong>{value}</strong></div>
    </div>
  );
}

export default function CandidateWorkspace() {
  const [dashboard, setDashboard] = useState<CandidateDashboard | null>(null);
  const [items, setItems] = useState<CandidateResearchItem[]>([]);
  const [selected, setSelected] = useState<CandidateResearchItem | null>(null);
  const [form, setForm] = useState({ ticker: 'NVDA', theme: 'AI infrastructure', user_reason: 'External trend research candidate', source_label: 'User watchlist note', source_date: '2026-05-08', priority: 'medium' as CandidatePriority, tags: 'AI, GPU, infrastructure' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const analyzeAbortRef = useRef<AbortController | null>(null);

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      const [nextDashboard, nextItems] = await Promise.all([getCandidateDashboard(), listCandidates()]);
      setDashboard(nextDashboard);
      setItems(nextItems);
      setSelected((current) => nextItems.find((item) => item.candidate_id === current?.candidate_id) ?? nextItems[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load candidate workspace');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    return () => analyzeAbortRef.current?.abort();
  }, []);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    const created = await createCandidate({
      ticker: form.ticker,
      market: 'US',
      theme: form.theme || null,
      user_reason: form.user_reason || null,
      source_label: form.source_label || null,
      source_date: form.source_date || null,
      priority: form.priority,
      tags: form.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
    });
    setSelected(created);
    await refresh();
  }

  async function setStatus(item: CandidateResearchItem, status: CandidateStatus) {
    await updateCandidate(item.candidate_id, { status });
    await refresh();
  }

  async function runAnalyze(item: CandidateResearchItem) {
    analyzeAbortRef.current?.abort();
    const controller = new AbortController();
    analyzeAbortRef.current = controller;
    setLoading(true);
    try {
      const result = await analyzeCandidate(item.candidate_id, { refresh_evidence_summary: true }, controller.signal);
      setSelected(result.candidate);
      await refresh();
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setError(err instanceof Error ? err.message : 'Unable to analyze candidate');
    } finally {
      if (analyzeAbortRef.current === controller) {
        analyzeAbortRef.current = null;
        setLoading(false);
      }
    }
  }

  async function refreshEvidence(item: CandidateResearchItem) {
    setSelected(await refreshCandidateEvidenceSummary(item.candidate_id));
    await refresh();
  }

  async function archive(item: CandidateResearchItem) {
    await archiveCandidate(item.candidate_id);
    await refresh();
  }

  const summary = dashboard?.summary;
  return (
    <main className="page">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Candidate Workspace</p>
          <h1>Watchlist Research Flow</h1>
          <p>Local workflow metadata for user-provided US ticker ideas. Not investment advice.</p>
        </div>
      </header>

      {summary && (
        <section className="pageSection">
          <h2>Dashboard</h2>
          <div className="scoreGrid">
            <SummaryCard label="Active candidates" value={summary.active_candidates} />
            <SummaryCard label="High priority" value={summary.high_priority_count} />
            <SummaryCard label="Stale evidence" value={summary.stale_evidence_candidate_count} />
            <SummaryCard label="Needs review" value={summary.needs_review_count} />
            <SummaryCard label="Comparison evidence" value={summary.with_comparison_evidence_count} />
            <SummaryCard label="Avg latest score" value={summary.average_latest_score ?? 'N/A'} />
          </div>
        </section>
      )}

      <section className="pageSection">
        <h2>Add Candidate</h2>
        <form className="tickerForm" onSubmit={onCreate}>
          <label htmlFor="candidateTicker">Ticker</label>
          <input id="candidateTicker" value={form.ticker} onChange={(event) => setForm({ ...form, ticker: event.target.value })} maxLength={10} />
          <label htmlFor="candidateTheme">Theme</label>
          <input id="candidateTheme" value={form.theme} onChange={(event) => setForm({ ...form, theme: event.target.value })} />
          <label htmlFor="candidateReason">Reason</label>
          <input id="candidateReason" value={form.user_reason} onChange={(event) => setForm({ ...form, user_reason: event.target.value })} />
          <label htmlFor="candidateSource">Source label</label>
          <input id="candidateSource" value={form.source_label} onChange={(event) => setForm({ ...form, source_label: event.target.value })} />
          <label htmlFor="candidateDate">Source date</label>
          <input id="candidateDate" type="date" value={form.source_date} onChange={(event) => setForm({ ...form, source_date: event.target.value })} />
          <label htmlFor="candidatePriority">Priority</label>
          <select id="candidatePriority" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value as CandidatePriority })}>
            {['low', 'medium', 'high'].map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <label htmlFor="candidateTags">Tags</label>
          <input id="candidateTags" value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} />
          <button type="submit" disabled={loading}>{loading ? 'Saving...' : 'Add candidate'}</button>
        </form>
      </section>

      {error && <p className="errorText">{error}</p>}

      <section className="pageSection">
        <h2>Candidates</h2>
        <div className="tableWrap">
          <table>
            <thead><tr><th>Ticker</th><th>Theme</th><th>Status</th><th>Priority</th><th>Latest</th><th>Quality</th><th>Coverage</th><th>Stale</th><th>Comparison</th><th>Missing criteria</th><th>Next review</th><th>Actions</th></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.candidate_id} onClick={() => setSelected(item)}>
                  <td>{item.ticker}</td>
                  <td>{item.theme ?? 'N/A'}</td>
                  <td><SignalBadge label={item.status} variant={item.status === 'reviewed' ? 'positive' : 'neutral'} /></td>
                  <td>{item.priority}</td>
                  <td>{item.latest_score ?? 'N/A'} {item.latest_label ? <small>{item.latest_label}</small> : null}</td>
                  <td>{item.latest_data_quality_grade ?? 'N/A'}</td>
                  <td>{item.evidence_summary.criteria_covered.length} / 6</td>
                  <td>{item.evidence_summary.stale_evidence_count}</td>
                  <td>{item.evidence_summary.comparison_evidence_count}</td>
                  <td>{joinList(item.evidence_summary.criteria_missing.map(displayKey))}</td>
                  <td>{item.next_review_due_at ?? 'None'}</td>
                  <td>
                    <button type="button" onClick={(event) => { event.stopPropagation(); runAnalyze(item); }}>Analyze</button>
                    <button type="button" onClick={(event) => { event.stopPropagation(); refreshEvidence(item); }}>Refresh evidence</button>
                    <button type="button" onClick={(event) => { event.stopPropagation(); setStatus(item, 'researching'); }}>Researching</button>
                    <button type="button" onClick={(event) => { event.stopPropagation(); setStatus(item, 'reviewed'); }}>Reviewed</button>
                    <button type="button" onClick={(event) => { event.stopPropagation(); archive(item); }}>Archive</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!items.length && <p className="muted">No active candidates yet.</p>}
      </section>

      {selected && (
        <section className="pageSection">
          <h2>Candidate Detail</h2>
          <div className="summaryGrid">
            <div><strong>Ticker</strong><span>{selected.ticker}</span></div>
            <div><strong>Theme</strong><span>{selected.theme ?? 'N/A'}</span></div>
            <div><strong>User reason</strong><span>{selected.user_reason ?? 'N/A'}</span></div>
            <div><strong>Latest analysis</strong><span>{selected.last_analyzed_at ?? 'Not run'}</span></div>
            <div><strong>Latest score</strong><span>{selected.latest_score ?? 'N/A'} / {selected.latest_confidence ?? 'N/A'}</span></div>
            <div><strong>Review notes</strong><span>{selected.review_notes ?? 'None'}</span></div>
            <div><strong>Covered criteria</strong><span>{joinList(selected.evidence_summary.criteria_covered.map(displayKey))}</span></div>
            <div><strong>Missing criteria</strong><span>{joinList(selected.evidence_summary.criteria_missing.map(displayKey))}</span></div>
            <div><strong>Peer companies</strong><span>{joinList(selected.evidence_summary.peer_companies_mentioned)}</span></div>
          </div>
        </section>
      )}
    </main>
  );
}
