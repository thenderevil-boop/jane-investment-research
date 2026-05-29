import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { getOperationsDiagnostics, getSEC13FManagerUniverseSettings, resetSEC13FManagerUniverseSettings, updateSEC13FManagerUniverseSettings } from '../api/client';
import type { OperationsDiagnostics as OperationsDiagnosticsPayload, SEC13FManagerUniverseSettings } from '../types';

function yesNo(value: boolean) {
  return value ? 'Yes' : 'No';
}

function listText(items: string[] | undefined, fallback = 'None listed') {
  return items?.length ? items.join(', ') : fallback;
}

function criteriaText(items: number[] | undefined) {
  return items?.length ? items.map((item) => `C${item}`).join(', ') : 'No criterion mapping';
}

export function SEC13FManagerUniverseEditor({ settings, onSaved }: { settings: SEC13FManagerUniverseSettings; onSaved?: (settings: SEC13FManagerUniverseSettings) => void }) {
  const [managerText, setManagerText] = useState(settings.effective_manager_ciks.join('\n'));
  const [note, setNote] = useState(settings.note ?? '');
  const [message, setMessage] = useState<string | null>(null);

  const handleSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const managerCiks = managerText.split(/[\n,]+/).map((item) => item.trim()).filter(Boolean);
    try {
      const updated = await updateSEC13FManagerUniverseSettings(managerCiks, note || undefined);
      setManagerText(updated.effective_manager_ciks.join('\n'));
      setNote(updated.note ?? '');
      setMessage('Local 13F manager universe saved. Future 13F target-manager reads use this local scope.');
      onSaved?.(updated);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Unable to save local 13F manager universe');
    }
  };

  const handleReset = async () => {
    try {
      const updated = await resetSEC13FManagerUniverseSettings();
      setManagerText(updated.effective_manager_ciks.join('\n'));
      setNote(updated.note ?? '');
      setMessage('Local 13F manager universe reset. Effective scope now follows startup env or bundled starter universe.');
      onSaved?.(updated);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Unable to reset local 13F manager universe');
    }
  };

  return (
    <section className="pageSection">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Editable settings</p>
          <h2>Edit 13F Manager Universe</h2>
        </div>
      </div>
      <p className="muted">Local settings override startup env for future 13F manager selection. This changes research scope only; it does not change scoring or make 13F real-time evidence.</p>
      <form onSubmit={handleSave}>
        <label htmlFor="sec13fManagers">Manager CIKs</label>
        <textarea id="sec13fManagers" value={managerText} onChange={(event) => setManagerText(event.target.value)} />
        <label htmlFor="sec13fNote">Note</label>
        <input id="sec13fNote" value={note} onChange={(event) => setNote(event.target.value)} />
        <div className="buttonRow">
          <button type="submit">Save local 13F universe</button>
          <button type="button" onClick={handleReset}>Reset local 13F universe</button>
        </div>
      </form>
      {message ? <p className="muted">{message}</p> : null}
      <div className="briefMetricGrid">
        <div><span>Effective source</span><strong>{settings.source}</strong></div>
        <div><span>Effective managers</span><strong>{settings.effective_manager_ciks.length}</strong></div>
        <div><span>Precedence</span><strong>{settings.precedence.join(' > ')}</strong></div>
      </div>
    </section>
  );
}

