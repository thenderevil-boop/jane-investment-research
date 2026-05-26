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
    context_only_fred_fields?: string[];
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
  why_it_matters?: string | null;
  review_priority?: 'high' | 'medium' | 'low' | 'none';
  affects_final_score?: boolean | null;
  is_deprecated?: boolean;
  replaced_by?: string | null;
};

export type ValidationQualitySummary = {
  ticker: string;
  overall_validation_level: 'high_quality_validation' | 'usable_preliminary_validation' | 'limited_validation' | 'insufficient_validation';
  why: string;
  primary_supporting_evidence: string[];
  primary_limiting_factors: string[];
  manual_review_required: boolean;
  highest_priority_review_items: string[];
  data_quality_grade: 'A' | 'B' | 'C' | 'D';
  confidence_cap_applied: boolean;
  confidence_cap_reason?: string | null;
  not_investment_advice: boolean;
};

export type ForeignFilerContext = {
  ticker: string;
  is_foreign_filer_or_adr: boolean;
  country?: string | null;
  exchange?: string | null;
  sec_missing_concept_count: number;
  structural_coverage_limitation: boolean;
  user_explanation: string;
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
  optional_provider_fallback_categories: string[];
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
    agreement_level_with_yfinance: 'high' | 'moderate' | 'low' | 'insufficient' | 'provider_proxy_available';
  };
  fmp_financials?: {
    available: boolean;
    source_type: SourceType | 'insufficient';
    reported_currency?: string | null;
    latest_fiscal_year?: string | null;
    filing_date?: string | null;
    proxy_metric_count: number;
    ttm_ratio_count: number;
    used_for_financial_quality: boolean;
    optional_enhancement?: boolean;
  };
  foreign_filer_context?: ForeignFilerContext;
};

export type ForeignFilerCoverageLimitation = {
  area: 'sec_companyfacts' | 'sec_form4' | 'sec_13f' | 'fmp_transcript' | 'local_filings' | 'other';
  status: 'structural_gap' | 'provider_gap' | 'not_expected' | 'manual_verification_required';
  reason: string;
  affected_criteria: number[];
};

export type ForeignFilerManualCheck = {
  priority: 'high' | 'medium' | 'low';
  criterion_id?: number | null;
  check: string;
};

export type ForeignFilerCoverageDiagnostics = {
  is_foreign_filer_or_adr: boolean;
  detected_signals: string[];
  coverage_limitations: ForeignFilerCoverageLimitation[];
  recommended_manual_checks: ForeignFilerManualCheck[];
  affects_score: boolean;
  not_investment_advice: boolean;
};

export type EvidenceFreshnessPolicy = {
  policy_version: 'phase49_evidence_freshness_v1';
  manual_evidence_max_age_days: number;
  reviewed_evidence_review_days: number;
  provider_cache_review_days: number;
  data_source_windows: Record<string, string>;
  manual_review_triggers: string[];
  affects_score: boolean;
  not_investment_advice: boolean;
};

export type StaleReviewQueueItem = {
  priority: 'high' | 'medium' | 'low';
  category: string;
  trigger: 'stale_manual_evidence' | 'review_due' | 'missing_source_date' | 'stale_source_status';
  item_label: string;
  reason: string;
  recommended_action: 'refresh_or_archive' | 'review_evidence' | 'verify_or_refresh_source' | 'add_source_date';
  source_date?: string | null;
  review_due_at?: string | null;
  evidence_id?: string | null;
  blocks_confidence_upgrade: boolean;
  affects_score: boolean;
};

export type StaleReviewQueue = {
  items: StaleReviewQueueItem[];
  stale_count: number;
  review_due_count: number;
  missing_source_date_count: number;
  source_stale_count: number;
  high_priority_count: number;
  summary: string;
  affects_score: boolean;
  not_investment_advice: boolean;
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
  priority_rank?: number;
  blocking?: boolean;
  category?: string | null;
  related_evidence_category?: string | null;
  reason_short?: string;
};

