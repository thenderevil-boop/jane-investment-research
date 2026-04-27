import { afterEach, describe, expect, it, vi } from 'vitest';
import { getLatestDailyReport } from './client';

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
});
