import type { DesktopAppInfo } from "../../../shared/types";
import { Icon } from "@garment-counter/components/Icon";
import { getResearchComponentCount, WORKSTATION_MODULES } from "./module-registry";
import { PlatformHeader } from "./PlatformHeader";

function ManufacturingIllustration() {
  return (
    <div className="manufacturing-illustration" aria-hidden="true">
      <div className="illustration-grid" />
      <div className="illustration-orbit illustration-orbit-outer" />
      <div className="illustration-orbit illustration-orbit-inner" />

      <div className="illustration-core">
        <span className="illustration-core-glow" />
        <Icon name="chip" size={31} />
        <span>AI CORE</span>
      </div>

      <div className="illustration-station illustration-station-first">
        <span className="illustration-station-icon station-tone-indigo"><Icon name="activity" size={18} /></span>
        <span><strong>Sewing line</strong><small>Count · Cycle time</small></span>
        <span className="illustration-status-dot" />
      </div>

      <div className="illustration-station illustration-station-second">
        <span className="illustration-station-icon station-tone-green"><Icon name="shield" size={18} /></span>
        <span><strong>Quality check</strong><small>Good · Rework</small></span>
        <span className="illustration-status-dot" />
      </div>

      <div className="illustration-station illustration-station-packing">
        <span className="illustration-station-icon station-tone-violet"><Icon name="layers" size={18} /></span>
        <span><strong>Packing area</strong><small>Style · Color · Size</small></span>
        <span className="illustration-status-dot" />
      </div>

      <span className="illustration-particle illustration-particle-one" />
      <span className="illustration-particle illustration-particle-two" />
      <span className="illustration-particle illustration-particle-three" />
    </div>
  );
}

export function LandingScreen({
  appInfo,
  onContinue,
}: {
  appInfo: DesktopAppInfo | null;
  onContinue: () => void;
}) {
  return (
    <section className="platform-shell landing-shell">
      <PlatformHeader appInfo={appInfo} />

      <main className="landing-main">
        <div className="landing-hero">
          <div className="landing-copy">
            <span className="platform-eyebrow"><Icon name="spark" size={14} /> AI-POWERED APPAREL MANUFACTURING</span>
            <h1>Every production stage.<br /><span>One intelligent platform.</span></h1>
            <p>
              Bring sewing-line monitoring, rework counting, style and colour recognition, and size verification together
              in one focused desktop experience.
            </p>

            <div className="landing-actions">
              <button type="button" className="platform-primary-button" onClick={onContinue}>
                Explore workstations <Icon name="arrow-right" size={17} />
              </button>
              <span className="landing-caption"><Icon name="lock" size={14} /> Secure, local-first operation</span>
            </div>
          </div>

          <ManufacturingIllustration />
        </div>

        <div className="landing-metrics" aria-label="Platform overview">
          <div><strong>{String(WORKSTATION_MODULES.length).padStart(2, "0")}</strong><span>Integrated features</span></div>
          <div><strong>{String(getResearchComponentCount()).padStart(2, "0")}</strong><span>Research components</span></div>
          <div><strong>AI</strong><span>Vision-powered analysis</span></div>
          <div><strong>LOCAL</strong><span>Independent processing</span></div>
        </div>

        <div className="landing-process">
          {WORKSTATION_MODULES.map((workstation, index) => (
            <div key={workstation.id} className={`landing-process-step process-tone-${workstation.accent}`}>
              <span className="landing-process-index">0{index + 1}</span>
              <span className="landing-process-icon"><Icon name={workstation.icon} size={19} /></span>
              <span><strong>{workstation.name}</strong><small>{workstation.area}</small></span>
              {index < WORKSTATION_MODULES.length - 1 ? <Icon name="arrow-right" size={15} className="landing-process-arrow" /> : null}
            </div>
          ))}
        </div>
      </main>

      <footer className="platform-footer"><span>GARMENT INTELLIGENCE PLATFORM</span><span>RESEARCH PRESENTATION · 2026</span></footer>
    </section>
  );
}
