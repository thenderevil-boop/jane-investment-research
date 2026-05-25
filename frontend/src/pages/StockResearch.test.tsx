import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi, afterEach } from 'vitest';
import type { DataSourceStatus, JaneCriterion, ScoreLike, StockAnalysis } from '../types';
import { getJaneCriteria } from '../api/client';
import StockResearch, { AnalystBriefSection, AnalyzeDataQualitySection, CandidateSummarySection, CompanyFundamentalsSection, ComparisonEvidenceAssessmentSection, EvidenceMatrixSection, FinancialStatementSignalsSection, ForeignFilerCoverageDiagnosticsSection, FundamentalsCrossCheckSection, JaneCompanyQualitySection, JaneCriteriaCoverageSection, ManualChecksSection, ProfileGrid, QualitativeEvidenceAssessmentSection, ResearchSignalExplanationSection, ScoreBlock, SecFinancialFactsSection, SmartMoneySourceQualitySection, ThemeValidationBoundarySection, ValidationOSReportSection, ValidationQualitySummarySection, ValidationReportExportSection, ValuationRiskExplanationSection, buildJaneCriteriaEvidenceInput, parseQualitativeEvidenceJson } from './StockResearch';

const mockStatus: DataSourceStatus = {
  source_type: 'mock',
  provider: 'phase1_mock_dataset',
  source_date: '2026-04-24',
  fetched_at: null,
  is_fresh: true,
  freshness_window: 'latest_expected_trading_day',
  fallback_used: false,
  fallback_reason: null,
  limitations: [],
  missing_data: [],
};

afterEach(() => {
  vi.restoreAllMocks();
});

function score(status: DataSourceStatus | null = mockStatus): ScoreLike {
  return {
    name: 'leadership_score',
    score: 15,
    max_score: 20,
    label: 'watchlist_candidate',
    confidence: 0.7,
    raw_data: status ? { source_status: status } : {},
    derived_metrics: {},
    benchmark: {},
    trend: {},
    source: ['phase1_mock_dataset'],
    source_date: '2026-04-24',
    limitations: [],
    missing_data: [],
  };
}

