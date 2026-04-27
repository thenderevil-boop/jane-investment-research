import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import ScoreCard from './ScoreCard';

describe('ScoreCard', () => {
  it('renders score, label, and confidence', () => {
    const html = renderToStaticMarkup(
      <ScoreCard title="Macro regime" score={72} maxScore={100} label="recovery" confidence={0.82} />,
    );
    expect(html).toContain('Macro regime');
    expect(html).toContain('72');
    expect(html).toContain('recovery');
    expect(html).toContain('82%');
  });
});
