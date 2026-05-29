import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { OperationsDiagnostics as OperationsDiagnosticsPayload, SEC13FManagerUniverseSettings } from '../types';
import { OperationsDiagnosticsPanel } from './OperationsDiagnostics';

const payload: OperationsDiagnosticsPayload = {
  version: 'phase62_operations_diagnostics_v1',
  generated_at: '2026-05-26T00:00:00Z',
  runtime: {
    daily_report_read_mode: 'snapshot_first',
    daily_batch_allow_live_fetch: false,
    read_only: true,
    triggers_provider_calls: false,
    not_investment_advice: true,
  },
  providers: [
    {
      provider_id: 'sec_13f',
      label: 'SEC 13F institutional holdings',
      enabled: true,
      requires_api_key: false,
      has_api_key: false,
      source_type: 'live',
      status: 'available',
      cache_ttl_days: 7,
      limitations: ['13F filings are delayed.'],
      missing_data: [],
      next_action: 'Review candidate-specific target matches.',
    },
    {
      provider_id: 'fmp_financial_proxy',
      label: 'FMP financial statement proxy',
      enabled: false,
      requires_api_key: true,
      has_api_key: false,
      source_type: 'disabled',
      status: 'missing_key',
      cache_ttl_days: 7,
      limitations: [],
      missing_data: ['api_key'],
      next_action: 'Configure key if needed.',
    },
  ],
  coverage_readiness: [
    {
      criterion_id: 18,
      criterion_name: 'Patents / IP',
      provider_id: 'uspto_patentsview',
      readiness: 'ready',
      covered_submetrics: ['patent_count'],
      next_action: 'Review patent quality.',
      not_investment_advice: true,
    },
    {
      criterion_id: 19,
      criterion_name: 'VC / Institutional Support',
      provider_id: 'sec_13f',
      readiness: 'ready',
      covered_submetrics: ['institutional_support', 'fund_support'],
      next_action: 'Review delayed filings.',
      not_investment_advice: true,
    },
  ],
  manager_universe: {
    source: 'bundled_starter_universe',
    manager_count: 5,
    is_runtime_override: false,
    bundled_starter_count: 5,
    editable: true,
    warnings: [],
  },
  source_health_actions_version: 'phase66_source_health_actions_v1',
  source_health_actions: [
    {
      action_id: 'missing_fmp_key',
      provider_id: 'fmp_financial_proxy',
      severity: 'high',
      category: 'missing_key',
      title: 'Configure FMP key',
      recommended_action: 'Add FMP API key in local environment before relying on ADR financial proxy context.',
      affected_criteria: [5, 6, 10],
      affected_surfaces: ['operations', 'stock_research', 'daily_report'],
      route_hint: 'operations',
      affects_score: false,
      not_investment_advice: true,
    },
  ],
  secrets_policy: {
    api_key_values_returned: false,
    redaction_policy: 'only safe booleans are exposed; API key values are never returned',
  },
  not_investment_advice: true,
};

const managerSettings: SEC13FManagerUniverseSettings = {
  version: 'phase63_13f_manager_universe_settings_v1',
  source: 'local_settings',
  effective_manager_ciks: ['0001067983', '0000102909'],
  local_manager_ciks: ['0001067983', '0000102909'],
  startup_env_manager_ciks: ['0001364742'],
  bundled_starter_manager_ciks: ['0001067983', '0000102909', '0001364742', '0000093751', '0001214717'],
  bundled_starter_count: 5,
  editable: true,
  precedence: ['local_settings', 'startup_env', 'bundled_starter_universe'],
  note: 'test scope',
  warnings: [],
  not_investment_advice: true,
};

describe('OperationsDiagnosticsPanel', () => {
  it('renders provider health, coverage readiness, runtime universe, and secrets policy', () => {
    const html = renderToStaticMarkup(<OperationsDiagnosticsPanel diagnostics={payload} />);

    expect(html).toContain('Provider Health');
    expect(html).toContain('Source Health Actions');
    expect(html).toContain('Configure FMP key');
    expect(html).toContain('missing_key');
    expect(html).toContain('C5, C6, C10');
    expect(html).toContain('operations, stock_research, daily_report');
    expect(html).toContain('Non-scoring operations action');
    expect(html).toContain('Coverage Readiness');
    expect(html).toContain('SEC 13F institutional holdings');
    expect(html).toContain('C18 Patents / IP');
    expect(html).toContain('patent_count');
    expect(html).toContain('13F Runtime Universe');
    expect(html).toContain('bundled_starter_universe');
    expect(html).toContain('API key values are never returned');
    expect(html).not.toContain('[object Object]');
    expect(html).not.toContain('should_not_leak_phase62');
  });

  it('renders editable 13F manager universe controls when settings are loaded', () => {
    const html = renderToStaticMarkup(<OperationsDiagnosticsPanel diagnostics={payload} managerSettings={managerSettings} />);

    expect(html).toContain('Edit 13F Manager Universe');
    expect(html).toContain('Save local 13F universe');
    expect(html).toContain('Reset local 13F universe');
    expect(html).toContain('0001067983');
    expect(html).toContain('local_settings');
    expect(html).toContain('This changes research scope only; it does not change scoring');
  });
});
