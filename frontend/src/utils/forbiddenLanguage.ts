export const forbiddenTerms = [
  'buy',
  'sell',
  'hold',
  'liquidate',
  'exit position',
  'enter position',
  'must invest',
  '買進',
  '賣出',
  '持有',
  '出清',
  '進場',
  '離場',
  '必買',
];

export function detectForbiddenLanguage(value: unknown): string[] {
  const text = typeof value === 'string' ? value : JSON.stringify(value ?? '');
  const lower = text.toLowerCase();
  return forbiddenTerms.filter((term) => {
    if (/^[a-z ]+$/.test(term)) {
      return new RegExp(`\\b${term.replace(/\s+/g, '\\s+')}\\b`, 'i').test(lower);
    }
    return text.includes(term);
  });
}

export function hasForbiddenLanguage(value: unknown): boolean {
  return detectForbiddenLanguage(value).length > 0;
}
