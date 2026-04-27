import type { ApiError, DailyReport, StockAnalysis } from '../types';

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

export function analyzeStock(ticker: string): Promise<StockAnalysis> {
  return request<StockAnalysis>('/api/analyze-stock', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ticker: ticker.trim().toUpperCase(),
      market: 'US',
      period: '3Y',
      user_context: {
        friends_asking_about_stock: false,
        social_discussion_level: 'low',
      },
    }),
  });
}
