import { afterEach, describe, expect, it, vi } from 'vitest';
import { addCandidateNote, analyzeCandidate, analyzeStock, archiveCandidate, archiveManualEvidence, createCandidate, exportAnalyzeStockReport, exportLocalBackup, getCandidateAnalysisHistory, getCandidateDashboard, getCandidateNotes, getLatestDailyReport, getManualEvidenceDashboard, getOperationsDiagnostics, listCandidates, refreshCandidateEvidenceSummary, restoreCandidate, updateCandidate, listManualEvidence, updateManualEvidence, createManualEvidence } from './client';

describe('api client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('turns 404 into endpoint unavailable message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 404, headers: { 'content-type': 'application/json' } })));
    await expect(getLatestDailyReport()).rejects.toThrow('Endpoint not available yet');
  });

  it('rejects malformed responses', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('not-json', { status: 200, headers: { 'content-type': 'text/plain' } })));
    await expect(getLatestDailyReport()).rejects.toThrow('Malformed response');
  });

  it('uses backend JSON detail in error messages', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"detail":"evidence_id path segment is required"}', { status: 400, headers: { 'content-type': 'application/json' } })));
    await expect(getLatestDailyReport()).rejects.toThrow('evidence_id path segment is required');
  });

  it('sends qualitative evidence in analyze-stock requests', async () => {
    const fetchMock = vi.fn(async () => new Response('{"ticker":"NVDA","market":"US"}', { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    const controller = new AbortController();
    await analyzeStock(
      'nvda',
      { theme: 'AI infrastructure', user_reason: 'External trend research' },
      [
        {
          criterion: 'network_effect',
          evidence_type: 'platform_ecosystem',
          summary: 'CUDA developer ecosystem claim requiring manual verification.',
          source_label: 'User research note',
          source_url: null,
          source_date: '2026-05-06',
          confidence: 0.65,
          user_provided: true,
          limitations: ['Manual review required.'],
        },
      ],
      controller.signal,
    );
    const calls = (fetchMock as unknown as { mock: { calls: Array<[string, RequestInit]> } }).mock.calls;
    const init = calls[0][1];
    const body = JSON.parse(String(init.body));
    expect(body.ticker).toBe('NVDA');
    expect(body.qualitative_evidence).toHaveLength(1);
    expect(body.qualitative_evidence[0].criterion).toBe('network_effect');
    expect(init.signal).toBe(controller.signal);
  });

  it('calls operations diagnostics endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response('{"version":"phase62_operations_diagnostics_v1","providers":[],"coverage_readiness":[],"not_investment_advice":true}', { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    await getOperationsDiagnostics();
    expect(fetchMock).toHaveBeenCalledWith('/api/operations/diagnostics', undefined);
  });

  it('calls manual evidence library endpoints', async () => {
    const fetchMock = vi.fn(async () => new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    const calls = (fetchMock as unknown as { mock: { calls: Array<[string, RequestInit | undefined]> } }).mock.calls;
    await listManualEvidence('nvda', 'reviewed');
    expect(calls[0][0]).toBe('/api/manual-evidence?ticker=NVDA&review_status=reviewed');

    fetchMock.mockResolvedValueOnce(new Response('{"evidence_id":"manual_1"}', { status: 200, headers: { 'content-type': 'application/json' } }));
    await createManualEvidence({
      ticker: 'NVDA',
      criterion: 'network_effect',
      evidence_type: 'platform_ecosystem',
      summary: 'CUDA developer ecosystem claim requiring manual verification.',
      source_label: 'User research note',
      source_url: null,
      source_date: '2026-05-06',
      confidence: 0.65,
      review_status: 'unreviewed',
      created_by: 'local_user',
      limitations: ['Manual review required.'],
      tags: ['CUDA'],
    });
    expect(calls[1][0]).toBe('/api/manual-evidence');

    fetchMock.mockResolvedValueOnce(new Response('{"evidence_id":"manual_1","review_status":"reviewed"}', { status: 200, headers: { 'content-type': 'application/json' } }));
    await updateManualEvidence('manual_1', { review_status: 'reviewed' });
    expect(calls[2][0]).toBe('/api/manual-evidence/manual_1');

    fetchMock.mockResolvedValueOnce(new Response('{"evidence_id":"manual_1","review_status":"archived"}', { status: 200, headers: { 'content-type': 'application/json' } }));
    await archiveManualEvidence('manual_1');
    expect(calls[3][0]).toBe('/api/manual-evidence/manual_1');
    expect(calls[3][1]?.method).toBe('DELETE');
  });

  it('calls manual evidence dashboard with filters', async () => {
    const fetchMock = vi.fn(async () => new Response('{"summary":{},"ticker_summaries":[],"review_queue":[],"stale_queue":[],"audit_queue":[],"peer_company_index":[]}', { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    await getManualEvidenceDashboard({ ticker: 'nvda', review_status: 'unreviewed', stale_only: true, has_comparison_context: true });
    const calls = (fetchMock as unknown as { mock: { calls: Array<[string, RequestInit | undefined]> } }).mock.calls;
    expect(calls[0][0]).toBe('/api/manual-evidence/dashboard?ticker=NVDA&review_status=unreviewed&stale_only=true&has_comparison_context=true');
  });

  it('calls export endpoints with normalized payload and options', async () => {
    const fetchMock = vi.fn(async () => new Response('{"export_id":"export_1","generated_at":"2026-05-09T15:01:06Z","ticker":"NVDA","format":"json","filename":"jane-validation-NVDA-2026-05-09T150106Z.json","content_type":"application/json","report":{},"source_status":{"source_type":"derived","provider":"analyze_stock_export","source_date":"2026-05-09T15:01:06Z","is_fresh":true,"freshness_window":"export_generated_at","fallback_used":false,"limitations":[],"missing_data":[]},"not_investment_advice":true}', { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    await exportAnalyzeStockReport({
      ticker: 'nvda',
      format: 'json',
      research_context: { theme: 'AI infrastructure', user_reason: 'External trend research' },
      include_raw_evidence: true,
      include_manual_evidence: true,
    });
    let calls = (fetchMock as unknown as { mock: { calls: Array<[string, RequestInit | undefined]> } }).mock.calls;
    expect(calls[0][0]).toBe('/api/analyze-stock/export');
    expect(JSON.parse(String(calls[0][1]?.body)).ticker).toBe('NVDA');
    expect(JSON.parse(String(calls[0][1]?.body)).include_raw_evidence).toBe(true);

    fetchMock.mockResolvedValueOnce(new Response('{"backup_metadata":{"backup_id":"backup_1","generated_at":"2026-05-09T15:01:06Z","schema_version":"phase25_local_backup_v1","not_investment_advice":true,"limitations":[]},"source_status":{"source_type":"derived","provider":"local_backup_export","source_date":"2026-05-09T15:01:06Z","is_fresh":true,"freshness_window":"local_export_generated_at","fallback_used":false,"limitations":[],"missing_data":[]},"not_investment_advice":true}', { status: 200, headers: { 'content-type': 'application/json' } }));
    await exportLocalBackup({ include_archived: false, include_rejected: false });
    calls = (fetchMock as unknown as { mock: { calls: Array<[string, RequestInit | undefined]> } }).mock.calls;
    expect(calls[1][0]).toBe('/api/local-backup/export?format=json&include_archived=false&include_rejected=false');
  });

  it('calls candidate workspace endpoints', async () => {
    const fetchMock = vi.fn(async () => new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    const calls = (fetchMock as unknown as { mock: { calls: Array<[string, RequestInit | undefined]> } }).mock.calls;

    await listCandidates({ ticker: 'nvda', priority: 'high', stale_evidence_only: true, needs_review_only: true, has_comparison_evidence: true, sort_by: 'latest_score', sort_order: 'desc' });
    expect(calls[0][0]).toBe('/api/candidates?ticker=NVDA&priority=high&stale_evidence_only=true&needs_review_only=true&has_comparison_evidence=true&sort_by=latest_score&sort_order=desc');

    fetchMock.mockResolvedValueOnce(new Response('{"candidate_id":"candidate_1","ticker":"NVDA"}', { status: 200, headers: { 'content-type': 'application/json' } }));
    await createCandidate({ ticker: 'nvda', theme: 'AI infrastructure', priority: 'high', tags: ['AI'] });
    expect(calls[1][0]).toBe('/api/candidates');
    expect(JSON.parse(String(calls[1][1]?.body)).ticker).toBe('NVDA');

    fetchMock.mockResolvedValueOnce(new Response('{"candidate_id":"candidate_1","status":"reviewed"}', { status: 200, headers: { 'content-type': 'application/json' } }));
    await updateCandidate('candidate_1', { status: 'reviewed' });
    expect(calls[2][0]).toBe('/api/candidates/candidate_1');

    fetchMock.mockResolvedValueOnce(new Response('{"candidate_id":"candidate_1"}', { status: 200, headers: { 'content-type': 'application/json' } }));
    await refreshCandidateEvidenceSummary('candidate_1');
    expect(calls[3][0]).toBe('/api/candidates/candidate_1/refresh-evidence-summary');

    fetchMock.mockResolvedValueOnce(new Response('{"candidate":{"candidate_id":"candidate_1"},"analysis":{}}', { status: 200, headers: { 'content-type': 'application/json' } }));
    const controller = new AbortController();
    await analyzeCandidate('candidate_1', { refresh_evidence_summary: true }, controller.signal);
    expect(calls[4][0]).toBe('/api/candidates/candidate_1/analyze');
    expect(calls[4][1]?.signal).toBe(controller.signal);

    fetchMock.mockResolvedValueOnce(new Response('{"candidate_id":"candidate_1","status":"archived"}', { status: 200, headers: { 'content-type': 'application/json' } }));
    await archiveCandidate('candidate_1');
    expect(calls[5][1]?.method).toBe('DELETE');

    fetchMock.mockResolvedValueOnce(new Response('{"candidate_id":"candidate_1","status":"watching"}', { status: 200, headers: { 'content-type': 'application/json' } }));
    await restoreCandidate('candidate_1');
    expect(calls[6][0]).toBe('/api/candidates/candidate_1/restore');

    fetchMock.mockResolvedValueOnce(new Response('{"note_id":"note_1","note":"Needs source review."}', { status: 200, headers: { 'content-type': 'application/json' } }));
    await addCandidateNote('candidate_1', { note: 'Needs source review.', note_type: 'general', tags: ['review'] });
    expect(calls[7][0]).toBe('/api/candidates/candidate_1/notes');

    fetchMock.mockResolvedValueOnce(new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }));
    await getCandidateNotes('candidate_1');
    expect(calls[8][0]).toBe('/api/candidates/candidate_1/notes');

    fetchMock.mockResolvedValueOnce(new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }));
    await getCandidateAnalysisHistory('candidate_1');
    expect(calls[9][0]).toBe('/api/candidates/candidate_1/analysis-history');

    fetchMock.mockResolvedValueOnce(new Response('{"summary":{},"items":[],"review_queue":[]}', { status: 200, headers: { 'content-type': 'application/json' } }));
    await getCandidateDashboard({ include_archived: true });
    expect(calls[10][0]).toBe('/api/candidates/dashboard?include_archived=true');
  });
});