describe('StockResearch presentation helpers', () => {
  it('renders qualitative evidence JSON input on the stock research form', () => {
    const html = renderToStaticMarkup(<StockResearch />);
    expect(html).toContain('Primary workflow: submit a ticker to validate the idea using evidence, data quality, and missing-data checks.');
    expect(html).toContain('Qualitative Evidence JSON');
    expect(html).toContain('Structured qualitative evidence');
    expect(html).toContain('Jane 20 Criteria Evidence Input');
    expect(html).toContain('User-provided evidence is local validation context only');
    expect(html).not.toContain('[object Object]');
  });

  it('renders user-supplied theme boundary as validation-only context', () => {
    const html = renderToStaticMarkup(
      <ThemeValidationBoundarySection
        context={{
          supplied_theme: 'AI infrastructure',
          user_reason: 'External Jane note',
          input_source: 'user_supplied',
          boundary_label: 'user_supplied_validation_target',
          validation_status: 'needs_manual_evidence',
          ranking_or_scoring_policy: 'not_ranked_or_scored',
          confidence: 0,
          theme_discovery_enabled: false,
          system_generated_theme: false,
          affects_score: false,
          manual_checks: ['Verify actual company revenue exposure to the user-supplied theme.'],
          limitations: ['No automatic theme discovery or theme ranking is performed.'],
          not_investment_advice: true,
        }}
      />,
    );

    expect(html).toContain('User-Supplied Theme Validation Boundary');
    expect(html).toContain('AI infrastructure');
    expect(html).toContain('Validation target only');
    expect(html).toContain('Theme discovery: off');
    expect(html).toContain('Ranking/scoring: not ranked or scored');
    expect(html).toContain('Affects score: no');
    expect(html).toContain('Verify actual company revenue exposure');
    expect(html).toContain('No automatic theme discovery');
    expect(html).toContain('Not investment advice');
  });

  it('fetches Jane criteria from the canonical API endpoint', async () => {
    const payload = {
      criteria: [
        {
          criterion_id: 1,
          criterion_name: 'Market Monopoly / Entry Barrier',
          submetrics: ['switching_cost'],
          evidence_type: 'qualitative',
          auto_derivable_submetrics: [],
          requires_user_input_submetrics: ['switching_cost'],
          financial_proxy_source: null,
        },
      ],
      count: 1,
      not_investment_advice: true,
    };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => payload,
    } as unknown as Response);

    await expect(getJaneCriteria()).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith('/api/jane-criteria', undefined);
  });

  it('builds canonical Jane criteria evidence input for analyze requests', () => {
    const criterion: JaneCriterion = {
      criterion_id: 1,
      criterion_name: 'Market Monopoly / Entry Barrier',
      submetrics: ['switching_cost'],
      evidence_type: 'qualitative',
      auto_derivable_submetrics: [],
      requires_user_input_submetrics: ['switching_cost'],
      financial_proxy_source: null,
    };

    const evidence = buildJaneCriteriaEvidenceInput({
      criterion,
      submetric: 'switching_cost',
      summary: 'Customer migration requires workflow retraining and data migration.',
      sourceLabel: 'user research note',
      confidence: 0.6,
    });

    expect(evidence).toMatchObject({
      criterion: 'monopoly_power',
      criterion_id: 1,
      criterion_name: 'Market Monopoly / Entry Barrier',
      submetric: 'switching_cost',
      evidence_type: 'switching_cost',
      user_provided: true,
    });
    expect(evidence.limitations.join(' ')).toContain('local validation context only');
  });

  it('renders structured foreign filer diagnostics as neutral manual research context', () => {
    const html = renderToStaticMarkup(
      <ForeignFilerCoverageDiagnosticsSection
        diagnostics={{
          is_foreign_filer_or_adr: true,
          detected_signals: ['known_adr_or_foreign_listing', 'sec_companyfacts_sparse'],
          coverage_limitations: [
            {
              area: 'sec_companyfacts',
              status: 'structural_gap',
              reason: 'SEC Companyfacts concepts are sparse for ADR issuers.',
              affected_criteria: [5, 6, 10],
            },
            {
              area: 'sec_form4',
              status: 'not_expected',
              reason: 'SEC Form 4 may not apply to foreign issuers.',
              affected_criteria: [2, 12],
            },
          ],
          recommended_manual_checks: [
            {
              priority: 'high',
              criterion_id: 2,
              check: 'Verify founder / CEO status from annual report and local filings.',
            },
          ],
          affects_score: false,
          not_investment_advice: true,
        }}
      />,
    );
    expect(html).toContain('Foreign Filer / ADR Coverage Note');
    expect(html).toContain('ADR Manual Evidence Intake Helper');
    expect(html).toContain('adr_evidence_type');
    expect(html).toContain('document_date');
    expect(html).toContain('excluded from scoring');
    expect(html).toContain('Affects score: no');
    expect(html).toContain('sec_companyfacts');
    expect(html).toContain('SEC Form 4 may not apply');
    expect(html).toContain('Recommended manual checks');
  });

  it('does not render foreign filer diagnostics for domestic tickers', () => {
    const html = renderToStaticMarkup(
      <ForeignFilerCoverageDiagnosticsSection
        diagnostics={{
          is_foreign_filer_or_adr: false,
          detected_signals: [],
          coverage_limitations: [],
          recommended_manual_checks: [],
          affects_score: false,
          not_investment_advice: true,
        }}
      />,
    );
    expect(html).not.toContain('Foreign Filer / ADR Coverage Note');
  });

  it('renders analyst brief with triage fields and Phase 31 overheat context', () => {
    const result = {
      ticker: 'NVDA',
      market: 'US',
      candidate_validation_summary: {
        ticker: 'NVDA',
        research_priority: 'watchlist_candidate',
        score: 42,
        confidence: 0.72,
        environment_assessment: 'Macro environment is neutral_to_constructive.',
        company_assessment: 'Company evidence is live/cached-live.',
        smart_money_assessment: 'Smart-money assessment is limited by fallback components.',
        data_quality_assessment: 'Source quality grade B.',
        overall_summary: 'NVDA is usable for preliminary validation but still needs manual evidence checks.',
        primary_strengths: ['Macro context is usable.', 'Company profile is live.'],
        primary_risks: ['Manual qualitative evidence still needs source review.'],
        missing_or_mock_evidence: ['Some components are fallback.'],
        next_manual_checks: ['Verify monopoly power evidence.'],
      },
      validation_os_report: {
        ticker: 'NVDA',
        research_label: 'watchlist_candidate',
        validation_level: 'usable_preliminary_validation',
        data_quality_grade: 'B',
        report_sections: [],
        executive_summary: 'Validation summary text.',
        macro_backdrop: 'Macro environment is neutral_to_constructive.',
        jane_quality_summary: 'Jane quality is preliminary.',
        jane_criteria_coverage_summary: {
          covered_count: 2,
          partial_count: 3,
          insufficient_count: 15,
          coverage_gap_count: 18,
          user_input_required_count: 18,
          financial_proxy_available_count: 6,
          source_quality_summary: 'Jane 20 coverage is preliminary.',
        },
        financial_signals_summary: 'Financial signals are adequate.',
        smart_money_summary: 'Smart money is limited.',
        top_strengths: ['Macro context is usable.'],
        top_limitations: ['Manual evidence required.'],
        top_evidence_gaps: [],
        top_manual_checks: ['Verify monopoly power evidence.'],
        source_quality_caveats: ['Some components are fallback.'],
        manual_verification_required: true,
        scoring_note: 'Non-scoring report.',
        limitations: [],
        not_investment_advice: true,
      },
      macro_regime: { score: 62, label: 'neutral_to_constructive', confidence: 0.95 },
      market_timing_context: {
        score: 0,
        label: 'insufficient_data_or_unfavorable',
        confidence: 0.92,
        derived_metrics: {
          phase36_explanation_version: 'market_timing_condition_explanation_v2',
          score_zero_interpretation: 'Score 0 means Jane entry timing conditions are not met; this is expected near market highs.',
          entry_timing_summary: 'Jane entry timing conditions are not met yet; this is expected near market highs or calm markets.',
          condition_checklist: [
            { id: 'fed_consecutive_cuts', label: 'Fed consecutive cuts', status: 'not_met', observed_value: '0 consecutive cut(s)', explanation: 'Jane timing framework looks for at least two consecutive cuts.', affects_score: false },
            { id: 'market_drawdown_stabilization', label: 'Market drawdown and stabilization', status: 'not_met', observed_value: 'SPY -4.0%, QQQ -7.0% drawdown', explanation: 'Jane timing framework looks for a deep drawdown plus stabilization.', affects_score: false },
            { id: 'vix_spike_recovery', label: 'VIX spike and recovery', status: 'not_met', observed_value: 'VIX 17.0; spike no; falling no', explanation: 'Jane timing framework looks for volatility spike confirmation and recovery.', affects_score: false },
            { id: 'overheat_state', label: 'Overheat / normal / fear state', status: 'normal', observed_value: 'VIX 17.0; drawdown -7.0%', explanation: 'Normal market context often means entry timing score remains low.', affects_score: false },
          ],
        },
      },
      earnings_transcript_analysis: {
        ticker: 'NVDA',
        provider: 'fmp',
        source_status: { ...mockStatus, source_type: 'live', provider: 'fmp', source_date: '2026-04-24' },
        quarters_analyzed: 2,
        management_consistency: { label: 'consistent', confidence: 0.78, evidence_snippets: ['Management repeatedly described cloud and AI strategy.'], limitations: [], affects_score: false },
        strategy_clarity: { label: 'clear', confidence: 0.72, evidence_snippets: ['Management described platform priorities.'], limitations: [], affects_score: false },
        risk_acknowledgement: { label: 'partial', confidence: 0.65, evidence_snippets: ['Management acknowledged compute cost pressure.'], limitations: [], affects_score: false },
        customer_demand_signal: { label: 'strong_positive', confidence: 0.7, evidence_snippets: [], limitations: [], affects_score: false },
        margin_pressure_signal: { label: 'manageable_pressure', confidence: 0.66, evidence_snippets: [], limitations: [], affects_score: false },
        capital_allocation_focus: { label: 'reinvestment_focused', confidence: 0.67, evidence_snippets: [], limitations: [], affects_score: false },
        positive_themes: [{ theme: 'customer_demand', label: 'supportive_context', evidence_snippets: ['Customer demand is strong.'], confidence: 0.6, limitations: [], affects_score: false }],
        risk_themes: [{ theme: 'margin_pressure', label: 'review_context', evidence_snippets: ['Compute costs remain a margin pressure.'], confidence: 0.6, limitations: [], affects_score: false }],
        manual_checks: ['Review full transcript context before interpreting management claims.'],
        limitations: ['Earnings transcript analysis is research context only.'],
        affects_score: false,
        not_investment_advice: true,
      },
      jane_criteria_external_evidence: {
        ticker: 'NVDA',
        provider: 'fmp',
        source: 'fmp_earnings_transcript',
        source_status: { ...mockStatus, source_type: 'live', provider: 'fmp', source_date: '2026-04-24' },
        criteria_count: 2,
        criteria: [
          {
            criterion_id: 2,
            criterion_name: 'Visionary Founder / CEO',
            source: 'fmp_earnings_transcript',
            source_quality: 'provider_backed',
            support_level: 'partial',
            confidence: 0.7,
            covered_submetrics: ['long_term_vision_consistency'],
            evidence_snippets: ['Management repeatedly described cloud and AI strategy.'],
            manual_checks: ['Confirm transcript themes against filings.'],
            limitations: ['Transcript context only.'],
            missing_data: [],
            requires_manual_review: true,
            affects_score: false,
          },
          {
            criterion_id: 17,
            criterion_name: 'Mission and Narrative Power',
            source: 'fmp_earnings_transcript',
            source_quality: 'provider_backed',
            support_level: 'supportive',
            confidence: 0.72,
            covered_submetrics: ['clear_long_term_mission', 'founder_narrative_consistency'],
            evidence_snippets: ['Management described platform priorities.'],
            manual_checks: ['Confirm transcript themes against filings.'],
            limitations: ['Transcript context only.'],
            missing_data: [],
            requires_manual_review: true,
            affects_score: false,
          },
        ],
        manual_checks: ['Confirm transcript themes against filings.'],
        limitations: ['Transcript context only.'],
        affects_score: false,
        not_investment_advice: true,
      },
      government_relationship_evidence: {
        ticker: 'NVDA',
        provider: 'usaspending',
        source: 'usaspending_contract_awards',
        source_status: { ...mockStatus, source_type: 'live', provider: 'usaspending', source_date: '2025-02-14' },
        query_name: 'NVIDIA Corporation',
        recipient_candidates: [{ recipient_name: 'NVIDIA CORPORATION', recipient_hash: 'recipient-nvda-parent', uei: 'NVDAUEI123', duns: null, source: 'usaspending_recipient_autocomplete' }],
        award_records: [],
        total_obligated_amount: 15000000,
        award_count: 2,
        top_awarding_agencies: [{ agency: 'Department of Defense', obligated_amount: 12500000, award_count: 1 }],
        criteria_count: 1,
        criteria: [{
          criterion_id: 15,
          criterion_name: 'Regulatory / Government Relationship',
          source: 'usaspending_contract_awards',
          source_quality: 'provider_backed',
          support_level: 'supportive',
          confidence: 0.74,
          covered_submetrics: ['government_contracts', 'defense_or_infrastructure_status'],
          evidence_snippets: ['Department of Defense: $12,500,000 across 1 award(s).'],
          manual_checks: ['Confirm recipient candidates, subsidiaries, award descriptions, and agency context before relying on C15 government relationship evidence.'],
          limitations: ['Government contract context only.'],
          missing_data: [],
          requires_manual_review: true,
          affects_score: false,
        }],
        relationship_signal: 'supportive',
        manual_checks: ['Confirm recipient candidates, subsidiaries, award descriptions, and agency context before relying on C15 government relationship evidence.'],
        limitations: ['Government contract context only.'],
        affects_score: false,
        not_investment_advice: true,
      },
      overheat_risk: {
        score: 63,
        label: 'overheated',
        confidence: 0.72,
        derived_metrics: {
          components: {
            volume_and_extension_context_score: {
              score: 75,
              label: 'overheated',
              derived_metrics: { volume_ratio: 2.5, price_vs_200d_pct: 30 },
            },
          },
        },
      },
      financial_quality: { score: 52, label: 'adequate', confidence: 0.7 },
      smart_money: { score: 48, label: 'neutral', confidence: 0.62 },
      human_verification_queue: [
        {
          item: 'jane_social_heat_check',
          question: 'Have non-investor friends or family recently asked you about this stock or theme unprompted?',
          jane_reference: 'Jane handbook social heat check.',
          action: 'If yes, treat as additional overheat evidence. Not a scoring input — human judgment required.',
          needs_human_verification: true,
        },
      ],
      not_investment_advice: true,
    } as StockAnalysis;

    const html = renderToStaticMarkup(<AnalystBriefSection result={result} />);

    expect(html).toContain('Analyst Brief');
    expect(html).toContain('watchlist candidate');
    expect(html).toContain('Data quality: B');
    expect(html).toContain('Macro: neutral to constructive');
    expect(html).toContain('Entry timing conditions');
    expect(html).toContain('Score 0 means Jane entry timing conditions are not met; this is expected near market highs.');
    expect(html).toContain('Fed consecutive cuts');
    expect(html).toContain('0 consecutive cut(s)');
    expect(html).toContain('Market drawdown and stabilization');
    expect(html).toContain('SPY -4.0%, QQQ -7.0% drawdown');
    expect(html).toContain('VIX spike and recovery');
    expect(html).toContain('Overheat / normal / fear state');
    expect(html).toContain('Non-scoring explanation');
    expect(html).toContain('Management narrative context');
    expect(html).toContain('Provider: FMP');
    expect(html).toContain('Quarters analyzed: 2');
    expect(html).toContain('Strategy clarity: clear');
    expect(html).toContain('Risk acknowledgement: partial');
    expect(html).toContain('Non-scoring evidence only');
    expect(html).toContain('C2 Visionary Founder / CEO: partial (provider_backed)');
    expect(html).toContain('C17 Mission and Narrative Power: supportive (provider_backed)');
    expect(html).toContain('Covered: long term vision consistency');
    expect(html).toContain('Confirm transcript themes against filings.');
    expect(html).toContain('Government relationship context');
    expect(html).toContain('Provider: USASPENDING');
    expect(html).toContain('Total obligated amount: $15,000,000');
    expect(html).toContain('Award count: 2');
    expect(html).toContain('C15 Regulatory / Government Relationship: supportive (provider_backed)');
    expect(html).toContain('Covered: government contracts');
    expect(html).toContain('Department of Defense: $12,500,000 across 1 award(s)');
    expect(html).toContain('Confirm recipient candidates, subsidiaries, award descriptions, and agency context before relying on C15 government relationship evidence.');
    expect(html).toContain('Overheat: overheated');
    expect(html).toContain('Volume ratio: 2.5x');
    expect(html).toContain('Price vs 200d MA: 30%');
    expect(html).toContain('Social heat: human verification only');
    expect(html).toContain('Verify monopoly power evidence.');
    expect(html).toContain('Not investment advice');
    expect(html).not.toContain('Social heat score');
    expect(html).not.toContain('[object Object]');
  });

  it('renders research signal explanations for common confusing outputs', () => {
    const result = {
      ticker: 'NVDA',
      market: 'US',
      jane_criteria_coverage: {
        covered_count: 0,
        partial_count: 1,
        insufficient_count: 19,
        coverage_gap_count: 19,
        user_input_required_count: 19,
        financial_proxy_available_count: 6,
        source_quality_summary: 'Jane 20 coverage is preliminary and needs manual qualitative evidence.',
        not_investment_advice: true,
        criteria: [],
      },
      jane_company_quality: {
        ...score({ ...mockStatus, source_type: 'derived', provider: 'derived_from_yfinance' }),
        label: 'preliminary',
        source_status: { ...mockStatus, source_type: 'derived', provider: 'derived_from_yfinance' },
        criteria: [],
      },
      market_timing_context: {
        ...score({ ...mockStatus, source_type: 'derived', provider: 'derived_from_yfinance' }),
        score: 0,
        label: 'insufficient_data_or_unfavorable',
      },
      institutional_13f: {
        ...score({ ...mockStatus, source_type: 'derived', provider: 'derived_from_SEC_EDGAR_13F' }),
        raw_data: {
          candidate_specific_evidence: {
            interpretation_label: 'no_reported_13f_position_observed',
            score_contribution_allowed: false,
          },
        },
      },
      valuation_context: {
        ...score({ ...mockStatus, source_type: 'derived', provider: 'derived_from_yfinance' }),
        label: 'valuation_context_elevated',
      },
      not_investment_advice: true,
    } as StockAnalysis;

    const html = renderToStaticMarkup(<ResearchSignalExplanationSection result={result} />);

    expect(html).toContain('Research Signal Explanation');
    expect(html).toContain('Coverage Matrix is evidence completeness');
    expect(html).toContain('Market Sentiment measures entry environment');
    expect(html).toContain('Fallback badges lower confidence');
    expect(html).toContain('No reported 13F position is not a negative trading signal');
    expect(html).toContain('Elevated valuation is a risk context');
    expect(html).toContain('Not investment advice');
    expect(html).not.toContain('[object Object]');
  });

  it('explains Form 4 fallback neutrality when fallback source status is present', () => {
    const fallbackStatus: DataSourceStatus = {
      ...mockStatus,
      source_type: 'fallback',
      provider: 'SEC EDGAR',
      fallback_used: true,
      fallback_reason: 'Live SEC Form 4 fetch failed',
    };
    const result = {
      ticker: 'NVDA',
      market: 'US',
      insider_activity: {
        ...score(fallbackStatus),
        label: 'insider_activity_neutral',
        raw_data: { source_status: fallbackStatus },
      },
      smart_money: {
        ...score({ ...mockStatus, source_type: 'derived', provider: 'mixed_smart_money_sources' }),
        source_quality_breakdown: {
          form4: { source_type: 'fallback', interpretation: 'Fallback-limited.', score_impact: 'Neutral context.' },
        },
      },
      not_investment_advice: true,
    } as StockAnalysis;

    const html = renderToStaticMarkup(<ResearchSignalExplanationSection result={result} />);

    expect(html).toContain('Fallback Form 4 rows are not scored as insider selling pressure');
    expect(html).toContain('disposition counts are treated as neutral context');
    expect(html).not.toContain('insider_distribution_risk');
    expect(html).not.toContain('[object Object]');
  });

  it('renders validation report export controls without adding an editor', () => {
    const html = renderToStaticMarkup(
      <ValidationReportExportSection
        ticker="NVDA"
        theme="AI infrastructure"
        userReason="External trend research"
        qualitativeEvidenceJson=""
      />,
    );
    expect(html).toContain('Validation Report Export');
    expect(html).toContain('Export JSON');
    expect(html).toContain('Export Markdown');
    expect(html).toContain('Include raw evidence');
    expect(html).toContain('Export is research reference only. Not investment advice.');
    expect(html).not.toContain('report editor');
    expect(html).not.toContain('[object Object]');
  });

  it('validates qualitative evidence JSON before analyze requests', () => {
    const parsed = parseQualitativeEvidenceJson(JSON.stringify([
      {
        criterion: 'network_effect',
        evidence_type: 'platform_ecosystem',
        summary: 'CUDA developer ecosystem claim requiring manual verification.',
        source_label: 'User research note',
        confidence: 0.65,
        user_provided: true,
        limitations: ['Manual review required.'],
      },
    ]));

    expect(parsed?.[0].criterion).toBe('network_effect');
    const canonical = parseQualitativeEvidenceJson(JSON.stringify([
      {
        criterion: 'monopoly_power',
        criterion_id: 1,
        criterion_name: 'Market Monopoly / Entry Barrier',
        submetric: 'switching_cost',
        evidence_type: 'switching_cost',
        summary: 'Customer migration requires workflow retraining and data migration.',
        source_label: 'user research note',
        confidence: 0.6,
        user_provided: true,
        limitations: ['Manual review required.'],
      },
    ]));
    expect(canonical?.[0].criterion_id).toBe(1);
    expect(canonical?.[0].criterion_name).toBe('Market Monopoly / Entry Barrier');
    expect(canonical?.[0].submetric).toBe('switching_cost');
    const adr = parseQualitativeEvidenceJson(JSON.stringify([
      {
        criterion: 'visionary_founder_ceo',
        criterion_id: 2,
        criterion_name: 'Visionary Founder / CEO',
        submetric: 'founder_ownership',
        evidence_type: 'filing_reference',
        summary: 'Annual report governance disclosure describes leadership ownership alignment requiring human review.',
        source_label: 'Nokia Annual Report FY2025',
        source_url: 'https://example.com/nokia-annual-report.pdf',
        document_title: 'Nokia Annual Report 2025',
        document_date: '2026-03-05',
        filing_period: 'FY2025',
        quoted_text: 'Governance section quote for local filing review.',
        adr_evidence_type: 'annual_report',
        local_market: 'NASDAQ Helsinki',
        local_ticker: 'NOKIA',
        confidence: 0.72,
        user_provided: true,
        limitations: ['Manual ADR filing verification required.'],
      },
    ]));
    expect(adr?.[0].adr_evidence_type).toBe('annual_report');
    expect(adr?.[0].document_date).toBe('2026-03-05');
    expect(adr?.[0].local_ticker).toBe('NOKIA');
    expect(() => parseQualitativeEvidenceJson('[{"criterion":"visionary_founder_ceo","evidence_type":"filing_reference","summary":"x","source_label":"note","confidence":0.5,"user_provided":true,"adr_evidence_type":"bad_type"}]')).toThrow('unsupported adr_evidence_type');
    expect(() => parseQualitativeEvidenceJson('[{"criterion":"unsupported","evidence_type":"platform_ecosystem","summary":"x","source_label":"note","confidence":0.5,"user_provided":true}]')).toThrow('unsupported criterion');
    expect(() => parseQualitativeEvidenceJson('[{"criterion":"network_effect","evidence_type":"platform_ecosystem","summary":"","source_label":"note","confidence":0.5,"user_provided":true}]')).toThrow('needs a summary');
    expect(() => parseQualitativeEvidenceJson('[{"criterion":"network_effect","evidence_type":"platform_ecosystem","summary":"x","source_label":"note","confidence":2,"user_provided":true}]')).toThrow('between 0 and 1');
  });

  it('accepts each canonical Jane 20 qualitative criterion and rejects unsupported criteria', () => {
    const canonicalCriteria = [
      'monopoly_power',
      'visionary_founder_ceo',
      'early_skepticism',
      'disruptive_innovation',
      'superior_technology_r_and_d',
      'scalable_business_model',
      'brand_power_fandom',
      'data_advantage',
      'capital_allocation',
      'cash_flow_creation',
      'mega_trend_fit',
      'talent_attraction_retention',
      'global_expansion',
      'life_changing_necessary_product',
      'regulatory_government_relationship',
      'network_effect',
      'mission_narrative_power',
      'patents_ip',
      'vc_institutional_support',
      'retention_repurchase_rate',
    ];
    const parsed = parseQualitativeEvidenceJson(JSON.stringify(canonicalCriteria.map((criterion) => ({
      criterion,
      evidence_type: 'user_provided_note',
      summary: `Specific ${criterion} claim requiring manual verification with cited user evidence.`,
      source_label: 'User research note',
      confidence: 0.6,
      user_provided: true,
      limitations: ['Manual review required.'],
    }))));

    expect(parsed?.map((item) => item.criterion)).toEqual(canonicalCriteria);
    expect(() => parseQualitativeEvidenceJson('[{"criterion":"unsupported_criterion","evidence_type":"user_provided_note","summary":"x","source_label":"note","confidence":0.5,"user_provided":true}]')).toThrow('unsupported criterion');
  });

  it('validates request-scoped comparison evidence JSON', () => {
    const parsed = parseQualitativeEvidenceJson(JSON.stringify([
      {
        criterion: 'network_effect',
        evidence_type: 'ecosystem_comparison',
        summary: 'CUDA ecosystem comparison claim requiring manual verification.',
        source_label: 'User competitor research note',
        confidence: 0.65,
        user_provided: true,
        limitations: ['Manual review required.'],
        comparison_context: {
          comparison_type: 'platform_ecosystem',
          peer_companies: ['AMD', 'INTC'],
          comparison_summary: 'CUDA ecosystem is manually compared against ROCm and oneAPI.',
          claimed_advantage: 'stronger',
          source_basis: 'user_note',
          limitations: ['Needs peer validation.'],
        },
      },
    ]));

    expect(parsed?.[0].evidence_type).toBe('ecosystem_comparison');
    expect(parsed?.[0].comparison_context?.peer_companies).toEqual(['AMD', 'INTC']);
    expect(() => parseQualitativeEvidenceJson('[{"criterion":"network_effect","evidence_type":"ecosystem_comparison","summary":"x","source_label":"note","confidence":0.5,"user_provided":true,"comparison_context":{"comparison_type":"unsupported","comparison_summary":"x","claimed_advantage":"unclear","peer_companies":[],"source_basis":"user_note","limitations":[]}}]')).toThrow('unsupported comparison_type');
  });

  it('does not render profile objects as [object Object]', () => {
    const html = renderToStaticMarkup(
      <ProfileGrid
        profile={{
          company_name: 'NVIDIA Corporation',
          research_context: {
            theme: 'AI infrastructure',
            user_reason: 'External trend research',
          },
          source_status: mockStatus,
        }}
      />,
    );
    expect(html).not.toContain('[object Object]');
    expect(html).toContain('research_context.theme');
    expect(html).toContain('AI infrastructure');
    expect(html).toContain('research_context.user_reason');
    expect(html).toContain('External trend research');
    expect(html).toContain('source_status.source_type');
    expect(html).toContain('mock');
    expect(html).toContain('source_status.provider');
    expect(html).toContain('phase1_mock_dataset');
  });

  it('shows a mock leadership warning', () => {
    const html = renderToStaticMarkup(<ScoreBlock title="Leadership" score={score()} />);
    expect(html).toContain('Leadership score is mock-based preliminary evidence');
  });

  it('uses nested source_status for source badges instead of Unknown', () => {
    const html = renderToStaticMarkup(<ScoreBlock title="Leadership" score={score({ ...mockStatus, source_type: 'derived', provider: 'derived_from_yfinance' })} />);
    expect(html).toContain('Derived');
    expect(html).not.toContain('Unknown');
  });

  it('renders Candidate Validation Summary', () => {
    const result = {
      ticker: 'NVDA',
      market: 'US',
      candidate_validation_summary: {
        ticker: 'NVDA',
        research_priority: 'watchlist_candidate',
        score: 58,
        confidence: 0.72,
        environment_assessment: 'Macro environment is neutral.',
        company_assessment: 'Company evidence remains mock-based.',
        smart_money_assessment: 'Smart-money evidence is limited.',
        data_quality_assessment: 'Grade C.',
        overall_summary: 'NVDA qualifies as a watchlist_candidate research candidate.',
        primary_strengths: ['Macro context is neutral.'],
        primary_risks: ['Leadership evidence is mock-based.'],
        missing_or_mock_evidence: ['leadership_score'],
        next_manual_checks: ['Replace mock leadership evidence.'],
      },
    } as StockAnalysis;
    const html = renderToStaticMarkup(<CandidateSummarySection result={result} />);
    expect(html).toContain('Candidate Validation Summary');
    expect(html).toContain('watchlist_candidate');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Data Quality Summary', () => {
    const html = renderToStaticMarkup(
      <AnalyzeDataQualitySection
        dataQuality={{
          mode: 'mixed_preliminary',
          confidence_cap_applied: true,
          confidence_cap_reason: 'Mock evidence caps confidence.',
          live_components: 3,
          mock_components: 2,
          fallback_components: 1,
          missing_source_date_components: 0,
          stale_components: 0,
          source_quality_grade: 'C',
          source_quality_summary: 'Some evidence is preliminary.',
          mock_evidence_categories: ['leadership_score'],
          fallback_evidence_categories: ['smart_money'],
          optional_provider_fallback_categories: ['earnings_transcript_analysis', 'fmp_financials'],
          missing_source_date_categories: [],
          excluded_from_scoring: ['ISM Manufacturing PMI', 'CNN Fear & Greed'],
          insufficient_evidence_categories: ['monopoly_power', 'network_effect'],
          company_quality: {
            evidence_backed_criteria_count: 3,
            insufficient_criteria_count: 4,
            mock_criteria_count: 0,
            derived_live_criteria_count: 3,
            user_context_criteria_count: 1,
            filing_backed_criteria_count: 1,
          },
          sec_companyfacts: {
            available: true,
            source_type: 'live',
            filing_backed_metric_count: 8,
            missing_concept_count: 2,
            latest_filing_date: '2026-03-15',
            latest_report_period: '2026-01-31',
            agreement_level_with_yfinance: 'high',
          },
          fmp_financials: {
            available: true,
            source_type: 'live',
            reported_currency: 'EUR',
            latest_fiscal_year: '2025',
            filing_date: '2026-03-05',
            proxy_metric_count: 17,
            ttm_ratio_count: 4,
            used_for_financial_quality: true,
            optional_enhancement: false,
          },
          foreign_filer_context: {
            ticker: 'NOK',
            is_foreign_filer_or_adr: true,
            country: null,
            exchange: 'NYSE',
            sec_missing_concept_count: 14,
            structural_coverage_limitation: true,
            user_explanation: '此公司為非美國本土公司／ADR，部分 SEC Companyfacts 與 13F candidate-specific coverage 受限屬正常情況。',
            limitations: ['ADR/foreign-filer SEC coverage can be structurally limited.'],
          },
        }}
      />,
    );
    expect(html).toContain('Data Quality Summary');
    expect(html).toContain('Grade C');
    expect(html).toContain('leadership_score');
    expect(html).toContain('Quality backed');
    expect(html).toContain('SEC facts');
    expect(html).toContain('FMP financial proxy');
    expect(html).toContain('FMP TTM ratios');
    expect(html).toContain('Optional provider fallback');
    expect(html).toContain('earnings_transcript_analysis');
    expect(html).toContain('ADR / foreign filer coverage note');
    expect(html).toContain('非美國本土公司');
    expect(html).toContain('EUR');
    expect(html).toContain('2025');
    expect(html).toContain('monopoly_power');
    expect(html).not.toContain('[object Object]');
  });

  it('renders corrected fallback categories without macro when macro is derived-live', () => {
    const html = renderToStaticMarkup(
      <AnalyzeDataQualitySection
        dataQuality={{
          mode: 'mixed_preliminary',
          confidence_cap_applied: true,
          confidence_cap_reason: 'Fallback smart-money evidence caps confidence.',
          live_components: 8,
          mock_components: 1,
          fallback_components: 2,
          missing_source_date_components: 0,
          stale_components: 0,
          source_quality_grade: 'B',
          source_quality_summary: 'Macro is derived from live or cached scored components; fallback categories reflect actual fallback source status.',
          mock_evidence_categories: ['legacy_leadership_score'],
          fallback_evidence_categories: ['insider_activity', 'smart_money'],
          optional_provider_fallback_categories: [],
          missing_source_date_categories: [],
          excluded_from_scoring: ['ISM Manufacturing PMI', 'CNN Fear & Greed'],
          insufficient_evidence_categories: [],
          company_quality: {
            evidence_backed_criteria_count: 4,
            insufficient_criteria_count: 3,
            mock_criteria_count: 0,
            derived_live_criteria_count: 2,
            user_context_criteria_count: 1,
            filing_backed_criteria_count: 2,
          },
          sec_companyfacts: {
            available: true,
            source_type: 'cached_live',
            filing_backed_metric_count: 12,
            missing_concept_count: 0,
            latest_filing_date: '2026-03-15',
            latest_report_period: '2026-01-31',
            agreement_level_with_yfinance: 'high',
          },
        }}
      />,
    );
    expect(html).toContain('insider_activity');
    expect(html).toContain('smart_money');
    expect(html).toContain('Excluded from scoring: ISM Manufacturing PMI, CNN Fear &amp; Greed');
    expect(html).not.toContain('<li>macro_environment</li>');
    expect(html).not.toContain('[object Object]');
  });

  it('renders qualitative evidence data quality counts', () => {
    const html = renderToStaticMarkup(
      <AnalyzeDataQualitySection
        dataQuality={{
          mode: 'mixed_preliminary',
          confidence_cap_applied: false,
          live_components: 8,
          mock_components: 1,
          fallback_components: 2,
          missing_source_date_components: 0,
          stale_components: 0,
          source_quality_grade: 'B',
          source_quality_summary: 'Some evidence is preliminary.',
          mock_evidence_categories: ['legacy_leadership_score'],
          fallback_evidence_categories: ['insider_activity', 'smart_money'],
          optional_provider_fallback_categories: [],
          missing_source_date_categories: [],
          excluded_from_scoring: [],
          insufficient_evidence_categories: ['monopoly_power'],
          qualitative_evidence: {
            provided: true,
            accepted_count: 2,
            rejected_count: 1,
            user_provided_count: 2,
            independently_verified_count: 0,
            criteria_covered: ['network_effect'],
            criteria_still_insufficient: ['monopoly_power'],
            comparison: {
              provided: true,
              accepted_count: 1,
              reviewed_count: 1,
              stale_count: 0,
              peer_company_count: 2,
              criteria_supported: ['network_effect'],
              claimed_advantage_breakdown: { stronger: 1, similar: 0, weaker: 0, unclear: 0 },
            },
          },
        }}
      />,
    );
    expect(html).toContain('Qualitative provided');
    expect(html).toContain('Accepted');
    expect(html).toContain('Comparison accepted');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Comparison Evidence Assessment', () => {
    const html = renderToStaticMarkup(
      <ComparisonEvidenceAssessmentSection
        assessment={{
          ticker: 'NVDA',
          comparison_evidence_count: 1,
          accepted_comparison_count: 1,
          reviewed_comparison_count: 1,
          stale_comparison_count: 0,
          criteria_supported: ['network_effect'],
          peer_companies_mentioned: ['AMD', 'INTC'],
          claimed_advantage_breakdown: { stronger: 1, similar: 0, weaker: 0, unclear: 0 },
          source_quality: 'user_provided',
          limitations: ['Peer comparison requires manual validation.'],
          missing_data: [],
          source_status: { ...mockStatus, source_type: 'derived', provider: 'user_provided_comparison_evidence' },
          items: [
            {
              origin: 'saved_library',
              criterion: 'network_effect',
              evidence_type: 'ecosystem_comparison',
              comparison_type: 'platform_ecosystem',
              peer_companies: ['AMD', 'INTC'],
              claimed_advantage: 'stronger',
              comparison_summary: 'CUDA ecosystem comparison requiring manual review.',
              source_basis: 'user_note',
              review_status: 'reviewed',
              evidence_quality_score: 88,
              evidence_quality_label: 'high',
              is_stale: false,
              accepted: true,
              limitations: [],
            },
          ],
        }}
      />,
    );
    expect(html).toContain('Comparison Evidence Assessment');
    expect(html).toContain('Peer companies: AMD, INTC');
    expect(html).toContain('stronger');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Evidence Matrix rows with source quality badges', () => {
    const html = renderToStaticMarkup(
      <EvidenceMatrixSection
        rows={[
          {
            category: 'leadership_score',
            status: 'supportive',
            score: 15,
            confidence: 0.7,
            source_quality: 'mock_only',
            summary: 'Leadership is preliminary.',
            key_evidence: ['15 / 20'],
            limitations: ['Mock leadership warning remains visible.'],
          },
        ]}
      />,
    );
    expect(html).toContain('Evidence Matrix');
    expect(html).toContain('mock_only');
    expect(html).toContain('Mock-only evidence');
  });

  it('renders macro evidence as derived live while excluded indicators stay separate', () => {
    const html = renderToStaticMarkup(
      <EvidenceMatrixSection
        rows={[
          {
            category: 'macro_environment',
            status: 'supportive',
            score: 66.75,
            confidence: 0.95,
            source_quality: 'derived_live',
            summary: 'Macro score is neutral_to_constructive under macro_v12_5.',
            key_evidence: ['Mock context score weight: 0', 'Excluded from scoring: ISM Manufacturing PMI, CNN Fear & Greed'],
            limitations: ['FRED release lag may apply.'],
          },
        ]}
      />,
    );
    expect(html).toContain('derived_live');
    expect(html).toContain('Excluded from scoring');
    expect(html).not.toContain('Fallback or mixed source quality');
  });

  it('renders Jane Company Quality criteria and user theme as context', () => {
    const html = renderToStaticMarkup(
      <JaneCompanyQualitySection
        profile={{
          research_context: { theme: 'AI infrastructure', user_reason: 'External trend research' },
        }}
        quality={{
          name: 'jane_company_quality_score',
          score: 32,
          max_score: 100,
          confidence: 0.5,
          label: 'preliminary',
          source_status: { ...mockStatus, source_type: 'derived', provider: 'derived_from_yfinance_company_quality' },
          limitations: ['Qualitative principles require evidence.'],
          missing_data: ['market share evidence'],
          criteria: [
            {
              name: 'monopoly_power',
              display_name: 'Market Monopoly / Moat',
              score: null,
              max_score: 10,
              status: 'insufficient',
              source_quality: 'insufficient',
              affects_score: false,
              evidence: [],
              limitations: [],
              missing_data: ['market share evidence', 'patent or moat evidence'],
            },
            {
              name: 'mega_trend_fit',
              display_name: 'Mega Trend Fit',
              score: null,
              max_score: 10,
              status: 'neutral',
              source_quality: 'user_context',
              affects_score: false,
              evidence: ['User-provided theme context: AI infrastructure'],
              limitations: ['User-provided theme is research context and is not independently verified evidence.'],
              missing_data: [],
            },
          ],
        }}
      />,
    );
    expect(html).toContain('Jane Company Quality');
    expect(html).toContain('Market Monopoly / Moat');
    expect(html).toContain('insufficient');
    expect(html).toContain('This is context, not verified evidence');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Validation OS Report with summary, gaps, and caveats', () => {
    const html = renderToStaticMarkup(
      <ValidationOSReportSection
        report={{
          ticker: 'NVDA',
          research_label: 'watchlist_candidate',
          validation_level: 'usable_preliminary_validation',
          data_quality_grade: 'B',
          report_sections: ['candidate_context', 'macro_backdrop', 'jane_quality', 'evidence_coverage', 'financial_signals', 'smart_money', 'manual_verification', 'source_quality'],
          executive_summary: 'NVDA validation workflow summary: structured evidence exists and manual verification remains required.',
          macro_backdrop: 'Macro environment is normal.',
          jane_quality_summary: 'Jane company quality is preliminary.',
          jane_criteria_coverage_summary: {
            covered_count: 0,
            partial_count: 1,
            insufficient_count: 19,
            coverage_gap_count: 20,
            user_input_required_count: 20,
            financial_proxy_available_count: 6,
            source_quality_summary: 'Jane 20 coverage: 0 covered, 1 partial, 19 insufficient.',
          },
          financial_signals_summary: 'Financial statement signals are adequate.',
          smart_money_summary: 'Smart-money assessment is neutral.',
          top_strengths: ['Macro environment has usable macro_v12_5 context.'],
          top_limitations: ['Manual validation required for user-provided qualitative claims.'],
          top_evidence_gaps: [
            {
              criterion_id: 1,
              criterion_name: 'Market Monopoly / Entry Barrier',
              coverage_status: 'partial',
              missing_submetrics: ['market_share', 'pricing_power'],
              next_manual_check: 'Verify Jane criterion 1 missing submetrics.',
            },
          ],
          top_manual_checks: ['Verify company fundamentals with current filings.'],
          source_quality_caveats: ['User-provided qualitative evidence is local validation context and still requires source review.'],
          manual_verification_required: true,
          scoring_note: 'Validation OS Report is non-scoring and does not change the final research verdict.',
          limitations: ['This report organizes existing analyze-stock outputs and does not add new data providers.'],
          not_investment_advice: true,
        }}
      />,
    );

    expect(html).toContain('Validation OS Report');
    expect(html).toContain('NVDA validation workflow summary');
    expect(html).toContain('Coverage gaps: 20');
    expect(html).toContain('Market Monopoly / Entry Barrier');
    expect(html).toContain('market_share, pricing_power');
    expect(html).toContain('non-scoring');
    expect(html).toContain('Not investment advice');
    expect(html).not.toContain('[object Object]');
  });

  it('renders user-provided qualitative criteria coverage in Jane Company Quality', () => {
    const html = renderToStaticMarkup(
      <JaneCompanyQualitySection
        quality={{
          name: 'jane_company_quality_score',
          score: 40,
          max_score: 100,
          confidence: 0.6,
          label: 'preliminary',
          source_status: { ...mockStatus, source_type: 'derived', provider: 'derived_from_yfinance_company_quality' },
          limitations: ['User-provided evidence is preliminary.'],
          missing_data: ['independent verification for Network Effect'],
          criteria: [
            {
              name: 'network_effect',
              display_name: 'Network Effect',
              score: 6,
              max_score: 10,
              status: 'neutral',
              source_quality: 'user_provided',
              evidence_strength: 'moderate',
              verification_level: 'user_provided',
              affects_score: true,
              evidence: ['platform ecosystem: CUDA developer ecosystem claim.'],
              limitations: ['Manual source review is required.'],
              missing_data: ['independent verification for Network Effect'],
            },
          ],
        }}
      />,
    );
    expect(html).toContain('user_provided');
    expect(html).toContain('moderate');
    expect(html).toContain('Network Effect');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Jane Criteria Coverage Matrix with counts and missing submetrics', () => {
    const html = renderToStaticMarkup(
      <JaneCriteriaCoverageSection
        coverage={{
          covered_count: 0,
          partial_count: 1,
          insufficient_count: 19,
          user_input_required_count: 20,
          financial_proxy_available_count: 6,
          source_quality_summary: 'Jane 20 coverage: 0 covered, 1 partial, 19 insufficient.',
          not_investment_advice: true,
          criteria: [
            {
              criterion_id: 1,
              criterion_name: 'Market Monopoly / Entry Barrier',
              evidence_type: 'qualitative',
              coverage_status: 'partial',
              source_quality: 'user_provided',
              confidence: 0.6,
              auto_derivable_submetrics: [],
              requires_user_input_submetrics: ['switching_cost', 'network_effect'],
              covered_submetrics: ['switching_cost'],
              missing_submetrics: ['network_effect'],
              evidence_item_count: 1,
              accepted_evidence_item_count: 1,
              financial_proxy_source: null,
              requires_human_verification: true,
              summary: 'Jane criterion 1 coverage is partial.',
              limitations: ['User-provided evidence still requires manual source verification.'],
              next_manual_check: 'Verify Jane criterion 1 missing submetrics: network_effect.',
            },
          ],
        }}
      />,
    );
    expect(html).toContain('Jane Criteria Coverage Matrix');
    expect(html).toContain('Partial: 1');
    expect(html).toContain('Insufficient: 19');
    expect(html).toContain('Market Monopoly / Entry Barrier');
    expect(html).toContain('switching_cost');
    expect(html).toContain('network_effect');
    expect(html).toContain('Not investment advice');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Qualitative Evidence Assessment accepted and rejected evidence', () => {
    const html = renderToStaticMarkup(
      <QualitativeEvidenceAssessmentSection
        assessment={{
          ticker: 'NVDA',
          evidence_count: 2,
          accepted_evidence_count: 1,
          rejected_evidence_count: 1,
          criteria_covered: ['network_effect'],
          criteria_still_insufficient: ['monopoly_power'],
          source_quality_summary: '1 user-provided qualitative evidence item accepted for preliminary review.',
          source_status: { ...mockStatus, source_type: 'derived', provider: 'user_provided_qualitative_evidence' },
          limitations: ['User-provided qualitative evidence is preliminary and requires manual verification.'],
          missing_data: [],
          evidence_items: [
            {
              criterion: 'network_effect',
              evidence_type: 'platform_ecosystem',
              summary: 'CUDA developer ecosystem claim requiring manual verification.',
              source_label: 'User research note',
              source_date: '2026-05-06',
              source_quality: 'user_provided',
              accepted: true,
              acceptance_reason: 'Accepted as preliminary user-provided qualitative evidence.',
              confidence: 0.65,
              limitations: ['Manual review required.'],
              missing_data: [],
            },
            {
              criterion: 'network_effect',
              evidence_type: 'platform_ecosystem',
              summary: 'Rejected qualitative evidence omitted from response for safety.',
              source_label: 'User research note',
              source_date: null,
              source_quality: 'rejected',
              accepted: false,
              acceptance_reason: 'Rejected because summary is empty.',
              confidence: 0,
              limitations: ['Rejected qualitative evidence does not affect scoring.'],
              missing_data: ['source_date'],
            },
          ],
        }}
      />,
    );
    expect(html).toContain('Qualitative Evidence Assessment');
    expect(html).toContain('user-provided, not independently verified');
    expect(html).toContain('accepted');
    expect(html).toContain('rejected');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Financial Statement Signals', () => {
    const html = renderToStaticMarkup(
      <FinancialStatementSignalsSection
        signals={{
          score: 45,
          confidence: 0.5,
          label: 'adequate',
          source_status: { ...mockStatus, source_type: 'derived', provider: 'derived_from_yfinance_financial_statement_signals' },
          limitations: ['Yfinance normalization caveat.'],
          missing_data: ['accounts_receivable'],
          signals: [
            {
              name: 'revenue_growth_quality',
              status: 'supportive',
              source_quality: 'filing_backed',
              evidence: ['Revenue YoY growth pct: 80.2'],
              limitations: [],
              missing_data: [],
            },
            {
              name: 'receivables_vs_revenue_risk',
              status: 'insufficient',
              source_quality: 'insufficient',
              evidence: [],
              limitations: [],
              missing_data: ['accounts_receivable'],
            },
          ],
        }}
      />,
    );
    expect(html).toContain('Financial Statement Signals');
    expect(html).toContain('revenue growth quality');
    expect(html).toContain('filing_backed');
    expect(html).toContain('accounts_receivable');
    expect(html).not.toContain('[object Object]');
  });

  it('renders SEC Financial Facts and missing concepts', () => {
    const html = renderToStaticMarkup(
      <SecFinancialFactsSection
        facts={{
          ticker: 'NVDA',
          cik: '0001045810',
          latest_filing_date: '2026-03-15',
          latest_report_period: '2026-01-31',
          source_status: { ...mockStatus, source_type: 'live', provider: 'SEC EDGAR companyfacts' },
          facts: {
            revenue: { value: 130000000000, unit: 'USD', period: '2026-01-31', form: '10-K', filed: '2026-03-15', concept: 'us-gaap:Revenues' },
            inventory: null,
          },
          missing_data: ['SEC Companyfacts concept unavailable for inventory'],
        }}
      />,
    );
    expect(html).toContain('SEC Financial Facts');
    expect(html).toContain('revenue');
    expect(html).toContain('Missing SEC concepts');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Fundamentals Cross-Check discrepancy warnings', () => {
    const html = renderToStaticMarkup(
      <FundamentalsCrossCheckSection
        crossCheck={{
          agreement_level: 'low',
          summary: 'SEC/yfinance cross-check found material metric discrepancies that need review.',
          source_status: { ...mockStatus, source_type: 'derived', provider: 'mixed_SEC_companyfacts_and_yfinance' },
          checked_metrics: [
            { name: 'revenue_ttm', yfinance_value: 80, sec_value: 130, difference_pct: 62.5, status: 'divergent' },
          ],
        }}
      />,
    );
    expect(html).toContain('Fundamentals Cross-Check');
    expect(html).toContain('SEC/yfinance discrepancy requires manual review');
    expect(html).toContain('divergent');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Company Fundamentals and valuation context', () => {
    const liveStatus = { ...mockStatus, source_type: 'live' as const, provider: 'yfinance' };
    const result = {
      ticker: 'NVDA',
      market: 'US',
      company_profile: {
        company_name: 'NVIDIA Corporation',
        market_cap: 3000000000000,
        enterprise_value: 2990000000000,
        source_status: liveStatus,
      },
      financial_quality: {
        ...score(liveStatus),
        raw_data: {
          revenue_yoy_growth_pct: 80,
          gross_margin_pct: 70,
          free_cash_flow_ttm: 29000000000,
          cash_and_equivalents: 26000000000,
          total_debt: 9000000000,
        },
        missing_data: ['share_dilution_3y_pct'],
      },
      valuation_context: {
        ...score({ ...liveStatus, source_type: 'derived', provider: 'derived_from_yfinance' }),
        raw_data: {
          price_to_sales_ttm: 24,
          ev_to_sales_ttm: 23,
          valuation_summary: 'Valuation context is elevated as a research risk flag.',
        },
        missing_data: [],
      },
    } as StockAnalysis;
    const html = renderToStaticMarkup(<CompanyFundamentalsSection result={result} />);
    expect(html).toContain('Company Fundamentals');
    expect(html).toContain('Revenue growth');
    expect(html).toContain('Price/sales TTM');
    expect(html).toContain('Missing fundamentals');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Next Manual Checks as checklist-style items', () => {
    const html = renderToStaticMarkup(
      <ManualChecksSection
        checks={[
          {
            priority: 'high',
            area: 'source_quality',
            check: 'Verify company profile and fundamentals with live company data.',
            reason: 'Mock evidence is present.',
            priority_rank: 1,
            blocking: true,
            category: 'source_quality',
            reason_short: 'Mock evidence is present.',
          },
        ]}
      />,
    );
    expect(html).toContain('Next Manual Checks');
    expect(html).toContain('Verify company profile');
    expect(html).toContain('#1 source quality');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Validation Quality Summary panel', () => {
    const html = renderToStaticMarkup(
      <ValidationQualitySummarySection
        summary={{
          ticker: 'NVDA',
          overall_validation_level: 'usable_preliminary_validation',
          why: 'Usable preliminary validation is available.',
          primary_supporting_evidence: ['Macro context is usable.'],
          primary_limiting_factors: ['insufficient qualitative evidence'],
          manual_review_required: true,
          highest_priority_review_items: ['Review source quality.'],
          data_quality_grade: 'B',
          confidence_cap_applied: true,
          confidence_cap_reason: 'Source constraints cap confidence.',
          not_investment_advice: true,
        }}
      />,
    );
    expect(html).toContain('Validation Quality Summary');
    expect(html).toContain('usable_preliminary_validation');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Smart Money Source Quality Breakdown panel', () => {
    const html = renderToStaticMarkup(
      <SmartMoneySourceQualitySection
        smartMoney={{
          ...score(mockStatus),
          source_quality_breakdown: {
            form4: { source_type: 'fallback', interpretation: 'Fallback-limited.', score_impact: 'Limited impact.' },
            institutional_13f: { source_type: 'mock', interpretation: 'Delayed quarterly evidence.', score_impact: 'Context only.' },
            options: {
              source_type: 'live',
              provider: 'openbb_stockgrid',
              large_block_count: 2,
              total_premium: 1750000,
              interpretation: 'OpenBB Stockgrid options blocks are provider-backed supplemental context.',
              score_impact: 'Provider-backed options context.',
            },
            aggregate_interpretation: 'source_quality_constraints_disclosed',
          },
        }}
      />,
    );
    expect(html).toContain('Smart Money Source Quality Breakdown');
    expect(html).toContain('Delayed quarterly evidence');
    expect(html).toContain('openbb_stockgrid');
    expect(html).toContain('1,750,000');
    expect(html).not.toContain('[object Object]');
  });

  it('renders Valuation Risk Explanation panel', () => {
    const html = renderToStaticMarkup(
      <ValuationRiskExplanationSection
        valuation={{
          ...score(mockStatus),
          explanation: {
            valuation_risk_label: 'elevated',
            plain_language_summary: 'Valuation risk appears elevated under available proxy metrics.',
            metrics_used: [{ name: 'price_to_sales_ttm', value: 24, threshold_context: 'Elevated proxy threshold >= 15.', limitation: 'Provider timing can differ.' }],
            why_it_matters: 'Proxy risk can temper validation confidence.',
            manual_review_hint: 'Compare with peer context.',
          },
        }}
      />,
    );
    expect(html).toContain('Valuation Risk Explanation');
    expect(html).toContain('price to sales ttm');
    expect(html).not.toContain('[object Object]');
  });
});
