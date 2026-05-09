import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import App from './App';

describe('App navigation', () => {
  it('opens to Stock Research and renders validation-first helper text', () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain('US Ticker Research');
    expect(html).toContain('Primary workflow: submit a ticker to validate the idea using evidence, data quality, and missing-data checks.');
    expect(html).toContain('Candidate Workspace and Evidence tools are supporting local workflow aids, not recommendations or note systems.');
    expect(html).toContain('Evidence Dashboard');
    expect(html).toContain('Evidence Library');
    expect(html).toContain('Candidate Workspace');
    expect(html).toContain('Stock Research');
    expect(html).not.toContain('[object Object]');
  });

  it('orders navigation around ticker validation first', () => {
    const html = renderToStaticMarkup(<App />);
    const navStart = html.indexOf('<nav');
    const navEnd = html.indexOf('</nav>');
    const nav = html.slice(navStart, navEnd);
    expect(nav.indexOf('Stock Research')).toBeLessThan(nav.indexOf('Candidate Workspace'));
    expect(nav.indexOf('Candidate Workspace')).toBeLessThan(nav.indexOf('Evidence Library'));
    expect(nav.indexOf('Evidence Library')).toBeLessThan(nav.indexOf('Evidence Dashboard'));
    expect(nav.indexOf('Evidence Dashboard')).toBeLessThan(nav.indexOf('Daily Report'));
  });
});
