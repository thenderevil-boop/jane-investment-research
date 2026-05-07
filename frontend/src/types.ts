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
  source_quality: 'live_backed' | 'derived_live' | 'cached_live' | 'mixed_with_fallback' | 'user_context' | 'user_provided' | 'mock_only' | 'filing_backed' | 'provider_backed' | 'derived_from_mixed_sources' | 'insufficient';
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
  insufficient_evidence_categories?: string[];
  company_quality?: {
    evidence_backed_criteria_count: number;
    insufficient_criteria_count: number;
    mock_criteria_count: number;
    derived_live_criteria_count: number;
    user_context_criteria_count: number;
    user_provided_criteria_count?: number;
    filing_backed_criteria_count?: number;
    mixed_source_criteria_count?: number;
  };
  qualitative_evidence?: {
    provided: boolean;
    accepted_count: number;
    rejected_count: number;
    user_provided_count: number;
    independently_verified_count: number;
    saved_library_count?: number;
    request_scoped_count?: number;
    reviewed_count?: number;
    unreviewed_count?: number;
    reviewed_active_count?: number;
    unreviewed_active_count?: number;
    stale_count?: number;
    review_due_count?: number;
    quality_score_average?: number | null;
    high_quality_count?: number;
    medium_quality_count?: number;
    low_quality_count?: number;
    incomplete_count?: number;
    archived_or_rejected_ignored_count?: number;
    criteria_covered: string[];
    criteria_still_insufficient: string[];
    comparison?: {
      provided: boolean;
      accepted_count: number;
      reviewed_count: number;
      stale_count: number;
      peer_company_count: number;
      criteria_supported: string[];
      claimed_advantage_breakdown: Record<string, number>;
    };
  };
  sec_companyfacts?: {
    available: boolean;
    source_type: SourceType | 'insufficient';
    filing_backed_metric_count: number;
    missing_concept_count: number;
    latest_filing_date?: string | null;
    latest_report_period?: string | null;
    agreement_level_with_yfinance: 'high' | 'moderate' | 'low' | 'insufficient';
  };
};

export type JaneCompanyQualityCriterion = {
  name: string;
  display_name: string;
  score?: number | null;
  max_score: number;
  status: 'supportive' | 'neutral' | 'caution' | 'insufficient';
  source_quality: 'live_backed' | 'derived_live' | 'cached_live' | 'user_context' | 'user_provided' | 'filing_backed' | 'derived_from_mixed_sources' | 'insufficient' | 'mock_only';
  affects_score: boolean;
  evidence_strength?: 'none' | 'weak' | 'moderate' | 'strong';
  verification_level?: 'user_provided' | 'filing_backed' | 'derived_live' | 'independently_verified' | 'insufficient';
  evidence: string[];
  limitations: string[];
  missing_data: string[];
  evidence_quality_score?: number;
  evidence_quality_label?: 'high' | 'medium' | 'low' | 'incomplete';
  evidence_quality_reasons?: string[];
  is_stale?: boolean;
  stale_reason?: string | null;
  next_review_due_at?: string | null;
  source_reliability_label?: string;
};

export type JaneCompanyQuality = {
  name: string;
  score: number;
  max_score: number;
  confidence: number;
  label: 'evidence_backed' | 'preliminary' | 'insufficient_data';
  criteria: JaneCompanyQualityCriterion[];
  source_status: DataSourceStatus;
  limitations: string[];
  missing_data: string[];
};

export type FinancialStatementSignal = {
  name: string;
  status: 'supportive' | 'neutral' | 'caution' | 'insufficient';
  source_quality: 'live_backed' | 'derived_live' | 'filing_backed' | 'yfinance_backed' | 'derived_from_mixed_sources' | 'insufficient';
  evidence: string[];
  limitations: string[];
  missing_data: string[];
};

export type FinancialStatementSignals = {
  score: number;
  confidence: number;
  label: 'strong' | 'adequate' | 'caution' | 'insufficient';
  signals: FinancialStatementSignal[];
  source_status: DataSourceStatus;
  limitations: string[];
  missing_data: string[];
};

export type JaneQualityMethodologyReference = {
  framework: string;
  principles: string[];
  affects_score: boolean;
  limitations: string[];
};

export type ScoreDriver = {
  name: string;
  category: string;
  effect: 'positive' | 'preliminary_positive' | 'limiting' | 'negative' | 'insufficient';
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
  area: 'company_fundamentals' | 'leadership' | 'qualitative_evidence' | 'filings' | 'smart_money' | 'valuation' | 'risk' | 'source_quality';
  check: string;
  reason: string;
};

export type QualitativeEvidenceInput = {
  evidence_id?: string | null;
  criterion: string;
  evidence_type: string;
  summary: string;
  source_label: string;
  source_url?: string | null;
  source_date?: string | null;
  confidence: number;
  user_provided: boolean;
  limitations: string[];
  comparison_context?: ComparisonContext | null;
};

export type ComparisonContext = {
  comparison_type: 'competitor' | 'market_share' | 'product_capability' | 'platform_ecosystem' | 'customer_adoption' | 'pricing_power' | 'switching_cost' | 'r_and_d_intensity' | 'other';
  subject_company?: string | null;
  peer_companies: string[];
  comparison_summary: string;
  claimed_advantage: 'stronger' | 'similar' | 'weaker' | 'unclear';
  metric_name?: string | null;
  metric_value?: number | string | null;
  metric_unit?: string | null;
  comparison_period?: string | null;
  source_basis: 'user_note' | 'company_filing' | 'investor_presentation' | 'third_party_research' | 'manual_estimate' | 'other';
  limitations: string[];
};

