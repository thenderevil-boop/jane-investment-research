import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { DataSourceStatus, ScoreLike, StockAnalysis } from '../types';
import { AnalyzeDataQualitySection, CandidateSummarySection, CompanyFundamentalsSection, EvidenceMatrixSection, FinancialStatementSignalsSection, FundamentalsCrossCheckSection, JaneCompanyQualitySection, ManualChecksSection, ProfileGrid, ScoreBlock, SecFinancialFactsSection } from './StockResearch';

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
        }}
      />,
    );
    expect(html).toContain('Data Quality Summary');
    expect(html).toContain('Grade C');
    expect(html).toContain('leadership_score');
    expect(html).toContain('Quality backed');
    expect(html).toContain('SEC facts');
    expect(html).toContain('monopoly_power');
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
          },
        ]}
      />,
    );
    expect(html).toContain('Next Manual Checks');
    expect(html).toContain('Verify company profile');
    expect(html).not.toContain('[object Object]');
  });
});
