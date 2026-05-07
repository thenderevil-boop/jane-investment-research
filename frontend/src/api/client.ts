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

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new Error('Network error: backend is not reachable');
  }

  if (response.status === 404) {
    const error = new Error('Endpoint not available yet') as ApiError;
    error.status = 404;
    throw error;
  }

  if (!response.ok) {
    const error = new Error(`Request failed with status ${response.status}`) as ApiError;
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

export function analyzeStock(ticker: string, researchContext?: ResearchContext, qualitativeEvidence?: QualitativeEvidenceInput[]): Promise<StockAnalysis> {
  const trimmedEvidence = qualitativeEvidence?.length ? qualitativeEvidence : undefined;
  return request<StockAnalysis>('/api/analyze-stock', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
