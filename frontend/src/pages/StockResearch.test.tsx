import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { DataSourceStatus, ScoreLike, StockAnalysis } from '../types';
import { AnalyzeDataQualitySection, CandidateSummarySection, EvidenceMatrixSection, ManualChecksSection, ProfileGrid, ScoreBlock } from './StockResearch';

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
        }}
      />,
    );
    expect(html).toContain('Data Quality Summary');
    expect(html).toContain('Grade C');
    expect(html).toContain('leadership_score');
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
