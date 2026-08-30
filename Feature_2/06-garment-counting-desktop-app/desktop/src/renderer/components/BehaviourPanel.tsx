import { Icon } from "./Icon";

const frozenRules = [
  { code: "NORMAL", description: "Valid sewing cycles can be counted.", style: "rule-normal" },
  { code: "REWORK", description: "Repair time is recorded; counting pauses.", style: "rule-rework" },
  { code: "DOWNTIME", description: "Stopped production is timed separately.", style: "rule-downtime" },
];

export function BehaviourPanel() {
  return (
    <section className="panel behaviour-panel">
      <header className="panel-heading panel-heading-compact">
        <div>
          <span className="eyebrow">PHASE 00 BASELINE</span>
          <h2>Frozen operator rules</h2>
        </div>
        <Icon name="lock" size={16} className="muted-icon" />
      </header>

      <div className="behaviour-rules">
        {frozenRules.map((rule) => (
          <article key={rule.code} className="behaviour-row">
            <span className={`operator-mode ${rule.style}`}>{rule.code}</span>
            <span>{rule.description}</span>
          </article>
        ))}
      </div>

      <div className="behaviour-note">
        <Icon name="warning" size={16} />
        <span>Device disconnect pauses production. Reset never clears the garment count.</span>
      </div>
    </section>
  );
}
