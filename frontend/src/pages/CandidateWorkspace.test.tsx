import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import CandidateWorkspace from './CandidateWorkspace';

describe('CandidateWorkspace', () => {
  it('renders candidate workspace controls without object leakage', () => {
    const html = renderToStaticMarkup(<CandidateWorkspace />);
    expect(html).toContain('Watchlist Research Flow');
    expect(html).toContain('Add Candidate');
    expect(html).toContain('Candidates');
    expect(html).not.toContain('[object Object]');
  });
});
