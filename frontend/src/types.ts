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
  macro?: {
    provider?: string;
    live_macro_fields_count?: number;
    derived_macro_fields_count?: number;
    mock_macro_fields_count?: number;
    has_mock_macro_context?: boolean;
    mock_context_fields?: string[];
    fred_backed_fields?: string[];
    derived_from_fred_fields?: string[];
    yfinance_backed_fields?: string[];
    derived_from_yfinance_fields?: string[];
    excluded_indicators?: Record<string, unknown>[];
    scoring?: Record<string, unknown>;
    yfinance_macro_fields_count?: number;
    market_context_reused_from_daily_market_data?: boolean;
    confidence_adjustment_applied?: boolean;
  } | null;
};

export type CandidateValidationSummary = {
  ticker: string;
  research_priority: 'worth_deep_research' | 'watchlist_candidate' | 'insufficient_data' | 'high_risk_context';
  score: number;
  confidence: number;
  environment_assessment: string;
  company_assessment: string;
  smart_money_assessment: string;
  data_quality_assessment: string;
  overall_summary: string;
  primary_strengths: string[];
  primary_risks: string[];
  missing_or_mock_evidence: string[];
  next_manual_checks: string[];
};

export type EvidenceMatrixItem = {
  category: string;
  status: 'supportive' | 'neutral' | 'caution' | 'insufficient';
  score?: number | null;
  confidence: number;
  source_quality: 'live_backed' | 'derived_live' | 'cached_live' | 'mixed_with_fallback' | 'mock_only' | 'insufficient';
  summary: string;
  key_evidence: string[];
  limitations: string[];
};

export type AnalyzeStockDataQualitySummary = {
  mode: 'live_with_fallback' | 'mixed_preliminary' | 'mostly_mock' | 'insufficient';
  confidence_cap_applied: boolean;
  confidence_cap_reason?: string | null;
  live_components: number;
  mock_components: number;
  fallback_components: number;
  missing_source_date_components: number;
  stale_components: number;
  source_quality_grade: 'A' | 'B' | 'C' | 'D';
  source_quality_summary: string;
  mock_evidence_categories: string[];
  fallback_evidence_categories: string[];
  missing_source_date_categories: string[];
  excluded_from_scoring: string[];
};

export type ScoreDriver = {
  name: string;
  category: string;
  effect: 'positive' | 'limiting' | 'negative' | 'insufficient';
  source_quality: string;
  summary: string;
};

export type ScoreDriverBreakdown = {
  final_score: number;
  final_confidence: number;
  positive_drivers: ScoreDriver[];
  negative_or_limiting_drivers: ScoreDriver[];
  neutral_drivers: ScoreDriver[];
};

export type NextManualCheck = {
  priority: 'high' | 'medium' | 'low';
  area: 'company_fundamentals' | 'leadership' | 'filings' | 'smart_money' | 'valuation' | 'risk' | 'source_quality';
  check: string;
  reason: string;
};

export type JaneReferenceCondition = {
  name: string;
  display_text: string;
  system_status: string;
  mapped_system_fields: string[];
  score_contribution_allowed: boolean;
  limitation?: string | null;
};

export type JaneReferenceConditions = {
  title: string;
  source_type?: string;
  affects_score: boolean;
  not_investment_advice: boolean;
  conditions: JaneReferenceCondition[];
  limitations: string[];
};

export type MacroScoreComponent = {
  name: string;
  display_name: string;
  weight: number;
  raw_value?: unknown;
  component_score?: number;
  weighted_contribution?: number;
  source_type?: SourceType | string;
  provider?: string;
  source_date?: string;
  freshness_window?: string;
  is_fresh?: boolean;
  limitation?: string | null;
};

export type MacroScoreGroup = {
  name: string;
  display_name: string;
  weight: number;
  weighted_contribution_sum: number;
  components: MacroScoreComponent[];
};

export type MacroExcludedIndicator = {
  name: string;
  display_name?: string;
  reason?: string;
  affects_score: boolean;
  weight: number;
};

export type MacroConfidenceExplanation = {
  confidence: number;
  basis: Record<string, unknown>;
  deductions: Array<{
    reason: string;
    amount: number;
    affected_components: string[];
  }>;
  max_confidence: number;
};

export type MacroScoreExplanation = {
  scoring_model_version: string;
  score: number;
  max_score: number;
  label: string;
  confidence: number;
  active_weight_total: number;
  weighted_contribution_sum: number;
  rounding_difference: number;
  rounding_tolerance: number;
  groups: MacroScoreGroup[];
  excluded_indicators: MacroExcludedIndicator[];
  confidence_basis: Record<string, unknown>;
  confidence_explanation?: MacroConfidenceExplanation;
  limitations: string[];
};

