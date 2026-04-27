import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import SignalBadge from './SignalBadge';

describe('SignalBadge', () => {
  it('renders the provided label', () => {
    const html = renderToStaticMarkup(<SignalBadge label="watchlist_candidate" variant="neutral" />);
    expect(html).toContain('watchlist_candidate');
    expect(html).toContain('neutral');
  });

  it('treats smart money supportive labels as positive variants', () => {
    const html = renderToStaticMarkup(<SignalBadge label="smart_money_supportive" />);
    expect(html).toContain('positive');
  });
});
