import type { JaneReferenceConditions } from '../types';

const statusLabel: Record<string, string> = {
  observable_not_evaluated: '可觀察，未評分',
  partially_observable: '部分可觀察',
  observed_condition: '已觀察到條件',
  not_observed: '未觀察到',
  excluded_unlicensed_source: '資料源未啟用',
};

export default function JaneReferencePanel({ reference }: { reference?: JaneReferenceConditions | null }) {
  if (!reference) return null;
  return (
    <div className="janeReferencePanel">
      <div className="panelHeader">
        <div>
          <h3>Jane Methodology Reference Conditions</h3>
          <p>僅作方法論脈絡參考，不參與系統評分。</p>
        </div>
        <span className="smallPill">未納入評分</span>
      </div>
      <div className="referenceConditionGrid">
        {reference.conditions.map((condition) => (
          <article className="referenceCondition" key={condition.name}>
            <p className="conditionText">{condition.display_text}</p>
            <div className="conditionMeta">
              <span>{statusLabel[condition.system_status] ?? condition.system_status}</span>
              <span>score_contribution_allowed=false</span>
            </div>
            {condition.mapped_system_fields.length > 0 ? (
              <div className="fieldList">
                {condition.mapped_system_fields.map((field) => <span key={field}>{field}</span>)}
              </div>
            ) : null}
            {condition.limitation ? <p className="conditionLimitation">{condition.limitation}</p> : null}
          </article>
        ))}
      </div>
    </div>
  );
}