export type QualitativeEvidenceAssessmentItem = {
  evidence_id?: string | null;
  origin?: 'saved_library' | 'request_scoped';
  review_status?: string | null;
  criterion: string;
  evidence_type: string;
  summary: string;
  source_label: string;
  source_date?: string | null;
  source_quality: 'user_provided' | 'filing_backed' | 'derived_live' | 'insufficient' | 'rejected';
  accepted: boolean;
  acceptance_reason: string;
  confidence: number;
  limitations: string[];
  missing_data: string[];
  evidence_quality_score?: number;
  evidence_quality_label?: 'high' | 'medium' | 'low' | 'incomplete';
  evidence_quality_reasons?: string[];
  is_stale?: boolean;
  stale_reason?: string | null;
  next_review_due_at?: string | null;
  source_reliability_label?: string;
  comparison_context?: ComparisonContext | null;
};

export type QualitativeEvidenceAssessment = {
  ticker: string;
  evidence_count: number;
  accepted_evidence_count: number;
  rejected_evidence_count: number;
  saved_evidence_count?: number;
  request_evidence_count?: number;
  deduplicated_count?: number;
  reviewed_count?: number;
  unreviewed_count?: number;
  reviewed_active_count?: number;
  unreviewed_active_count?: number;
  quality_score_average?: number | null;
  high_quality_count?: number;
  medium_quality_count?: number;
  low_quality_count?: number;
  incomplete_count?: number;
  stale_count?: number;
  review_due_count?: number;
  archived_or_rejected_ignored_count?: number;
  criteria_covered: string[];
  criteria_still_insufficient: string[];
  source_quality_summary: string;
  evidence_items: QualitativeEvidenceAssessmentItem[];
  source_status: DataSourceStatus;
  limitations: string[];
  missing_data: string[];
};

export type ComparisonEvidenceAssessmentItem = {
  evidence_id?: string | null;
  origin: 'saved_library' | 'request_scoped';
  criterion: string;
  evidence_type: string;
  comparison_type: string;
  peer_companies: string[];
  claimed_advantage: string;
  comparison_summary: string;
  source_basis: string;
  review_status?: string | null;
  evidence_quality_score: number;
  evidence_quality_label: 'high' | 'medium' | 'low' | 'incomplete';
  is_stale: boolean;
  accepted: boolean;
  limitations: string[];
};

export type ComparisonEvidenceAssessment = {
  ticker: string;
  comparison_evidence_count: number;
  accepted_comparison_count: number;
  reviewed_comparison_count: number;
  stale_comparison_count: number;
  criteria_supported: string[];
  peer_companies_mentioned: string[];
  claimed_advantage_breakdown: Record<string, number>;
  source_quality: 'user_provided' | 'insufficient';
  limitations: string[];
  missing_data: string[];
  items: ComparisonEvidenceAssessmentItem[];
  source_status: DataSourceStatus;
};

export type ManualQualitativeEvidence = {
  evidence_id: string;
  ticker: string;
  criterion: string;
  evidence_type: string;
  summary: string;
  source_label: string;
  source_url?: string | null;
  source_date?: string | null;
  confidence: number;
  review_status: 'unreviewed' | 'reviewed' | 'rejected' | 'archived';
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  review_notes?: string | null;
  source_reliability_label: 'user_note' | 'official_company_material' | 'sec_filing_reference' | 'company_investor_relations' | 'reputable_third_party_research' | 'unknown' | 'other';
  evidence_quality_score: number;
  evidence_quality_label: 'high' | 'medium' | 'low' | 'incomplete';
  evidence_quality_reasons: string[];
  is_stale: boolean;
  stale_reason?: string | null;
  expires_at?: string | null;
  last_reviewed_at?: string | null;
  next_review_due_at?: string | null;
  user_provided: true;
  created_at: string;
  updated_at: string;
  created_by?: string | null;
  limitations: string[];
  tags: string[];
  comparison_context?: ComparisonContext | null;
};

export type ManualQualitativeEvidenceCreate = Omit<
  ManualQualitativeEvidence,
  | 'evidence_id'
  | 'created_at'
  | 'updated_at'
  | 'user_provided'
  | 'evidence_quality_score'
  | 'evidence_quality_label'
  | 'evidence_quality_reasons'
  | 'is_stale'
  | 'stale_reason'
  | 'reviewed_at'
  | 'reviewed_by'
  | 'review_notes'
  | 'source_reliability_label'
  | 'expires_at'
  | 'last_reviewed_at'
  | 'next_review_due_at'
> & {
  user_provided?: true;
  review_notes?: string | null;
  source_reliability_label?: ManualQualitativeEvidence['source_reliability_label'];
  expires_at?: string | null;
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
  qualitative_evidence_assessment?: QualitativeEvidenceAssessment;
  company_profile?: Record<string, unknown>;
  macro_regime?: ScoreLike;
  leadership_score?: ScoreLike;
  jane_company_quality?: JaneCompanyQuality;
  financial_statement_signals?: FinancialStatementSignals;
  sec_financial_facts?: Record<string, unknown>;
  fundamentals_cross_check?: Record<string, unknown>;
  market_timing_context?: ScoreLike;
  overheat_risk?: ScoreLike;
  smart_money?: ScoreLike;
  insider_activity?: ScoreLike;
  institutional_13f?: ScoreLike;
  financial_quality?: ScoreLike;
  valuation_context?: ScoreLike;
  risk_flags?: string[];
  jane_reference_conditions?: JaneReferenceConditions | null;
  jane_quality_methodology_reference?: JaneQualityMethodologyReference | null;
  missing_data?: string[];
  human_verification_queue?: string[];
  data_quality?: DataQualitySummary | null;
  source_status?: DataSourceStatus | null;
  comparison_evidence_assessment?: ComparisonEvidenceAssessment;
  not_investment_advice?: boolean;
};

export type ApiError = Error & {
  status?: number;
};
