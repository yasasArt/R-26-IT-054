import { Icon, type IconName } from "./Icon";

const pipelineStages: { icon: IconName; label: string; detail: string }[] = [
  { icon: "camera", label: "Camera", detail: "Live frame" },
  { icon: "shield", label: "YOLO gate", detail: "Valid workstation" },
  { icon: "chip", label: "MobileNet", detail: "8-frame clip" },
  { icon: "activity", label: "Counter", detail: "Confirmed transition" },
];

export function PipelinePanel() {
  return (
    <section className="panel pipeline-panel">
      <header className="panel-heading panel-heading-compact">
        <div>
          <span className="eyebrow">VISION ARCHITECTURE</span>
          <h2>Counting pipeline</h2>
        </div>
      </header>

      <div className="pipeline-stages">
        {pipelineStages.map((stage, index) => (
          <article key={stage.label} className="pipeline-stage">
            <div className="pipeline-stage-icon">
              <Icon name={stage.icon} size={17} />
            </div>
            <div className="pipeline-stage-copy">
              <strong>{stage.label}</strong>
              <span>{stage.detail}</span>
            </div>
            {index < pipelineStages.length - 1 ? <span className="pipeline-link" aria-hidden="true" /> : null}
          </article>
        ))}
      </div>

      <div className="transition-callout">
        <span>Only confirmed</span>
        <strong>SEWING</strong>
        <Icon name="arrow-right" size={15} />
        <strong>IDLE_SETUP</strong>
        <span>adds one piece.</span>
      </div>
    </section>
  );
}
