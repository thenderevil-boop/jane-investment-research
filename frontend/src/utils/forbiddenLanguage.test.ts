import { describe, expect, it } from 'vitest';
import { detectForbiddenLanguage, hasForbiddenLanguage } from './forbiddenLanguage';

describe('forbidden language utility', () => {
  it('detects restricted English and Chinese terms', () => {
    expect(detectForbiddenLanguage('This says buy and 必買')).toEqual(['buy', '必買']);
  });

  it('ignores research labels and field names with underscores', () => {
    expect(hasForbiddenLanguage({ label: 'watchlist_candidate', key: 'net_insider_buy_value_180d' })).toBe(false);
  });
});
