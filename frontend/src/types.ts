export type SourceType = 'live' | 'cached_live' | 'mock' | 'fallback' | 'derived' | 'unknown';

export type DataSourceStatus = {
  source_type: SourceType;
  provider: string;
  source_date: string;
  fetched_at?: string | null;
  is_fresh: boolean;
  freshness_window: string;
  fallback_used: boolean;
  fallback_reason?: string | null;
  limitations: string[];
  missing_data: string[];
};

export type DataQualitySummary = {
  mode: 'all_mock' | 'mixed' | 'mostly_live' | 'live_with_fallback';
  live_components: number;
  mock_components: number;
  fallback_components: number;
  stale_components: number;
  missing_source_date_components?: number;
  limitations: string[];
};

export type ScoreLike = {
  name?: string;
  title?: string;
  score?: number;
  max_score?: number;
  maxScore?: number;
  label?: string;
  confidence?: number;
  raw_data?: Record<string, unknown>;
  derived_metrics?: Record<string, unknown>;
  benchmark?: Record<string, unknown>;
  trend?: Record<string, unknown>;
  source?: string[];
  source_date?: string;
  limitations?: string[];
  missing_data?: string[];
  source_status?: DataSourceStatus | null;
  components?: unknown[];
  criteria?: unknown[];
};

export type FutureTheme = ScoreLike & {
  theme?: string;
  candidate_companies?: string[];
};

export type StockCandidate = {
  ticker: string;
  company_name: string;
  theme: string;
  leadership_score: number;
  smart_money_score: number;
  market_timing_score: number;
  overheat_score: number;
  risk_score: number;
  label: string;
  source: string[];
  source_date: string;
  confidence: number;
  limitations: string[];
  missing_data: string[];
  source_status?: DataSourceStatus | null;
  institutional_13f?: Record<string, unknown> | null;
};

export type RiskAllocation = {
  risk_posture?: string;
  score?: number;
  reference?: Record<string, string>;
  risk_flags?: string[];
  raw_data?: Record<string, unknown>;
  derived_metrics?: Record<string, unknown>;
  benchmark?: Record<string, unknown>;
  trend?: Record<string, unknown>;
  source?: string[];
  source_date?: string;
  confidence?: number;
  limitations?: string[];
  missing_data?: string[];
  source_status?: DataSourceStatus | null;
};

export type DailyReport = {
  date: string;
  market: string;
  report_generated_at?: string;
  macro_regime?: ScoreLike;
  market_timing?: ScoreLike;
  overheat_risk?: ScoreLike;
  crisis_risk?: ScoreLike;
  crisis?: {
    level?: string;
    confidence?: number;
    reference?: Record<string, string>;
    components?: unknown[];
    limitations?: string[];
    missing_data?: string[];
  };
  future_themes?: FutureTheme[];
  stock_candidates?: StockCandidate[];
  smart_money_summary?: ScoreLike;
  smart_money?: ScoreLike;
  risk_allocation?: RiskAllocation;
  risk_notes?: string[];
  limitations?: string[];
  missing_data?: string[];
  human_verification_queue?: string[];
  data_quality?: DataQualitySummary | null;
  not_investment_advice?: boolean;
};

export type StockAnalysis = {
  ticker: string;
  market: string;
  company_profile?: Record<string, unknown>;
  leadership_score?: ScoreLike;
  market_timing_context?: ScoreLike;
  overheat_risk?: ScoreLike;
  smart_money?: ScoreLike;
  financial_quality?: ScoreLike;
  valuation_context?: ScoreLike;
  risk_flags?: string[];
  missing_data?: string[];
  human_verification_queue?: string[];
  data_quality?: DataQualitySummary | null;
  source_status?: DataSourceStatus | null;
  not_investment_advice?: boolean;
};

export type ApiError = Error & {
  status?: number;
};