export type EarningsTranscriptDimension = {
  label: string;
  confidence: number;
  evidence_snippets: string[];
  limitations: string[];
  affects_score: boolean;
};

export type TranscriptTheme = {
  theme: string;
  label: string;
  evidence_snippets: string[];
  confidence: number;
  limitations: string[];
  affects_score: boolean;
};

export type EarningsTranscriptAnalysis = {
  ticker: string;
  provider: string;
  source_status: DataSourceStatus;
  quarters_analyzed: number;
  management_consistency: EarningsTranscriptDimension;
  strategy_clarity: EarningsTranscriptDimension;
  risk_acknowledgement: EarningsTranscriptDimension;
  customer_demand_signal: EarningsTranscriptDimension;
  margin_pressure_signal: EarningsTranscriptDimension;
  capital_allocation_focus: EarningsTranscriptDimension;
  positive_themes: TranscriptTheme[];
  risk_themes: TranscriptTheme[];
  manual_checks: string[];
  limitations: string[];
  affects_score: boolean;
  not_investment_advice: boolean;
};

export type JaneCriteriaExternalEvidenceItem = {
  criterion_id: number;
  criterion_name: string;
  source: string;
  source_quality: 'provider_backed' | 'cached_live' | 'insufficient';
  support_level: 'supportive' | 'partial' | 'insufficient_data';
  confidence: number;
  covered_submetrics: string[];
  evidence_snippets: string[];
  manual_checks: string[];
  limitations: string[];
  missing_data: string[];
  requires_manual_review: boolean;
  affects_score: boolean;
};

export type JaneCriteriaExternalEvidence = {
  ticker: string;
  provider: string;
  source: string;
  source_status: DataSourceStatus;
  criteria: JaneCriteriaExternalEvidenceItem[];
  criteria_count: number;
  manual_checks: string[];
  limitations: string[];
  affects_score: boolean;
  not_investment_advice: boolean;
};

export type GovernmentRecipientCandidate = {
  recipient_name: string;
  recipient_hash?: string | null;
  uei?: string | null;
  duns?: string | null;
  source: string;
};

export type GovernmentAwardRecord = {
  award_id: string;
  recipient_name: string;
  awarding_agency: string;
  obligated_amount: number;
  award_date: string;
  award_type: string;
  description: string;
};

export type GovernmentAwardingAgencySummary = {
  agency: string;
  obligated_amount: number;
  award_count: number;
};

export type GovernmentRelationshipEvidence = {
  ticker: string;
  provider: string;
  source: string;
  source_status: DataSourceStatus;
  query_name: string;
  recipient_candidates: GovernmentRecipientCandidate[];
  award_records: GovernmentAwardRecord[];
  total_obligated_amount: number;
  award_count: number;
  top_awarding_agencies: GovernmentAwardingAgencySummary[];
  criteria: JaneCriteriaExternalEvidenceItem[];
  criteria_count: number;
  relationship_signal: 'supportive' | 'limited' | 'insufficient_data';
  manual_checks: string[];
  limitations: string[];
  affects_score: boolean;
  not_investment_advice: boolean;
};

export type PatentRecord = {
  patent_id: string;
  patent_date: string;
  patent_title: string;
  assignee_organization: string;
};

export type PatentIPEvidence = {
  ticker: string;
  provider: string;
  source: string;
  source_status: DataSourceStatus;
  query_name: string;
  patent_count: number;
  patent_records: PatentRecord[];
  criteria: JaneCriteriaExternalEvidenceItem[];
  criteria_count: number;
  ip_signal: 'supportive' | 'limited' | 'insufficient_data';
  manual_checks: string[];
  limitations: string[];
  affects_score: boolean;
  not_investment_advice: boolean;
};

export type AdrEvidenceType =
  | 'annual_report'
  | 'local_regulatory_filing'
  | 'governance_page'
  | 'investor_presentation'
  | 'earnings_webcast'
  | 'company_ir_page'
  | 'other';