export function OperationsDiagnosticsPanel({ diagnostics, managerSettings, onManagerSettingsSaved }: { diagnostics: OperationsDiagnosticsPayload; managerSettings?: SEC13FManagerUniverseSettings | null; onManagerSettingsSaved?: (settings: SEC13FManagerUniverseSettings) => void }) {
  return (
    <main className="pageShell">
      <header className="heroCard">
        <p className="eyebrow">Phase 62 · Read-only operations</p>
        <h1>Operations Diagnostics</h1>
        <p>Review provider readiness, source status, Coverage Matrix readiness, and runtime 13F universe settings before interpreting Daily Report or Stock Research outputs.</p>
        <div className="disclaimer">Read-only diagnostics. No provider calls are triggered. Not investment advice.</div>
      </header>

      <section className="pageSection">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">Runtime</p>
            <h2>Read-only runtime status</h2>
          </div>
        </div>
        <div className="briefMetricGrid">
          <div><span>Daily report mode</span><strong>{diagnostics.runtime.daily_report_read_mode}</strong></div>
          <div><span>Live fetch from daily batch</span><strong>{yesNo(diagnostics.runtime.daily_batch_allow_live_fetch)}</strong></div>
          <div><span>Triggers provider calls</span><strong>{yesNo(diagnostics.runtime.triggers_provider_calls)}</strong></div>
        </div>
      </section>

      <section className="pageSection">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">Data sources</p>
            <h2>Provider Health</h2>
          </div>
        </div>
        <div className="tableWrap">
          <table>
            <thead>
              <tr><th>Provider</th><th>Enabled</th><th>Source / status</th><th>Key present</th><th>Cache</th><th>Next action</th></tr>
            </thead>
            <tbody>
              {diagnostics.providers.map((provider) => (
                <tr key={provider.provider_id}>
                  <td>{provider.label}</td>
                  <td>{yesNo(provider.enabled)}</td>
                  <td>{provider.source_type} / {provider.status}</td>
                  <td>{provider.requires_api_key ? yesNo(provider.has_api_key) : 'Not required'}</td>
                  <td>{provider.cache_ttl_days ? `${provider.cache_ttl_days} days` : provider.cache_ttl_hours ? `${provider.cache_ttl_hours} hours` : 'N/A'}</td>
                  <td>{provider.next_action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {diagnostics.source_health_actions?.length ? (
        <section className="pageSection">
          <div className="panelHeader">
            <div>
              <p className="eyebrow">Phase 66 · Routed operations work</p>
              <h2>Source Health Actions</h2>
            </div>
          </div>
          <p className="muted">Non-scoring operations action list. These route provider setup, disabled-source, and cache-refresh work without changing scores or verdicts.</p>
          <div className="tableWrap">
            <table>
              <thead>
                <tr><th>Action</th><th>Provider</th><th>Category</th><th>Criteria</th><th>Surfaces</th><th>Route</th><th>Recommended action</th></tr>
              </thead>
              <tbody>
                {diagnostics.source_health_actions.map((action) => (
                  <tr key={action.action_id}>
                    <td>{action.title}</td>
                    <td>{action.provider_id}</td>
                    <td>{action.category}</td>
                    <td>{criteriaText(action.affected_criteria)}</td>
                    <td>{listText(action.affected_surfaces)}</td>
                    <td>{action.route_hint}</td>
                    <td>{action.recommended_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="pageSection">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">Jane criteria</p>
            <h2>Coverage Readiness</h2>
          </div>
        </div>
        <div className="tableWrap">
          <table>
            <thead>
              <tr><th>Criterion</th><th>Provider</th><th>Readiness</th><th>Covered submetrics</th><th>Next action</th></tr>
            </thead>
            <tbody>
              {diagnostics.coverage_readiness.map((row) => (
                <tr key={`${row.criterion_id}-${row.provider_id}`}>
                  <td>C{row.criterion_id} {row.criterion_name}</td>
                  <td>{row.provider_id}</td>
                  <td>{row.readiness}</td>
                  <td>{listText(row.covered_submetrics)}</td>
                  <td>{row.next_action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="pageSection">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">13F runtime</p>
            <h2>13F Runtime Universe</h2>
          </div>
        </div>
        <div className="briefMetricGrid">
          <div><span>Universe source</span><strong>{diagnostics.manager_universe.source}</strong></div>
          <div><span>Manager count</span><strong>{diagnostics.manager_universe.manager_count}</strong></div>
          <div><span>Runtime override</span><strong>{yesNo(diagnostics.manager_universe.is_runtime_override)}</strong></div>
        </div>
        {diagnostics.manager_universe.warnings.length ? <p className="muted">{listText(diagnostics.manager_universe.warnings)}</p> : null}
      </section>

      {managerSettings ? <SEC13FManagerUniverseEditor settings={managerSettings} onSaved={onManagerSettingsSaved} /> : null}

      <section className="pageSection">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">Secrets policy</p>
            <h2>API key values are never returned</h2>
          </div>
        </div>
        <p className="muted">{diagnostics.secrets_policy.redaction_policy}</p>
      </section>
    </main>
  );
}

export default function OperationsDiagnostics() {
  const [diagnostics, setDiagnostics] = useState<OperationsDiagnosticsPayload | null>(null);
  const [managerSettings, setManagerSettings] = useState<SEC13FManagerUniverseSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getOperationsDiagnostics(), getSEC13FManagerUniverseSettings()])
      .then(([diagnosticsPayload, settingsPayload]) => {
        setDiagnostics(diagnosticsPayload);
        setManagerSettings(settingsPayload);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load operations diagnostics'));
  }, []);

  const handleManagerSettingsSaved = (settingsPayload: SEC13FManagerUniverseSettings) => {
    setManagerSettings(settingsPayload);
    getOperationsDiagnostics()
      .then(setDiagnostics)
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to refresh operations diagnostics'));
  };

  if (error) return <main className="pageShell"><div className="errorBanner">{error}</div></main>;
  if (!diagnostics) return <main className="pageShell"><div className="loading">Loading operations diagnostics…</div></main>;
  return <OperationsDiagnosticsPanel diagnostics={diagnostics} managerSettings={managerSettings} onManagerSettingsSaved={handleManagerSettingsSaved} />;
}
