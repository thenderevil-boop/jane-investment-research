import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import EvidenceLibrary from './EvidenceLibrary';
import { ComparisonEvidenceAssessmentSection, QualitativeEvidenceAssessmentSection } from './StockResearch';

describe('EvidenceLibrary', () => {
  it('renders evidence library filter, create form, and saved evidence table', () => {
    const html = renderToStaticMarkup(<EvidenceLibrary />);
    expect(html).toContain('Manual Evidence Library');
    expect(html).toContain('Evidence Library');
    expect(html).toContain('Create Evidence Item');
    expect(html).toContain('Saved Evidence');
    expect(html).toContain('Load evidence');
    expect(html).toContain('Create saved evidence');
    expect(html).toContain('Review status');
    expect(html).toContain('Source reliability');
    expect(html).toContain('Expires at');
    expect(html).toContain('Quality');
    expect(html).toContain('Comparison type');
    expect(html).toContain('Peer companies');
    expect(html).toContain('Claimed advantage');
    expect(html).toContain('Research Note Workflow');
    expect(html).toContain('Note title');
    expect(html).toContain('Research question');
    expect(html).toContain('Thesis direction');
    expect(html).toContain('Workflow status');
    expect(html).toContain('review_ready');
    expect(html).not.toContain('[object Object]');
  });

  it('renders ADR manual evidence library helper fields and review queue guidance', () => {
    const html = renderToStaticMarkup(<EvidenceLibrary />);
    expect(html).toContain('ADR Manual Evidence Library Helper');
    expect(html).toContain('ADR evidence type');
    expect(html).toContain('annual_report');
    expect(html).toContain('local_regulatory_filing');
    expect(html).toContain('Document title');
    expect(html).toContain('Document date');
    expect(html).toContain('Filing period');
    expect(html).toContain('Quoted text');
    expect(html).toContain('Local market');
    expect(html).toContain('Local ticker');
    expect(html).toContain('Translation note');
    expect(html).toContain('Document date can fill source date for freshness review');
    expect(html).toContain('review queue');
    expect(html).toContain('not independently verified');
    expect(html).toContain('does not change scoring');
    expect(html).not.toContain('[object Object]');
  });

  it('renders saved and request-scoped badges in Stock Research assessment', () => {
    const html = renderToStaticMarkup(
      <QualitativeEvidenceAssessmentSection
        assessment={{
          ticker: 'NVDA',
          evidence_count: 2,
          accepted_evidence_count: 2,
          rejected_evidence_count: 0,
          saved_evidence_count: 1,
          request_evidence_count: 1,
          deduplicated_count: 0,
          reviewed_count: 1,
          unreviewed_count: 0,
          reviewed_active_count: 1,
          unreviewed_active_count: 0,
          quality_score_average: 82,
          high_quality_count: 1,
          medium_quality_count: 1,
          low_quality_count: 0,
          incomplete_count: 0,
          stale_count: 1,
          review_due_count: 1,
          archived_or_rejected_ignored_count: 0,
          criteria_covered: ['network_effect', 'visionary_founder_ceo'],
          criteria_still_insufficient: ['monopoly_power'],
          source_quality_summary: 'Manual evidence accepted for preliminary review.',
          source_status: {
            source_type: 'derived',
            provider: 'user_provided_qualitative_evidence',
            source_date: '2026-05-06',
            fetched_at: null,
            is_fresh: false,
            freshness_window: 'user_provided_context',
            fallback_used: false,
            fallback_reason: null,
            limitations: [],
            missing_data: [],
          },
          limitations: ['Manual verification is required.'],
          missing_data: [],
          evidence_items: [
            {
              evidence_id: 'manual_1',
              origin: 'saved_library',
              review_status: 'reviewed',
              criterion: 'network_effect',
              evidence_type: 'platform_ecosystem',
              summary: 'CUDA ecosystem claim requiring manual verification.',
              source_label: 'User research note',
              source_date: '2026-05-06',
              source_quality: 'user_provided',
              accepted: true,
              acceptance_reason: 'Accepted as preliminary user-provided qualitative evidence.',
              confidence: 0.65,
              limitations: [],
              missing_data: [],
              evidence_quality_score: 86,
              evidence_quality_label: 'high',
              evidence_quality_reasons: ['Evidence has been locally reviewed.'],
              is_stale: false,
              stale_reason: null,
              next_review_due_at: '2027-05-06T00:00:00+00:00',
              source_reliability_label: 'company_investor_relations',
              note_title: 'NVDA CUDA ecosystem lock-in thesis',
              research_question: 'Does CUDA create durable developer switching costs?',
              thesis_direction: 'supportive',
              workflow_status: 'accepted',
            },
            {
              evidence_id: null,
              origin: 'request_scoped',
              review_status: null,
              criterion: 'visionary_founder_ceo',
              evidence_type: 'founder_operator',
              summary: 'Founder-led management claim requiring manual verification.',
              source_label: 'User research note',
              source_date: '2026-05-06',
              source_quality: 'user_provided',
              accepted: true,
              acceptance_reason: 'Accepted as preliminary user-provided qualitative evidence.',
              confidence: 0.6,
              limitations: [],
              missing_data: [],
              evidence_quality_score: 78,
              evidence_quality_label: 'medium',
              evidence_quality_reasons: ['Evidence is unreviewed.'],
              is_stale: true,
              stale_reason: 'source_date older than 365 days',
              next_review_due_at: null,
              source_reliability_label: 'user_note',
            },
          ],
        }}
      />,
    );
    expect(html).toContain('Saved 1');
    expect(html).toContain('Request 1');
    expect(html).toContain('saved_library');
    expect(html).toContain('request_scoped');
    expect(html).toContain('reviewed');
    expect(html).toContain('Reviewed 1');
    expect(html).toContain('Stale 1');
    expect(html).toContain('Avg quality 82');
    expect(html).toContain('company_investor_relations');
    expect(html).toContain('NVDA CUDA ecosystem lock-in thesis');
    expect(html).toContain('accepted');
    expect(html).not.toContain('[object Object]');
  });

  it('renders comparison evidence assessment without object leaks', () => {
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
          limitations: ['Comparison evidence requires manual validation.'],
          missing_data: [],
          source_status: {
            source_type: 'derived',
            provider: 'user_provided_comparison_evidence',
            source_date: '2026-05-07',
            fetched_at: null,
            is_fresh: false,
            freshness_window: 'user_provided_context',
            fallback_used: false,
            fallback_reason: null,
            limitations: [],
            missing_data: [],
          },
          items: [
            {
              evidence_id: 'manual_1',
              origin: 'saved_library',
              criterion: 'network_effect',
              evidence_type: 'ecosystem_comparison',
              comparison_type: 'platform_ecosystem',
              peer_companies: ['AMD', 'INTC'],
              claimed_advantage: 'stronger',
              comparison_summary: 'CUDA ecosystem is manually compared with ROCm and oneAPI.',
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
    expect(html).toContain('AMD, INTC');
    expect(html).toContain('stronger');
    expect(html).toContain('user-provided, not independently verified');
    expect(html).not.toContain('[object Object]');
  });
});
