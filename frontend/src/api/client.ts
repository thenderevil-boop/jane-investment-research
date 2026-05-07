import type { ApiError, DailyReport, ManualQualitativeEvidence, ManualQualitativeEvidenceCreate, QualitativeEvidenceInput, ResearchContext, StockAnalysis } from '../types';

async function parseJson<T>(response: Response): Promise<T> {
  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    const error = new Error('Malformed response: expected JSON') as ApiError;
    error.status = response.status;
    throw error;
  }
  return response.json() as Promise<T>;
}

function formatErrorDetail(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') return fallback;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === 'object' && item ? Object.values(item).filter((value) => typeof value === 'string').join(' ') : String(item)))
      .filter(Boolean)
      .join('; ') || fallback;
  }
  if (detail && typeof detail === 'object') {
    const error = (detail as { error?: unknown }).error;
    if (typeof error === 'string') return error;
    return JSON.stringify(detail);
  }
  return fallback;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw err;
    }
    throw new Error('Network error: backend is not reachable');
  }

  if (response.status === 404) {
    const error = new Error('Endpoint not available yet') as ApiError;
    error.status = 404;
    throw error;
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      if ((response.headers.get('content-type') ?? '').includes('application/json')) {
        message = formatErrorDetail(await response.json(), message);
      }
    } catch {
      // Keep the status-based fallback if the backend returns a malformed error.
    }
    const error = new Error(message) as ApiError;
    error.status = response.status;
    throw error;
  }

  return parseJson<T>(response);
}

export function getLatestDailyReport(): Promise<DailyReport> {
  return request<DailyReport>('/api/daily-report/latest');
}

export function listManualEvidence(ticker?: string): Promise<ManualQualitativeEvidence[]> {
  const query = ticker?.trim() ? `?ticker=${encodeURIComponent(ticker.trim().toUpperCase())}` : '';
  return request<ManualQualitativeEvidence[]>(`/api/manual-evidence${query}`);
}

export function createManualEvidence(payload: ManualQualitativeEvidenceCreate): Promise<ManualQualitativeEvidence> {
  return request<ManualQualitativeEvidence>('/api/manual-evidence', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function updateManualEvidence(evidenceId: string, patch: Partial<ManualQualitativeEvidence>): Promise<ManualQualitativeEvidence> {
  return request<ManualQualitativeEvidence>(`/api/manual-evidence/${encodeURIComponent(evidenceId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
}

export function archiveManualEvidence(evidenceId: string): Promise<ManualQualitativeEvidence> {
  return request<ManualQualitativeEvidence>(`/api/manual-evidence/${encodeURIComponent(evidenceId)}`, { method: 'DELETE' });
}

export function analyzeStock(ticker: string, researchContext?: ResearchContext, qualitativeEvidence?: QualitativeEvidenceInput[], signal?: AbortSignal): Promise<StockAnalysis> {
  const trimmedEvidence = qualitativeEvidence?.length ? qualitativeEvidence : undefined;
  return request<StockAnalysis>('/api/analyze-stock', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      ticker: ticker.trim().toUpperCase(),
      market: 'US',
      research_context: {
        theme: researchContext?.theme?.trim() || undefined,
        user_reason: researchContext?.user_reason?.trim() || undefined,
      },
      user_context: {
        friends_asking_about_stock: false,
        social_discussion_level: 'low',
      },
      qualitative_evidence: trimmedEvidence,
    }),
  });
}
