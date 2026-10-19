import type { DesktopAppInfo } from "../../../shared/types";
import { Icon } from "@garment-counter/components/Icon";
import { type WorkstationId, WORKSTATION_MODULES } from "./module-registry";
import { PlatformHeader } from "./PlatformHeader";

export function WorkstationSelectionScreen({
  appInfo,
  selectedWorkstation,
  onSelect,
  onContinue,
  onBack,
}: {
  appInfo: DesktopAppInfo | null;
  selectedWorkstation: WorkstationId | null;
  onSelect: (id: WorkstationId) => void;
  onContinue: () => void;
  onBack: () => void;
}) {
  return (
    <section className="platform-shell selection-shell">
      <PlatformHeader appInfo={appInfo} compact onHome={onBack} />

      <main className="selection-main">
        <button type="button" className="platform-back-link" onClick={onBack}>
          <Icon name="arrow-right" size={15} className="platform-back-arrow" /> Platform overview
        </button>

        <div className="selection-heading">
          <span className="platform-eyebrow"><Icon name="layers" size={14} /> WORKSTATION ACCESS</span>
          <h1>Select your workstation</h1>
          <p>Choose the production area you want to open. Each workstation keeps its own dedicated workflow and analysis.</p>
        </div>

        <div className="workstation-grid" role="radiogroup" aria-label="Choose a workstation">
          {WORKSTATION_MODULES.map((workstation, index) => {
            const selected = selectedWorkstation === workstation.id;

            return (
              <button
                key={workstation.id}
                type="button"
                role="radio"
                aria-checked={selected}
                className={`workstation-card workstation-tone-${workstation.accent} ${selected ? "is-selected" : ""}`}
                onClick={() => onSelect(workstation.id)}
              >
                <span className="workstation-card-top">
                  <span className="workstation-card-icon"><Icon name={workstation.icon} size={24} /></span>
                  <span className="workstation-selection-indicator">{selected ? <Icon name="check" size={14} /> : null}</span>
                </span>

                <span className="workstation-area">{workstation.area}</span>
                <span className="workstation-name">{workstation.name}</span>
                <span className="workstation-summary">{workstation.summary}</span>

                <span className="workstation-features">
                  {workstation.features.map((feature) => (
                    <span key={feature}><Icon name="check" size={13} /> {feature}</span>
                  ))}
                </span>

                <span className="workstation-card-footer">
                  <span>WORKSTATION 0{index + 1}</span>
                  <span>{workstation.componentCount === 1 ? "1 COMPONENT" : "2 COMPONENTS"}</span>
                </span>
              </button>
            );
          })}
        </div>

        <div className="selection-actions">
          <span className="selection-helper">
            <Icon name="lock" size={15} /> Workstations operate independently with isolated application services.
          </span>
          <button type="button" className="platform-primary-button" onClick={onContinue} disabled={!selectedWorkstation}>
            Continue to workstation <Icon name="arrow-right" size={17} />
          </button>
        </div>
      </main>

      <footer className="platform-footer"><span>04 FEATURES · 04 RESEARCH COMPONENTS</span><span>SECURE LOCAL OPERATION</span></footer>
    </section>
  );
}
