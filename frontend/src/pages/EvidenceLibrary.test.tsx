import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import EvidenceLibrary from './EvidenceLibrary';
import { QualitativeEvidenceAssessmentSection } from './StockResearch';

describe('EvidenceLibrary', () => {
  it('renders evidence library filter, create form, and saved evidence table', () => {
    const html = renderToStaticMarkup(<EvidenceLibrary />);
    expect(html).toContain('Manual Evidence Library');
    expect(html).toContain('Evidence Library');
    expect(html).toContain('Create Evidence Item');
    expect(html).toContain('Saved Evidence');
    expect(html).toContain('Load evidence');
    expect(html).toContain('Create saved evidence');
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
    expect(html).not.toContain('[object Object]');
  });
});
