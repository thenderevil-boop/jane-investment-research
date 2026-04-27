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
  not_investment_advice?: boolean;
};

export type ApiError = Error & {
  status?: number;
};
