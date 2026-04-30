import type { MacroScoreExplanation } from '../types';

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'N/A';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return String(value);
}

function formatPercent(value?: number): string {
  if (value === undefined || Number.isNaN(value)) return 'N/A';
  return `${Math.round(value * 100)}%`;
}

export default function MacroScoreExplanationPanel({
  explanation,
  provider,
}: {
  explanation?: MacroScoreExplanation | null;
  provider?: string | null;
}) {
  if (!explanation) return null;
  const showRounding = Math.abs(explanation.rounding_difference ?? 0) > 0;

  return (
    <div className="macroExplanationPanel">
      <div className="panelHeader">
        <div>
          <h3>Macro Score Explanation</h3>
          <p>Active FRED, yfinance, and derived components only.</p>
        </div>
        <span className="smallPill">{explanation.scoring_model_version}</span>
      </div>

      <dl className="macroSummaryGrid">
        <div><dt>Score</dt><dd>{formatValue(explanation.score)} / {formatValue(explanation.max_score)}</dd></div>
        <div><dt>Label</dt><dd>{explanation.label}</dd></div>
        <div><dt>Confidence</dt><dd>{formatPercent(explanation.confidence)}</dd></div>
        <div><dt>Active weight</dt><dd>{formatValue(explanation.active_weight_total)}</dd></div>
        <div><dt>Contribution sum</dt><dd>{formatValue(explanation.weighted_contribution_sum)}</dd></div>
        <div><dt>Data provider</dt><dd>{provider || 'N/A'}</dd></div>
        {showRounding ? <div><dt>Rounding difference</dt><dd>{formatValue(explanation.rounding_difference)}</dd></div> : null}
      </dl>

      <div className="macroGroupList">
        {explanation.groups.map((group) => (
          <section className="macroGroup" key={group.name}>
            <div className="macroGroupHeader">
              <h4>{group.display_name}</h4>
              <span>weight {formatValue(group.weight)} · contribution {formatValue(group.weighted_contribution_sum)}</span>
            </div>
            <div className="tableWrap">
              <table className="macroComponentTable">
                <thead>
                  <tr>
                    <th>Component</th>
                    <th>Raw value</th>
                    <th>Component score</th>
                    <th>Weight</th>
                    <th>Contribution</th>
                    <th>Source</th>
                    <th>Date</th>
                    <th>Freshness</th>
                  </tr>
                </thead>
                <tbody>
                  {group.components.map((component) => (
                    <tr key={component.name}>
                      <td>{component.display_name}</td>
                      <td>{formatValue(component.raw_value)}</td>
                      <td>{formatValue(component.component_score)}</td>
                      <td>{formatValue(component.weight)}</td>
                      <td>{formatValue(component.weighted_contribution)}</td>
                      <td>{component.provider || component.source_type || 'unknown'}</td>
                      <td>{component.source_date || 'N/A'}</td>
                      <td>
                        <span className={`freshnessPill ${component.is_fresh ? 'fresh' : 'stale'}`}>
                          {component.is_fresh ? 'fresh' : 'needs review'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))}
      </div>

      <section className="excludedIndicators">
        <h4>Excluded Indicators</h4>
        <div className="excludedIndicatorGrid">
          {explanation.excluded_indicators.map((indicator) => (
            <article className="excludedIndicator" key={indicator.name}>
              <strong>{indicator.display_name || indicator.name}</strong>
              <p>{indicator.reason || 'Excluded from active scoring.'}</p>
              <div className="conditionMeta">
                <span>affects_score=false</span>
                <span>weight=0</span>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