export type QualitativeEvidenceInput = {
  evidence_id?: string | null;
  criterion: string;
  criterion_id?: number | null;
  criterion_name?: string | null;
  submetric?: string | null;
  evidence_type: string;
  summary: string;
  source_label: string;
  source_url?: string | null;
  source_date?: string | null;
  adr_evidence_type?: AdrEvidenceType | null;
  document_title?: string | null;
  document_date?: string | null;
  filing_period?: string | null;
  quoted_text?: string | null;
  local_market?: string | null;
  local_ticker?: string | null;
  translation_note?: string | null;
  confidence: number;
  user_provided: boolean;
  limitations: string[];
  comparison_context?: ComparisonContext | null;
};

export type JaneEvidenceType = 'financial_proxy' | 'qualitative' | 'semi_structured';

export type JaneCriterion = {
  criterion_id: number;
  criterion_name: string;
  submetrics: string[];
  evidence_type: JaneEvidenceType;
  auto_derivable_submetrics: string[];
  requires_user_input_submetrics: string[];
  financial_proxy_source?: string | null;
};

export type JaneCriteriaResponse = {
  criteria: JaneCriterion[];
  count: number;
  not_investment_advice: true;
};

export type JaneCriterionCoverageItem = {
  criterion_id: number;
  criterion_name: string;
  evidence_type: JaneEvidenceType;
  coverage_status: 'covered' | 'partial' | 'insufficient';
  source_quality: 'filing_backed' | 'derived_live' | 'cached_live' | 'user_context' | 'user_provided' | 'mixed_with_fallback' | 'mock_only' | 'provider_backed' | 'derived_from_mixed_sources' | 'insufficient';
  confidence: number;
  auto_derivable_submetrics: string[];
  requires_user_input_submetrics: string[];
  covered_submetrics: string[];
  missing_submetrics: string[];
  evidence_item_count: number;
  accepted_evidence_item_count: number;
  financial_proxy_source?: string | null;
  requires_human_verification: boolean;
  summary: string;
  limitations: string[];
  next_manual_check?: string | null;
};

export type JaneCriteriaCoverageMatrix = {
  criteria: JaneCriterionCoverageItem[];
  covered_count: number;
  partial_count: number;
  insufficient_count: number;
  user_input_required_count: number;
  financial_proxy_available_count: number;
  source_quality_summary: string;
  not_investment_advice: boolean;
};

export type ValidationOSEvidenceGap = {
  criterion_id: number;
  criterion_name: string;
  coverage_status: 'partial' | 'insufficient';
  missing_submetrics: string[];
  next_manual_check?: string | null;
};

export type ThemeValidationContext = {
  supplied_theme?: string | null;
  user_reason?: string | null;
  input_source: 'none' | 'user_supplied';
  boundary_label: 'no_theme_supplied' | 'user_supplied_validation_target';
  validation_status: 'not_requested' | 'needs_manual_evidence';
  ranking_or_scoring_policy: 'not_applicable' | 'not_ranked_or_scored';
  confidence: number;
  theme_discovery_enabled: boolean;
  system_generated_theme: boolean;
  affects_score: boolean;
  manual_checks: string[];
  limitations: string[];
  not_investment_advice: boolean;
};

export type MacroFlowSignalItem = {
  name: string;
  category: 'macro' | 'flow';
  label: string;
  observed_value?: string | number | null;
  source_quality: SourceType;
  source_date: string;
  interpretation: string;
  limitations: string[];
  affects_score: boolean;
  is_real_time_signal?: boolean | null;
};

export type MacroFlowSignalBreakdown = {
  version: 'phase57_macro_flow_signal_breakdown_v1';
  summary: string;
  macro_regime_label: string;
  smart_money_label: string;
  research_verdict_label: string;
  final_score: number;
  macro_signal_count: number;
  flow_signal_count: number;
  macro_signals: MacroFlowSignalItem[];
  flow_signals: MacroFlowSignalItem[];
  manual_review_required: boolean;
  manual_checks: string[];
  limitations: string[];
  affects_score: boolean;
  final_score_unchanged: boolean;
  not_investment_advice: boolean;
};


