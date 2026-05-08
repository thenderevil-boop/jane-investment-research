import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import App from './App';

describe('App navigation', () => {
  it('renders Evidence Library tab', () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain('Evidence Dashboard');
    expect(html).toContain('Evidence Library');
    expect(html).toContain('Candidate Workspace');
    expect(html).toContain('Stock Research');
    expect(html).not.toContain('[object Object]');
  });
});
