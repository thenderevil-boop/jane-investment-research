export function sanitizeUserFacingText(value: string): string {
  return value
    .replace(/Research criteria coverage/g, 'Research criteria coverage')
    .replace(/Jane 20 criteria/g, '20 research criteria')
    .replace(/Jane criteria/g, 'research criteria')
    .replace(/Jane Criteria/g, 'Research Criteria')
    .replace(/Jane criterion/g, 'research criterion')
    .replace(/Jane Criterion/g, 'Research Criterion')
    .replace(/Jane reference condition/g, 'Research reference condition')
    .replace(/Jane Company Quality/g, 'Company Quality')
    .replace(/Jane company quality/g, 'company quality')
    .replace(/Jane quality/g, 'Quality')
    .replace(/Jane methodology/g, 'research methodology')
    .replace(/Jane Methodology/g, 'Research Methodology')
    .replace(/Jane framework/g, 'research framework')
    .replace(/Jane Framework/g, 'Research Framework')
    .replace(/Jane handbook/g, 'research handbook')
    .replace(/Jane qualitative/g, 'research qualitative')
    .replace(/Jane evidence/g, 'research evidence')
    .replace(/\bjane_company_quality\b/g, 'company_quality')
    .replace(/\bjane_criteria_external_evidence\b/g, 'criteria_external_evidence')
    .replace(/\bjane_criteria_coverage\b/g, 'criteria_coverage')
    .replace(/\bjane_reference_conditions\b/g, 'reference_conditions')
    .replace(/\bjane_quality_methodology_reference\b/g, 'quality_methodology_reference')
    .replace(/\bjane_social_heat_check\b/g, 'social_heat_check');
}

export function displayUserFacingKey(value: string): string {
  return sanitizeUserFacingText(value).replace(/_/g, ' ');
}

export function sanitizeUserFacingValue<T>(value: T): T {
  if (typeof value === 'string') return sanitizeUserFacingText(value) as T;
  if (Array.isArray(value)) return value.map((item) => sanitizeUserFacingValue(item)) as T;
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [sanitizeUserFacingText(key), sanitizeUserFacingValue(item)]),
    ) as T;
  }
  return value;
}