export type CompanyEventSignalItem = {
  name: string;
  category: 'company_event' | 'insider' | 'institutional' | 'options' | 'lockup';
  label: string;
  observed_value?: string | number | boolean | null;
  source_quality: SourceType;
  source_date: string;
  interpretation: string;
  manual_check: string;
  limitations: string[];
  affects_score: boolean;
  is_real_time_signal?: boolean | null;
};

export type CompanyEventSignalBreakdown = {
  version: 'phase58_company_event_signal_breakdown_v1';
  summary: string;
  event_signal_count: number;
  event_signals: CompanyEventSignalItem[];
  insider_summary: Record<string, unknown>;
  institutional_summary: Record<string, unknown>;
  options_summary: Record<string, unknown>;
  lockup_summary: Record<string, unknown>;
  manual_review_required: boolean;
  manual_checks: string[];
  limitations: string[];
  affects_score: boolean;
  final_score_unchanged: boolean;
  not_investment_advice: boolean;
};

export type PlatformBusinessQualityMetric = {
  name: 'gmv_growth' | 'take_rate' | 'net_dollar_retention' | 'burn_rate' | 'runway' | 'marketplace_liquidity' | 'network_effect' | 'ltv_cac' | 'contribution_margin_operating_leverage';
  label: string;
  category: 'growth' | 'monetization' | 'retention' | 'cash' | 'marketplace' | 'network_effect' | 'unit_economics' | 'operating_leverage';
  status: 'computed_proxy' | 'manual_evidence' | 'manual_or_disclosed_only' | 'unavailable';
  observed_value?: unknown;
  source_quality: SourceType | 'user_provided' | 'unavailable';
  source_date: string;
  interpretation: string;
  manual_check: string;
  limitations: string[];
  requires_manual_evidence: boolean;
  affects_score: boolean;
};

export type PlatformBusinessQualityCard = {
  version: 'phase59_platform_business_quality_card_v1';
  summary: string;
  platform_metric_count: number;
  computed_metric_names: string[];
  manual_evidence_metric_names: string[];
  manual_or_disclosed_metric_names: string[];
  metrics: PlatformBusinessQualityMetric[];
  manual_review_required: boolean;
  manual_checks: string[];
  limitations: string[];
  affects_score: boolean;
  final_score_unchanged: boolean;
  not_investment_advice: boolean;
};

export type ValidationOSReport = {
  ticker: string;
  research_label: string;
  validation_level: string;
  data_quality_grade: 'A' | 'B' | 'C' | 'D';
  report_sections: string[];
  executive_summary: string;
  macro_backdrop: string;
  jane_quality_summary: string;
  jane_criteria_coverage_summary: {
    covered_count: number;
    partial_count: number;
    insufficient_count: number;
    coverage_gap_count: number;
    user_input_required_count: number;
    financial_proxy_available_count: number;
    source_quality_summary: string;
  };
  financial_signals_summary: string;
  smart_money_summary: string;
  top_strengths: string[];
  top_limitations: string[];
  top_evidence_gaps: ValidationOSEvidenceGap[];
  top_manual_checks: string[];
  source_quality_caveats: string[];
  manual_verification_required: boolean;
  scoring_note: string;
  limitations: string[];
  not_investment_advice: boolean;
};

