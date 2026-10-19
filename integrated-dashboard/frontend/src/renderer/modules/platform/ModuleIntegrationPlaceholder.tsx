import type { DesktopAppInfo } from "../../../shared/types";
import { Icon } from "@garment-counter/components/Icon";
import { type WorkstationId, getWorkstation } from "./module-registry";
import { PlatformHeader } from "./PlatformHeader";

export function ModuleIntegrationPlaceholder({
  appInfo,
  workstationId,
  onExit,
}: {
  appInfo: DesktopAppInfo | null;
  workstationId: WorkstationId;
  onExit: () => void;
}) {
  const workstation = getWorkstation(workstationId);

  return (
    <section className="platform-shell integration-shell">
      <PlatformHeader appInfo={appInfo} compact onHome={onExit} />

      <main className="integration-main">
        <button type="button" className="platform-back-link" onClick={onExit}>
          <Icon name="arrow-right" size={15} className="platform-back-arrow" /> Choose another workstation
        </button>

        <div className={`integration-panel workstation-tone-${workstation.accent}`}>
          <span className="integration-panel-icon"><Icon name={workstation.icon} size={27} /></span>
          <span className="platform-eyebrow">{workstation.area}</span>
          <h1>{workstation.name}</h1>
          <p>{workstation.summary}</p>

          <div className="integration-feature-list">
            {workstation.features.map((feature) => <span key={feature}><Icon name="check" size={15} /> {feature}</span>)}
          </div>

          <div className="integration-notice"><Icon name="chip" size={18} /><span><strong>Integration slot is ready</strong><small>Connect your teammate’s existing frontend and independent backend to activate this workstation.</small></span></div>

          <dl className="integration-paths">
            <div><dt>Frontend adapter</dt><dd>{workstation.frontendEntry}</dd></div>
            <div><dt>Separate backend</dt><dd>{workstation.backendDirectory}</dd></div>
            <div><dt>Model resources</dt><dd>{workstation.modelDirectory}</dd></div>
          </dl>

          <button type="button" className="platform-primary-button" onClick={onExit}>Back to workstations <Icon name="arrow-right" size={16} /></button>
        </div>
      </main>
    </section>
  );
}
