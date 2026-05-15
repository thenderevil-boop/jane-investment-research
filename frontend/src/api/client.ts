import type { AnalyzeStockExportPayload, AnalyzeStockExportResponse, ApiError, CandidateAnalysisHistoryItem, CandidateAnalyzeResponse, CandidateDashboard, CandidateFilters, CandidateResearchItem, CandidateResearchItemCreate, CandidateReviewNote, CandidateReviewNoteCreate, DailyReport, JaneCriteriaResponse, LocalBackupExportOptions, LocalBackupExportResponse, ManualEvidenceDashboard, ManualEvidenceDashboardFilters, ManualQualitativeEvidence, ManualQualitativeEvidenceCreate, QualitativeEvidenceInput, ResearchContext, StockAnalysis } from '../types';

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

export function getJaneCriteria(): Promise<JaneCriteriaResponse> {
  return request<JaneCriteriaResponse>('/api/jane-criteria');
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
  if (filters.needs_review_only) params.set('needs_review_only', 'true');
  if (filters.has_comparison_evidence !== undefined && filters.has_comparison_evidence !== null) params.set('has_comparison_evidence', String(filters.has_comparison_evidence));
  if (filters.missing_criterion?.trim()) params.set('missing_criterion', filters.missing_criterion.trim());
  if (filters.data_quality_grade?.trim()) params.set('data_quality_grade', filters.data_quality_grade.trim().toUpperCase());
  if (filters.sort_by) params.set('sort_by', filters.sort_by);
  if (filters.sort_order) params.set('sort_order', filters.sort_order);
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

export function restoreCandidate(candidateId: string): Promise<CandidateResearchItem> {
  return request<CandidateResearchItem>(`/api/candidates/${encodeURIComponent(candidateId)}/restore`, { method: 'POST' });
}

export function addCandidateNote(candidateId: string, payload: CandidateReviewNoteCreate): Promise<CandidateReviewNote> {
  return request<CandidateReviewNote>(`/api/candidates/${encodeURIComponent(candidateId)}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, tags: payload.tags ?? [] }),
  });
}

export function getCandidateNotes(candidateId: string): Promise<CandidateReviewNote[]> {
  return request<CandidateReviewNote[]>(`/api/candidates/${encodeURIComponent(candidateId)}/notes`);
}

export function getCandidateAnalysisHistory(candidateId: string): Promise<CandidateAnalysisHistoryItem[]> {
  return request<CandidateAnalysisHistoryItem[]>(`/api/candidates/${encodeURIComponent(candidateId)}/analysis-history`);
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

export function exportAnalyzeStockReport(payload: AnalyzeStockExportPayload): Promise<AnalyzeStockExportResponse> {
  return request<AnalyzeStockExportResponse>('/api/analyze-stock/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...payload,
      ticker: payload.ticker.trim().toUpperCase(),
      market: 'US',
      research_context: {
        theme: payload.research_context?.theme?.trim() || undefined,
        user_reason: payload.research_context?.user_reason?.trim() || undefined,
      },
      qualitative_evidence: payload.qualitative_evidence?.length ? payload.qualitative_evidence : undefined,
      include_raw_evidence: payload.include_raw_evidence ?? false,
      include_manual_evidence: payload.include_manual_evidence ?? true,
      include_candidate_metadata: payload.include_candidate_metadata ?? false,
      redact_sensitive_fields: payload.redact_sensitive_fields ?? true,
    }),
  });
}

export function exportLocalBackup(options: LocalBackupExportOptions = {}): Promise<LocalBackupExportResponse> {
  const params = new URLSearchParams();
  params.set('format', options.format ?? 'json');
  if (options.include_manual_evidence !== undefined) params.set('include_manual_evidence', String(options.include_manual_evidence));
  if (options.include_candidate_workspace !== undefined) params.set('include_candidate_workspace', String(options.include_candidate_workspace));
  if (options.include_evidence_dashboard !== undefined) params.set('include_evidence_dashboard', String(options.include_evidence_dashboard));
  if (options.include_archived !== undefined) params.set('include_archived', String(options.include_archived));
  if (options.include_rejected !== undefined) params.set('include_rejected', String(options.include_rejected));
  return request<LocalBackupExportResponse>(`/api/local-backup/export?${params.toString()}`);
}
