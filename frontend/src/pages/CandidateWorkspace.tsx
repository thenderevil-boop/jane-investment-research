import { FormEvent, useEffect, useRef, useState } from 'react';
import { addCandidateNote, analyzeCandidate, archiveCandidate, createCandidate, getCandidateAnalysisHistory, getCandidateDashboard, getCandidateNotes, getCandidateReadinessComparison, listCandidates, refreshCandidateEvidenceSummary, restoreCandidate, updateCandidate } from '../api/client';
import SignalBadge from '../components/SignalBadge';
import type { CandidateAnalysisHistoryItem, CandidateDashboard, CandidateFilters, CandidatePriority, CandidateReadinessComparison, CandidateResearchItem, CandidateReviewNote, CandidateReviewNoteCreate, CandidateStatus } from '../types';

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

function badgeVariant(severity: string) {
  return severity === 'success' ? 'positive' : severity === 'warning' ? 'warning' : 'neutral';
}

export default function CandidateWorkspace() {
  const [dashboard, setDashboard] = useState<CandidateDashboard | null>(null);
  const [readinessComparison, setReadinessComparison] = useState<CandidateReadinessComparison | null>(null);
  const [items, setItems] = useState<CandidateResearchItem[]>([]);
  const [selected, setSelected] = useState<CandidateResearchItem | null>(null);
  const [form, setForm] = useState({ ticker: 'NVDA', theme: 'AI infrastructure', user_reason: 'External trend research candidate', source_label: 'User watchlist note', source_date: '2026-05-08', priority: 'medium' as CandidatePriority, tags: 'AI, GPU, infrastructure' });
  const [filters, setFilters] = useState<CandidateFilters>({ sort_by: 'updated_at', sort_order: 'desc' });
  const [noteForm, setNoteForm] = useState<CandidateReviewNoteCreate>({ note: '', note_type: 'general', tags: [] });
  const [notes, setNotes] = useState<CandidateReviewNote[]>([]);
  const [analysisHistory, setAnalysisHistory] = useState<CandidateAnalysisHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const analyzeAbortRef = useRef<AbortController | null>(null);

  async function loadDetail(candidate: CandidateResearchItem | null) {
    if (!candidate) {
      setNotes([]);
      setAnalysisHistory([]);
      return;
    }
    const [nextNotes, nextHistory] = await Promise.all([
      getCandidateNotes(candidate.candidate_id),
      getCandidateAnalysisHistory(candidate.candidate_id),
    ]);
    setNotes(nextNotes);
    setAnalysisHistory(nextHistory);
  }

  async function refresh(nextFilters = filters) {
    setLoading(true);
    setError('');
    try {
      const [nextDashboard, nextComparison, nextItems] = await Promise.all([getCandidateDashboard(nextFilters), getCandidateReadinessComparison(nextFilters), listCandidates(nextFilters)]);
      setDashboard(nextDashboard);
      setReadinessComparison(nextComparison);
      setItems(nextItems);
      const nextSelected = nextItems.find((item) => item.candidate_id === selected?.candidate_id) ?? nextItems[0] ?? null;
      setSelected(nextSelected);
      await loadDetail(nextSelected);
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

  async function restore(item: CandidateResearchItem) {
    setSelected(await restoreCandidate(item.candidate_id));
    await refresh({ ...filters, include_archived: true });
  }

  async function onAddNote(event: FormEvent) {
    event.preventDefault();
    if (!selected || !noteForm.note.trim()) return;
    await addCandidateNote(selected.candidate_id, {
      ...noteForm,
      note: noteForm.note.trim(),
      tags: typeof noteForm.tags === 'string' ? [] : noteForm.tags,
    });
    setNoteForm({ note: '', note_type: 'general', tags: [] });
    const updated = await getCandidateNotes(selected.candidate_id);
    setNotes(updated);
    await refresh();
  }

  function applyFilters(next: CandidateFilters) {
    setFilters(next);
    refresh(next);
  }

  const summary = dashboard?.summary;
  return (
    <main className="page">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Candidate Workspace</p>
          <h1>Watchlist Research Flow</h1>
          <p>Local workflow metadata for user-provided US ticker ideas. Not investment advice. Phase 70 adds Candidate Readiness Comparison for evidence gaps and next actions.</p>
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
            <SummaryCard label="Needs analysis" value={summary.needs_analysis_count} />
            <SummaryCard label="Review overdue" value={summary.review_overdue_count} />
            <SummaryCard label="Comparison evidence" value={summary.with_comparison_evidence_count} />
            <SummaryCard label="Avg latest score" value={summary.average_latest_score ?? 'N/A'} />
          </div>
        </section>
      )}

      {readinessComparison && (
        <section className="pageSection">
          <h2>Candidate Readiness Comparison</h2>
          <p className="muted">Workflow-only readiness view. Items are not ranked by score or recommendation.</p>
          <div className="scoreGrid">
            <SummaryCard label="Candidates" value={readinessComparison.summary.candidate_count} />
            <SummaryCard label="Manual evidence gaps" value={readinessComparison.summary.needs_manual_evidence_count} />
            <SummaryCard label="Needs analysis refresh" value={readinessComparison.summary.needs_analysis_refresh_count} />
            <SummaryCard label="Review queue attention" value={readinessComparison.summary.review_queue_attention_count} />
          </div>
          <div className="tableWrap">
            <table>
              <thead><tr><th>Ticker</th><th>Readiness</th><th>Evidence</th><th>Top gap</th><th>Next action</th></tr></thead>
              <tbody>
                {readinessComparison.items.map((item) => (
                  <tr key={item.candidate_id}>
                    <td>{item.ticker}</td>
                    <td><SignalBadge label={displayKey(item.readiness_state)} variant={item.readiness_state === 'comparison_ready_for_review' ? 'positive' : 'warning'} /></td>
                    <td>{item.evidence_completeness.covered_count} covered / {item.evidence_completeness.missing_count} missing</td>
                    <td>{item.top_gap.criterion ? displayKey(item.top_gap.criterion) : displayKey(item.top_gap.gap_type)}</td>
                    <td>{item.next_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
        <div className="filterBar">
          <label>Status<select value={filters.status ?? ''} onChange={(event) => applyFilters({ ...filters, status: event.target.value as CandidateStatus | '' })}><option value="">Any</option>{['watching', 'researching', 'reviewed', 'archived'].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <label>Priority<select value={filters.priority ?? ''} onChange={(event) => applyFilters({ ...filters, priority: event.target.value as CandidatePriority | '' })}><option value="">Any</option>{['low', 'medium', 'high'].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <label>Ticker<input value={filters.ticker ?? ''} onChange={(event) => setFilters({ ...filters, ticker: event.target.value })} onBlur={() => refresh()} /></label>
          <label>Tag<input value={filters.tag ?? ''} onChange={(event) => setFilters({ ...filters, tag: event.target.value })} onBlur={() => refresh()} /></label>
          <label>Comparison<select value={filters.has_comparison_evidence === undefined || filters.has_comparison_evidence === null ? '' : String(filters.has_comparison_evidence)} onChange={(event) => applyFilters({ ...filters, has_comparison_evidence: event.target.value === '' ? null : event.target.value === 'true' })}><option value="">Any</option><option value="true">Present</option><option value="false">None</option></select></label>
          <label>Sort<select value={filters.sort_by ?? 'updated_at'} onChange={(event) => applyFilters({ ...filters, sort_by: event.target.value as CandidateFilters['sort_by'] })}>{['updated_at', 'latest_score', 'next_review_due_at', 'stale_evidence_count'].map((value) => <option key={value} value={value}>{displayKey(value)}</option>)}</select></label>
          <label>Order<select value={filters.sort_order ?? 'desc'} onChange={(event) => applyFilters({ ...filters, sort_order: event.target.value as 'asc' | 'desc' })}><option value="desc">Desc</option><option value="asc">Asc</option></select></label>
          <label><input type="checkbox" checked={Boolean(filters.stale_evidence_only)} onChange={(event) => applyFilters({ ...filters, stale_evidence_only: event.target.checked })} /> Stale evidence only</label>
          <label><input type="checkbox" checked={Boolean(filters.needs_review_only)} onChange={(event) => applyFilters({ ...filters, needs_review_only: event.target.checked })} /> Needs review only</label>
          <label><input type="checkbox" checked={Boolean(filters.include_archived)} onChange={(event) => applyFilters({ ...filters, include_archived: event.target.checked })} /> Include archived</label>
        </div>
        <div className="tableWrap">
          <table>
            <thead><tr><th>Ticker</th><th>Theme</th><th>Status</th><th>Priority</th><th>Latest</th><th>Quality</th><th>Badges</th><th>Coverage</th><th>Next review</th><th>Actions</th></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.candidate_id} onClick={() => { setSelected(item); loadDetail(item); }}>
                  <td>{item.ticker}</td>
                  <td>{item.theme ?? 'N/A'}</td>
                  <td><SignalBadge label={item.status} variant={item.status === 'reviewed' ? 'positive' : 'neutral'} /></td>
                  <td><SignalBadge label={item.priority} variant={item.priority === 'high' ? 'warning' : 'neutral'} /></td>
                  <td>{item.latest_score ?? 'N/A'} {item.latest_confidence ? <small>conf {item.latest_confidence}</small> : null} {item.latest_label ? <small>{item.latest_label}</small> : null}</td>
                  <td>{item.latest_data_quality_grade ?? 'N/A'}</td>
                  <td>{item.evidence_badges.map((badge) => <SignalBadge key={badge.label} label={displayKey(badge.label)} variant={badgeVariant(badge.severity)} />)}</td>
                  <td>{item.evidence_summary.criteria_covered.length} / 6</td>
                  <td>{item.next_review_due_at ?? 'None'}</td>
                  <td>
                    <button type="button" onClick={(event) => { event.stopPropagation(); runAnalyze(item); }}>Analyze</button>
                    <button type="button" onClick={(event) => { event.stopPropagation(); refreshEvidence(item); }}>Refresh evidence</button>
                    <button type="button" onClick={(event) => { event.stopPropagation(); setStatus(item, 'researching'); }}>Researching</button>
                    <button type="button" onClick={(event) => { event.stopPropagation(); setStatus(item, 'reviewed'); }}>Reviewed</button>
                    {item.status === 'archived' ? <button type="button" onClick={(event) => { event.stopPropagation(); restore(item); }}>Restore</button> : <button type="button" onClick={(event) => { event.stopPropagation(); archive(item); }}>Archive</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!items.length && <p className="muted">No active candidates yet.</p>}
      </section>

      {dashboard?.review_queue.length ? (
        <section className="pageSection">
          <h2>Review Queue</h2>
          <div className="queueList">
            {dashboard.review_queue.map((item) => (
              <button type="button" key={item.candidate_id} onClick={() => { setSelected(item); loadDetail(item); }}>
                <strong>{item.ticker}</strong>
                <span>{joinList((item.review_reasons ?? []).map(displayKey))}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

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
            <div><strong>Evidence counts</strong><span>{selected.evidence_summary.active_evidence_count} active, {selected.evidence_summary.stale_evidence_count} stale, {selected.evidence_summary.comparison_evidence_count} comparison</span></div>
            <div><strong>Covered criteria</strong><span>{joinList(selected.evidence_summary.criteria_covered.map(displayKey))}</span></div>
            <div><strong>Missing criteria</strong><span>{joinList(selected.evidence_summary.criteria_missing.map(displayKey))}</span></div>
            <div><strong>Peer companies</strong><span>{joinList(selected.evidence_summary.peer_companies_mentioned)}</span></div>
          </div>
          <div className="twoColumn">
            <div>
              <h3>Review Notes History</h3>
              <form className="stackedForm" onSubmit={onAddNote}>
                <label>Note type<select value={noteForm.note_type} onChange={(event) => setNoteForm({ ...noteForm, note_type: event.target.value as CandidateReviewNote['note_type'] })}>{['general', 'evidence_review', 'analysis_review', 'risk_review', 'follow_up'].map((value) => <option key={value} value={value}>{displayKey(value)}</option>)}</select></label>
                <label>Note<textarea value={noteForm.note} onChange={(event) => setNoteForm({ ...noteForm, note: event.target.value })} /></label>
                <label>Tags<input value={(noteForm.tags ?? []).join(', ')} onChange={(event) => setNoteForm({ ...noteForm, tags: event.target.value.split(',').map((tag) => tag.trim()).filter(Boolean) })} /></label>
                <button type="submit">Add note</button>
              </form>
              <ul className="noteList">{notes.map((note) => <li key={note.note_id}><strong>{displayKey(note.note_type)}</strong> <span>{note.created_at}</span><p>{note.note}</p><small>{joinList(note.tags)}</small></li>)}</ul>
              {!notes.length && <p className="muted">No review notes yet.</p>}
            </div>
            <div>
              <h3>Analysis History</h3>
              <ul className="noteList">{analysisHistory.map((entry) => <li key={entry.analysis_snapshot_id}><strong>{entry.score ?? 'N/A'} / {entry.confidence ?? 'N/A'}</strong> <span>{entry.analyzed_at}</span><p>{entry.label ?? 'No label'} · quality {entry.data_quality_grade ?? 'N/A'}</p><small>{entry.evidence_coverage_summary.active_evidence_count} active evidence, {entry.evidence_coverage_summary.criteria_missing.length} missing criteria</small></li>)}</ul>
              {!analysisHistory.length && <p className="muted">No analysis history yet.</p>}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