export type DailyReportMetadata = {
  read_mode: string;
  snapshot_used: boolean;
  snapshot_id?: string | null;
  snapshot_generated_at?: string | null;
  snapshot_is_fresh: boolean;
  batch_refresh_status: string;
  batch_refresh_started_at?: string | null;
  batch_refresh_completed_at?: string | null;
  batch_duration_ms?: number | null;
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
  macro_data_quality?: Record<string, unknown> | null;
  macro_score_explanation?: MacroScoreExplanation | null;
  components?: unknown[];
  criteria?: unknown[];
};

export type FutureTheme = ScoreLike & {
  theme?: string;
  candidate_companies?: string[];
};

export type Candidate13FSpecificEvidence = {
  ticker?: string | null;
  resolved_ticker?: string | null;
  resolved_cusip?: string | null;
  resolved_issuer_name?: string | null;
  local_security_map_used?: boolean | null;
  matched_in_13f?: boolean | null;
  match_confidence?: string | null;
  match_method?: string | null;
  position_value_usd?: number | null;
  position_shares_or_principal_amount?: number | null;
  portfolio_weight_pct?: number | null;
  source_date?: string | null;
  report_date?: string | null;
  filing_date?: string | null;
  latest_report_date?: string | null;
  latest_filing_date?: string | null;
  manager_cik?: string | null;
  manager_name?: string | null;
  manager_metadata_source?: string | null;
  value_unit_confidence_summary?: string | null;
  interpretation_label?: string | null;
  interpretation_summary?: string | null;
  score_contribution_allowed?: boolean | null;
};

export type Candidate13FPortfolioContext = {
  manager_cik?: string | null;
  manager_name?: string | null;
  manager_metadata_source?: string | null;
  latest_report_date?: string | null;
  latest_filing_date?: string | null;
  holding_count_grouped?: number | null;
  mapped_holding_count?: number | null;
  top_holdings_by_value?: Record<string, unknown>[];
  source_status?: DataSourceStatus | Record<string, unknown> | null;
};

export type Candidate13FEvidence = {
  source_status?: DataSourceStatus | Record<string, unknown> | null;
  candidate_specific_evidence?: Candidate13FSpecificEvidence | Record<string, unknown> | null;
  target_matches?: Record<string, unknown>[];
  portfolio_context?: Candidate13FPortfolioContext | Record<string, unknown> | null;
  limitations?: string[];
  missing_data?: string[];
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
  institutional_13f?: Candidate13FEvidence | Record<string, unknown> | null;
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
  jane_reference_conditions?: JaneReferenceConditions | null;
  limitations?: string[];
  missing_data?: string[];
  human_verification_queue?: string[];
  data_quality?: DataQualitySummary | null;
  source_status?: DataSourceStatus | null;
  daily_report_metadata?: DailyReportMetadata | null;
  not_investment_advice?: boolean;
};

export type ResearchContext = {
  theme?: string;
  user_reason?: string;
};

export type ResearchVerdict = {
  label: 'worth_deep_research' | 'watchlist_candidate' | 'insufficient_data' | 'high_risk_context';
  score: number;
  confidence: number;
  summary: string;
  confidence_factors?: {
    confidence_boosters: string[];
    confidence_limiters: string[];
  };
};

export type StockAnalysis = {
  ticker: string;
  market: string;
  analysis_mode?: 'ticker_validation';
  research_verdict?: ResearchVerdict;
  candidate_validation_summary?: CandidateValidationSummary;
  evidence_matrix?: EvidenceMatrixItem[];
  data_quality_summary?: AnalyzeStockDataQualitySummary;
  score_driver_breakdown?: ScoreDriverBreakdown;
  next_manual_checks?: NextManualCheck[];
  company_profile?: Record<string, unknown>;
  macro_regime?: ScoreLike;
  leadership_score?: ScoreLike;
  market_timing_context?: ScoreLike;
  overheat_risk?: ScoreLike;
  smart_money?: ScoreLike;
  insider_activity?: ScoreLike;
  institutional_13f?: ScoreLike;
  financial_quality?: ScoreLike;
  valuation_context?: ScoreLike;
  risk_flags?: string[];
  jane_reference_conditions?: JaneReferenceConditions | null;
  missing_data?: string[];
  human_verification_queue?: string[];
  data_quality?: DataQualitySummary | null;
  source_status?: DataSourceStatus | null;
  not_investment_advice?: boolean;
};

export type ApiError = Error & {
  status?: number;
};
