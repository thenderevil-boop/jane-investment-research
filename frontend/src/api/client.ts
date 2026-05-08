import type { ApiError, CandidateAnalyzeResponse, CandidateDashboard, CandidateFilters, CandidateResearchItem, CandidateResearchItemCreate, DailyReport, ManualEvidenceDashboard, ManualEvidenceDashboardFilters, ManualQualitativeEvidence, ManualQualitativeEvidenceCreate, QualitativeEvidenceInput, ResearchContext, StockAnalysis } from '../types';

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

export function listManualEvidence(ticker?: string, reviewStatus?: string): Promise<ManualQualitativeEvidence[]> {
  const params = new URLSearchParams();
  if (ticker?.trim()) params.set('ticker', ticker.trim().toUpperCase());
  if (reviewStatus?.trim()) params.set('review_status', reviewStatus.trim());
  const query = params.toString() ? `?${params.toString()}` : '';
  return request<ManualQualitativeEvidence[]>(`/api/manual-evidence${query}`);
}

export function getManualEvidenceDashboard(filters: ManualEvidenceDashboardFilters = {}): Promise<ManualEvidenceDashboard> {
  const params = new URLSearchParams();
  if (filters.ticker?.trim()) params.set('ticker', filters.ticker.trim().toUpperCase());
  if (filters.review_status?.trim()) params.set('review_status', filters.review_status.trim());
  if (filters.criterion?.trim()) params.set('criterion', filters.criterion.trim());
  if (filters.stale_only) params.set('stale_only', 'true');
  if (filters.review_due_only) params.set('review_due_only', 'true');
  if (filters.has_comparison_context !== undefined && filters.has_comparison_context !== null) params.set('has_comparison_context', String(filters.has_comparison_context));
  if (filters.include_archived) params.set('include_archived', 'true');
  if (filters.include_rejected) params.set('include_rejected', 'true');
  if (filters.min_quality_label) params.set('min_quality_label', filters.min_quality_label);
  const query = params.toString() ? `?${params.toString()}` : '';
  return request<ManualEvidenceDashboard>(`/api/manual-evidence/dashboard${query}`);
}

function candidateQuery(filters: CandidateFilters = {}) {
  const params = new URLSearchParams();
  if (filters.include_archived) params.set('include_archived', 'true');
  if (filters.ticker?.trim()) params.set('ticker', filters.ticker.trim().toUpperCase());
  if (filters.status) params.set('status', filters.status);
  if (filters.priority) params.set('priority', filters.priority);
  if (filters.tag?.trim()) params.set('tag', filters.tag.trim());
  if (filters.stale_evidence_only) params.set('stale_evidence_only', 'true');
  return params.toString() ? `?${params.toString()}` : '';
}

export function listCandidates(filters: CandidateFilters = {}): Promise<CandidateResearchItem[]> {
  return request<CandidateResearchItem[]>(`/api/candidates${candidateQuery(filters)}`);
}

export function getCandidate(candidateId: string): Promise<CandidateResearchItem> {
  return request<CandidateResearchItem>(`/api/candidates/${encodeURIComponent(candidateId)}`);
}

export function createCandidate(payload: CandidateResearchItemCreate): Promise<CandidateResearchItem> {
  return request<CandidateResearchItem>('/api/candidates', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, ticker: payload.ticker.trim().toUpperCase(), market: 'US' }),
  });
}

export function updateCandidate(candidateId: string, patch: Partial<CandidateResearchItem>): Promise<CandidateResearchItem> {
  return request<CandidateResearchItem>(`/api/candidates/${encodeURIComponent(candidateId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
}

export function archiveCandidate(candidateId: string): Promise<CandidateResearchItem> {
  return request<CandidateResearchItem>(`/api/candidates/${encodeURIComponent(candidateId)}`, { method: 'DELETE' });
}

export function refreshCandidateEvidenceSummary(candidateId: string): Promise<CandidateResearchItem> {
  return request<CandidateResearchItem>(`/api/candidates/${encodeURIComponent(candidateId)}/refresh-evidence-summary`, { method: 'POST' });
}

export function analyzeCandidate(candidateId: string, payload: { refresh_evidence_summary?: boolean; qualitative_evidence?: QualitativeEvidenceInput[] } = {}, signal?: AbortSignal): Promise<CandidateAnalyzeResponse> {
  return request<CandidateAnalyzeResponse>(`/api/candidates/${encodeURIComponent(candidateId)}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({ refresh_evidence_summary: true, ...payload }),
  });
}

export function getCandidateDashboard(filters: CandidateFilters = {}): Promise<CandidateDashboard> {
  return request<CandidateDashboard>(`/api/candidates/dashboard${candidateQuery({ include_archived: filters.include_archived })}`);
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
