import { useEffect, useState } from 'react';
import { archiveManualEvidence, exportLocalBackup, getManualEvidenceDashboard, updateManualEvidence } from '../api/client';
import SignalBadge from '../components/SignalBadge';
import type { ManualEvidenceDashboard, ManualEvidenceDashboardFilters, ManualEvidenceDashboardQueueItem } from '../types';

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

function backupFilename(generatedAt?: string) {
  const stamp = new Date(generatedAt || Date.now()).toISOString().replace(/\.\d{3}Z$/, 'Z').replace(/:/g, '');
  return `jane-local-backup-${stamp}.json`;
}

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function QueueTable({ title, items, onMarkReviewed, onArchive }: {
  title: string;
  items: ManualEvidenceDashboardQueueItem[];
  onMarkReviewed?: (id: string) => void;
  onArchive?: (id: string) => void;
}) {
  return (
    <section className="pageSection">
      <h2>{title}</h2>
      <div className="tableWrap">
        <table>
          <thead><tr><th>Evidence ID</th><th>Ticker</th><th>Criterion</th><th>Status</th><th>Quality</th><th>Stale</th><th>Review date</th><th>Summary</th><th>Action</th></tr></thead>
          <tbody>
            {items.map((item) => (
              <tr key={`${title}-${item.evidence_id}`}>
                <td>{item.evidence_id}</td>
                <td>{item.ticker}</td>
                <td>{displayKey(item.criterion)}</td>
                <td>
                  <SignalBadge label={item.review_status} variant={item.review_status === 'reviewed' ? 'positive' : 'neutral'} />
                  <span className="smallPill">{displayKey(item.review_due_reason)}</span>
                </td>
                <td>{item.evidence_quality_score} <SignalBadge label={item.evidence_quality_label} variant={item.evidence_quality_label === 'high' ? 'positive' : item.evidence_quality_label === 'incomplete' ? 'warning' : 'neutral'} /></td>
                <td>{item.is_stale ? <span className="smallPill">stale</span> : <span className="muted">fresh</span>}{item.stale_reason && <small> {item.stale_reason}</small>}</td>
                <td>{item.next_review_due_at ?? 'None'}</td>
                <td>{item.summary}{item.adr_review_label ? <small> {item.adr_review_label}: {item.adr_evidence_type}; {item.document_title ?? 'untitled'} {item.document_date ? `dated ${item.document_date}` : 'missing document date'}{item.local_ticker ? `; local ticker ${item.local_ticker}` : ''}. {item.adr_review_guidance.join(' ')}</small> : null}{item.peer_companies.length ? <small> Peers: {joinList(item.peer_companies)}</small> : null}</td>
                <td>
                  {onMarkReviewed && <button type="button" onClick={() => onMarkReviewed(item.evidence_id)}>Mark reviewed</button>}
                  {onArchive && <button type="button" onClick={() => onArchive(item.evidence_id)}>Archive</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!items.length && <p className="muted">No evidence items for this queue.</p>}
    </section>
  );
}

export default function EvidenceDashboard() {
  const [dashboard, setDashboard] = useState<ManualEvidenceDashboard | null>(null);
  const [filters, setFilters] = useState<ManualEvidenceDashboardFilters>({ ticker: '', review_status: '', stale_only: false, has_comparison_context: null });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [backupOptions, setBackupOptions] = useState({ includeManualEvidence: true, includeCandidateWorkspace: true, includeArchivedRejected: true });
  const [backupFilenameText, setBackupFilenameText] = useState('');

  async function refresh(nextFilters = filters) {
    setLoading(true);
    setError('');
    try {
      setDashboard(await getManualEvidenceDashboard(nextFilters));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load evidence dashboard');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function markReviewed(evidenceId: string) {
    await updateManualEvidence(evidenceId, { review_status: 'reviewed' });
    await refresh();
  }

  async function archiveEvidence(evidenceId: string) {
    await archiveManualEvidence(evidenceId);
    await refresh();
  }

  async function onExportBackup() {
    setError('');
    try {
      const backup = await exportLocalBackup({
        include_manual_evidence: backupOptions.includeManualEvidence,
        include_candidate_workspace: backupOptions.includeCandidateWorkspace,
        include_evidence_dashboard: true,
        include_archived: backupOptions.includeArchivedRejected,
        include_rejected: backupOptions.includeArchivedRejected,
        format: 'json',
      });
      const filename = backupFilename(backup.backup_metadata.generated_at);
      downloadJson(filename, backup);
      setBackupFilenameText(filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to export local backup');
    }
  }

  const summary = dashboard?.summary;
  return (
    <main className="page">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Evidence Dashboard</p>
          <h1>Manual Evidence Dashboard</h1>
          <p>Local evidence inventory, review queues, stale checks, and peer context. User-provided and not independently verified.</p>
        </div>
      </header>

      <section className="pageSection">
        <h2>Filters</h2>
        <div className="tickerForm">
          <label htmlFor="dashboardTicker">Ticker</label>
          <input id="dashboardTicker" value={filters.ticker ?? ''} onChange={(event) => setFilters({ ...filters, ticker: event.target.value })} />
          <label htmlFor="dashboardReviewStatus">Review status</label>
          <select id="dashboardReviewStatus" value={filters.review_status ?? ''} onChange={(event) => setFilters({ ...filters, review_status: event.target.value })}>
            <option value="">All</option>
            {['unreviewed', 'reviewed', 'rejected', 'archived'].map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <label htmlFor="dashboardComparison">Comparison context</label>
          <select
            id="dashboardComparison"
            value={filters.has_comparison_context === null || filters.has_comparison_context === undefined ? '' : String(filters.has_comparison_context)}
            onChange={(event) => setFilters({ ...filters, has_comparison_context: event.target.value === '' ? null : event.target.value === 'true' })}
          >
            <option value="">All</option>
            <option value="true">With comparison</option>
            <option value="false">Without comparison</option>
          </select>
          <label className="checkLabel"><input type="checkbox" checked={Boolean(filters.stale_only)} onChange={(event) => setFilters({ ...filters, stale_only: event.target.checked })} /> Stale only</label>
          <button type="button" onClick={() => refresh()} disabled={loading}>{loading ? 'Loading...' : 'Apply filters'}</button>
        </div>
      </section>

      {error && <p className="errorText">{error}</p>}

      <section className="pageSection">
        <h2>Local Backup Export</h2>
        <p className="muted">Backup contains local user-provided evidence and workspace metadata. It does not verify claims.</p>
        <div className="filterBar">
          <label><input type="checkbox" checked={backupOptions.includeManualEvidence} onChange={(event) => setBackupOptions({ ...backupOptions, includeManualEvidence: event.target.checked })} /> Include manual evidence</label>
          <label><input type="checkbox" checked={backupOptions.includeCandidateWorkspace} onChange={(event) => setBackupOptions({ ...backupOptions, includeCandidateWorkspace: event.target.checked })} /> Include candidate workspace</label>
          <label><input type="checkbox" checked={backupOptions.includeArchivedRejected} onChange={(event) => setBackupOptions({ ...backupOptions, includeArchivedRejected: event.target.checked })} /> Include archived/rejected</label>
          <button type="button" onClick={onExportBackup}>Export Local Backup JSON</button>
        </div>
        {backupFilenameText && <p className="muted">Generated filename: {backupFilenameText}</p>}
      </section>

      {summary && (
        <section className="pageSection">
          <h2>Summary</h2>
          <div className="scoreGrid">
            <SummaryCard label="Total evidence" value={summary.total_evidence_count} />
            <SummaryCard label="Active evidence" value={summary.active_evidence_count} />
            <SummaryCard label="Stale evidence" value={summary.stale_count} />
            <SummaryCard label="Review overdue" value={summary.review_overdue_count} />
            <SummaryCard label="Reviewed / unreviewed" value={`${summary.reviewed_count} / ${summary.unreviewed_count}`} />
            <SummaryCard label="Comparison evidence" value={summary.comparison_evidence_count} />
            <SummaryCard label="Tickers covered" value={summary.tickers_covered_count} />
          </div>
        </section>
      )}

      <section className="pageSection">
        <h2>Ticker Summaries</h2>
        <div className="tableWrap">
          <table>
            <thead><tr><th>Ticker</th><th>Active</th><th>Stale</th><th>Review overdue</th><th>Covered</th><th>Missing</th><th>Peers</th><th>Highest quality</th></tr></thead>
            <tbody>
              {dashboard?.ticker_summaries.map((item) => (
                <tr key={item.ticker}>
                  <td>{item.ticker}</td>
                  <td>{item.active_evidence_count}</td>
                  <td>{item.stale_count}</td>
                  <td>{item.review_overdue_count}</td>
                  <td>{joinList(item.criteria_covered.map(displayKey))}</td>
                  <td>{joinList(item.criteria_missing.map(displayKey))}</td>
                  <td>{joinList(item.peer_companies_mentioned)}</td>
                  <td><SignalBadge label={item.highest_quality_label} variant={item.highest_quality_label === 'high' ? 'positive' : item.highest_quality_label === 'incomplete' ? 'warning' : 'neutral'} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!dashboard?.ticker_summaries.length && <p className="muted">No ticker summaries for this filter.</p>}
      </section>

      <QueueTable title="Review Queue" items={dashboard?.review_queue ?? []} onMarkReviewed={markReviewed} onArchive={archiveEvidence} />
      <QueueTable title="Stale Queue" items={dashboard?.stale_queue ?? []} onMarkReviewed={markReviewed} onArchive={archiveEvidence} />

      <section className="pageSection">
        <h2>Peer Company Index</h2>
        <div className="tableWrap">
          <table>
            <thead><tr><th>Peer</th><th>Evidence</th><th>Tickers</th><th>Criteria</th><th>Comparison types</th><th>Advantage claims</th></tr></thead>
            <tbody>
              {dashboard?.peer_company_index.map((item) => (
                <tr key={item.peer_company}>
                  <td>{item.peer_company}</td>
                  <td>{item.evidence_count}</td>
                  <td>{joinList(item.tickers)}</td>
                  <td>{joinList(item.criteria.map(displayKey))}</td>
                  <td>{joinList(item.comparison_types.map(displayKey))}</td>
                  <td>{Object.entries(item.claimed_advantage_breakdown).map(([key, value]) => `${key}: ${value}`).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!dashboard?.peer_company_index.length && <p className="muted">No peer companies from comparison context for this filter.</p>}
      </section>
    </main>
  );
}