export type JaneLeadershipCriterionDefinition = {
  name: string;
  display_name_zh: string;
  display_name_en: string;
  description: string;
  accepted_evidence_types: string[];
  manual_check_questions: string[];
  default_status: 'insufficient';
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
  criterion_id?: number | null;
  criterion_name?: string | null;
  submetric?: string | null;
  evidence_type: string;
  summary: string;
  source_label: string;
  source_url?: string | null;
  source_date?: string | null;
  adr_evidence_type?: AdrEvidenceType | null;
  document_title?: string | null;
  document_date?: string | null;
  filing_period?: string | null;
  quoted_text?: string | null;
  local_market?: string | null;
  local_ticker?: string | null;
  translation_note?: string | null;
  source_quality: 'user_provided' | 'filing_backed' | 'derived_live' | 'insufficient' | 'rejected';
  verification_level?: 'user_provided' | 'filing_backed' | 'insufficient' | 'rejected';
  affects_score?: boolean;
  not_investment_advice?: boolean;
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
  note_title?: string | null;
  research_question?: string | null;
  thesis_direction?: ManualEvidenceThesisDirection;
  workflow_status?: ManualEvidenceWorkflowStatus;
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

export type ManualEvidenceThesisDirection = 'supportive' | 'neutral' | 'challenging' | 'unknown';
export type ManualEvidenceWorkflowStatus = 'draft' | 'review_ready' | 'accepted' | 'needs_refresh' | 'rejected' | 'archived';

export type ManualQualitativeEvidence = {
  evidence_id: string;
  ticker: string;
  criterion: string;
  evidence_type: string;
  summary: string;
  source_label: string;
  source_url?: string | null;
  source_date?: string | null;
  adr_evidence_type?: AdrEvidenceType | null;
  document_title?: string | null;
  document_date?: string | null;
  filing_period?: string | null;
  quoted_text?: string | null;
  local_market?: string | null;
  local_ticker?: string | null;
  translation_note?: string | null;
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
  note_title?: string | null;
  research_question?: string | null;
  thesis_direction: ManualEvidenceThesisDirection;
  workflow_status: ManualEvidenceWorkflowStatus;
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
  | 'thesis_direction'
  | 'workflow_status'
> & {
  user_provided?: true;
  review_notes?: string | null;
  source_reliability_label?: ManualQualitativeEvidence['source_reliability_label'];
  expires_at?: string | null;
  thesis_direction?: ManualQualitativeEvidence['thesis_direction'];
  workflow_status?: ManualQualitativeEvidence['workflow_status'];
};

export type ManualEvidenceDashboardFilters = {
  ticker?: string;
  review_status?: string;
  stale_only?: boolean;
  review_due_only?: boolean;
  has_comparison_context?: boolean | null;
  include_archived?: boolean;
  include_rejected?: boolean;
  criterion?: string;
  min_quality_label?: 'high' | 'medium' | 'low' | 'incomplete' | '';
};

export type ManualEvidenceDashboardQueueItem = {
  evidence_id: string;
  ticker: string;
  criterion: string;
  evidence_type: string;
  review_status: string;
  evidence_quality_label: string;
  evidence_quality_score: number;
  is_stale: boolean;
  stale_reason?: string | null;
  next_review_due_at?: string | null;
  review_due_reason: string;
  summary: string;
  source_label: string;
  source_date?: string | null;
  adr_evidence_type?: AdrEvidenceType | null;
  document_title?: string | null;
  document_date?: string | null;
  filing_period?: string | null;
  local_market?: string | null;
  local_ticker?: string | null;
  adr_review_label?: string | null;
  adr_review_guidance: string[];
  affects_score: boolean;
  not_investment_advice: boolean;
  has_comparison_context: boolean;
  peer_companies: string[];
};

export type ManualEvidenceTickerSummary = {
  ticker: string;
  total_evidence_count: number;
  active_evidence_count: number;
  reviewed_count: number;
  unreviewed_count: number;
  stale_count: number;
  review_due_count: number;
  review_scheduled_count: number;
  review_overdue_count: number;
  comparison_evidence_count: number;
  criteria_covered: string[];
  criteria_missing: string[];
  peer_companies_mentioned: string[];
  quality_label_breakdown: Record<string, number>;
  highest_quality_label: 'high' | 'medium' | 'low' | 'incomplete' | 'none';
  next_review_due_at?: string | null;
};

export type ManualEvidencePeerCompanyIndexItem = {
  peer_company: string;
  evidence_count: number;
  tickers: string[];
  criteria: string[];
  comparison_types: string[];
  claimed_advantage_breakdown: Record<string, number>;
};

export type ManualEvidenceDashboard = {
  generated_at: string;
  source_status: {
    source_type: 'derived';
    provider: 'local_manual_evidence_library';
    source_date?: string | null;
    fetched_at: null;
    is_fresh: boolean;
    freshness_window: 'local_evidence_store';
    fallback_used: boolean;
    fallback_reason: null;
    limitations: string[];
    missing_data: string[];
  };
  summary: {
    total_evidence_count: number;
    active_evidence_count: number;
    reviewed_count: number;
    unreviewed_count: number;
    stale_count: number;
    review_due_count: number;
    review_scheduled_count: number;
    review_overdue_count: number;
    archived_count: number;
    rejected_count: number;
    comparison_evidence_count: number;
    tickers_covered_count: number;
    average_quality_score?: number | null;
    quality_label_breakdown: Record<string, number>;
    review_status_breakdown: Record<string, number>;
    criteria_coverage: Record<string, number>;
  };
  ticker_summaries: ManualEvidenceTickerSummary[];
  review_queue: ManualEvidenceDashboardQueueItem[];
  stale_queue: ManualEvidenceDashboardQueueItem[];
  audit_queue: ManualEvidenceDashboardQueueItem[];
  peer_company_index: ManualEvidencePeerCompanyIndexItem[];
  limitations: string[];
  missing_data: string[];
  not_investment_advice: boolean;
};

export type CandidateStatus = 'watching' | 'researching' | 'reviewed' | 'archived';
export type CandidatePriority = 'low' | 'medium' | 'high';

export type CandidateEvidenceSummary = {
  manual_evidence_count: number;
  active_evidence_count: number;
  reviewed_evidence_count: number;
  unreviewed_evidence_count: number;
  stale_evidence_count: number;
  comparison_evidence_count: number;
  criteria_covered: string[];
  criteria_missing: string[];
  peer_companies_mentioned: string[];
};

export type CandidateReviewNote = {
  note_id: string;
  created_at: string;
  created_by: 'local_user';
  note: string;
  note_type: 'general' | 'evidence_review' | 'analysis_review' | 'risk_review' | 'follow_up';
  related_analysis_snapshot_id?: string | null;
  tags: string[];
};

export type CandidateReviewNoteCreate = {
  note: string;
  note_type?: CandidateReviewNote['note_type'];
  related_analysis_snapshot_id?: string | null;
  tags?: string[];
};

export type CandidateAnalysisHistoryItem = {
  analysis_snapshot_id: string;
  analyzed_at: string;
  score?: number | null;
  confidence?: number | null;
  label?: string | null;
  data_quality_grade?: string | null;
  evidence_coverage_summary: {
    criteria_covered: string[];
    criteria_missing: string[];
    active_evidence_count: number;
    stale_evidence_count: number;
    comparison_evidence_count: number;
  };
  limitations: string[];
};

export type CandidateEvidenceBadge = {
  label: string;
  severity: 'info' | 'warning' | 'success';
  reason: string;
};

export type CandidateResearchItem = {
  candidate_id: string;
  ticker: string;
  market: 'US';
  company_name?: string | null;
  theme?: string | null;
  user_reason?: string | null;
  source_label?: string | null;
  source_date?: string | null;
  status: CandidateStatus;
  priority: CandidatePriority;
  tags: string[];
  created_at: string;
  updated_at: string;
  last_analyzed_at?: string | null;
  last_analysis_snapshot_id?: string | null;
  latest_score?: number | null;
  latest_confidence?: number | null;
  latest_label?: string | null;
  latest_data_quality_grade?: string | null;
  evidence_summary: CandidateEvidenceSummary;
  next_review_due_at?: string | null;
  review_notes?: string | null;
  review_note_history: CandidateReviewNote[];
  analysis_history: CandidateAnalysisHistoryItem[];
  evidence_badges: CandidateEvidenceBadge[];
  review_reasons: string[];
  limitations: string[];
  not_investment_advice: true;
};

export type CandidateResearchItemCreate = {
  ticker: string;
  market?: 'US';
  company_name?: string | null;
  theme?: string | null;
  user_reason?: string | null;
  source_label?: string | null;
  source_date?: string | null;
  priority?: CandidatePriority;
  tags?: string[];
};

export type CandidateDashboard = {
  generated_at: string;
  source_status: {
    source_type: 'derived';
    provider: 'local_candidate_workspace';
    source_date?: string | null;
    fetched_at: null;
    is_fresh: boolean;
    freshness_window: 'local_workspace_store';
    fallback_used: boolean;
    fallback_reason: null;
    limitations: string[];
    missing_data: string[];
  };
  summary: {
    total_candidates: number;
    active_candidates: number;
    watching_count: number;
    researching_count: number;
    reviewed_count: number;
    archived_count: number;
    high_priority_count: number;
    stale_evidence_candidate_count: number;
    needs_review_count: number;
    with_comparison_evidence_count: number;
    needs_analysis_count: number;
    stale_analysis_count: number;
    missing_evidence_candidate_count: number;
    review_overdue_count: number;
    status_breakdown: Record<string, number>;
    priority_breakdown: Record<string, number>;
    missing_criteria_breakdown: Record<string, number>;
    average_latest_score?: number | null;
    data_quality_grade_breakdown: Record<string, number>;
  };
  items: CandidateResearchItem[];
  review_queue: CandidateResearchItem[];
  limitations: string[];
  missing_data: string[];
  not_investment_advice: boolean;
};

export type CandidateFilters = {
  include_archived?: boolean;
  ticker?: string;
  status?: CandidateStatus | '';
  priority?: CandidatePriority | '';
  tag?: string;
  stale_evidence_only?: boolean;
  needs_review_only?: boolean;
  has_comparison_evidence?: boolean | null;
  missing_criterion?: string;
  data_quality_grade?: string;
  sort_by?: 'updated_at' | 'created_at' | 'priority' | 'latest_score' | 'latest_confidence' | 'next_review_due_at' | 'stale_evidence_count' | 'active_evidence_count';
  sort_order?: 'asc' | 'desc';
};

export type CandidateAnalyzeResponse = {
  candidate: CandidateResearchItem;
  analysis: StockAnalysis;
  not_investment_advice: boolean;
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

export type SmartMoneySourceQualityComponent = {
  source_type?: SourceType | string;
  provider?: string | null;
  large_block_count?: number | null;
  total_premium?: number | null;
  interpretation?: string | null;
  score_impact?: string | null;
};

export type SmartMoneySourceQualityBreakdown = {
  form4?: SmartMoneySourceQualityComponent;
  institutional_13f?: SmartMoneySourceQualityComponent;
  options?: SmartMoneySourceQualityComponent;
  aggregate_interpretation?: string | null;
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
  source_quality_breakdown?: SmartMoneySourceQualityBreakdown | Record<string, unknown> | null;
  explanation?: Record<string, unknown> | null;
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

export type HumanVerificationQueueItem = {
  item: string;
  question: string;
  jane_reference: string;
  action: string;
  needs_human_verification: boolean;
};

export type HumanVerificationQueueEntry = string | HumanVerificationQueueItem;

export type TodayResearchAction = {
  priority: 'high' | 'medium' | 'low';
  ticker?: string | null;
  action_type: 'source_setup' | 'evidence_review' | 'coverage_gap' | 'watchlist_change' | 'macro_context';
  title: string;
  reason: string;
  source: 'existing_data';
  affects_score: boolean;
  not_investment_advice: boolean;
};

export type DailyMacroDelta = {
  version: 'phase61_macro_delta_v1';
  previous_report_date?: string | null;
  macro_score_change?: number | null;
  vix_change?: number | null;
  yield_curve_10y2y_spread_change_bps?: number | null;
  latest_inflation_observations?: Array<Record<string, string | number | null>>;
  source: 'daily_report_snapshot_compare';
  limitations?: string[];
  not_investment_advice: boolean;
};

export type DailyWatchlistDeltaItem = {
  ticker: string;
  price_change_pct?: number | null;
  overheat_score_change?: number | null;
  new_form4_count?: number | null;
  institutional_13f_status: string;
  data_issue?: string | null;
  source: 'daily_report_snapshot_compare';
  not_investment_advice: boolean;
};

export type DailyWatchlistDelta = {
  version: 'phase61_watchlist_delta_v1';
  previous_report_date?: string | null;
  items?: DailyWatchlistDeltaItem[];
  limitations?: string[];
  not_investment_advice: boolean;
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
  human_verification_queue?: HumanVerificationQueueEntry[];
  today_research_actions?: TodayResearchAction[];
  macro_delta?: DailyMacroDelta | null;
  watchlist_delta?: DailyWatchlistDelta | null;
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
  validation_quality_summary?: ValidationQualitySummary;
  evidence_matrix?: EvidenceMatrixItem[];
  jane_criteria_coverage?: JaneCriteriaCoverageMatrix;
  theme_validation_context?: ThemeValidationContext;
  macro_flow_signal_breakdown?: MacroFlowSignalBreakdown;
  company_event_signal_breakdown?: CompanyEventSignalBreakdown;
  platform_business_quality_card?: PlatformBusinessQualityCard;
  validation_os_report?: ValidationOSReport;
  data_quality_summary?: AnalyzeStockDataQualitySummary;
  foreign_filer_coverage_diagnostics?: ForeignFilerCoverageDiagnostics;
  evidence_freshness_policy?: EvidenceFreshnessPolicy;
  stale_review_queue?: StaleReviewQueue;
  score_driver_breakdown?: ScoreDriverBreakdown;
  next_manual_checks?: NextManualCheck[];
  qualitative_evidence_assessment?: QualitativeEvidenceAssessment;
  earnings_transcript_analysis?: EarningsTranscriptAnalysis;
  jane_criteria_external_evidence?: JaneCriteriaExternalEvidence;
  government_relationship_evidence?: GovernmentRelationshipEvidence;
  patent_ip_evidence?: PatentIPEvidence;
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
  human_verification_queue?: HumanVerificationQueueEntry[];
  data_quality?: DataQualitySummary | null;
  source_status?: DataSourceStatus | null;
  comparison_evidence_assessment?: ComparisonEvidenceAssessment;
  not_investment_advice?: boolean;
};

export type AnalyzeStockExportPayload = {
  ticker: string;
  market?: 'US';
  research_context?: ResearchContext;
  qualitative_evidence?: QualitativeEvidenceInput[];
  format: 'json' | 'markdown';
  include_raw_evidence?: boolean;
  include_manual_evidence?: boolean;
  include_candidate_metadata?: boolean;
  redact_sensitive_fields?: boolean;
};

export type AnalyzeStockExportResponse = {
  export_id: string;
  generated_at: string;
  ticker: string;
  format: 'json' | 'markdown';
  filename: string;
  content_type: string;
  report: Record<string, unknown> | string;
  source_status: DataSourceStatus;
  not_investment_advice: boolean;
};

export type LocalBackupExportOptions = {
  include_manual_evidence?: boolean;
  include_candidate_workspace?: boolean;
  include_evidence_dashboard?: boolean;
  include_archived?: boolean;
  include_rejected?: boolean;
  format?: 'json';
};

export type LocalBackupExportResponse = {
  backup_metadata: {
    backup_id: string;
    generated_at: string;
    schema_version: 'phase25_local_backup_v1';
    not_investment_advice: boolean;
    limitations: string[];
  };
  manual_evidence?: Record<string, unknown> | null;
  candidate_workspace?: Record<string, unknown> | null;
  source_status: DataSourceStatus;
  not_investment_advice: boolean;
};

export type ApiError = Error & {
  status?: number;
};
