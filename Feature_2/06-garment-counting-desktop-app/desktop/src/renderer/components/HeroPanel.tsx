import type { SystemReadiness } from "../../shared/types";
import { Icon } from "./Icon";

export function HeroPanel({
  readiness,
  refreshing,
  onRefresh,
}: {
  readiness: SystemReadiness | null;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const componentCount = readiness?.components.length || 6;
  const readyCount = readiness?.components.filter((component) => component.status === "ready").length || 0;

  return (
    <section className="hero-panel">
      <div className="hero-copy">
        <span className="eyebrow eyebrow-inverse">
          <Icon name="spark" size={15} />
          ELECTRON DESKTOP FOUNDATION
        </span>
        <h1>A calmer, clearer view of every sewing shift.</h1>
        <p>
          One secure desktop workspace for workstation-aware garment counting,
          live production sessions, and Bluetooth operator events.
        </p>

        <div className="hero-actions">
          <button type="button" className="button button-primary" onClick={onRefresh} disabled={refreshing}>
            <Icon name="refresh" size={16} className={refreshing ? "spin" : undefined} />
            {refreshing ? "Checking system" : "Run system check"}
          </button>
          <span className="hero-caption">No Next.js · No browser · Offline-first</span>
        </div>
      </div>

      <div className="hero-readiness" aria-label={`${readyCount} of ${componentCount} components ready`}>
        <div className="readiness-orbit">
          <span className="readiness-orbit-inner">
            <strong>{String(readyCount).padStart(2, "0")}</strong>
            <span>/ {String(componentCount).padStart(2, "0")}</span>
          </span>
        </div>
        <p>Components ready</p>
        <span>Real workstation components</span>
      </div>
    </section>
  );
}
