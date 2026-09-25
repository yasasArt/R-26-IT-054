import type { DesktopAppInfo, SystemReadiness } from "../../shared/types";
import { Icon } from "./Icon";

function formatCheckTime(timestamp: string | undefined): string {
  if (!timestamp) return "Awaiting check";

  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

export function ActivityPanel({
  appInfo,
  readiness,
}: {
  appInfo: DesktopAppInfo | null;
  readiness: SystemReadiness | null;
}) {
  return (
    <section className="panel activity-panel">
      <header className="panel-heading panel-heading-compact">
        <div>
          <span className="eyebrow">DESKTOP RUNTIME</span>
          <h2>Foundation activity</h2>
        </div>
        <span className="panel-meta">{formatCheckTime(readiness?.checkedAt)}</span>
      </header>

      <div className="activity-list">
        <article className="activity-item">
          <span className="activity-marker marker-success" />
          <div>
            <strong>Secure Electron window started</strong>
            <span>Context isolation, sandbox, and navigation protection enabled.</span>
          </div>
        </article>

        <article className="activity-item">
          <span className="activity-marker marker-neutral" />
          <div>
            <strong>Model resources inspected</strong>
            <span>Checkpoint presence is checked without claiming inference readiness.</span>
          </div>
        </article>

        <article className="activity-item">
          <span className="activity-marker marker-neutral" />
          <div>
            <strong>Python and Bluetooth protected</strong>
            <span>Verified local services and physical controller notifications use secure desktop boundaries.</span>
          </div>
        </article>
      </div>

      <footer className="runtime-footer">
        <span>
          <Icon name="folder" size={14} />
          Local app data
        </span>
        <span>Electron {appInfo?.electronVersion || "—"}</span>
      </footer>
    </section>
  );
}
