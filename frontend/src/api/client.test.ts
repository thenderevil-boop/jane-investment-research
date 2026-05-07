import { afterEach, describe, expect, it, vi } from 'vitest';
import { analyzeStock, archiveManualEvidence, createManualEvidence, getLatestDailyReport, listManualEvidence, updateManualEvidence } from './client';

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

  it('sends qualitative evidence in analyze-stock requests', async () => {
    const fetchMock = vi.fn(async () => new Response('{"ticker":"NVDA","market":"US"}', { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
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
    );
    const calls = (fetchMock as unknown as { mock: { calls: Array<[string, RequestInit]> } }).mock.calls;
    const init = calls[0][1];
    const body = JSON.parse(String(init.body));
    expect(body.ticker).toBe('NVDA');
    expect(body.qualitative_evidence).toHaveLength(1);
    expect(body.qualitative_evidence[0].criterion).toBe('network_effect');
  });

  it('calls manual evidence library endpoints', async () => {
    const fetchMock = vi.fn(async () => new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    const calls = (fetchMock as unknown as { mock: { calls: Array<[string, RequestInit | undefined]> } }).mock.calls;
    await listManualEvidence('nvda');
    expect(calls[0][0]).toBe('/api/manual-evidence?ticker=NVDA');

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
});
