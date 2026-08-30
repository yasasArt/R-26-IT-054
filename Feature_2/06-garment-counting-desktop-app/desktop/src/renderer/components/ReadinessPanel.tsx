import { useState } from "react";

import type { ReadinessComponent, ReadinessComponentId, SystemReadiness } from "../../shared/types";
import { Icon, type IconName } from "./Icon";
import { StatusBadge } from "./StatusBadge";

const componentIcons: Record<ReadinessComponentId, IconName> = {
  desktop: "monitor",
  backend: "database",
  workstation_detector: "camera",
  garment_classifier: "chip",
  camera: "camera",
  workstation_view: "shield",
  iot_controller: "bluetooth",
};

function ReadinessRow({ component }: { component: ReadinessComponent }) {
  return (
    <article className="readiness-row">
      <div className={`readiness-icon readiness-icon-${component.status}`}>
        <Icon name={componentIcons[component.id]} size={18} />
      </div>

      <div className="readiness-copy">
        <div className="readiness-title-row">
          <h3>{component.label}</h3>
          <span>{component.description}</span>
        </div>
        <p>{component.detail}</p>
      </div>

      <StatusBadge status={component.status} />
    </article>
  );
}

export function ReadinessPanel({ readiness }: { readiness: SystemReadiness | null }) {
  const [expanded, setExpanded] = useState(false);
  const totalChecks = readiness?.components.length ?? 0;
  const readyChecks = readiness?.components.filter((component) => component.status === "ready").length ?? 0;

  return (
    <section className={`panel readiness-panel${expanded ? " is-expanded" : " is-collapsed"}`} id="readiness">
      <button
        type="button"
        className="panel-heading readiness-toggle"
        aria-expanded={expanded}
        aria-controls="readiness-check-list"
        onClick={() => setExpanded((current) => !current)}
      >
        <div>
          <span className="eyebrow">PRODUCTION PREFLIGHT</span>
          <h2>{expanded ? "Everything needed before a session" : `${readyChecks} of ${totalChecks} checks ready`}</h2>
        </div>
        <span className="readiness-toggle-meta">
          <span className={`connection-pill ${readiness?.productionReady ? "is-connected" : "is-pending"}`}>
            {readiness?.productionReady ? "Ready" : "View checks"}
          </span>
          <Icon name="arrow-right" size={17} className="readiness-toggle-arrow" />
        </span>
      </button>

      {expanded ? (
        <>
          <div className="readiness-list" id="readiness-check-list">
            {readiness?.components.map((component) => (
              <ReadinessRow key={component.id} component={component} />
            ))}
          </div>

          <footer className="readiness-footer">
            <Icon name="lock" size={15} />
            <span>Production stays locked until every required component is actually ready.</span>
          </footer>
        </>
      ) : null}
    </section>
  );
}
